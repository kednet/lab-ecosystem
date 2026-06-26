# Video Creator Skill v0.1

Универсальный генератор коротких видео (15-90 сек) для 5 проектов экосистемы kfigh.

## Что умеет (Phase 1, MVP)

- **Генерация сценариев** для TikTok / YouTube Shorts / VK Клипы / Telegram / Instagram Reels
- **5 профилей проектов** через `data/profiles/*.yaml`:
  - `lab` — Лаборатория желаний (полный профиль)
  - `wl` — WishLibrarian
  - `coach` — WishCoach
  - `experts` — Экспертный хаб
  - `market` — Wish Market
- **Override-матрица**: CLI-флаг → profile.defaults → profile.branding
- **Идемпотентность** через `state/<profile>/<slug>.json`
- **Dry-run** для просмотра промпта без вызова LLM
- **Валидация** сценария (≥3 шота, duration±2 сек, ≥5 хештегов, CTA)
- **LLM-фабрика** через `wish_librarian/agent/ai/factory.py` (singleton)
- **Stub-fallback** если LLM-ключ отсутствует

## Быстрый старт

```bash
# 1. Проверить профили
python scripts/video.py profile list

# 2. Dry-run (посмотреть промпт)
python scripts/video.py script reels engagement soulful 30 "5 ошибок карты желаний" --profile=lab --dry-run

# 3. Сгенерировать сценарий
python scripts/video.py script reels engagement soulful 30 "5 ошибок карты желаний" --profile=lab

# 4. Проверить state
python scripts/video.py state show lab/5-oshibok-karty-zhelaniy

# 5. Валидировать
python scripts/video.py validate examples/lab-5-oshibok-karty-zhelaniy.md
```

## Что будет дальше (Phase 2-4)

| Phase | Режим | Что делает | Срок |
|---|---|---|---|
| 1 ✅ | script | Генерация сценариев | сделано |
| 2 | auto | Pexels+Pixabay+ffmpeg+TTS → mp4 | ~6-8 ч |
| 3 | manual | yt-dlp + multi-trim → highlights | ~4-6 ч |
| 4 | publish | R2 + Astro + 4 канала | отложено |

## Структура

См. `SKILL.md` (полная документация) или дерево в нём.

## Связи

- `wish_librarian/agent/ai/factory.py` — LLM
- `audio_skill/scripts/tts_yandex.py` — TTS (Phase 2)
- `publisher_skill/scripts/post_channels.py` — публикация в 4 канала (Phase 4)
- `publisher_skill/scripts/deploy_pages.py` — деплой на VPS (Phase 4)

## Планы

- `C:/Users/kfigh/.claude/plans/video-skill-universal-2026-06-17.md` — общий план v1.0 (818 строк)
- `C:/Users/kfigh/.claude/plans/swirling-singing-rivest.md` — план Phase 1 (эта сессия)

## Требует

- Python 3.10+
- `pip install pyyaml` (для профилей)
- `wish_librarian` доступен по `C:/Users/kfigh/wish_librarian` (для LLM)
- Phase 2: Pexels/Pixabay/Yandex SpeechKit ключи
- Phase 3: `pip install yt-dlp`
- Phase 4: Cloudflare R2 + 4 канала публикации
