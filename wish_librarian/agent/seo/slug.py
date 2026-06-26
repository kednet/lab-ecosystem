"""
Slug-генератор — портировано из C:/Users/kfigh/seo-advisor-skill/scripts/slugify.py
с минимальными правками для работы без зависимостей (только re).
"""
from __future__ import annotations

import re
from typing import List


# Транслитерация (ГОСТ 7.79 упрощённо)
_TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}

# Стоп-слова (удаляются из slug)
_STOP_WORDS_RU = frozenset({
    'и', 'в', 'на', 'по', 'с', 'со', 'о', 'об', 'от', 'до', 'из', 'за',
    'для', 'же', 'бы', 'ли', 'ни', 'так', 'его', 'её', 'их',
    'к', 'у', 'над', 'под', 'при', 'без', 'через', 'между', 'перед',
    'наш', 'ваш', 'свой', 'мой', 'твой', 'ещё',
    'уже', 'только', 'даже', 'потом', 'теперь',
    'это', 'эта', 'этот', 'эти', 'тот', 'та', 'те',
    'или', 'но', 'а',
})

_STOP_WORDS_EN = frozenset({
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'be', 'been',
    'this', 'that', 'these', 'those', 'it', 'its',
})


def slugify(text: str, max_length: int = 60) -> str:
    """
    Превращает заголовок в URL-slug.
    - Транслитерация кириллицы
    - Удаление стоп-слов (кроме смыслообразующих: как, не, без, с)
    - Длина до max_length по границе слова
    """
    if not text:
        return ''

    # 1. Lowercase
    text = text.lower().strip()

    # 2. Транслитерация
    result = []
    for char in text:
        result.append(_TRANSLIT.get(char, char))
    text = ''.join(result)

    # 3. Заменяем всё не-alphanumeric на пробел
    text = re.sub(r'[^a-z0-9]+', ' ', text)

    # 4. Удаляем стоп-слова
    words = [w for w in text.split() if w and w not in _STOP_WORDS_RU and w not in _STOP_WORDS_EN]

    # 5. Если получилось < 1 слова — fallback: только транслит, без удаления
    if not words:
        words = [w for w in re.sub(r'[^a-z0-9]+', ' ', text).split() if w]

    # 6. Соединяем через дефис
    slug = '-'.join(words)

    # 7. Обрезаем по границе слова
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit('-', 1)[0]

    # 8. Чистка дефисов
    slug = re.sub(r'-+', '-', slug).strip('-')

    return slug


def make_canonical_url(slug: str, base: str = "https://lab.com", path_prefix: str = "/library/") -> str:
    """Сгенерировать canonical URL по slug."""
    if not slug:
        return base
    return f"{base.rstrip('/')}{path_prefix}{slug}/"
