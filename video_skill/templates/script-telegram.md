# Шаблон сценария: Telegram (кружочки)

## Использование
Шаблон-каркас для `python scripts/video.py script telegram ...`. Генерирует сценарий под TG-кружочки (1:1, max 60 сек).

## Метаданные платформы
- **aspect:** 1:1 (квадрат 720×720) — ОСОБЫЙ СЛУЧАЙ
- **max_duration:** 60 сек
- **safe_zones:** top=30, bottom=30, left=30, right=30 (минимальные)
- **default_voice:** ermil (male, educational)
- **default_music_mood:** silence (без BGM в кружочках)

## Специфика TG-кружочков
- **НЕТ субтитров** (только голос)
- **НЕТ BGM** (только голос)
- **НЕТ safe-zones** для UI (минимальные)
- Видео квадратное 1:1
- Длительность 60 сек
- Хештеги **НЕ работают** (опускаются)

## Структура каркаса
См. `templates/script-tiktok.md`, но:
- aspect=1:1
- subtitles=off
- bgm=off
- hashtags_base пустой (или только брендовые)

## Phase 2
- ffmpeg scale до 720×720
- audio: только voiceover, без amix

## Пример
TBD
