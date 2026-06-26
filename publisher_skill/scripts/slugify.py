# slugify.py — общий модуль
# Используется publisher_skill, seo-advisor-skill.
# Копия / обёртка для standalone-использования.
#
# Оригинал: C:/Users/kfigh/seo-advisor-skill/scripts/slugify.py

import re
import unicodedata


def slugify(text: str, max_length: int = 80) -> str:
    """Транслитерация RU→EN, нижний регистр, дефисы.

    >>> slugify("Трансерфинг реальности")
    'transerfing-realnosti'
    """
    text = text.strip().lower()
    # Транслитерация (упрощённая, ISO 9)
    translit = {
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z',
        'и':'i','й':'i','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r',
        'с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c','ч':'ch','ш':'sh','щ':'shch',
        'ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
    }
    out = []
    for ch in text:
        if ch in translit:
            out.append(translit[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch.isspace() or ch in '-_':
            out.append('-')
        else:
            # Unicode-нормализация для остальных
            try:
                norm = unicodedata.normalize('NFKD', ch).encode('ascii', 'ignore').decode('ascii')
                out.append(norm)
            except Exception:
                pass
    s = ''.join(out)
    # Схлопнуть множественные дефисы
    s = re.sub(r'-+', '-', s).strip('-')
    return s[:max_length]


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('Usage: python slugify.py <text>')
        sys.exit(1)
    print(slugify(' '.join(sys.argv[1:])))
