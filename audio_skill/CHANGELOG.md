# Changelog

## v0.1 — 2026-06-11 (Phase 1, каркас)

### Что сделано
- ✅ Структура `audio_skill/` (9 папок)
- ✅ `SKILL.md` — оркестратор с 7 командами
- ✅ `README.md` + `CHANGELOG.md`
- ✅ `.env.example` — Yandex Cloud, R2, LLM, publisher_skill
- ✅ `data/voices.yaml` — каталог голосов Yandex SpeechKit
- ✅ `data/backgrounds.yaml` — каталог фоновых треков
- ✅ `examples/zolotye-pravila.yaml` — **твой скрипт №1** из PDF, адаптированный
- ✅ `prompts/affirm-adapt.md` — промпт LLM-адаптера
- ✅ `scripts/pdf_parse.py` — pdfplumber → черновой YAML
- ✅ `scripts/llm_adapt.py` — LLM-адаптер (черновой → финальный YAML)
- ✅ `scripts/state.py` — идемпотентность (импорт из publisher_skill)
- ✅ `scripts/slugify.py` — общий slugify
- ✅ `commands/publish-audio.md` + `commands/adapt-pdf.md` — рецепты
- ✅ `templates/audio-page-astro.astro` — HTML5-плеер
- ✅ `templates/announcement-tg-audio.md` + `announcement-vk-audio.md`
- ✅ Smoke-test: парсер прочитал 10 скриптов из твоего PDF

### Что НЕ сделано (Phase 2)
- ❌ `scripts/tts_yandex.py` — реальный TTS-вызов
- ❌ `scripts/mix_audio.py` — ffmpeg mix
- ❌ `scripts/upload_r2.py` — R2 upload
- ❌ `scripts/render_audio.py` — Astro-страница из mp3 + meta
- ❌ `scripts/deploy_audio.py` — обёртка над publisher_skill
- ❌ `scripts/announce_audio.py` — обёртка над publisher_skill
- ❌ `/watch-audio` — фоновый режим
- ❌ `/rollback-audio` — откат
- ❌ Тесты (pytest)
