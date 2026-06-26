"""Интеграция с Bitrix24 — в demo-режиме возвращает фейковые ответы."""

import logging
from typing import Any

import httpx

from ..shared.config import settings
from .schemas import QualifiedLead

logger = logging.getLogger(__name__)


class Bitrix24Client:
    """Клиент Bitrix24 REST API. В demo-режиме не делает реальных вызовов."""

    def __init__(self, webhook_url: str | None = None, mock: bool | None = None) -> None:
        self.webhook_url = webhook_url or settings.bitrix24_webhook_url
        self.mock = mock if mock is not None else settings.bitrix24_mock_mode

    async def create_lead(self, lead: QualifiedLead) -> str:
        """Создать лид + контакт в Bitrix24. Возвращает ID лида."""

        if self.mock:
            fake_id = f"MOCK-{lead.session_id[:8].upper()}"
            logger.info(
                f"[MOCK] Created lead {fake_id}",
                extra={
                    "session_id": lead.session_id,
                    "lang": lead.client_lang,
                    "score": lead.score,
                    "budget": lead.budget,
                },
            )
            return fake_id

        # 1. Создаём контакт
        contact_id = await self._call(
            "crm.contact.add",
            {
                "fields": {
                    "NAME": "AI Lead",
                    "SECOND_NAME": "",
                    "LAST_NAME": f"({lead.client_lang})",
                    "OPENED": "Y",
                    "ASSIGNED_BY_ID": 1,
                    "TYPE_ID": "CLIENT",
                    "SOURCE_ID": "AI_CONCIERGE",
                    "SOURCE_DESCRIPTION": f"Язык: {lead.client_lang}, "
                    f"Цель: {lead.intent.value}, Бюджет: {lead.budget}",
                }
            },
        )

        # 2. Создаём лид
        lead_id = await self._call(
            "crm.lead.add",
            {
                "fields": {
                    "TITLE": f"AI Concierge lead ({lead.client_lang})",
                    "NAME": "AI Lead",
                    "STATUS_ID": "NEW",
                    "OPENED": "Y",
                    "ASSIGNED_BY_ID": 1,
                    "SOURCE_ID": "AI_CONCIERGE",
                    "SOURCE_DESCRIPTION": lead.dialog_summary,
                    "CONTACT_ID": contact_id,
                    "OPPORTUNITY": self._estimate_opportunity(lead),
                    "CURRENCY_ID": "RUB",
                    "COMMENTS": f"Бюджет: {lead.budget}\n"
                    f"Район: {lead.district}\n"
                    f"Сроки: {lead.timeline}\n"
                    f"Оплата: {lead.payment}\n"
                    f"Детали: {lead.details}\n"
                    f"Score: {lead.score}\n"
                    f"Канал: {lead.source}",
                }
            },
        )

        logger.info(f"Created Bitrix24 lead {lead_id} for session {lead.session_id}")
        return str(lead_id)

    def _estimate_opportunity(self, lead: QualifiedLead) -> int:
        """Грубая оценка потенциальной суммы сделки по бюджету."""

        budget = lead.budget.lower()
        if "300" in budget or "300+" in budget or "$3m" in budget:
            return 350_000_000
        if "100-300" in budget or "$1-3" in budget:
            return 200_000_000
        if "100" in budget or "$1" in budget or "до 100" in budget:
            return 80_000_000
        return 150_000_000  # default

    async def _call(self, method: str, params: dict[str, Any]) -> Any:
        """Вызов REST API Bitrix24."""

        url = f"{self.webhook_url}{method}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=params)
            response.raise_for_status()
            data = response.json()

        if "error" in data:
            raise RuntimeError(f"Bitrix24 error: {data['error']}")

        return data.get("result")


def get_crm() -> Bitrix24Client:
    return Bitrix24Client()
