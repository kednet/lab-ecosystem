"""
Slugify для audio_skill.

Делегирует в publisher_skill/scripts/slugify.py, чтобы slugify был единым
по всем скиллам (audio, publisher, seo-advisor).

Если publisher_skill недоступен — fallback на локальную транслитерацию.
"""

import sys
from pathlib import Path

# Пытаемся импортировать общий slugify
PUBLISHER_ROOT = Path(__file__).parent.parent.parent / "publisher_skill"
if PUBLISHER_ROOT.exists() and str(PUBLISHER_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PUBLISHER_ROOT / "scripts"))

try:
    from slugify import slugify_ru, slugify_en  # type: ignore
except ImportError:
    # Fallback: простая транслитерация
    import re

    _translit = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }

    def slugify_ru(text: str) -> str:
        text = text.lower()
        result = []
        for ch in text:
            if ch in _translit:
                result.append(_translit[ch])
            elif ch.isalnum():
                result.append(ch)
            elif ch in (" ", "-", "_"):
                result.append("-")
        slug = "".join(result).strip("-")
        return re.sub(r"-+", "-", slug)

    def slugify_en(text: str) -> str:
        return slugify_ru(text)


__all__ = ["slugify_ru", "slugify_en"]
