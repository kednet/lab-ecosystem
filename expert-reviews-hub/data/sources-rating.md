# Веса источников отзывов

Используются при сведении оценок из разных источников в единый `weighted_average`.

## Таблица весов

| Источник | Вес | Почему |
|----------|-----|--------|
| **Литрес** | 1.5 | Verified покупатели, осмысленные тексты |
| **Свои** (лендинг, бот, VK) | 1.5 | Наши клиенты, максимальное доверие |
| **LiveLib** | 1.2 | Крупнейшая база книжных отзывов |
| **Author.Today** | 1.0 | Самиздат, вдумчивые рецензии |
| **Goodreads** | 1.0 | Международная база, но мало русских книг |
| **YouTube** | 0.9 | Развёрнутые обзоры, AI-анализ транскрипта |
| **VK** (группы) | 0.8 | Живое обсуждение, но часто без рейтинга |
| **Telegram** | 0.7 | Качественный контент, но коротко и мало |
| **Ozon** | 0.7 | Много накруток, фильтруем |

## Применение

```python
# При сведении
total_weighted = 0
total_weight = 0
for source in sources:
    if source.count == 0:
        continue
    total_weighted += source.avg_rating * source.weight * source.count
    total_weight += source.weight * source.count

weighted_average = total_weighted / total_weight
```

## Confidence score

`confidence` зависит от:
- **Количество источников** (1 = low, 2-3 = medium, 4+ = high)
- **Общее число отзывов** (< 50 = low, 50-500 = medium, 500+ = high)
- **Доля verified** (< 30% = low, 30-70% = medium, 70%+ = high)

```python
def calc_confidence(sources):
    n_sources = len([s for s in sources if s.count > 0])
    total = sum(s.count for s in sources)
    verified = sum(s.count for s in sources if s.verified)
    verified_ratio = verified / total if total else 0
    
    score = 0
    if n_sources >= 4: score += 1
    elif n_sources >= 2: score += 0.5
    if total >= 500: score += 1
    elif total >= 50: score += 0.5
    if verified_ratio >= 0.7: score += 1
    elif verified_ratio >= 0.3: score += 0.5
    
    if score >= 2.5: return "high"
    if score >= 1.5: return "medium"
    return "low"
```

## Trust score (0-1)

Дополнительная метрика — насколько можно доверять распределению:

```python
def trust_score(sources):
    # 1. Энтропия распределения оценок (равномернее = лучше)
    # 2. Длина текстов (длиннее = осмысленнее)
    # 3. Разброс дат (свежие отзывы = бонус)
    # 4. Доля verified
    
    if not sources: return 0
    
    # ... (упрощённо)
    base = 0.5
    if has_verified(sources): base += 0.2
    if total > 100: base += 0.2
    if has_diversity(sources): base += 0.1
    
    return min(1.0, base)
```
