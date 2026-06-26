# Шаблон сценария: Instagram Reels

## Использование
Шаблон-каркас для `python scripts/video.py script reels ...`. Генерирует сценарий под Instagram Reels (9:16, max **90 сек**).

## Метаданные платформы
- **aspect:** 9:16 (1080×1920)
- **max_duration:** **90 сек** (Instagram даёт 90, не 60)
- **safe_zones:** top=250, bottom=400, left=50, right=50
- **default_voice:** marina (female, playful)
- **default_music_mood:** uplifting

## Специфика Instagram Reels
- Аудитория эстетичная, любит качественный визуал
- Тон — от playful до educational
- Длительность 90 сек (длиннее TikTok/Shorts)
- **Трендовая музыка важна** (Pixabay Music в Phase 2)
- Хештеги: #reels (обязательно) + нишевые
- BGM: uplifting, трендовые жанры

## Структура каркаса
См. `templates/script-tiktok.md` (идентична), отличается:
- max_duration=90 (а не 60)
- watermark обязателен

## Пример
`examples/lab-5-oshibok-karty-zhelaniy.md` (target: Reels 30 сек)
