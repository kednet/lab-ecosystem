"""
Проверка статуса erid (маркера рекламы).

Без Bearer-токена ОРД VK — best-effort: возвращает unknown
и пишет в лог инструкцию, как проверить вручную через ЕРИР.

С Bearer-токеном — дёргает API:
    GET https://api.ord.vk.com/v1/creative/{external_id}/erir_status
    Authorization: Bearer <ORD_BEARER_TOKEN>

Где external_id — НЕ сам erid, а ID объекта в кабинете ОРД, у которого
был выдан erid. Для проверки самого erid нужен список своих объектов:

    POST https://api.ord.vk.com/v1/erir_statuses
    body: {"limit": 50, "data_type": "creative"}

и поиск по erir_id == <erid>.

Usage:
    from affiliate_links.verify_erid import verify_erid, EridStatus

    result = verify_erid("2VfnxyNkZrY")
    if result.is_safe:
        print("OK — можно публиковать")
    else:
        print(f"СТОП: {result.reason}")
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import urllib.request
import urllib.error


# ─── Конфигурация ─────────────────────────────────────────────────────────

ORD_API_BASE = os.environ.get("ORD_API_BASE", "https://api.ord.vk.com")
ORD_BEARER_TOKEN = os.environ.get("ORD_BEARER_TOKEN", "").strip()
ERIR_URL = "https://erir.grfc.ru"  # публичный поиск ЕРИР (через Госуслуги)

ADVCAKE_ERID_DEFAULT = os.environ.get("ADVCAKE_ERID", "2VfnxyNkZrY")


# ─── Модель результата ────────────────────────────────────────────────────

@dataclass
class EridStatus:
    erid: str
    status: str          # "verified" | "processing" | "rejected" | "unknown" | "expired"
    is_safe: bool        # True только если verified
    reason: str = ""     # человекочитаемое объяснение
    source: str = ""     # "ord_api" | "manual" | "fallback"
    raw: Optional[dict] = None
    checked_at: str = ""

    def to_dict(self) -> dict:
        return {
            "erid": self.erid,
            "status": self.status,
            "is_safe": self.is_safe,
            "reason": self.reason,
            "source": self.source,
            "checked_at": self.checked_at,
            "raw": self.raw,
        }


# ─── HTTP helper ──────────────────────────────────────────────────────────

def _http_get_json(url: str, headers: Optional[dict] = None, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict, headers: Optional[dict] = None,
                    timeout: int = 15) -> dict:
    data = json.dumps(payload).encode("utf-8")
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ─── Проверка ─────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _verify_via_ord_api(erid: str) -> EridStatus:
    """Через Bearer-токен ОРД VK: список статусов и поиск по erir_id."""
    if not ORD_BEARER_TOKEN:
        raise RuntimeError("ORD_BEARER_TOKEN not set")

    headers = {"Authorization": f"Bearer {ORD_BEARER_TOKEN}"}

    # Шаг 1: запросить список креативов с пагинацией.
    # erir_statuses принимает до 1000 за один раз, но мы не знаем заранее,
    # на какой странице наш erid — листаем, пока не найдём.
    cursor = None
    found_raw = None
    for _ in range(10):  # защита от бесконечного цикла
        payload = {"limit": 200, "data_type": "creative"}
        if cursor:
            payload["cursor"] = cursor
        try:
            data = _http_post_json(
                f"{ORD_API_BASE}/v1/erir_statuses", payload, headers=headers,
            )
        except urllib.error.HTTPError as e:
            return EridStatus(
                erid=erid,
                status="unknown",
                is_safe=False,
                reason=f"ORD API HTTP {e.code}: {e.reason}",
                source="ord_api",
                checked_at=_now_iso(),
            )

        # Ищем наш erid в ответе
        items = data.get("items") or data.get("data") or []
        for item in items:
            if item.get("erir_id") == erid or item.get("erid") == erid:
                found_raw = item
                break
        if found_raw:
            break
        cursor = data.get("cursor") or data.get("next_cursor")
        if not cursor:
            break

    if not found_raw:
        return EridStatus(
            erid=erid,
            status="unknown",
            is_safe=False,
            reason="erid не найден среди креативов аккаунта ОРД",
            source="ord_api",
            checked_at=_now_iso(),
        )

    status = (found_raw.get("erir_status") or found_raw.get("status") or "").lower()
    is_safe = status == "verified"
    reason = ""
    if status == "verified":
        reason = "erid подтверждён в ЕРИР — публикация разрешена"
    elif status == "processing":
        reason = "erid ещё в обработке ОРД (5–24 ч). Лучше подождать"
    elif status == "rejected":
        reason = "erid отклонён — НЕ публиковать, риск штрафа по 14.3 КоАП"
    else:
        reason = f"неизвестный статус ОРД: {status!r}"

    return EridStatus(
        erid=erid,
        status=status or "unknown",
        is_safe=is_safe,
        reason=reason,
        source="ord_api",
        raw=found_raw,
        checked_at=_now_iso(),
    )


def _verify_fallback(erid: str) -> EridStatus:
    """Без Bearer-токена: только проверка формата + инструкция."""
    # Минимум — проверим формат: 11 символов, base62
    import re
    if not re.match(r"^[A-Za-z0-9_-]{8,32}$", erid):
        return EridStatus(
            erid=erid,
            status="unknown",
            is_safe=False,
            reason=f"erid нестандартного формата ({len(erid)} симв.)",
            source="fallback",
            checked_at=_now_iso(),
        )

    return EridStatus(
        erid=erid,
        status="unknown",
        is_safe=True,  # не блокируем публикацию — формат валидный
        reason=(
            "ORD_BEARER_TOKEN не задан — статус не проверен. "
            f"Проверь вручную: {ERIR_URL} (вход через Госуслуги) "
            f"или задай ORD_BEARER_TOKEN в .env для авто-проверки."
        ),
        source="fallback",
        checked_at=_now_iso(),
    )


def verify_erid(erid: Optional[str] = None) -> EridStatus:
    """Публичная функция проверки erid.

    Сначала пробует ОРД API (если задан токен), иначе — fallback.
    Никогда не бросает исключения: возвращает EridStatus с reason.
    """
    erid = erid or ADVCAKE_ERID_DEFAULT
    if not erid:
        return EridStatus(
            erid="",
            status="unknown",
            is_safe=False,
            reason="erid не задан",
            source="fallback",
            checked_at=_now_iso(),
        )

    if ORD_BEARER_TOKEN:
        try:
            return _verify_via_ord_api(erid)
        except Exception as e:
            # Если API упал — fallback, но помечаем reason
            res = _verify_fallback(erid)
            res.reason = f"ORD API недоступен ({type(e).__name__}: {e}). {res.reason}"
            return res

    return _verify_fallback(erid)


# ─── CLI ──────────────────────────────────────────────────────────────────

def _cli() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Проверить статус erid")
    p.add_argument("erid", nargs="?", default=None,
                   help="erid (по умолчанию из ADVCAKE_ERID)")
    p.add_argument("--json", action="store_true", help="вывести JSON")
    args = p.parse_args()

    res = verify_erid(args.erid)
    if args.json:
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    else:
        sign = "✅" if res.is_safe else "⚠️"
        print(f"{sign} erid={res.erid} status={res.status}")
        print(f"   source={res.source} checked_at={res.checked_at}")
        print(f"   {res.reason}")


if __name__ == "__main__":
    _cli()