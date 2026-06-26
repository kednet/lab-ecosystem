"""
Тесты для Phase 8: CrisisFollowup — мягкий 24ч follow-up (аудит-метка, НЕ сообщение).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agent.services.crisis_followup import (
    BATCH_LIMIT,
    FOLLOWUP_AFTER,
    CrisisFollowup,
)


@pytest.mark.asyncio
async def test_crisis_followup_marks_old_logs(fake_repo) -> None:
    """Crisis-лог старше 24ч получает followed_up_at."""
    # Вставляем лог старше 24ч
    old_iso = (datetime.now(UTC) - FOLLOWUP_AFTER - timedelta(hours=1)).isoformat()
    await fake_repo.log_crisis(
        client_id=1, session_id=1, channel="web",
        message_hash="abc123", matched_pattern="suicide",
    )
    # Подменяем created_at вручную (т.к. log_crisis жёстко ставит now)
    fake_repo._crisis[0] = fake_repo._crisis[0].__class__(
        **{
            **fake_repo._crisis[0].__dict__,
            "created_at": old_iso,
        }
    )

    cf = CrisisFollowup(fake_repo)
    n = await cf.run_once(fake_repo)
    assert n == 1

    logs = await fake_repo.list_old_unfollowed_crisis(
        before_iso=datetime.now(UTC).isoformat(),
        limit=10,
    )
    # Старый лог уже followed_up — не должен попасть в список
    assert len(logs) == 0

    # Проверяем, что followed_up_at проставлен
    followed_logs = [c for c in fake_repo._crisis if c.followed_up_at is not None]
    assert len(followed_logs) == 1
    assert followed_logs[0].id == fake_repo._crisis[0].id


@pytest.mark.asyncio
async def test_crisis_followup_skips_recent(fake_repo) -> None:
    """Свежий crisis-лог (< 24ч) НЕ трогается."""
    await fake_repo.log_crisis(
        client_id=1, session_id=1, channel="web",
        message_hash="recent", matched_pattern="distress",
    )
    # created_at = now() (дефолт fake_repo) → моложе 24ч
    cf = CrisisFollowup(fake_repo)
    n = await cf.run_once(fake_repo)
    assert n == 0
    # followed_up_at остался None
    assert fake_repo._crisis[0].followed_up_at is None


@pytest.mark.asyncio
async def test_crisis_followup_respects_batch_limit(fake_repo) -> None:
    """BATCH_LIMIT ограничивает количество за один проход."""
    old_iso = (datetime.now(UTC) - FOLLOWUP_AFTER - timedelta(hours=1)).isoformat()
    # Вставим BATCH_LIMIT + 5 логов
    for i in range(BATCH_LIMIT + 5):
        await fake_repo.log_crisis(
            client_id=1, session_id=1, channel="web",
            message_hash=f"h{i}", matched_pattern="suicide",
        )
        fake_repo._crisis[i] = fake_repo._crisis[i].__class__(
            **{**fake_repo._crisis[i].__dict__, "created_at": old_iso}
        )

    cf = CrisisFollowup(fake_repo)
    n = await cf.run_once(fake_repo)
    assert n == BATCH_LIMIT
    # BATCH_LIMIT+5 - BATCH_LIMIT = 5 ещё без метки
    unmarked = [c for c in fake_repo._crisis if c.followed_up_at is None]
    assert len(unmarked) == 5


@pytest.mark.asyncio
async def test_crisis_followup_empty_nothing_to_do(fake_repo) -> None:
    """Без crisis-логов run_once возвращает 0 и не падает."""
    cf = CrisisFollowup(fake_repo)
    n = await cf.run_once(fake_repo)
    assert n == 0
