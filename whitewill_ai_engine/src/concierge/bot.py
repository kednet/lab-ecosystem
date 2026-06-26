"""Ядро диалоговой логики AI-консьержа.

Управляет состоянием, квалифицирует клиента, передаёт лиды в CRM.
"""

import json
import logging
import re
import uuid
from datetime import datetime

from ..shared.db import get_session
from ..shared.i18n import SUPPORTED_LANGUAGES, detect_language, t
from ..shared.llm import get_llm
from ..shared.models import Dialog as DialogModel
from ..shared.models import Message as MessageModel
from .crm import get_crm
from .prompts import build_system_prompt
from .rag import get_rag
from .schemas import (
    ChatRequest,
    ChatResponse,
    ClientLang,
    DialogState,
    IntentType,
    QualifiedLead,
)

logger = logging.getLogger(__name__)


class ConciergeBot:
    """AI-консьерж: ведёт диалог, квалифицирует, передаёт в CRM."""

    def __init__(self) -> None:
        self.llm = get_llm()
        self.rag = get_rag()
        self.crm = get_crm()

    async def handle(self, req: ChatRequest) -> ChatResponse:
        """Главный метод — обработать входящее сообщение."""

        # Определяем язык
        lang = req.lang.value if req.lang else detect_language(req.message)

        # Загружаем или создаём диалог
        async for session in get_session():
            dialog = await self._get_or_create_dialog(session, req.session_id, lang, req.source)

            # Парсим ввод клиента, обновляем поля диалога ДО подготовки промпта
            self._extract_qualification(req.message, dialog, lang)

            # Получаем RAG-результаты (по собранным данным)
            matched = await self._maybe_search(dialog, lang)

            # Готовим системный промпт
            sys_prompt = build_system_prompt(
                lang=lang,
                state=dialog.status,
                intent=dialog.intent,
                budget=dialog.budget,
                district=dialog.district,
                timeline=dialog.timeline,
                payment=dialog.payment,
                matched_properties=[m.model_dump() for m in matched],
            )

            # История диалога
            msgs = await dialog.awaitable_attrs.messages
            history = [
                {"role": "user" if m.role == "user" else "assistant", "content": m.content}
                for m in msgs[-6:]  # последние 6 сообщений
            ]
            messages = [{"role": "system", "content": sys_prompt}] + history
            messages.append({"role": "user", "content": req.message})

            # Запрос к LLM
            llm_result = await self.llm.chat(messages, temperature=0.5, max_tokens=400, lang=lang)
            reply = llm_result["content"]
            cost = self.llm.estimate_cost(llm_result["tokens_in"], llm_result["tokens_out"])

            # Сохраняем сообщения
            self._save_message(session, dialog, "user", req.message, 0, 0)
            self._save_message(
                session,
                dialog,
                "assistant",
                reply,
                llm_result["tokens_in"],
                llm_result["tokens_out"],
            )

            # Решаем, qualified ли диалог, по заполненным полям
            is_qualified, score, new_state = self._evaluate_qualification(dialog)
            dialog.status = new_state.value
            dialog.score = score
            dialog.is_qualified = is_qualified

            # Если QUALIFIED — собираем лид и отправляем в CRM
            crm_lead_id = None
            if is_qualified and not dialog.crm_lead_id:
                qualified_lead = self._build_lead(dialog, req, matched)
                crm_lead_id = await self.crm.create_lead(qualified_lead)
                dialog.crm_lead_id = crm_lead_id

                # Формируем красивый финальный ответ с подборкой
                reply = self._build_qualified_reply(matched, dialog, lang, crm_lead_id)

            await session.commit()

            return ChatResponse(
                session_id=dialog.session_id,
                reply=reply,
                state=DialogState(dialog.status),
                is_qualified=is_qualified,
                score=score,
                matched_properties=[m.model_dump() for m in matched],
                next_question=self._next_question(new_state, lang),
                crm_lead_id=crm_lead_id,
                cost_rub=cost,
                latency_ms=llm_result["latency_ms"],
            )

    async def _get_or_create_dialog(
        self, session, session_id: str, lang: str, source: str
    ) -> DialogModel:
        """Найти или создать диалог."""

        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        stmt = (
            select(DialogModel)
            .where(DialogModel.session_id == session_id)
            .options(selectinload(DialogModel.messages))
        )
        result = await session.execute(stmt)
        dialog = result.scalar_one_or_none()

        if dialog is None:
            dialog = DialogModel(
                session_id=session_id,
                client_lang=lang,
                status=DialogState.WELCOME.value,
                source=source,
            )
            session.add(dialog)
            await session.flush()

        return dialog

    def _save_message(
        self,
        session,
        dialog: DialogModel,
        role: str,
        content: str,
        tokens_in: int,
        tokens_out: int,
    ) -> None:
        msg = MessageModel(
            dialog_id=dialog.id,
            role=role,
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        session.add(msg)
        dialog.messages.append(msg)

    async def _maybe_search(
        self, dialog: DialogModel, lang: str
    ) -> list:
        """Запустить RAG, если уже есть ключевые параметры.

        Логика показа matched:
        - Район Dubai/международный → ВСЕГДА пусто (handoff клиенту)
        - District=None → пусто (клиент ещё не сказал район, нечего показывать)
        - District выбран + есть бюджет → ищем подборку
        """

        if not (dialog.budget or dialog.district):
            return []

        # Если район международный — не показываем московские объекты
        if self._is_international(dialog.district):
            return []

        # Если район ещё не выбран (но есть бюджет) — не показываем подборку,
        # иначе клиент увидит московские объекты когда хочет Дубай/Лондон/etc
        if not dialog.district:
            return []

        query_parts = []
        if dialog.district:
            query_parts.append(f"район {dialog.district}")
        if dialog.budget:
            query_parts.append(f"бюджет {dialog.budget}")
        if dialog.intent:
            query_parts.append(f"цель {dialog.intent}")

        query = " ".join(query_parts) or "элитная недвижимость Москва"

        # Парсим бюджет в диапазон (min, max). Если клиент сказал "100-300" —
        # фильтруем строго от 100 до 300 (а не всё что дешевле 300).
        budget_min = None
        budget_max = None
        if dialog.budget:
            b = dialog.budget
            if "до 100" in b or b.startswith("$1"):
                budget_max = 100_000_000
            elif ("100" in b and "300" in b) or "$1-3" in b or "$1–3" in b:
                budget_min = 100_000_000
                budget_max = 300_000_000
            elif "300" in b or "$3" in b or "свыше" in b:
                budget_min = 300_000_000
                budget_max = 5_000_000_000
            # "гибкий" — без фильтра

        return await self.rag.search(
            query,
            top_k=3,
            budget_min=budget_min,
            budget_max=budget_max,
            district=dialog.district if dialog.district else None,
        )

    def _extract_qualification(
        self,
        user_msg: str,
        dialog: DialogModel,
        lang: str,
    ) -> None:
        """Парсим ввод клиента, обновляем поля диалога (intent/budget/district/timeline/payment)."""

        msg = user_msg.lower()

        # Извлекаем intent
        if not dialog.intent:
            if any(w in msg for w in ["для себя", "personal"]):
                dialog.intent = IntentType.PERSONAL.value
            elif any(w in msg for w in ["инвестиц", "investment"]):
                dialog.intent = IntentType.INVESTMENT.value
            elif any(w in msg for w in ["сохранен", "preservation"]):
                dialog.intent = IntentType.PRESERVATION.value

        # Извлекаем бюджет
        if not dialog.budget:
            if "до 100" in msg or "$1" in msg or "up to 100" in msg:
                dialog.budget = "до 100 млн ₽"
            elif "100-300" in msg or "$1-3" in msg or "100–300" in msg:
                dialog.budget = "100–300 млн ₽"
            elif "300" in msg or "$3" in msg or "свыше" in msg or "$3M" in msg:
                dialog.budget = "300 млн+"
            elif "гибк" in msg or "flexible" in msg:
                dialog.budget = "гибкий"

        # Извлекаем район
        if not dialog.district:
            district_map = {
                "хамовник": "Хамовники",
                "остоженк": "Остоженка",
                "патриарш": "Патриаршие пруды",
                "преснен": "Пресненский",
                "арбат": "Арбат",
                "тверск": "Тверской",
                "замосквореч": "Замоскворечье",
                "таганск": "Таганский",
                "khamovniki": "Khamovniki",
                "ostozhenka": "Ostozhenka",
                "dubai": "Dubai",
                "abu dabi": "Abu Dhabi",
                "abu-dabi": "Abu Dhabi",
                "патриарших": "Патриаршие пруды",
                "арбатск": "Арбат",
            }
            for needle, full_name in district_map.items():
                if needle in msg:
                    dialog.district = full_name
                    break

        # Извлекаем сроки
        if not dialog.timeline:
            if "срочн" in msg or "urgent" in msg:
                dialog.timeline = "срочно"
            elif "1-3" in msg or "1–3" in msg:
                dialog.timeline = "1–3 мес"
            elif "3-6" in msg or "3–6" in msg:
                dialog.timeline = "3–6 мес"
            elif "6+" in msg or "6 мес" in msg:
                dialog.timeline = "6+ мес"

        # Извлекаем способ оплаты
        if not dialog.payment:
            if "ипотек" in msg or "mortgage" in msg:
                dialog.payment = "ипотека"
            elif "наличн" in msg or "кэш" in msg or "cash" in msg:
                dialog.payment = "наличные"
            elif "перевод" in msg or "transfer" in msg or "international" in msg:
                dialog.payment = "перевод из-за рубежа"

    def _evaluate_qualification(
        self,
        dialog: DialogModel,
    ) -> tuple[bool, float, DialogState]:
        """По заполненным полям dialog решаем, qualified ли, и какое следующее состояние."""

        is_qualified = all(
            [dialog.intent, dialog.budget, dialog.district, dialog.timeline, dialog.payment]
        )

        # Скоринг 0..1
        filled = sum(
            bool(x)
            for x in [dialog.intent, dialog.budget, dialog.district, dialog.timeline, dialog.payment]
        )
        score = filled / 5.0

        # Следующее состояние по текущему заполнению
        if is_qualified:
            new_state = DialogState.QUALIFIED
        elif dialog.payment:
            new_state = DialogState.QUALIFIED
        elif dialog.timeline:
            new_state = DialogState.PAYMENT
        elif dialog.district:
            new_state = DialogState.TIMELINE
        elif dialog.budget:
            new_state = DialogState.DISTRICT
        elif dialog.intent:
            new_state = DialogState.BUDGET
        else:
            new_state = DialogState.GOAL

        return is_qualified, score, new_state

    def _build_lead(
        self,
        dialog: DialogModel,
        req: ChatRequest,
        matched: list,
    ) -> QualifiedLead:
        """Собрать QualifiedLead из диалога."""

        summary = self._summarize(dialog)

        return QualifiedLead(
            session_id=dialog.session_id,
            client_lang=ClientLang(dialog.client_lang),
            intent=IntentType(dialog.intent) if dialog.intent else IntentType.UNKNOWN,
            budget=dialog.budget,
            district=dialog.district,
            timeline=dialog.timeline,
            payment=dialog.payment,
            details="",
            score=dialog.score,
            source=req.source,
            matched_properties=[m.id for m in matched],
            dialog_summary=summary,
        )

    def _summarize(self, dialog: DialogModel) -> str:
        """Краткое саммари диалога для CRM."""

        parts = []
        if dialog.intent:
            parts.append(f"Цель: {dialog.intent}")
        if dialog.budget:
            parts.append(f"Бюджет: {dialog.budget}")
        if dialog.district:
            parts.append(f"Район: {dialog.district}")
        if dialog.timeline:
            parts.append(f"Сроки: {dialog.timeline}")
        if dialog.payment:
            parts.append(f"Оплата: {dialog.payment}")
        return "; ".join(parts) or "Нет данных"

    def _next_question(self, state: DialogState, lang: str) -> str | None:
        """Что спросим дальше (для UI)."""

        return {
            DialogState.WELCOME: t("ask_goal", lang),
            DialogState.GOAL: t("ask_budget", lang),
            DialogState.BUDGET: t("ask_district", lang),
            DialogState.DISTRICT: t("ask_timeline", lang),
            DialogState.TIMELINE: t("ask_payment", lang),
            DialogState.PAYMENT: t("ask_details", lang),
            DialogState.QUALIFIED: None,
            DialogState.HANDOFF: None,
        }.get(state)

    # Районы, для которых Whitewill работает через международных партнёров
    # (нет объектов в собственной моковой базе — клиенту передаём лично брокеру)
    _INTERNATIONAL_DISTRICTS = {
        "dubai": "Dubai", "abu dhabi": "Abu Dhabi", "abu-dabi": "Abu Dhabi",
        "london": "London", "milan": "Milan", "paris": "Paris",
        "new york": "New York", "monaco": "Monaco",
    }

    def _is_international(self, district: str | None) -> bool:
        """Это международный район, для которого работаем через партнёров?"""
        if not district:
            return False
        return district.lower().strip() in self._INTERNATIONAL_DISTRICTS

    def _catalog_url(self, district: str | None, lang: str) -> str:
        """Ссылка на каталог (заглушка, в проде — реальный URL)."""
        slug = (district or "").lower().replace(" ", "-")
        base = "https://whitewill.com/intl" if lang == "en" else "https://whitewill.ru/intl"
        return f"{base}/{slug}" if slug else base

    def _build_qualified_reply(
        self,
        matched: list,
        dialog: DialogModel,
        lang: str,
        crm_lead_id: str,
    ) -> str:
        """Финальный ответ для qualified-клиента.

        Логика:
        - международный район (Dubai и др.) → передаём брокеру, даём ссылку на каталог
        - московский район → показываем подборку из базы + брокер
        """

        if lang == "en":
            if self._is_international(dialog.district):
                return self._build_handoff_reply_en(dialog, crm_lead_id)
            return self._build_match_reply_en(matched, dialog, crm_lead_id)

        # RU
        if self._is_international(dialog.district):
            return self._build_handoff_reply_ru(dialog, crm_lead_id)
        return self._build_match_reply_ru(matched, dialog, crm_lead_id)

    def _build_match_reply_ru(self, matched: list, dialog: DialogModel, crm_lead_id: str) -> str:
        """RU: подборка из базы по московскому району."""

        lines = ["✅ **Спасибо! Подобрал варианты по вашим критериям:**\n"]

        district_hint = f" в {dialog.district}" if dialog.district else ""
        budget_hint = f", бюджет {dialog.budget}" if dialog.budget else ""
        lines.append(f"📍 Район{district_hint}{budget_hint}\n")

        if not matched:
            lines.append("К сожалению, по вашим критериям в нашей базе пока нет точных совпадений. Брокер подберёт off-market варианты лично.\n")
        else:
            for i, m in enumerate(matched[:5], 1):
                price_m = m.price_rub / 1_000_000 if m.price_rub else 0
                rooms_str = self._format_rooms(m.rooms, "ru")
                lines.append(
                    f"{i}. 🏛 **{m.title}**\n"
                    f"   {m.district} • {m.area_sqm:.0f} м² • {rooms_str} • **{price_m:.0f} млн ₽**\n"
                )

        lines.append("— — — — — — — — — —")
        lines.append(
            f"👤 Персональный брокер **Алексей** свяжется в течение 30 минут.\n"
            f"📞 +7 (495) 255-01-61\n"
            f"🆔 ID сделки: `{crm_lead_id}`"
        )

        return "\n".join(lines)

    def _build_handoff_reply_ru(self, dialog: DialogModel, crm_lead_id: str) -> str:
        """RU: передаём брокеру + ссылка на международный каталог."""

        catalog = self._catalog_url(dialog.district, "ru")
        district_label = dialog.district or "за рубежом"

        return (
            f"✅ **Спасибо! Передаю ваше обращение брокеру по направлению {district_label}.**\n\n"
            f"🌍 У Whitewill есть проверенные партнёры в этом регионе — "
            f"брокер свяжется в течение 30 минут с актуальными вариантами off-market.\n\n"
            f"📖 А пока можете посмотреть наш каталог объектов в этом направлении:\n"
            f"🔗 [{catalog}]({catalog})\n\n"
            f"— — — — — — — — — —\n"
            f"👤 Персональный брокер **Алексей** свяжется в течение 30 минут.\n"
            f"📞 +7 (495) 255-01-61\n"
            f"🆔 ID сделки: `{crm_lead_id}`"
        )

    def _build_match_reply_en(self, matched: list, dialog: DialogModel, crm_lead_id: str) -> str:
        """EN: подборка из базы по московскому району."""

        lines = ["✅ **Thank you! Here are the matches for your criteria:**\n"]

        if not matched:
            lines.append("Unfortunately, no exact matches in our database for your criteria. Your broker will personally select off-market options.\n")
        else:
            for i, m in enumerate(matched[:5], 1):
                price_m = m.price_rub / 1_000_000 if m.price_rub else 0
                rooms_str = self._format_rooms(m.rooms, "en")
                lines.append(
                    f"{i}. 🏛 **{m.title_en or m.title}**\n"
                    f"   {m.district} • {m.area_sqm:.0f} m² • {rooms_str} • **${price_m:.1f}M**\n"
                )

        lines.append("— — — — — — — — — —")
        lines.append(
            f"👤 Your personal broker **Alexey** will contact you within 30 minutes.\n"
            f"📞 +7 (495) 255-01-61\n"
            f"🆔 Deal ID: `{crm_lead_id}`"
        )

        return "\n".join(lines)

    def _build_handoff_reply_en(self, dialog: DialogModel, crm_lead_id: str) -> str:
        """EN: hand off to broker + international catalog link."""

        catalog = self._catalog_url(dialog.district, "en")
        district_label = dialog.district or "international"

        return (
            f"✅ **Thank you! I'm connecting you with our broker specializing in {district_label}.**\n\n"
            f"🌍 Whitewill has vetted partners in this region — your broker will reach out within 30 minutes with current off-market options.\n\n"
            f"📖 In the meantime, feel free to browse our international catalog:\n"
            f"🔗 [{catalog}]({catalog})\n\n"
            f"— — — — — — — — — —\n"
            f"👤 Your personal broker **Alexey** will contact you within 30 minutes.\n"
            f"📞 +7 (495) 255-01-61\n"
            f"🆔 Deal ID: `{crm_lead_id}`"
        )

    def _format_rooms(self, rooms: int, lang: str) -> str:
        """Склонение 'комната/комнаты/комнат' в RU, 'room/rooms' в EN."""
        if lang == "en":
            return f"{rooms} room" if rooms == 1 else f"{rooms} rooms"
        if rooms == 1:
            return "1 комната"
        if 2 <= rooms <= 4:
            return f"{rooms} комнаты"
        return f"{rooms} комнат"


_bot: ConciergeBot | None = None


def get_bot() -> ConciergeBot:
    global _bot
    if _bot is None:
        _bot = ConciergeBot()
    return _bot
