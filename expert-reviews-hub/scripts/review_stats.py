"""
Review stats — расчёт взвешенной средней и confidence по bundle
Использование:
  python review_stats.py reviews/transerfing-realnosti/
  python review_stats.py reviews/transerfing-realnosti/ --json
Вход: папка с файлами {source}.json
Выход: summary.json + печать статистики
"""
import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict


# === UTF-8 fix for Windows ===
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


# === Веса источников (синхронизировано с data/sources-rating.md) ===
SOURCE_WEIGHTS = {
    'litres': 1.5,
    'own': 1.5,
    'livelib': 1.2,
    'author_today': 1.0,
    'goodreads': 1.0,
    'youtube': 0.9,
    'vk': 0.8,
    'telegram': 0.7,
    'ozon': 0.7,
}


def load_sources(input_dir):
    """Загрузить все .json файлы из папки (кроме summary.json)."""
    sources = []
    p = Path(input_dir)
    for f in sorted(p.glob('*.json')):
        if f.name in ('summary.json', 'bundle.json'):
            continue
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            data['_file'] = f.name
            data['_source_name'] = f.stem  # livelib, litres, ozon, social, own
            sources.append(data)
        except Exception as e:
            print(f"  ! Skip {f.name}: {e}", file=sys.stderr)
    return sources


def calc_weighted_average(sources):
    """Σ(rating × weight × count) / Σ(weight × count)"""
    total_weighted = 0.0
    total_weight = 0.0
    per_source = []

    for s in sources:
        rating = s.get('rating', {}).get('average')
        count = s.get('rating', {}).get('count', 0)
        source_name = s.get('source', s.get('_source_name', 'unknown'))
        weight = SOURCE_WEIGHTS.get(source_name, 1.0)

        if not rating or not count:
            continue

        # Если source-файл имеет weight (например own.json, social.json)
        if 'weight' in s and isinstance(s['weight'], (int, float)):
            weight = s['weight']

        contribution = rating * weight * count
        total_weighted += contribution
        total_weight += weight * count

        per_source.append({
            'source': source_name,
            'count': count,
            'avg': rating,
            'weight': weight,
            'contribution_pct': round(contribution / 1, 2),  # заполним позже
        })

    if total_weight == 0:
        return 0, per_source

    weighted_avg = total_weighted / total_weight

    # Пересчитать contribution_pct
    for ps in per_source:
        ps['contribution_pct'] = round(ps['avg'] * ps['weight'] * ps['count'] / total_weighted * 100, 1)

    return round(weighted_avg, 2), per_source


def calc_confidence(sources):
    """high | medium | low на основе количества источников, отзывов и verified."""
    n_sources = sum(1 for s in sources
                    if s.get('rating', {}).get('count', 0) > 0)
    total = sum(s.get('rating', {}).get('count', 0) for s in sources)
    verified = 0
    for s in sources:
        sn = s.get('source', s.get('_source_name', ''))
        if sn in ('litres', 'own'):  # эти — always verified
            verified += s.get('rating', {}).get('count', 0)
        elif 'verified_ratio' in s:
            verified += int(s.get('rating', {}).get('count', 0) * s.get('verified_ratio', 0))

    verified_ratio = verified / total if total else 0

    score = 0.0
    if n_sources >= 4: score += 1.0
    elif n_sources >= 2: score += 0.5

    if total >= 500: score += 1.0
    elif total >= 50: score += 0.5

    if verified_ratio >= 0.7: score += 1.0
    elif verified_ratio >= 0.3: score += 0.5

    if score >= 2.5: return 'high', score
    if score >= 1.5: return 'medium', score
    return 'low', score


def trust_score(sources):
    """0-1: доверие к распределению."""
    if not sources: return 0.0

    score = 0.5  # базовый

    # Бонус за наличие verified источников
    has_verified = any(s.get('source') in ('litres', 'own') for s in sources)
    if has_verified:
        score += 0.2

    # Бонус за большой объём
    total = sum(s.get('rating', {}).get('count', 0) for s in sources)
    if total > 100:
        score += 0.2
    elif total > 50:
        score += 0.1

    # Бонус за разнообразие источников
    n = sum(1 for s in sources if s.get('rating', {}).get('count', 0) > 0)
    if n >= 3:
        score += 0.1

    return min(1.0, round(score, 2))


def distribution(ratings):
    """5/4/3/2/1 — распределение по отзывам (если есть)."""
    counter = Counter()
    for s in ratings:
        for rev in s.get('reviews', []):
            r = rev.get('rating')
            if r and 1 <= r <= 5:
                counter[r] += 1
    return dict(counter)


def trends(sources):
    """Тренды по году (если в отзывах есть date)."""
    by_year = defaultdict(lambda: {'count': 0, 'sum_rating': 0})
    for s in sources:
        for rev in s.get('reviews', []):
            date = rev.get('date', '')
            year_m = str(date)[:4] if date else None
            r = rev.get('rating')
            if year_m and year_m.isdigit() and r:
                by_year[year_m]['count'] += 1
                by_year[year_m]['sum_rating'] += r

    result = []
    for year in sorted(by_year):
        d = by_year[year]
        if d['count'] > 0:
            result.append({
                'period': year,
                'count': d['count'],
                'avg_rating': round(d['sum_rating'] / d['count'], 2)
            })
    return result


def main():
    p = argparse.ArgumentParser(description='Review stats: weighted average + confidence')
    p.add_argument('input_dir', help='Папка с {source}.json файлами')
    p.add_argument('--json', action='store_true', help='Только JSON-вывод')
    args = p.parse_args()

    sources = load_sources(args.input_dir)
    if not sources:
        print("Нет источников в указанной папке", file=sys.stderr)
        sys.exit(1)

    # Извлечь инфо о книге из первого источника
    book_meta = {}
    for s in sources:
        if 'book' in s and s['book']:
            book_meta = s['book']
            break

    # Расчёты
    weighted_avg, per_source = calc_weighted_average(sources)
    confidence, conf_score = calc_confidence(sources)
    trust = trust_score(sources)
    dist = distribution(sources)
    trends_data = trends(sources)

    # Тональность (если есть)
    sentiment = {'positive': 0, 'neutral': 0, 'negative': 0, 'mixed': 0}
    for s in sources:
        for rev in s.get('reviews', []):
            tone = rev.get('tone')
            if tone in sentiment:
                sentiment[tone] += 1

    total_reviews = sum(s.get('rating', {}).get('count', 0) for s in sources)

    # Сводный отчёт
    summary = {
        'book': book_meta,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'total_reviews': total_reviews,
        'sources_count': len(per_source),
        'weighted_average': weighted_avg,
        'confidence': confidence,
        'confidence_score': conf_score,
        'trust_score': trust,
        'sources_breakdown': per_source,
        'rating_distribution': dist,
        'sentiment_distribution': sentiment,
        'trends': trends_data,
        'verdict': None  # заполняется AI-суммаризацией отдельно
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        # Человекочитаемый вывод
        print()
        print("=" * 60)
        title = book_meta.get('title', args.input_dir)
        author = book_meta.get('author', '')
        print(f"  Анализ отзывов: {title}" + (f" — {author}" if author else ''))
        print("=" * 60)
        print()
        print(f"  Взвешенная средняя:  ⭐ {weighted_avg}/5")
        print(f"  Всего отзывов:       {total_reviews} в {len(per_source)} источниках")
        print(f"  Уровень доверия:     {confidence.upper()} (score={conf_score})")
        print(f"  Trust score:         {trust}")
        print()
        print("  Распределение по источникам:")
        print(f"  {'Источник':<20} {'Отзывов':>8} {'⭐':>5} {'Вес':>5} {'Вклад':>8}")
        print("  " + "-" * 50)
        for ps in per_source:
            print(f"  {ps['source']:<20} {ps['count']:>8} {ps['avg']:>5} {ps['weight']:>5} {ps['contribution_pct']:>7}%")
        print()
        if dist:
            print(f"  Распределение оценок: {dict(sorted(dist.items(), reverse=True))}")
        if trends_data:
            print()
            print("  Тренды по годам:")
            for t in trends_data:
                print(f"    {t['period']}: {t['count']} отзывов, ⭐{t['avg_rating']}")
        print()
        print("=" * 60)

    # Сохранить
    out_path = Path(args.input_dir) / 'summary.json'
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    if not args.json:
        print(f"\n  Сохранено: {out_path}")


if __name__ == '__main__':
    main()
