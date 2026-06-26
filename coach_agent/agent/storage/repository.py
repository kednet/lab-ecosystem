"""
Типизированный async-репозиторий для D1.

Содержит CRUD-методы по всем таблицам. Все методы async.
Возвращают Pydantic-модели из agent.storage.models.

Конвенции:
- get_* → Optional[Row] или list[Row]
- upsert_* → Row (создаёт или обновляет)
- update_* → Row (обновляет, возвращает обновлённое)
- create_* → Row
- *_log → пишет в audit-таблицу (crisis_log, tone_profile)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from agent.storage.d1_client_async import D1ClientAsync, get_d1_async
from agent.storage.models import (
    ClientChannelRow,
    ClientRow,
    CrisisLogRow,
    DesireRow,
    DesireStepRow,
    MessageRow,
    SessionRow,
    WorkbookRunRow,
)
from agent.utils import get_logger

log = get_logger("repository")


def _now() -> str:
    """ISO-8601 UTC timestamp."""
    return datetime.now(UTC).isoformat()


class Repository:
    """Async-репозиторий поверх D1ClientAsync."""

    def __init__(self, client: D1ClientAsync | None = None) -> None:
        self._d1 = client or get_d1_async()

    # === Client ===

    async def get_client_by_id(self, client_id: int) -> ClientRow | None:
        row = await self._d1.fetch_one(
            "SELECT * FROM client WHERE id = ?", [client_id]
        )
        return ClientRow.from_d1_row(row) if row else None

    async def get_client_by_email(self, email: str) -> ClientRow | None:
        row = await self._d1.fetch_one(
            "SELECT * FROM client WHERE email = ?", [email]
        )
        return ClientRow.from_d1_row(row) if row else None

    async def upsert_client(
        self,
        email: str,
        name: str | None = None,
        current_tone: str = "warm",
        tone_intensity: int = 3,
    ) -> ClientRow:
        """Создаёт клиента, если нет; иначе обновляет last_seen_at и tone."""
        now = _now()
        # Пытаемся вставить; ON CONFLICT обновляет last_seen_at и tone
        await self._d1.execute(
            """
            INSERT INTO client (email, name, current_tone, tone_intensity, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                current_tone = excluded.current_tone,
                tone_intensity = excluded.tone_intensity
            """,
            [email, name, current_tone, tone_intensity, now, now],
        )
        client = await self.get_client_by_email(email)
        if client is None:
            raise RuntimeError(f"upsert_client не вернул строку для {email}")
        log.info("repository.upsert_client", client_id=client.id, email=email)
        return client

    async def update_client_tone(
        self, client_id: int, tone: str, intensity: int
    ) -> ClientRow | None:
        await self._d1.execute(
            "UPDATE client SET current_tone = ?, tone_intensity = ?, last_seen_at = ? WHERE id = ?",
            [tone, intensity, _now(), client_id],
        )
        return await self.get_client_by_id(client_id)

    async def update_client_onboarding(
        self, client_id: int, onboarding_state: str
    ) -> ClientRow | None:
        await self._d1.execute(
            "UPDATE client SET onboarding_state = ?, last_seen_at = ? WHERE id = ?",
            [onboarding_state, _now(), client_id],
        )
        return await self.get_client_by_id(client_id)

    async def touch_client(self, client_id: int) -> None:
        await self._d1.execute(
            "UPDATE client SET last_seen_at = ? WHERE id = ?",
            [_now(), client_id],
        )

    # === ClientChannel (Phase 7) ===

    async def find_client_by_channel(
        self, channel: str, external_id: str
    ) -> ClientRow | None:
        """Найти клиента по привязке к внешнему каналу (vk/telegram/web).

        Возвращает ClientRow (НЕ ClientChannelRow) — нам нужен весь клиент
        для process_message. None если привязки нет.
        """
        row = await self._d1.fetch_one(
            """
            SELECT c.* FROM client c
            INNER JOIN client_channel cc ON cc.client_id = c.id
            WHERE cc.channel = ? AND cc.external_id = ?
            """,
            [channel, external_id],
        )
        return ClientRow.from_d1_row(row) if row else None

    async def upsert_client_channel(
        self,
        client_id: int,
        channel: str,
        external_id: str,
    ) -> ClientChannelRow:
        """Создаёт или обновляет привязку client → (channel, external_id).

        Использует UPSERT по (client_id, channel) — повторный вызов
        с тем же channel просто обновляет external_id и last_seen_at.
        """
        now = _now()
        await self._d1.execute(
            """
            INSERT INTO client_channel (client_id, channel, external_id, verified_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(client_id, channel) DO UPDATE SET
                external_id = excluded.external_id,
                verified_at = excluded.verified_at,
                last_seen_at = excluded.last_seen_at
            """,
            [client_id, channel, external_id, now, now],
        )
        row = await self._d1.fetch_one(
            "SELECT * FROM client_channel WHERE client_id = ? AND channel = ?",
            [client_id, channel],
        )
        if row is None:
            raise RuntimeError(
                f"upsert_client_channel: row not found for client_id={client_id}, channel={channel}"
            )
        log.info(
            "repository.upsert_client_channel",
            client_id=client_id,
            channel=channel,
            external_id=external_id,
        )
        return ClientChannelRow.from_d1_row(row)

    async def list_client_channels(
        self, client_id: int
    ) -> list[ClientChannelRow]:
        """Все привязки клиента (web/telegram/vk)."""
        rows = await self._d1.fetch_all(
            "SELECT * FROM client_channel WHERE client_id = ? ORDER BY channel",
            [client_id],
        )
        return [ClientChannelRow.from_d1_row(r) for r in rows]

    # === Session ===

    async def create_session(
        self,
        client_id: int,
        tone: str,
        tone_intensity: int,
        mode: str = "dialog",
    ) -> SessionRow:
        now = _now()
        await self._d1.execute(
            """
            INSERT INTO session (client_id, started_at, current_state, tone, tone_intensity, mode)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [client_id, now, "S_DIALOG", tone, tone_intensity, mode],
        )
        # Берём последний вставленный
        row = await self._d1.fetch_one(
            "SELECT * FROM session WHERE client_id = ? ORDER BY id DESC LIMIT 1",
            [client_id],
        )
        if row is None:
            raise RuntimeError("create_session: row not found after insert")
        log.info("repository.create_session", session_id=row["id"], client_id=client_id)
        return SessionRow.from_d1_row(row)

    async def get_active_session(self, client_id: int) -> SessionRow | None:
        row = await self._d1.fetch_one(
            "SELECT * FROM session WHERE client_id = ? AND ended_at IS NULL ORDER BY id DESC LIMIT 1",
            [client_id],
        )
        return SessionRow.from_d1_row(row) if row else None

    async def get_last_session(self, client_id: int) -> SessionRow | None:
        row = await self._d1.fetch_one(
            "SELECT * FROM session WHERE client_id = ? ORDER BY id DESC LIMIT 1",
            [client_id],
        )
        return SessionRow.from_d1_row(row) if row else None

    async def get_session_by_id(self, session_id: int) -> SessionRow | None:
        row = await self._d1.fetch_one(
            "SELECT * FROM session WHERE id = ?", [session_id]
        )
        return SessionRow.from_d1_row(row) if row else None

    async def update_session_state(
        self,
        session_id: int,
        state: str,
        total_cost_usd_delta: float = 0.0,
    ) -> SessionRow | None:
        """Обновить current_state и прибавить к total_cost_usd."""
        await self._d1.execute(
            """
            UPDATE session
            SET current_state = ?,
                total_cost_usd = COALESCE(total_cost_usd, 0) + ?
            WHERE id = ?
            """,
            [state, total_cost_usd_delta, session_id],
        )
        return await self.get_session_by_id(session_id)

    async def end_session(
        self,
        session_id: int,
        reason: str,
        summary: str | None = None,
    ) -> SessionRow | None:
        await self._d1.execute(
            """
            UPDATE session
            SET ended_at = ?,
                ended_reason = ?,
                summary = COALESCE(?, summary)
            WHERE id = ?
            """,
            [_now(), reason, summary, session_id],
        )
        return await self.get_session_by_id(session_id)

    # === Message ===

    async def append_message(
        self,
        session_id: int,
        role: str,
        content: str,
        is_crisis: bool = False,
        excluded_from_training: bool = False,
    ) -> MessageRow:
        await self._d1.execute(
            """
            INSERT INTO message (session_id, role, content, ts, is_crisis_message, excluded_from_training)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                session_id,
                role,
                content,
                _now(),
                1 if is_crisis else 0,
                1 if excluded_from_training else 0,
            ],
        )
        row = await self._d1.fetch_one(
            "SELECT * FROM message WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            [session_id],
        )
        if row is None:
            raise RuntimeError("append_message: row not found after insert")
        return MessageRow.from_d1_row(row)

    async def get_recent_messages(
        self, session_id: int, limit: int = 20
    ) -> list[MessageRow]:
        rows = await self._d1.fetch_all(
            "SELECT * FROM message WHERE session_id = ? ORDER BY id ASC LIMIT ?",
            [session_id, limit],
        )
        return [MessageRow.from_d1_row(r) for r in rows]

    async def count_messages(self, session_id: int) -> int:
        row = await self._d1.fetch_one(
            "SELECT COUNT(*) AS n FROM message WHERE session_id = ?",
            [session_id],
        )
        return int(row["n"]) if row else 0

    # === Desire ===

    async def create_desire(
        self,
        client_id: int,
        title: str,
        kind: str | None = None,
        score: float | None = None,
        verdict_label: str | None = None,
        module_scores: dict[str, float] | None = None,
        detector_depth: str | None = None,
        reasoning: str | None = None,
    ) -> DesireRow:
        now = _now()
        module_scores_json = json.dumps(module_scores) if module_scores else None
        await self._d1.execute(
            """
            INSERT INTO desire (
                client_id, title, kind, score, verdict_label, module_scores,
                detector_depth, reasoning, status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            [
                client_id, title, kind, score, verdict_label, module_scores_json,
                detector_depth, reasoning, now, now,
            ],
        )
        row = await self._d1.fetch_one(
            "SELECT * FROM desire WHERE client_id = ? ORDER BY id DESC LIMIT 1",
            [client_id],
        )
        if row is None:
            raise RuntimeError("create_desire: row not found after insert")
        log.info("repository.create_desire", desire_id=row["id"], client_id=client_id, title=title[:50])
        return DesireRow.from_d1_row(row)

    async def update_desire_verdict(
        self,
        desire_id: int,
        kind: str,
        score: float,
        verdict_label: str,
        module_scores: dict[str, float],
        detector_depth: str,
        reasoning: str,
    ) -> DesireRow | None:
        await self._d1.execute(
            """
            UPDATE desire SET
                kind = ?, score = ?, verdict_label = ?,
                module_scores = ?, detector_depth = ?, reasoning = ?,
                updated_at = ?
            WHERE id = ?
            """,
            [
                kind, score, verdict_label,
                json.dumps(module_scores), detector_depth, reasoning,
                _now(), desire_id,
            ],
        )
        row = await self._d1.fetch_one("SELECT * FROM desire WHERE id = ?", [desire_id])
        return DesireRow.from_d1_row(row) if row else None

    async def update_desire_status(
        self, desire_id: int, status: str
    ) -> DesireRow | None:
        await self._d1.execute(
            "UPDATE desire SET status = ?, updated_at = ? WHERE id = ?",
            [status, _now(), desire_id],
        )
        row = await self._d1.fetch_one("SELECT * FROM desire WHERE id = ?", [desire_id])
        return DesireRow.from_d1_row(row) if row else None

    async def get_active_desires(self, client_id: int) -> list[DesireRow]:
        rows = await self._d1.fetch_all(
            "SELECT * FROM desire WHERE client_id = ? AND status = 'active' ORDER BY id DESC",
            [client_id],
        )
        return [DesireRow.from_d1_row(r) for r in rows]

    async def get_desire_by_id(self, desire_id: int) -> DesireRow | None:
        row = await self._d1.fetch_one(
            "SELECT * FROM desire WHERE id = ?", [desire_id]
        )
        return DesireRow.from_d1_row(row) if row else None

    # === DesireStep ===

    async def create_desire_step(
        self,
        desire_id: int,
        title: str,
        deadline: str | None = None,
        deadline_type: str | None = None,
    ) -> DesireStepRow:
        now = _now()
        await self._d1.execute(
            """
            INSERT INTO desire_step (desire_id, title, deadline, deadline_type, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            [desire_id, title, deadline, deadline_type, now, now],
        )
        row = await self._d1.fetch_one(
            "SELECT * FROM desire_step WHERE desire_id = ? ORDER BY id DESC LIMIT 1",
            [desire_id],
        )
        if row is None:
            raise RuntimeError("create_desire_step: row not found")
        return DesireStepRow.from_d1_row(row)

    async def mark_step_done(self, step_id: int) -> DesireStepRow | None:
        await self._d1.execute(
            "UPDATE desire_step SET status = 'done', done_at = ?, updated_at = ? WHERE id = ?",
            [_now(), _now(), step_id],
        )
        row = await self._d1.fetch_one("SELECT * FROM desire_step WHERE id = ?", [step_id])
        return DesireStepRow.from_d1_row(row) if row else None

    async def list_steps(
        self, desire_id: int, status: str | None = None
    ) -> list[DesireStepRow]:
        """Список шагов желания. Опционально фильтр по статусу (pending|done|skipped)."""
        if status is not None:
            rows = await self._d1.fetch_all(
                "SELECT * FROM desire_step WHERE desire_id = ? AND status = ? "
                "ORDER BY id ASC",
                [desire_id, status],
            )
        else:
            rows = await self._d1.fetch_all(
                "SELECT * FROM desire_step WHERE desire_id = ? ORDER BY id ASC",
                [desire_id],
            )
        return [DesireStepRow.from_d1_row(r) for r in rows]

    async def get_step_by_id(self, step_id: int) -> DesireStepRow | None:
        row = await self._d1.fetch_one(
            "SELECT * FROM desire_step WHERE id = ?", [step_id]
        )
        return DesireStepRow.from_d1_row(row) if row else None

    async def mark_step_skipped(self, step_id: int) -> DesireStepRow | None:
        await self._d1.execute(
            "UPDATE desire_step SET status = 'skipped', updated_at = ? WHERE id = ?",
            [_now(), step_id],
        )
        row = await self._d1.fetch_one("SELECT * FROM desire_step WHERE id = ?", [step_id])
        return DesireStepRow.from_d1_row(row) if row else None

    async def update_step(
        self,
        step_id: int,
        title: str | None = None,
        deadline: str | None = None,
        deadline_type: str | None = None,
    ) -> DesireStepRow | None:
        """Частичное обновление шага — меняет только переданные поля.

        Чтобы «не передать» поле, передают значение-маркер. Здесь None означает
        «не менять» (SQL COALESCE) — но для title/deadline_type нужно явно
        отличать NULL от «не менять». Используем sentinel-объект.
        """
        # Простая версия: явно None = «записать NULL», иначе записать значение.
        # Чтобы «не менять», не передавайте аргумент.
        sets: list[str] = []
        params: list = []
        if title is not None:
            sets.append("title = ?")
            params.append(title)
        if deadline is not None:
            sets.append("deadline = ?")
            params.append(deadline)
        if deadline_type is not None:
            sets.append("deadline_type = ?")
            params.append(deadline_type)
        if not sets:
            return await self.get_step_by_id(step_id)
        sets.append("updated_at = ?")
        params.append(_now())
        params.append(step_id)
        await self._d1.execute(
            f"UPDATE desire_step SET {', '.join(sets)} WHERE id = ?", params
        )
        return await self.get_step_by_id(step_id)

    async def delete_step(self, step_id: int) -> bool:
        await self._d1.execute("DELETE FROM desire_step WHERE id = ?", [step_id])
        return True

    async def count_steps_by_status(self, desire_id: int, status: str) -> int:
        """Количество шагов с указанным статусом. Используется для all_done()."""
        rows = await self._d1.fetch_all(
            "SELECT id FROM desire_step WHERE desire_id = ? AND status = ?",
            [desire_id, status],
        )
        return len(rows)

    async def set_step_status(
        self, step_id: int, status: str, done_at: str | None = None
    ) -> DesireStepRow | None:
        """Универсальный setter статуса шага (для undo_done / undo_skip)."""
        await self._d1.execute(
            "UPDATE desire_step SET status = ?, done_at = ?, updated_at = ? WHERE id = ?",
            [status, done_at, _now(), step_id],
        )
        return await self.get_step_by_id(step_id)

    # === Crisis Log (только хэш!) ===

    async def log_crisis(
        self,
        client_id: int,
        session_id: int,
        channel: str,
        message_hash: str,
        matched_pattern: str,
    ) -> CrisisLogRow:
        await self._d1.execute(
            """
            INSERT INTO crisis_log (client_id, session_id, channel, message_hash, matched_pattern, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [client_id, session_id, channel, message_hash, matched_pattern, _now()],
        )
        row = await self._d1.fetch_one(
            "SELECT * FROM crisis_log WHERE client_id = ? ORDER BY id DESC LIMIT 1",
            [client_id],
        )
        if row is None:
            raise RuntimeError("log_crisis: row not found")
        log.warning(
            "repository.crisis_logged",
            client_id=client_id,
            session_id=session_id,
            pattern=matched_pattern,
        )
        return CrisisLogRow.from_d1_row(row)

    # === Session crisis flag (Phase 8) ===

    async def mark_session_crisis(self, session_id: int) -> None:
        """Пометить сессию как crisis (crisis_flag=1). Используется в _handle_crisis."""
        await self._d1.execute(
            "UPDATE session SET crisis_flag = 1 WHERE id = ?",
            [session_id],
        )
        log.warning("repository.session_crisis_marked", session_id=session_id)

    # === Crisis follow-up (Phase 8) ===

    async def list_old_unfollowed_crisis(
        self, before_iso: str, limit: int = 50
    ) -> list[CrisisLogRow]:
        """Crisis-логи старше `before_iso` (ISO-8601) без `followed_up_at`."""
        rows = await self._d1.fetch_all(
            """
            SELECT * FROM crisis_log
            WHERE created_at < ? AND followed_up_at IS NULL
            ORDER BY id ASC LIMIT ?
            """,
            [before_iso, limit],
        )
        return [CrisisLogRow.from_d1_row(r) for r in rows]

    async def mark_crisis_followed_up(self, log_id: int) -> None:
        """Поставить аудит-метку `followed_up_at=now()` (мягкий 24ч follow-up)."""
        await self._d1.execute(
            "UPDATE crisis_log SET followed_up_at = ? WHERE id = ?",
            [_now(), log_id],
        )
        log.info("repository.crisis_followed_up", log_id=log_id)

    # === WorkbookRun ===

    async def create_workbook_run(
        self,
        client_id: int,
        book_slug: str,
        session_id: int | None,
        step_index: int = 0,
    ) -> WorkbookRunRow:
        """Создаёт новый workbook_run (status='in_progress')."""
        now = _now()
        await self._d1.execute(
            """
            INSERT INTO workbook_run (
                client_id, book_slug, session_id, step_index, answer,
                status, created_at
            ) VALUES (?, ?, ?, ?, NULL, 'in_progress', ?)
            """,
            [client_id, book_slug, session_id, step_index, now],
        )
        row = await self._d1.fetch_one(
            "SELECT * FROM workbook_run WHERE client_id = ? ORDER BY id DESC LIMIT 1",
            [client_id],
        )
        if row is None:
            raise RuntimeError("create_workbook_run: row not found after insert")
        log.info(
            "repository.create_workbook_run",
            run_id=row["id"],
            client_id=client_id,
            book_slug=book_slug,
        )
        return WorkbookRunRow.from_d1_row(row)

    async def get_active_workbook_run(
        self, client_id: int
    ) -> WorkbookRunRow | None:
        """Последний in_progress run клиента (если есть)."""
        row = await self._d1.fetch_one(
            """
            SELECT * FROM workbook_run
            WHERE client_id = ? AND status = 'in_progress'
            ORDER BY id DESC LIMIT 1
            """,
            [client_id],
        )
        return WorkbookRunRow.from_d1_row(row) if row else None

    async def get_resumable_workbook_run(
        self, client_id: int
    ) -> WorkbookRunRow | None:
        """Последний run, который можно возобновить: in_progress ИЛИ paused."""
        row = await self._d1.fetch_one(
            """
            SELECT * FROM workbook_run
            WHERE client_id = ? AND status IN ('in_progress', 'paused')
            ORDER BY id DESC LIMIT 1
            """,
            [client_id],
        )
        return WorkbookRunRow.from_d1_row(row) if row else None

    async def reactivate_paused_run(self, run_id: int) -> WorkbookRunRow | None:
        """Перевод paused run в in_progress (resume)."""
        await self._d1.execute(
            "UPDATE workbook_run SET status = 'in_progress' WHERE id = ? AND status = 'paused'",
            [run_id],
        )
        log.info("repository.workbook_run_reactivated", run_id=run_id)
        return await self.get_workbook_run_by_id(run_id)

    async def get_workbook_run_by_id(
        self, run_id: int
    ) -> WorkbookRunRow | None:
        row = await self._d1.fetch_one(
            "SELECT * FROM workbook_run WHERE id = ?", [run_id]
        )
        return WorkbookRunRow.from_d1_row(row) if row else None

    async def append_workbook_answer(
        self,
        run_id: int,
        step_index: int,
        answer: str | None,
    ) -> WorkbookRunRow | None:
        """Записать ответ на шаг и продвинуть step_index.

        Если answer is None — это «пустое продвижение» (когда нужно перейти
        к следующему шагу без сохранения ответа, например после AI-рефлексии).
        Если answer — текст ответа, он сохраняется в поле `answer`.
        """
        if answer is not None:
            await self._d1.execute(
                """
                UPDATE workbook_run
                SET step_index = ?, answer = ?
                WHERE id = ?
                """,
                [step_index, answer, run_id],
            )
        else:
            await self._d1.execute(
                "UPDATE workbook_run SET step_index = ? WHERE id = ?",
                [step_index, run_id],
            )
        return await self.get_workbook_run_by_id(run_id)

    async def mark_workbook_run_completed(
        self,
        run_id: int,
        status: str = "completed",
    ) -> WorkbookRunRow | None:
        """Пометить run как завершённый (`completed` или `paused`)."""
        if status not in ("completed", "paused"):
            raise ValueError(f"Недопустимый workbook_run status: {status!r}")
        await self._d1.execute(
            "UPDATE workbook_run SET status = ? WHERE id = ?",
            [status, run_id],
        )
        log.info(
            "repository.workbook_run_completed",
            run_id=run_id,
            status=status,
        )
        return await self.get_workbook_run_by_id(run_id)


_default_repo: Repository | None = None


def get_repository() -> Repository:
    """Singleton (создаётся в lifespan)."""
    global _default_repo
    if _default_repo is None:
        _default_repo = Repository()
    return _default_repo


__all__ = ["Repository", "get_repository"]
