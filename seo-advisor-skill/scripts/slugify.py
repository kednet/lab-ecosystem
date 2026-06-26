"""Генерация URL-slug из заголовка.

Правила:
- Транслитерация кириллицы в латиницу (ГОСТ 7.79 + ISO 9 — упрощённо)
- В нижний регистр
- Замена пробелов и спецсимволов на дефис
- Удаление стоп-слов (и, в, на, по, the, a, of)
- Длина 3-60 символов
- Только [a-z0-9-]
- Без повторяющихся дефисов
- Без дефисов в начале/конце

Использование:
  python slugify.py "Трансерфинг реальности — Вадим Зеланд"
  → transerfing-realnosti-vadim-zeland
"""

import re
import sys

# Карта транслитерации (базовая, без ё→yo, ъ→'')
TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}

# Стоп-слова (удаляются)
STOP_WORDS_RU = {
    'и', 'в', 'на', 'по', 'с', 'со', 'о', 'об', 'от', 'до', 'из', 'за',
    'для', 'как', 'что', 'это', 'эта', 'этот', 'эти', 'тот', 'та', 'те',
    'или', 'но', 'а', 'же', 'бы', 'ли', 'ни', 'так', 'его', 'её', 'их',
    'к', 'у', 'над', 'под', 'при', 'без', 'через', 'между', 'перед',
    'все', 'всё', 'всех', 'наш', 'ваш', 'свой', 'мой', 'твой', 'ещё',
    'уже', 'только', 'даже', 'потом', 'теперь', 'когда', 'если', 'чтобы',
    'кто', 'где', 'куда', 'откуда', 'зачем', 'почему', 'сколько', 'какой',
}

STOP_WORDS_EN = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'be', 'been',
    'this', 'that', 'these', 'those', 'it', 'its',
}


def slugify(text: str, max_length: int = 60) -> str:
    """Превращает заголовок в URL-slug."""
    if not text:
        return ''

    # 1. В нижний регистр
    text = text.lower().strip()

    # 2. Транслитерация кириллицы
    result = []
    for char in text:
        result.append(TRANSLIT.get(char, char))
    text = ''.join(result)

    # 3. Заменяем все не-alphanumeric на пробел
    text = re.sub(r'[^a-z0-9]+', ' ', text)

    # 4. Удаляем стоп-слова
    words = [w for w in text.split() if w and w not in STOP_WORDS_RU and w not in STOP_WORDS_EN]

    # 5. Соединяем через дефис
    slug = '-'.join(words)

    # 6. Обрезаем до max_length по границе слова
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit('-', 1)[0]

    # 7. Чистка
    slug = re.sub(r'-+', '-', slug).strip('-')

    return slug


def variants(text: str, n: int = 5) -> list[str]:
    """Генерирует N вариантов slug (без стоп-слов / со стоп-словами / короткий / длинный)."""
    base = slugify(text, max_length=60)
    variants_list = [base]

    # Без длинного хвоста (первые 3 слова)
    words = base.split('-')
    if len(words) > 3:
        variants_list.append('-'.join(words[:3]))

    # С минимальной обрезкой
    if len(words) > 2:
        variants_list.append('-'.join(words[:4]))

    # Только уникальные и непустые
    seen = set()
    final = []
    for v in variants_list:
        if v and v not in seen:
            seen.add(v)
            final.append(v)

    return final[:n]


if __name__ == '__main__':
    # Windows cp1252 не выводит кириллицу — переключаем на utf-8
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass

    if len(sys.argv) < 2:
        print('Использование: python slugify.py "Заголовок страницы"')
        print('Пример: python slugify.py "Трансерфинг реальности — Вадим Зеланд"')
        sys.exit(1)

    text = ' '.join(sys.argv[1:])
    print(f'Заголовок: {text}')
    print(f'Основной slug: {slugify(text)}')
    print()
    print('Варианты:')
    for i, v in enumerate(variants(text), 1):
        print(f'  {i}. /{v}/')
