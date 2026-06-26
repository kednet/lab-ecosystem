"""
AI-стратегия для парсинга незнакомых сайтов.

Если URL не матчит ни одну из YAML-карт, а обычный OG-фолбэк дал мало
полей, передаём урезанный HTML в LLM и просим вернуть структурированный
BookInfo через JSON-формат (без function calling — это переносимо между
провайдерами).

Промт на английском — так модели стабильнее работают с JSON.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup

from agent.ai.base import BaseAIClient, AIClientError
from agent.models import BookInfo, ChapterInfo
from agent.parsers.prompts import find_site_for_url, load_all_sites
from agent.parsers.universal_parser import _Engine
from agent.utils.logger import get_logger


logger = get_logger()


# ── Промт ───────────────────────────────────────────────────────────
LLM_PARSE_SYSTEM = """You are a precise book metadata extractor.
You receive HTML of a book page and return a JSON object with fields:
  - title (string, required)
  - author (string)
  - year (int|null)
  - cover_url (absolute https URL or null)
  - short_description (1-3 sentences in original language)
  - isbn (string|null)
  - page_count (int|null)
  - genre (string|null)
  - key_ideas (array of 3-7 strings, original language)
  - quotes (array of 0-3 strings in «...»)
  - chapters (array of 0-10 chapter titles)

Rules:
  - Use ONLY what is on the page. Do not invent.
  - If a field is missing, return null or [].
  - Cover URL must be absolute (https://...). If only relative — prepend site origin.
  - key_ideas and quotes must be SHORT (under 200 chars each).
  - Return ONLY a valid JSON object. No prose, no markdown fences.
"""

LLM_PARSE_USER_TEMPLATE = """URL: {url}
Site: {site}

HTML (truncated, cleaned):
{html}

Return JSON:"""


# ── Подготовка HTML для LLM ─────────────────────────────────────────
def _truncate_html(html: str, max_chars: int = 12000) -> str:
    """Оставляем только meta-теги, h1-h3, p, и важные блоки."""
    soup = BeautifulSoup(html, "lxml")
    keep = []
    # meta-теги → текстом
    for m in soup.find_all("meta"):
        name = m.get("name") or m.get("property") or ""
        content = m.get("content", "").strip()
        if name and content and len(content) < 500:
            keep.append(f"[meta {name}] {content}")
    # заголовки и абзацы
    for tag in soup.find_all(["h1", "h2", "h3", "p", "li", "blockquote"]):
        txt = tag.get_text(" ", strip=True)
        if 10 <= len(txt) <= 800:
            keep.append(f"[{tag.name}] {txt}")
        if sum(len(x) for x in keep) > max_chars:
            break
    text = "\n".join(keep)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[... truncated ...]"
    return text


def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    """LLM может вернуть JSON с ```json``` обёрткой или мусором вокруг.
    Пытаемся извлечь первый валидный JSON-объект."""
    text = text.strip()
    # убираем markdown-fence
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
    # первый {...} блок
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


# ── Главный класс ────────────────────────────────────────────────────
class LLMParser:
    """Обёртка над LLM для парсинга неизвестных сайтов."""

    def __init__(self, ai: BaseAIClient):
        self.ai = ai

    def parse_unknown(
        self,
        url: str,
        html: str,
        fallback_site_name: str = "generic",
    ) -> Optional[BookInfo]:
        """Вернуть BookInfo или None, если LLM не справился."""
        # Не вызываем LLM, если сайт уже есть в картах
        sites = load_all_sites()
        matched = find_site_for_url(url, sites)
        if matched and matched.get("name") != "generic":
            logger.debug("LLM не нужен: URL матчит карту {}", matched.get("name"))
            return None

        truncated = _truncate_html(html)
        if not truncated.strip():
            logger.warning("HTML пустой — LLM не поможет")
            return None

        prompt = LLM_PARSE_USER_TEMPLATE.format(
            url=url, site=fallback_site_name, html=truncated
        )

        logger.info("🤖 Запрашиваю LLM-парсинг ({})", self.ai.name)
        try:
            response = self.ai.generate(
                system=LLM_PARSE_SYSTEM,
                user=prompt,
                max_tokens=2000,
                temperature=0.2,
            )
        except AIClientError as e:
            logger.error("LLM упал: {}", e)
            return None
        except Exception as e:
            logger.exception("LLM неожиданно упал: {}", e)
            return None

        data = _try_parse_json(response)
        if not data:
            logger.warning("LLM вернул не JSON: {}", response[:200])
            return None

        # Нормализуем в BookInfo
        chapters = []
        for i, ch in enumerate(data.get("chapters", []) or [], start=1):
            t = str(ch).strip()
            if 2 <= len(t) <= 200:
                chapters.append(ChapterInfo(number=i, title=t))

        info = BookInfo(
            title=str(data.get("title", "")).strip() or "Без названия",
            author=str(data.get("author", "")).strip() or "Неизвестен",
            year=data.get("year") if isinstance(data.get("year"), int) else None,
            source_url=url,
            cover_url=str(data.get("cover_url") or "").strip() or None,
            short_description=str(data.get("short_description") or "").strip() or None,
            key_ideas=[str(x).strip() for x in (data.get("key_ideas") or []) if str(x).strip()][:7],
            quotes=[str(x).strip() for x in (data.get("quotes") or []) if str(x).strip()][:5],
            chapters=chapters[:50],
            isbn=str(data.get("isbn") or "").strip() or None,
            page_count=data.get("page_count") if isinstance(data.get("page_count"), int) else None,
            genre=str(data.get("genre") or "").strip() or None,
        )
        logger.success(
            "✅ LLM-парсинг: «{}» — {} ({} идей, {} цитат)",
            info.title, info.author, len(info.key_ideas), len(info.quotes),
        )
        return info


def should_use_llm_fallback(soup_result: BookInfo, min_fields: int = 3) -> bool:
    """Решаем, нужен ли LLM, если обычный парсер мало что нашёл."""
    filled = sum(1 for f in (soup_result.title, soup_result.author,
                              soup_result.cover_url, soup_result.short_description,
                              soup_result.year)
                 if f)
    return filled < min_fields
