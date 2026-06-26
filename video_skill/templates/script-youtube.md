# Шаблон сценария: YouTube Shorts

## Использование
Шаблон-каркас для `python scripts/video.py script youtube ...`. Генерирует сценарий под YouTube Shorts (9:16, max 60 сек, educational).

## Метаданные платформы
- **aspect:** 9:16 (1080×1920)
- **max_duration:** 60 сек
- **safe_zones:** top=200, bottom=350, left=50, right=50
- **default_voice:** ermil (educational)
- **default_music_mood:** ambient

## Специфика YouTube Shorts
- Тон — **объясняйки/уроки**, не панчи
- Структура: hook (0-3 сек) → контекст → ключевая мысль → пример → CTA
- Хештеги: #shorts (обязательно) + #тема
- BGM: ambient, не отвлекает от голоса
- Финал — призыв подписаться (для goal=subscribe)

## Структура каркаса
См. `templates/script-tiktok.md` (идентична), отличается только метаданными платформы.

## Пример
TBD
