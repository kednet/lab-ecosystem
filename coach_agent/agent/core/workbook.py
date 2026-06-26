"""
WorkbookService — Phase 4: прохождение воркбуков по книгам.

Источник: `agent.core.workbook_parser` (regex-парсер workbook.md).
Хранилище: `Repository.create_workbook_run` / `get_active_workbook_run` / etc.
AI: прямой `ai.complete()` для эмпатичной рефлексии (1-3 предложения).

Конфиг: `settings.workbooks_dir` (env WORKBOOKS_DIR) — каталог с поддиректориями
по книгам; каждая содержит `workbook.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.ai.factory import AIClient, AIError, AIUnconfiguredError, get_ai_client
from agent.ai.prompts import ContextBlock, build_system_prompt
from agent.core.tones import Tone
from agent.core.workbook_parser import Workbook, WorkbookStep, parse_workbook
from agent.storage.models import ClientRow, SessionRow, WorkbookRunRow
from agent.storage.repository import Repository
from agent.utils import get_logger

log = get_logger("workbook")


# === Минимальная длина ответа, чтобы оправдать AI-вызов ===
MIN_ANSWER_LEN = 3

# === Спец-инструкция для AI-рефлексии ===
_REFLECTION_HINT = (
    "ЗАДАЧА: дай короткую (1-3 предложения) эмпатичную реакцию на ответ клиента "
    "по шагу воркбука. Без оценок ('правильно/неправильно'), без мотивашки, "
    "без 'молодец'. Подхвати ключевую мысль, уточни или углуби — но кратко. "
    "Не объясняй, что ты ИИ. Говори на русском."
)


# === BookMeta ===

@dataclass(frozen=True)
class BookMeta:
    """Метаданные книги из её workbook.md (без полного парсинга body)."""

    slug: str
    title: str
    step_count: int
    has_reflection: bool
    has_bonus: bool
    path: str  # абсолютный путь к workbook.md (для отладки)


# === WorkbookService ===

class WorkbookService:
    def __init__(
        self,
        repository: Repository,
        ai_client: AIClient | None = None,
    ) -> None:
        self._repo = repository
        self._ai = ai_client

    # === Пути ===

    def books_dir(self) -> Path:
        """Каталог с поддиректориями `<slug>/workbook.md`."""
        from agent.config import settings
        return Path(settings.workbooks_dir)

    def _workbook_path(self, slug: str) -> Path:
        # Защита от path-traversal: slug не должен содержать '/' или '..'
        if not slug or "/" in slug or "\\" in slug or ".." in slug:
            raise ValueError(f"Недопустимый slug: {slug!r}")
        return self.books_dir() / slug / "workbook.md"

    # === Сканирование каталога ===

    def list_books(self) -> list[BookMeta]:
        """Сканирует `books_dir`, возвращает список BookMeta.

        Директории без `workbook.md` или с битым парсером — пропускаются
        (с warning в логе). Возвращается отсортированный по title список.
        """
        root = self.books_dir()
        if not root.exists():
            log.warning("workbook.books_dir_missing", path=str(root))
            return []
        out: list[BookMeta] = []
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            md_path = child / "workbook.md"
            if not md_path.is_file():
                continue
            try:
                wb = parse_workbook(child.name, md_path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as e:
                log.warning(
                    "workbook.parse_failed",
                    slug=child.name,
                    error=str(e),
                )
                continue
            out.append(
                BookMeta(
                    slug=wb.slug,
                    title=wb.title,
                    step_count=len(wb.steps),
                    has_reflection=wb.reflection is not None,
                    has_bonus=wb.bonus is not None,
                    path=str(md_path),
                )
            )
        out.sort(key=lambda b: b.title.lower())
        return out

    # === Загрузка одной книги ===

    def load_book(self, slug: str) -> Workbook:
        path = self._workbook_path(slug)
        if not path.is_file():
            raise FileNotFoundError(f"workbook.md для slug={slug!r} не найден: {path}")
        return parse_workbook(slug, path.read_text(encoding="utf-8"))

    # === Helpers для текущего шага ===

    def current_step(self, run: WorkbookRunRow, workbook: Workbook) -> WorkbookStep:
        if not 0 <= run.step_index < len(workbook.steps):
            raise IndexError(
                f"run.step_index={run.step_index} вне диапазона "
                f"[0, {len(workbook.steps)})"
            )
        return workbook.steps[run.step_index]

    # === Старт run ===

    async def start_run(
        self,
        client: ClientRow,
        session: SessionRow,
        slug: str,
    ) -> tuple[WorkbookRunRow, WorkbookStep, Workbook]:
        """Создаёт workbook_run (status=in_progress) и возвращает (run, step0, workbook).

        Resume:
        - если есть in_progress run → возвращаем его
        - если есть paused run с тем же slug → реактивируем (status=in_progress)
        - иначе → создаём новый

        Raises:
            FileNotFoundError: если workbook.md для slug не найден.
        """
        workbook = self.load_book(slug)
        # Сначала проверяем in_progress (уже идёт)
        existing = await self._repo.get_active_workbook_run(client.id)
        if existing is not None:
            log.info(
                "workbook.resuming_in_progress",
                client_id=client.id,
                run_id=existing.id,
                slug=existing.book_slug,
            )
            try:
                step = self.current_step(existing, workbook)
            except IndexError:
                step = workbook.steps[0]
            return existing, step, workbook

        # Paused run с тем же slug — реактивируем
        resumable = await self._repo.get_resumable_workbook_run(client.id)
        if resumable is not None and resumable.book_slug == slug:
            log.info(
                "workbook.reactivating_paused",
                client_id=client.id,
                run_id=resumable.id,
                slug=slug,
            )
            run = await self._repo.reactivate_paused_run(resumable.id)
            try:
                step = self.current_step(run, workbook)
            except IndexError:
                step = workbook.steps[0]
            return run, step, workbook

        # Чистый старт
        run = await self._repo.create_workbook_run(
            client_id=client.id,
            book_slug=slug,
            session_id=session.id,
            step_index=0,
        )
        step = workbook.steps[0]
        log.info(
            "workbook.run_started",
            run_id=run.id,
            client_id=client.id,
            slug=slug,
        )
        return run, step, workbook

    # === AI-рефлексия ===

    async def reflect(
        self,
        tone: Tone,
        intensity: int,
        book_title: str,
        step: WorkbookStep,
        answer: str,
    ) -> tuple[str, float]:
        """Возвращает (reflection_text, cost_usd).

        Прямой вызов ai.complete() — без ToolDispatcher, без FSM.
        При недоступном AI — возвращает generic fallback (без падения).
        """
        try:
            ai = self._ai or get_ai_client(prefer="claude")
        except AIUnconfiguredError as e:
            log.warning("workbook.ai_unconfigured", error=str(e))
            return _fallback_reflection(answer), 0.0

        ctx = ContextBlock(
            mode_hint="workbook_reflection",
            active_desire_title=book_title,
            channel="web",
        )
        system = build_system_prompt(tone, intensity, ctx) + "\n\n" + _REFLECTION_HINT

        # Шаг + ответ клиента (truncate body чтобы не раздувать prompt)
        step_preview = step.body[:300].strip()
        user_msg = (
            f"Книга: {book_title}\n"
            f"Шаг '{step.title}':\n{step_preview}\n\n"
            f"Ответ клиента: {answer.strip()}"
        )
        messages = [{"role": "user", "content": user_msg}]

        try:
            resp = await ai.complete(
                system=system,
                messages=messages,
                max_tokens=300,
            )
        except AIError as e:
            log.warning("workbook.ai_error", error=str(e))
            return _fallback_reflection(answer), 0.0

        from agent.ai.claude_client import estimate_cost
        cost = estimate_cost(
            resp.model or "claude-sonnet-4-5",
            resp.input_tokens,
            resp.output_tokens,
        )
        text = (resp.text or "").strip() or _fallback_reflection(answer)
        return text, cost


# === Fallback при недоступном AI ===

def _fallback_reflection(answer: str) -> str:
    """Короткая нейтральная реакция, если AI недоступен."""
    snippet = answer.strip().split("\n")[0][:120]
    if not snippet:
        return "Принято. Двигаемся дальше."
    return f"Принято: «{snippet}»."


# === Re-exports ===

__all__ = [
    "BookMeta",
    "WorkbookService",
    "MIN_ANSWER_LEN",
]
