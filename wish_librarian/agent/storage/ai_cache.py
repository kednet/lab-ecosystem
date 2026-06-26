"""
Кеш ответов AI по (book_fingerprint, prompt_kind, model, template, style_hash).

Идея: если мы перепарсили книгу и content-факты (title, author, year, isbn)
те же, что в предыдущий раз — не вызываем AI повторно, читаем из кеша.

Хранилище: cache_dir/ai_responses/{fingerprint}/{kind}__{model}__{ver}__{tpl}__{style}.md

Legacy-формат (``{kind}__{model}__{ver}.md``) остаётся на диске для обратной
совместимости, но ``get_cached`` его НЕ возвращает — он служит только для
ручного просмотра. Это гарантирует, что при переходе на новый шаблон
содержимое гарантированно пересоздаётся, а не подсовывается из старого кеша.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from agent.config import get_settings
from agent.models import BookInfo
from agent.utils.logger import get_logger


logger = get_logger()


# Версии промтов — менять при изменении формулировок.
# При изменении версии кеш автоматически инвалидируется.
# v2: добавлены внешние шаблоны + style injection. Вместе с этим бампом
# меняется формат имени файла кеша (включает tpl + style_hash), но legacy
# файлы v1 остаются на диске и не возвращаются get_cached.
PROMPT_VERSIONS = {
    "summary": "v2",
    "workbook": "v2",
    "tips": "v2",
}


# ── Пути ─────────────────────────────────────────────────────────────
def _safe(s: str) -> str:
    """Убрать из имени файла/каталога недопустимые символы (Windows- и URL-опасные)."""
    return (
        s.replace(":", "_")
         .replace("/", "_")
         .replace("\\", "_")
         .replace(" ", "_")
    )


def _cache_path(
    book: BookInfo,
    kind: str,
    model: str,
    tpl: str = "default",
    style_hash: str = "default",
) -> Path:
    settings = get_settings()
    fp = book.fingerprint()
    safe_fp = _safe(fp)
    safe_model = _safe(model)
    version = PROMPT_VERSIONS.get(kind, "v1")
    fname = f"{kind}__{safe_model}__{version}__{_safe(tpl)}__{style_hash}.md"
    return settings.cache_dir / "ai_responses" / safe_fp / fname


def _legacy_cache_path(book: BookInfo, kind: str, model: str) -> Path:
    """Старый формат имени: {kind}__{model}__{version}.md (без tpl/style)."""
    settings = get_settings()
    fp = book.fingerprint()
    safe_fp = _safe(fp)
    safe_model = _safe(model)
    version = PROMPT_VERSIONS.get(kind, "v1")
    fname = f"{kind}__{safe_model}__{version}.md"
    return settings.cache_dir / "ai_responses" / safe_fp / fname


# ── API ──────────────────────────────────────────────────────────────
def get_cached(
    book: BookInfo,
    kind: str,
    model: str,
    *,
    tpl: str = "default",
    style_hash: str = "default",
    allow_legacy: bool = True,
) -> Optional[str]:
    """
    Вернуть закешированный текст или None.

    По умолчанию legacy-файлы (без ``tpl``/``style_hash`` в имени)
    НЕ возвращаются — это сделано намеренно, чтобы новые шаблоны и стили
    гарантированно перегенерировались. Передайте ``allow_legacy=False``
    для полной изоляции.
    """
    p = _cache_path(book, kind, model, tpl=tpl, style_hash=style_hash)
    if p.exists() and p.stat().st_size > 0:
        logger.debug("💾 Кеш HIT: {} ({} байт)", p.name, p.stat().st_size)
        return p.read_text(encoding="utf-8")

    # Legacy fallback: читаем, но только если не было нового ключа и
    # пользователь явно не отказался.
    if allow_legacy:
        legacy = _legacy_cache_path(book, kind, model)
        if legacy.exists() and legacy.stat().st_size > 0:
            logger.info(
                "♻️  Legacy-кеш найден, но игнорируется (нужна регенерация с новым шаблоном/стилем): {}",
                legacy.name,
            )
    return None


def save_cached(
    book: BookInfo,
    kind: str,
    model: str,
    content: str,
    *,
    tpl: str = "default",
    style_hash: str = "default",
) -> None:
    """Сохранить ответ AI в кеш."""
    p = _cache_path(book, kind, model, tpl=tpl, style_hash=style_hash)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    logger.debug("💾 Кеш SAVE: {} ({} байт)", p.name, len(content))


def clear_cache_for(book: BookInfo) -> int:
    """Очистить весь кеш для одной книги. Возвращает кол-во удалённых файлов."""
    fp = book.fingerprint().replace(":", "_")
    settings = get_settings()
    target = settings.cache_dir / "ai_responses" / fp
    if not target.exists():
        return 0
    n = sum(1 for _ in target.glob("*") if _.is_file())
    import shutil
    shutil.rmtree(target, ignore_errors=True)
    return n


def clear_legacy_cache() -> int:
    """
    Удалить все legacy-файлы (без tpl/style_hash) из кеша.
    Возвращает количество удалённых файлов.
    Используется CLI-флагом ``--purge-legacy-cache``.
    """
    settings = get_settings()
    root = settings.cache_dir / "ai_responses"
    if not root.exists():
        return 0
    import re
    # Legacy-шаблон: {kind}__{model}__{vN}.md  (4 сегмента, 3 подчёркивания)
    legacy_re = re.compile(r"^[^_]+__[^_]+__v\d+\.md$")
    n = 0
    for p in root.rglob("*.md"):
        if legacy_re.match(p.name):
            try:
                p.unlink()
                n += 1
            except OSError:
                pass
    return n
