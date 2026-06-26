"""Сканер кадастровых номеров: собирает сигналы из ЕГРН / ФССП / нотариата / банкротств."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from ..shared.config import settings

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"


class OffMarketScanner:
    """Сканер: собирает сигналы из разных источников по кадастровому номеру.

    В demo-режиме читает из mock-данных. В production — реальные API.
    """

    def __init__(self) -> None:
        self.egrn_mode = settings.egrn_api_mode
        self.fssp_mode = settings.fssp_api_mode

    async def get_watch_list(self) -> list[str]:
        """Список кадастровых номеров для мониторинга.

        В production — берём из watchlist (районы ЦАО + премиум).
        В demo — из mock-файла.
        """

        watch_path = DATA_DIR / "egrn_changes.json"
        if not watch_path.exists():
            logger.warning("egrn_changes.json not found")
            return []

        with open(watch_path, encoding="utf-8") as f:
            data = json.load(f)

        return [item["cadastral_number"] for item in data]

    async def scan_one(self, cadastral_number: str) -> dict:
        """Сканировать один кадастровый номер. Возвращает словарь сигналов."""

        # В demo — из mock-данных
        egrn_path = DATA_DIR / "egrn_changes.json"
        fssp_path = DATA_DIR / "fssp_records.json"
        inherit_path = DATA_DIR / "inheritance.json"

        signals = {"cadastral_number": cadastral_number}

        # EGRN
        if egrn_path.exists():
            with open(egrn_path, encoding="utf-8") as f:
                egrn_data = json.load(f)
            for item in egrn_data:
                if item["cadastral_number"] == cadastral_number:
                    signals["address"] = item.get("address", "")
                    signals["district"] = item.get("district", "")
                    signals["estimated_value_rub"] = item.get("estimated_value_rub", 0)
                    signals["egrn_change_type"] = item.get("change_type", "")
                    signals["egrn_change_date"] = self._parse_date(item.get("change_date"))
                    break

        # FSSP
        if fssp_path.exists():
            with open(fssp_path, encoding="utf-8") as f:
                fssp_data = json.load(f)
            for item in fssp_data:
                if item["cadastral_number"] == cadastral_number:
                    signals["fssp_amount"] = item.get("amount", 0)
                    break

        # Inheritance
        if inherit_path.exists():
            with open(inherit_path, encoding="utf-8") as f:
                inherit_data = json.load(f)
            for item in inherit_data:
                if item["cadastral_number"] == cadastral_number:
                    signals["has_inheritance"] = True
                    signals["inheritance_date"] = self._parse_date(item.get("opened_date"))
                    break

        # Encumbrance (mock — из EGRN)
        if "encumbrance_type" in signals:
            signals["has_encumbrance"] = True
            signals["encumbrance_type"] = signals["encumbrance_type"]

        return signals

    def _parse_date(self, date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None


_scanner: OffMarketScanner | None = None


def get_scanner() -> OffMarketScanner:
    global _scanner
    if _scanner is None:
        _scanner = OffMarketScanner()
    return _scanner
