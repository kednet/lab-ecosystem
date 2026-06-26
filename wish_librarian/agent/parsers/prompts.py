"""
Карты сайтов для универсального парсера книг.

Каждая карта — это декларативное описание того, как достать поля книги
из конкретного ресурса. Декларация в YAML/JSON-стиле, чтобы было легко
добавлять новые источники без правки Python-кода.

Формат карты (SiteMap):
  - name:       уникальный id сайта
  - display:    человеко-читаемое имя
  - host_patterns: список regex'ов для матчинга URL
  - encoding:   предпочитаемая кодировка (utf-8 / cp1251 / auto)
  - selectors:  словарь {поле → (css_selector | [селекторы] | extraction_kind)}
  - strategy:   "metadata" | "og_meta" | "ld_json" | "microdata" | "opengraph"
  - extras:     дополнительные правила (chapters, comments, reviews)

Extraction kinds в selectors:
  - "text"     : element.text (strip)
  - "attr:src": element['src']
  - "attr:href": element['href']
  - "attr:content": meta[name=...] / meta[property=...] content
  - "list_text": все вложенные элементы по селектору, .text каждого
  - "title_split": взять title tag, split по ' - ' / ' — ' / ' / ' и вернуть сегмент
  - "url_slug": взять путь URL, первый сегмент после strip('/')

Если в карте selector — строка, по умолчанию используется "text".
Если список — первый непустой результат.

Чтобы добавить новый сайт — просто положите .yaml в agent/parsers/sites/.
Он подхватится автоматически при следующем запуске.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml  # type: ignore
    _HAS_YAML = True
except ImportError:  # pragma: no cover
    _HAS_YAML = False


SITES_DIR = Path(__file__).parent / "sites"


def _load_yaml(path: Path) -> Optional[dict]:
    if not _HAS_YAML:
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, ValueError):
        return None


def _load_json(path: Path) -> Optional[dict]:
    try:
        import json
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load_all_sites() -> List[dict]:
    """Загрузить все карты из sites/*.yaml (и *.json как fallback)."""
    out: List[dict] = []
    if not SITES_DIR.exists():
        return out
    for p in sorted(SITES_DIR.glob("*.yaml")):
        data = _load_yaml(p)
        if data:
            data["_file"] = p.name
            out.append(data)
    for p in sorted(SITES_DIR.glob("*.yml")):
        data = _load_yaml(p)
        if data:
            data["_file"] = p.name
            out.append(data)
    for p in sorted(SITES_DIR.glob("*.json")):
        data = _load_json(p)
        if data:
            data["_file"] = p.name
            out.append(data)
    # Карта 'generic' срабатывает последней (она матчит ЛЮБОЙ URL).
    # Сортируем так, чтобы она оказалась в конце списка.
    out.sort(key=lambda s: 1 if s.get("name") == "generic" else 0)
    return out


def find_site_for_url(url: str, sites: List[dict]) -> Optional[dict]:
    """Найти первую карту, у которой host_pattern матчит URL."""
    import re
    # Сначала пробуем не-generic карты (приоритет у более специфичных)
    for s in sites:
        if s.get("name") == "generic":
            continue
        for pat in s.get("host_patterns", []):
            try:
                if re.search(pat, url, re.IGNORECASE):
                    return s
            except re.error:
                continue
    # Затем — generic fallback
    for s in sites:
        if s.get("name") == "generic":
            return s
    return None


# Экспорт
__all__ = [
    "SITES_DIR",
    "load_all_sites",
    "find_site_for_url",
]
