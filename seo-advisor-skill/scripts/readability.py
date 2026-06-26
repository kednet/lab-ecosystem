"""Подсчёт слов, знаков, воды и приближённый Flesch-Kincaid для русского текста.

Использование:
  python readability.py file.txt
  python readability.py
  (затем ввести текст, конец = EOF / Ctrl+Z)
"""

import re
import sys
from pathlib import Path


# Список "водяных" слов (высокочастотные служебные + канцелярит)
STOP_LIKE_WATER = {
    'и', 'в', 'на', 'по', 'с', 'со', 'о', 'об', 'от', 'до', 'из', 'за',
    'для', 'как', 'что', 'это', 'эта', 'этот', 'эти', 'тот', 'та', 'те',
    'или', 'но', 'а', 'же', 'бы', 'ли', 'ни', 'так', 'его', 'её', 'их',
    'к', 'у', 'над', 'под', 'при', 'без', 'через', 'между', 'перед',
    'все', 'всё', 'всех', 'наш', 'ваш', 'свой', 'мой', 'твой', 'ещё',
    'уже', 'только', 'даже', 'потом', 'теперь', 'когда', 'если', 'чтобы',
    'кто', 'где', 'куда', 'откуда', 'зачем', 'почему', 'сколько', 'какой',
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'be', 'been',
    'это', 'также', 'кроме', 'однако', 'поэтому', 'более', 'менее',
    'является', 'являются', 'который', 'которая', 'которые', 'которых',
    'данный', 'данная', 'данные', 'следует', 'необходимо', 'нужно',
    'возможно', 'вероятно', 'наверное', 'кажется', 'стоит', 'может',
    'могут', 'мог', 'могла', 'могли', 'можно', 'нужен', 'нужна', 'нужно',
    'какой-то', 'какая-то', 'какое-то', 'какие-то',
}

# Сложные слова (3+ слогов) — для Flesch-Kincaid
VOWELS = 'аеёиоуыэюя'


def count_syllables_ru(word: str) -> int:
    """Грубый подсчёт слогов для русского слова (по гласным)."""
    word = re.sub(r'[^а-яё]', '', word.lower())
    if not word:
        return 0
    count = sum(1 for c in word if c in VOWELS)
    # Минимум 1 слог
    return max(1, count)


def split_sentences(text: str) -> list[str]:
    """Разделяет на предложения по .!? с учётом сокращений."""
    # Убираем переносы строк
    text = text.replace('\n', ' ').replace('\r', ' ')
    # Сплит по знакам препинания, оставляя знаки
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def water_score(text: str) -> dict:
    """Оценка воды: доля служебных / стоп-слов в тексте."""
    words = re.findall(r'[а-яёa-z]+', text.lower())
    if not words:
        return {'water_pct': 0, 'water_words': 0, 'total_words': 0}

    water = sum(1 for w in words if w in STOP_LIKE_WATER)
    return {
        'water_pct': round(water / len(words) * 100, 1),
        'water_words': water,
        'total_words': len(words),
    }


def flesch_kincaid_grade(text: str) -> dict:
    """Flesch-Kincaid Grade Level (адаптировано для русского).

    Формула: 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59
    """
    sentences = split_sentences(text)
    words = re.findall(r'[а-яёa-z]+', text.lower())

    if not sentences or not words:
        return {'grade': 0, 'words_per_sentence': 0, 'syllables_per_word': 0}

    syllables = sum(count_syllables_ru(w) for w in words)
    wps = len(words) / len(sentences)
    spw = syllables / len(words)
    grade = 0.39 * wps + 11.8 * spw - 15.59

    return {
        'grade': round(grade, 1),
        'words_per_sentence': round(wps, 1),
        'syllables_per_word': round(spw, 2),
    }


def readability_level(grade: float) -> str:
    """Интерпретация Grade Level для русского.

    NB: классическая формула Flesch-Kincaid заточена под английский.
    Для русского оценки завышены на ~3-5 grade level. Используй как
    относительную метрику (до/после правок), а не абсолютную.
    """
    if grade < 5:
        return '🟢 Очень просто (начальная школа) — отлично для лендингов'
    elif grade < 8:
        return '🟢 Просто (средняя школа) — идеально для блога и контент-маркетинга'
    elif grade < 12:
        return '🟡 Средне (старшая школа) — допустимо для экспертного контента'
    elif grade < 15:
        return '🟠 Сложно (вуз) — профессиональная литература'
    else:
        return '🔴 Очень сложно — научпоп / академический текст (для русского — нормально 10-14)'


def analyze(text: str) -> dict:
    """Полный анализ читаемости."""
    chars_total = len(text)
    chars_no_spaces = len(re.sub(r'\s', '', text))
    words = re.findall(r'[а-яёa-z]+', text.lower())
    sentences = split_sentences(text)

    return {
        'chars_total': chars_total,
        'chars_no_spaces': chars_no_spaces,
        'words': len(words),
        'sentences': len(sentences),
        'avg_sentence_len': round(len(words) / max(1, len(sentences)), 1),
        'fk_grade': flesch_kincaid_grade(text),
        'water': water_score(text),
    }


def print_report(text: str) -> None:
    """Печатает читаемый отчёт."""
    result = analyze(text)

    print('=' * 60)
    print('📊 АНАЛИЗ ЧИТАЕМОСТИ')
    print('=' * 60)
    print()
    print(f'Символов (с пробелами):    {result["chars_total"]:,}')
    print(f'Символов (без пробелов):   {result["chars_no_spaces"]:,}')
    print(f'Слов:                      {result["words"]:,}')
    print(f'Предложений:               {result["sentences"]:,}')
    print(f'Средняя длина предложения: {result["avg_sentence_len"]} слов')
    print()
    print(f'Flesch-Kincaid Grade:      {result["fk_grade"]["grade"]}')
    print(f'  - Слов в предложении:    {result["fk_grade"]["words_per_sentence"]}')
    print(f'  - Слогов в слове:        {result["fk_grade"]["syllables_per_word"]}')
    print(f'  - Уровень:               {readability_level(result["fk_grade"]["grade"])}')
    print()
    water_pct = result['water']['water_pct']
    water_emoji = '🟢' if water_pct < 35 else '🟡' if water_pct < 50 else '🔴'
    print(f'Вода (стоп-слова):         {water_pct}% ({result["water"]["water_words"]} из {result["water"]["total_words"]}) {water_emoji}')
    if water_pct >= 50:
        print('  ⚠️ Высокая вода! Замените канцеляризмы на живые глаголы.')
    print()
    print('=' * 60)
    print('💡 РЕКОМЕНДАЦИИ')
    print('=' * 60)

    if result['fk_grade']['grade'] > 12:
        print('• Упростите предложения (дробьте на 2-3 коротких)')
    if result['avg_sentence_len'] > 25:
        print(f'• Среднее предложение {result["avg_sentence_len"]} слов — сократите до 12-20')
    if water_pct > 45:
        print(f'• Уберите {water_pct - 30:.0f}% стоп-слов — замените на существительные/глаголы')
    if result['words'] < 300:
        print(f'• Текст короткий ({result["words"]} слов) — для блога нужно 800+, для конспекта 1500+')
    if result['words'] > 3000 and result['fk_grade']['grade'] > 10:
        print('• Длинный + сложный текст — добавьте подзаголовки H2/H3, списки, таблицы')

    print()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            print(f'Файл не найден: {path}')
            sys.exit(1)
        text = path.read_text(encoding='utf-8')
    else:
        print('Введите текст (Ctrl+Z = конец):')
        text = sys.stdin.read()

    if not text.strip():
        print('Текст пустой.')
        sys.exit(1)

    print_report(text)
