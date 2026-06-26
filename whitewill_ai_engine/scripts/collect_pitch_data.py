"""Собрать актуальные данные для PDF-питча: диалоги concierge + off-market top."""

import asyncio
import json
import logging
from pathlib import Path

import sys
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.concierge.bot import get_bot
from src.concierge.schemas import ChatRequest, ClientLang
from src.offmarket.scanner import get_scanner
from src.offmarket.scorer import get_scorer

logging.basicConfig(level=logging.WARNING)

OUT = ROOT / "docs" / "pitch_assets"
OUT.mkdir(parents=True, exist_ok=True)


async def collect_dialogs() -> list[dict]:
    """Прогон двух сценариев — RU и EN."""

    bot = get_bot()
    results = []

    scenarios = [
        {
            "lang": "ru",
            "session": "pitch-ru",
            "title": "RU: покупка для себя, 100-300 млн, Хамовники",
            "messages": [
                "Здравствуйте",
                "Для себя",
                "100-300 млн",
                "Хамовники",
                "1-3 мес",
                "наличные",
            ],
        },
        {
            "lang": "en",
            "session": "pitch-en",
            "title": "EN: investment, $1-3M, Khamovniki",
            "messages": [
                "Hello",
                "Investment",
                "$1-3M",
                "Khamovniki",
                "3-6 months",
                "international transfer",
            ],
        },
    ]

    for sc in scenarios:
        dialog_log = []
        for msg in sc["messages"]:
            req = ChatRequest(
                session_id=sc["session"],
                message=msg,
                lang=ClientLang(sc["lang"]),
                source="pitch",
            )
            resp = await bot.handle(req)
            dialog_log.append(
                {
                    "user": msg,
                    "bot": resp.reply,
                    "state": resp.state.value,
                    "score": resp.score,
                    "latency_ms": resp.latency_ms,
                    "matched": [m["title"] for m in resp.matched_properties],
                    "is_qualified": resp.is_qualified,
                    "crm_lead_id": resp.crm_lead_id,
                    "cost_rub": resp.cost_rub,
                }
            )
            if resp.is_qualified:
                break

        results.append(
            {
                "title": sc["title"],
                "lang": sc["lang"],
                "dialog": dialog_log,
            }
        )

    return results


async def collect_offmarket() -> list[dict]:
    """Сканирование 10 кадастровых номеров."""

    scanner = get_scanner()
    scorer = get_scorer()

    cadastral_numbers = await scanner.get_watch_list()
    results = []
    for cn in cadastral_numbers:
        signals = await scanner.scan_one(cn)
        scored = scorer.score(cn, signals)
        results.append({**signals, **scored, "cadastral_number": cn})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


async def main() -> None:
    print("==> Dialogs...")
    dialogs = await collect_dialogs()
    print(f"    {len(dialogs)} scenarios")

    print("==> Off-market...")
    offmarket = await collect_offmarket()
    print(f"    {len(offmarket)} objects")

    (OUT / "dialogs.json").write_text(
        json.dumps(dialogs, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (OUT / "offmarket.json").write_text(
        json.dumps(offmarket, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    # Summary metrics
    total_latency_ru = sum(s["latency_ms"] for s in dialogs[0]["dialog"])
    total_latency_en = sum(s["latency_ms"] for s in dialogs[1]["dialog"])
    total_cost_ru = sum(s["cost_rub"] for s in dialogs[0]["dialog"])
    total_cost_en = sum(s["cost_rub"] for s in dialogs[1]["dialog"])

    high = sum(1 for r in offmarket if r["priority"] == "high")
    medium = sum(1 for r in offmarket if r["priority"] == "medium")
    total_value = sum(
        r.get("estimated_value_rub", 0)
        for r in offmarket
        if r["priority"] in ("high", "medium")
    )

    metrics = {
        "concierge": {
            "ru_steps": len(dialogs[0]["dialog"]),
            "en_steps": len(dialogs[1]["dialog"]),
            "ru_latency_ms_total": total_latency_ru,
            "en_latency_ms_total": total_latency_en,
            "ru_cost_rub_total": round(total_cost_ru, 4),
            "en_cost_rub_total": round(total_cost_en, 4),
            "ru_qualified": dialogs[0]["dialog"][-1]["is_qualified"],
            "en_qualified": dialogs[1]["dialog"][-1]["is_qualified"],
            "ru_crm_lead": dialogs[0]["dialog"][-1]["crm_lead_id"],
            "en_crm_lead": dialogs[1]["dialog"][-1]["crm_lead_id"],
        },
        "offmarket": {
            "total_objects": len(offmarket),
            "high_priority": high,
            "medium_priority": medium,
            "total_value_rub": total_value,
            "top_address": offmarket[0]["address"] if offmarket else None,
            "top_score": offmarket[0]["score"] if offmarket else 0,
            "top_value_rub": offmarket[0].get("estimated_value_rub", 0) if offmarket else 0,
        },
    }
    (OUT / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("==> Metrics:")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"\nSaved to {OUT}/")


if __name__ == "__main__":
    asyncio.run(main())