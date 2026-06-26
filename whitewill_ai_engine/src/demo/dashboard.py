"""Демо-дашборд на Streamlit для презентации Олегу Торбосову.

Запуск:
    streamlit run src/demo/dashboard.py
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Streamlit уже запускает asyncio loop, поэтому nest_asyncio нужен для вложенного запуска.
# uvloop удалён из окружения (см. /opt/whitewill/.venv) — иначе nest_asyncio
# не совместим с uvloop-loop'ом, который Streamlit 1.58+ ставит по умолчанию.
import nest_asyncio
nest_asyncio.apply()

from src.concierge.bot import get_bot
from src.concierge.schemas import ChatRequest, ClientLang
from src.offmarket.scanner import get_scanner
from src.offmarket.scorer import get_scorer


def run_async(coro):
    """Запустить корутину в уже работающем event loop (Streamlit)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)

st.set_page_config(
    page_title="Whitewill AI Engine — Demo",
    page_icon="🏛",
    layout="wide",
)

st.title("🏛 Whitewill AI Engine")
st.markdown("### Демо для Олега Торбосова — AI-консьерж + Off-market матчинг")

tab1, tab2, tab3 = st.tabs(
    ["🤖 AI-консьерж (live)", "📊 Off-market сканирование", "📈 Бизнес-кейс"]
)

# ============================================
# TAB 1: AI-консьерж
# ============================================
with tab1:
    st.header("AI-консьерж в действии")
    st.caption("RU + EN • RAG по 10 объектам Whitewill • Mock-LLM (zero cost)")

    col1, col2 = st.columns([3, 1])

    with col2:
        st.markdown("**Параметры диалога**")

        # Инициализация ключа для языка
        if "lang_select" not in st.session_state:
            st.session_state["lang_select"] = "ru"
        if "pending_lang" not in st.session_state:
            st.session_state["pending_lang"] = None

        # Если сценарий поставил pending_lang — подтянуть в виджет до его рендера
        if st.session_state["pending_lang"] is not None:
            st.session_state["lang_select"] = st.session_state["pending_lang"]
            st.session_state["pending_lang"] = None

        lang = st.selectbox("Язык", ["ru", "en"], key="lang_select")
        source = st.selectbox("Канал", ["web", "telegram", "whatsapp"], key="source_select")
        session_id = st.text_input(
            "Session ID", value=f"demo-{datetime.now().strftime('%H%M%S')}", key="session_id"
        )
        st.divider()
        st.markdown("**Готовые сценарии:**")

        # Сценарии пишут в pending_lang → на следующем rerun виджет подхватит
        def _set_scenario_ru():
            st.session_state["scripted_msgs"] = [
                "Здравствуйте!",
                "Для себя, переехать в центр",
                "до 100 млн",
                "Хамовники",
                "1-3 мес",
                "наличные",
            ]
            st.session_state["pending_lang"] = "ru"

        def _set_scenario_en():
            st.session_state["scripted_msgs"] = [
                "Hello!",
                "Investment",
                "$3M+",
                "Dubai",
                "3-6 months",
                "international transfer",
            ]
            st.session_state["pending_lang"] = "en"

        st.button("🎬 Сценарий 1: RU покупка", on_click=_set_scenario_ru)
        st.button("🎬 Сценарий 2: EN investor", on_click=_set_scenario_en)

    with col1:
        # Инициализация истории
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "scripted_msgs" not in st.session_state:
            st.session_state.scripted_msgs = []

        # Приветствие
        if not st.session_state.messages:
            greeting = (
                "Здравствуйте! Я AI-ассистент Whitewill. Помогу подобрать элитную недвижимость. "
                "Какая цель покупки?"
                if lang == "ru"
                else "Hello! I'm Whitewill's AI assistant. What's the purpose of your purchase?"
            )
            st.session_state.messages.append({"role": "assistant", "content": greeting})

        # Показываем историю
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Автозапуск сценария
        if st.session_state.scripted_msgs:
            scripted = st.session_state.scripted_msgs
            bot = get_bot()
            with st.spinner(f"AI думает... ({len(scripted)} сообщений)"):
                for user_msg in scripted:
                    st.session_state.messages.append({"role": "user", "content": user_msg})
                    with st.chat_message("user"):
                        st.markdown(user_msg)

                    req = ChatRequest(
                        session_id=session_id,
                        message=user_msg,
                        lang=ClientLang(lang),
                        source=source,
                    )
                    response = run_async(bot.handle(req))
                    st.session_state.messages.append(
                        {"role": "assistant", "content": response.reply}
                    )
                    with st.chat_message("assistant"):
                        st.markdown(response.reply)
                        st.caption(
                            f"State: {response.state.value} • Score: {response.score:.2f} • "
                            f"{response.latency_ms}ms • "
                            f"${response.cost_rub:.3f}"
                        )
                        if response.matched_properties:
                            matched_titles = [
                                (p.get("title_en") or p["title"]) if lang == "en" else p["title"]
                                for p in response.matched_properties
                            ]
                            matched_label = "📍 Matched" if lang == "en" else "📍 Подобрано"
                            st.info(matched_label + ": " + ", ".join(matched_titles))
                        if response.crm_lead_id:
                            crm_label = "✅ Lead created in Bitrix24 (mock)" if lang == "en" else "✅ Lead создан в Bitrix24 (mock)"
                            st.success(f"{crm_label}: {response.crm_lead_id}")
            st.session_state.scripted_msgs = []

        # Свободный ввод
        chat_placeholder = "Type a message..." if lang == "en" else "Напишите сообщение..."
        if user_input := st.chat_input(chat_placeholder):
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            bot = get_bot()
            req = ChatRequest(
                session_id=session_id,
                message=user_input,
                lang=ClientLang(lang),
                source=source,
            )
            with st.spinner("AI думает..."):
                response = run_async(bot.handle(req))
            st.session_state.messages.append({"role": "assistant", "content": response.reply})
            with st.chat_message("assistant"):
                st.markdown(response.reply)
                st.caption(
                    f"State: {response.state.value} • Score: {response.score:.2f} • "
                    f"{response.latency_ms}ms"
                )
                if response.matched_properties:
                    matched_titles = [
                        (p.get("title_en") or p["title"]) if lang == "en" else p["title"]
                        for p in response.matched_properties
                    ]
                    matched_label = "📍 Matched" if lang == "en" else "📍 Подобрано"
                    st.info(matched_label + ": " + ", ".join(matched_titles))
                if response.crm_lead_id:
                    crm_label = "✅ Lead created" if lang == "en" else "✅ Lead создан"
                    st.success(f"{crm_label}: {response.crm_lead_id}")


# ============================================
# TAB 2: Off-market сканирование
# ============================================
with tab2:
    st.header("📊 Off-market матчинг через ЕГРН")
    st.caption("10 кадастровых номеров ЦАО • 4 источника сигналов • ML-скоринг")

    if st.button("🚀 Запустить сканирование", type="primary"):
        with st.spinner("Сканируем 10 кадастровых номеров..."):
            scanner = get_scanner()
            scorer = get_scorer()

            cadastral_numbers = run_async(scanner.get_watch_list())
            st.info(f"Watch list: {len(cadastral_numbers)} кадастровых номеров")

            results = []
            for cn in cadastral_numbers:
                signals = run_async(scanner.scan_one(cn))
                scored = scorer.score(cn, signals)
                results.append({**signals, **scored})

            results.sort(key=lambda x: x["score"], reverse=True)

            # Сохраняем в session state
            st.session_state["offmarket_results"] = results

    if "offmarket_results" not in st.session_state:
        st.session_state["offmarket_results"] = []

    results = st.session_state["offmarket_results"]

    if results:
        # Метрики
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("Всего объектов", len(results))
        col_b.metric("High priority", sum(1 for r in results if r["priority"] == "high"))
        col_c.metric(
            "Средний score",
            f"{sum(r['score'] for r in results) / len(results):.2f}" if results else "0",
        )
        col_d.metric(
            "Потенциал, млрд ₽",
            f"{sum(r.get('estimated_value_rub', 0) for r in results if r['priority'] in ('high', 'medium')) / 1_000_000_000:.1f}",
        )

        st.divider()
        st.subheader("🏆 Топ off-market объектов")

        for i, r in enumerate(results, 1):
            priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(r["priority"], "⚪")

            with st.expander(
                f"{priority_emoji} #{i} • {r.get('address', '?')} • "
                f"score {r['score']:.2f} • "
                f"{r.get('estimated_value_rub', 0) / 1_000_000:.0f} млн ₽"
            ):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown("**📍 Параметры**")
                    st.write(f"Кадастровый: `{r['cadastral_number']}`")
                    st.write(f"Район: {r.get('district', '—')}")
                    st.write(
                        f"Стоимость: **{r.get('estimated_value_rub', 0) / 1_000_000:.0f} млн ₽**"
                    )
                    st.write(f"Тип смены: {r.get('egrn_change_type', '—')}")
                    st.write(f"Обременение: {r.get('encumbrance_type', '—')}")
                    st.write(f"ФССП: {r.get('fssp_amount', 0) / 1_000_000:.1f} млн ₽")
                    st.write(f"Наследство: {'✅' if r.get('has_inheritance') else '❌'}")
                with col2:
                    st.markdown("**📊 Сработавшие сигналы**")
                    for sig in r["signals"]:
                        st.write(f"  ✅ {sig}")
                    st.markdown("**🎯 Рекомендация**")
                    if r["priority"] == "high":
                        st.error(
                            "🔴 **Высокий приоритет** — связаться с собственником/нотариусом в течение 24 ч"
                        )
                    elif r["priority"] == "medium":
                        st.warning("🟡 Средний приоритет — прозвонить в течение недели")
                    else:
                        st.info("🟢 Низкий приоритет — наблюдать")


# ============================================
# TAB 3: Бизнес-кейс
# ============================================
with tab3:
    st.header("💰 Бизнес-кейс для Whitewill")

    st.markdown("""
### Прогноз ROI (12 месяцев)

| Метрика | Расчёт | Значение |
|---|---|---|
| **Экономия на квалификации** | 1.5 ч × 50 диалогов/мес × 12 мес × 10 000 ₽/ч | **9 млн ₽/год** |
| **Доп. выручка off-market** | 4 сделки × 200 млн ₽ × 3% комиссия | **24 млн ₽/год** |
| **Стоимость пилота** | 4 мес × команда 3–4 чел. | **5.8 млн ₽** |
| **Ежемесячные затраты** | YandexGPT + SpeechKit + хостинг | **~25 000 ₽/мес** |
| **ROI за первый год** | (9 + 24) / 5.8 | **570%** |

### Конкурентные преимущества
- **Первый в РФ AI-консьерж с 4 языками** для элитной недвижимости
- **Единственный, кто комбинирует ЕГРН + ФССП + нотариат** для off-market
- **YandexGPT** — нативный стек, без зависимости от зарубежных LLM
- **Эксклюзивность** для Whitewill в элитке РФ — 6 месяцев
""")

    col_x, col_y, col_z = st.columns(3)
    with col_x:
        st.metric("Брокеров в Whitewill", "800+", "штат 2024")
    with col_y:
        st.metric("Сделок в год", "2 700", "+3% г/г")
    with col_z:
        st.metric("Оборот 2024", "165 млрд ₽", "исторический рекорд")

    st.success(
        "🎯 **Готовы к пилоту?** Следующие шаги: подписание NDA → доступ к sandbox Битрикс24 → старт через 1 неделю"
    )
