# Подбор ключевых слов для Pexels — Video Creator Skill v1.0 (Phase 2 STUB)

Phase 1: ЗАГЛУШКА.
Phase 2: маппинг shot.vo_text → английские keywords для поиска в Pexels Videos API.

## Алгоритм (план)
1. Для каждого shot берём `vo_text` (на русском)
2. LLM-перевод на английский + синонимы (3-5 вариантов на шот)
3. Pexels API: `GET /videos/search?query=<kw>&orientation=portrait&per_page=5`
4. Fallback на Pixabay Videos API если Pexels 429
5. Выбираем лучшее по `duration >= shot.t_end - shot.t_start` (или loop)

## Промпт для LLM
```
Переведи на английский следующие русские фразы для поиска стокового видео.
Верни JSON: [{idx, ru, en_keywords: [...3-5 вариантов]}]
```

Phase 2 — будет реализован в `scripts/fetch_clips.py`.
