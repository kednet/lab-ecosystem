"""Быстрый smoke-test всех компонентов MVP."""

import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.concierge.bot import get_bot
from src.concierge.schemas import ChatRequest, ClientLang
from src.offmarket.scanner import get_scanner
from src.offmarket.scorer import get_scorer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("smoke_test")


async def test_concierge_ru() -> None:
    """Тест AI-консьержа на русском."""

    log.info("=" * 60)
    log.info("TEST 1: AI-консьерж (RU)")
    log.info("=" * 60)

    bot = get_bot()
    session_id = "smoke-test-ru-001"

    messages = [
        "Здравствуйте",
        "Для себя",
        "100-300 млн",
        "Хамовники",
        "1-3 мес",
        "наличные",
    ]

    for msg in messages:
        req = ChatRequest(
            session_id=session_id,
            message=msg,
            lang=ClientLang.RU,
            source="smoke_test",
        )
        response = await bot.handle(req)
        log.info(f"USER: {msg}")
        log.info(f"BOT ({response.latency_ms}ms, score {response.score:.2f}): {response.reply[:100]}")
        if response.matched_properties:
            log.info(f"  → Matched: {[p['title'] for p in response.matched_properties]}")
        if response.crm_lead_id:
            log.info(f"  ✅ CRM Lead: {response.crm_lead_id}")
        if response.is_qualified:
            log.info(f"  🎯 QUALIFIED!")
            break


async def test_concierge_en() -> None:
    """Тест AI-консьержа на английском."""

    log.info("=" * 60)
    log.info("TEST 2: AI-консьерж (EN)")
    log.info("=" * 60)

    bot = get_bot()
    session_id = "smoke-test-en-001"

    messages = [
        "Hello",
        "Investment",
        "$1-3M",
        "Khamovniki",
        "3-6 months",
        "international transfer",
    ]

    for msg in messages:
        req = ChatRequest(
            session_id=session_id,
            message=msg,
            lang=ClientLang.EN,
            source="smoke_test",
        )
        response = await bot.handle(req)
        log.info(f"USER: {msg}")
        log.info(f"BOT ({response.latency_ms}ms, score {response.score:.2f}): {response.reply[:100]}")
        if response.is_qualified:
            log.info(f"  🎯 QUALIFIED!")
            break


async def test_offmarket() -> None:
    """Тест off-market матчинга."""

    log.info("=" * 60)
    log.info("TEST 3: Off-market матчинг")
    log.info("=" * 60)

    scanner = get_scanner()
    scorer = get_scorer()

    cadastral_numbers = await scanner.get_watch_list()
    log.info(f"Сканируем {len(cadastral_numbers)} кадастровых номеров")

    results = []
    for cn in cadastral_numbers:
        signals = await scanner.scan_one(cn)
        scored = scorer.score(cn, signals)
        results.append({**signals, **scored, "cadastral_number": cn})

    results.sort(key=lambda x: x["score"], reverse=True)

    for r in results[:5]:
        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(r["priority"], "⚪")
        log.info(
            f"{emoji} {r['address']} • score {r['score']:.2f} • "
            f"{r.get('estimated_value_rub', 0) / 1_000_000:.0f}M ₽"
        )
        for sig in r["signals"][:3]:
            log.info(f"   • {sig}")


async def test_rag() -> None:
    """Тест RAG индекса."""

    log.info("=" * 60)
    log.info("TEST 4: RAG поиск")
    log.info("=" * 60)

    from src.concierge.rag import get_rag

    rag = get_rag()
    await rag.load()
    log.info(f"Загружено объектов: {len(rag.properties)}")

    queries = [
        "пентхаус с видом на реку",
        "дом в Хамовниках",
        "квартира в новостройке",
    ]

    for q in queries:
        results = await rag.search(q, top_k=2, budget_max=300_000_000)
        log.info(f"QUERY: {q}")
        for r in results:
            log.info(f"  → {r.title} ({r.district}, {r.price_rub / 1_000_000:.0f} млн, score {r.score:.2f})")


async def main() -> None:
    log.info("🚀 Whitewill AI Engine — smoke tests")
    await test_rag()
    await test_concierge_ru()
    await test_concierge_en()
    await test_offmarket()
    log.info("=" * 60)
    log.info("✅ ALL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
