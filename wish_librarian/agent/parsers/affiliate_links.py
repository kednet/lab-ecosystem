"""
Генератор партнёрских ссылок на Литрес, Лабиринт, Ozon.

Если партнёрский ID указан — добавляет его в URL. Иначе возвращает обычную ссылку на поиск.
"""
from __future__ import annotations

from typing import List
from urllib.parse import quote_plus

from agent.config import get_settings
from agent.models import AffiliateLink, BookInfo
from agent.utils.logger import get_logger


logger = get_logger()


class AffiliateLinksGenerator:
    """Создаёт партнёрские ссылки на основные книжные магазины."""

    def __init__(self):
        self.settings = get_settings()

    def generate(self, book: BookInfo) -> List[AffiliateLink]:
        logger.info("🔗 Генерирую партнёрские ссылки для «{}»", book.title)
        query = f"{book.title} {book.author}"
        encoded = quote_plus(query)

        links: List[AffiliateLink] = []

        # ── Литрес ───────────────────────────────────────────────
        litres_url = (
            f"https://www.litres.ru/search/?q={encoded}"
        )
        if self.settings.litres_partner_id:
            litres_url += f"&utm_source=wl&utm_medium=affiliate&utm_campaign={self.settings.litres_partner_id}"
        links.append(
            AffiliateLink(
                store="Литрес",
                url=litres_url,
                partner_id=self.settings.litres_partner_id or None,
            )
        )

        # ── Лабиринт ────────────────────────────────────────────
        labirint_url = f"https://www.labirint.ru/search/{encoded}/"
        if self.settings.labirint_partner_id:
            labirint_url += f"?partner={self.settings.labirint_partner_id}"
        links.append(
            AffiliateLink(
                store="Лабиринт",
                url=labirint_url,
                partner_id=self.settings.labirint_partner_id or None,
            )
        )

        # ── Ozon ─────────────────────────────────────────────────
        ozon_url = f"https://www.ozon.ru/search/?text={encoded}"
        if self.settings.ozon_partner_id:
            ozon_url += f"&partner={self.settings.ozon_partner_id}"
        links.append(
            AffiliateLink(
                store="Ozon",
                url=ozon_url,
                partner_id=self.settings.ozon_partner_id or None,
            )
        )

        logger.info("🔗 Сгенерировано ссылок: {}", len(links))
        return links
