r"""
Копирайтер для соцсетей (VK, Telegram, meta description).

Использует AI-фабрику из wish_librarian/agent/ai/factory.py через sys.path.
Если AI недоступен — генерирует fallback-тексты из шаблонов.

Промпты:
  - vk_announcement — 1000-1500 символов, интрига в первой строке, эмодзи, хештеги
  - tg_announcement — 600-900 символов, короче, акцент на практическую пользу
  - meta_description — <= 155 символов для <meta name="description">

Зависимости: работает с любым BaseAIClient (claude / yandex / gigachat).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

# ── UTF-8 fix for Windows ─────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── Гарантируем доступность WL agent.ai.factory ───────────
WISHLIBRARIAN_PATH = Path(__file__).resolve().parent.parent.parent / "wish_librarian"
if str(WISHLIBRARIAN_PATH) not in sys.path:
    sys.path.insert(0, str(WISHLIBRARIAN_PATH))

from loaders import SeoPackage  # noqa: E402

# Ленивая загрузка — чтобы не падать без `anthropic` в dev
_ai_client = None
_ai_client_error: Optional[Exception] = None


def _get_ai_client():
    """Получить AI-клиент (ленивая инициализация + кеш)."""
    global _ai_client, _ai_client_error
    if _ai_client is not None:
        return _ai_client
    if _ai_client_error is not None:
        return None
    try:
        from agent.ai.factory import get_ai_client
        _ai_client = get_ai_client()
        return _ai_client
    except Exception as e:
        _ai_client_error = e
        print(f"  ! AI client unavailable: {e}. Using fallback templates.", file=sys.stderr)
        return None


# ── Промпты ───────────────────────────────────────────────
PROMPT_VK = """Ты — SMM-копирайтер сообщества «ЛАБОРАТОРИЯ ЖЕЛАНИЙ» (психология, саморазвитие, осознанность).

Напиши анонс для ВКонтакте о выходе нового конспекта книги.

Длина: 1000-1500 символов. НЕ превышай 1500.
Структура:
- Первая строка — интригующий крючок (вопрос или парадокс)
- 2-3 коротких абзаца о сути книги
- Что читатель получит от конспекта (bullet-список, 3-4 пункта, можно emoji)
- Призыв к действию (забрать конспект, подписаться)
- 3-5 хештегов в конце (#лабораторияжеланий #конспект #[автор] #[тема])

Тон: тёплый, дружелюбный, без пафоса. Никаких "шок", "вы не поверите", заглавных букв в каждом слове.

Книга: {title} — {author} ({year})
Описание: {description}
Ключевые идеи: {key_ideas}

Пиши ТОЛЬКО текст поста, без заголовка 'Пост:' и без кавычек вокруг."""

PROMPT_TG = """Ты — копирайтер Telegram-канала о книгах и саморазвитии.

Напиши анонс для Telegram о выходе нового конспекта.

Длина: 600-900 символов. НЕ превышай 900.
Структура:
- Первая строка — крючок (1-2 строки)
- Одно предложение — о чём книга
- 3-4 буллита: что полезного в конспекте (используй •)
- Финальная строка — призыв + ссылка

Telegram поддерживает HTML: <b>жирный</b>, <i>курсив</i>, <a href="URL">текст</a>. Используй <b> для ключевых слов.
НЕ используй markdown-разметку (никаких ** или ##).
Эмодзи — умеренно (1-2 на пост).

Книга: {title} — {author} ({year})
Описание: {description}

Пиши ТОЛЬКО текст поста."""

PROMPT_META = """Сгенерируй meta description для SEO (description в <head>).

Длина: 140-155 символов. Содержит:
- Главную тему / проблему книги
- Что получит читатель
- 1-2 ключевых слова

Книга: {title} — {author} ({year})
Описание: {description}

Верни ТОЛЬКО текст описания, без 'Description:'."""


# ── AI wrapper ────────────────────────────────────────────
class AIProtocol(Protocol):
    async def complete(self, prompt: str, **kwargs) -> str: ...


async def _ai_complete(prompt: str, max_tokens: int = 1000) -> Optional[str]:
    """Запрос к AI-клиенту. Возвращает None если AI недоступен."""
    client = _get_ai_client()
    if client is None:
        return None
    try:
        # Пробуем разные сигнатуры
        if hasattr(client, "complete"):
            return await client.complete(prompt, max_tokens=max_tokens)
        if hasattr(client, "achat"):
            return await client.achat(prompt, max_tokens=max_tokens)
        if hasattr(client, "generate"):
            return await client.generate(prompt, max_tokens=max_tokens)
        return None
    except Exception as e:
        print(f"  ! AI call failed: {e}", file=sys.stderr)
        return None


def _format_ideas(ideas: list[str]) -> str:
    if not ideas:
        return ""
    return "\n".join(f"- {i}" for i in ideas[:5])


# ── Fallback-шаблоны (без AI) ─────────────────────────────
def _fallback_vk(pkg: SeoPackage, site_url: str = "") -> str:
    title = pkg.book_meta.title or pkg.book_slug
    author = pkg.book_meta.author or "?"
    year = pkg.book_meta.year or "—"
    short = (pkg.book_meta.short_description or "").strip().replace("\n", " ")[:200]
    ideas = pkg.book_meta.key_ideas[:3]
    ideas_block = "\n".join(f"• {i}" for i in ideas) if ideas else ""

    text = f"""📚 Новый конспект: {title}

{short or f"Книга {author} ({year}) — в нашей библиотеке."}

Что внутри:
{ideas_block or "• конспект основных идей\n• практические упражнения\n• советы по применению"}

👉 Забрать конспект: {site_url or f"https://app.pulab.online/library/{pkg.book_slug}/"}

#лабораторияжеланий #конспект #{author.split()[0] if author else 'книга'}
"""
    return text.strip()


def _fallback_tg(pkg: SeoPackage, site_url: str = "") -> str:
    title = pkg.book_meta.title or pkg.book_slug
    author = pkg.book_meta.author or "?"
    year = pkg.book_meta.year or "—"
    short = (pkg.book_meta.short_description or "").strip().replace("\n", " ")[:140]
    ideas = pkg.book_meta.key_ideas[:3]
    ideas_block = "\n".join(f"• {i[:60]}" for i in ideas) if ideas else "• конспект идей\n• практические упражнения"
    default_url = f"https://app.pulab.online/library/{pkg.book_slug}/"

    text = f"""<b>{title}</b> — {author} ({year})

{short or "Новый конспект в библиотеке."}

<b>Что в конспекте:</b>
{ideas_block}

👉 <a href="{site_url or default_url}">Забрать конспект</a>
"""
    return text.strip()


def _fallback_meta(pkg: SeoPackage) -> str:
    title = pkg.book_meta.title or pkg.book_slug
    author = pkg.book_meta.author or "?"
    short = (pkg.book_meta.short_description or "").strip().replace("\n", " ")
    if short:
        desc = f"{title} — {author}. {short}"
    else:
        desc = f"Конспект книги {title} — {author}. Главные идеи, практические упражнения и советы по применению."
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc[:155]


# ── Main class ────────────────────────────────────────────
class SocialCopywriter:
    """Генератор текстов для соцсетей и SEO.

    Использует AI из общей фабрики (claude / yandex / gigachat).
    При недоступности AI — fallback на шаблоны из SeoPackage.
    """

    def __init__(self, ai_client=None, site_url: str = "https://app.pulab.online"):
        self._ai_override = ai_client
        self.site_url = site_url.rstrip("/")
        self.last_source: str = "fallback"  # 'ai' | 'fallback' — для отладки

    @property
    def ai(self):
        if self._ai_override is not None:
            return self._ai_override
        return _get_ai_client()

    def _book_url(self, slug: str) -> str:
        return f"{self.site_url}/library/{slug}/"

    async def vk_announcement(self, pkg: SeoPackage) -> str:
        """1000-1500 символов анонс для ВК."""
        if self.ai is not None:
            prompt = PROMPT_VK.format(
                title=pkg.book_meta.title,
                author=pkg.book_meta.author,
                year=pkg.book_meta.year or "—",
                description=(pkg.book_meta.short_description or "")[:300],
                key_ideas=_format_ideas(pkg.book_meta.key_ideas),
            )
            result = await _ai_complete(prompt, max_tokens=800)
            if result and 200 < len(result) < 2000:
                self.last_source = "ai"
                return result.strip()
        self.last_source = "fallback"
        return _fallback_vk(pkg, self._book_url(pkg.book_slug))

    async def tg_announcement(self, pkg: SeoPackage) -> str:
        """600-900 символов анонс для TG (HTML)."""
        if self.ai is not None:
            prompt = PROMPT_TG.format(
                title=pkg.book_meta.title,
                author=pkg.book_meta.author,
                year=pkg.book_meta.year or "—",
                description=(pkg.book_meta.short_description or "")[:300],
            )
            result = await _ai_complete(prompt, max_tokens=500)
            if result and 100 < len(result) < 1500:
                self.last_source = "ai"
                return result.strip()
        self.last_source = "fallback"
        return _fallback_tg(pkg, self._book_url(pkg.book_slug))

    async def meta_description(self, pkg: SeoPackage) -> str:
        """<= 155 символов для <meta name='description'>."""
        if self.ai is not None:
            prompt = PROMPT_META.format(
                title=pkg.book_meta.title,
                author=pkg.book_meta.author,
                year=pkg.book_meta.year or "—",
                description=(pkg.book_meta.short_description or "")[:300],
            )
            result = await _ai_complete(prompt, max_tokens=100)
            if result and 80 < len(result) < 200:
                self.last_source = "ai"
                return re.sub(r"\s+", " ", result).strip()
        self.last_source = "fallback"
        return _fallback_meta(pkg)


# ── FastAPI endpoint integration ──────────────────────────
async def copywrite_book_endpoint(
    book_slug: str, site_url: str = "https://app.pulab.online"
) -> dict:
    """Вызывается из main.py как FastAPI endpoint.

    Returns:
        {
          "ok": true,
          "book_slug": "...",
          "vk": "...",
          "tg": "...",
          "meta_description": "...",
          "source": "ai" | "fallback"
        }
    """
    from loaders import load_seo_package

    pkg = load_seo_package(book_slug)
    if pkg is None:
        return {"ok": False, "error": "book_not_found", "book_slug": book_slug}

    cw = SocialCopywriter(site_url=site_url)
    vk = await cw.vk_announcement(pkg)
    tg = await cw.tg_announcement(pkg)
    meta = await cw.meta_description(pkg)

    return {
        "ok": True,
        "book_slug": book_slug,
        "vk": vk,
        "tg": tg,
        "meta_description": meta,
        "source": cw.last_source,
        "book": {
            "title": pkg.book_meta.title,
            "author": pkg.book_meta.author,
            "year": pkg.book_meta.year,
        },
    }


# ── CLI: smoke test ───────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    from loaders import load_seo_package

    async def _main():
        slug = "Вадим_Зеланд_Трансерфинг_реальности_2004"
        pkg = load_seo_package(slug)
        if pkg is None:
            print(f"Book '{slug}' not found")
            return

        cw = SocialCopywriter()
        print(f"AI client: {cw.ai}")
        print()

        for kind, coro in [
            ("VK", cw.vk_announcement(pkg)),
            ("TG", cw.tg_announcement(pkg)),
            ("META", cw.meta_description(pkg)),
        ]:
            text = await coro
            print(f"=== {kind} ({len(text)} chars, source={cw.last_source}) ===")
            print(text)
            print()

    asyncio.run(_main())
