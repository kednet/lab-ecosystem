# Changelog — Video Creator Skill

## v0.1 (2026-06-17) — Phase 1 (MVP)

**Первая рабочая версия. C-режим (генерация сценариев).**

### Реализовано
- ✅ Структура папок (~57 файлов, 16 директорий)
- ✅ 5 профилей в `data/profiles/` (lab полный, 4 заглушки)
- ✅ `data/platforms.yaml` — параметры 5 платформ (aspect, safe_zones)
- ✅ `data/voice_map.yaml` — маппинг 10 тонов → голоса Yandex
- ✅ `scripts/video.py` — orchestrator с argparse (7 sub-команд)
- ✅ `scripts/cmd_script.py` — C-режим (resolve_params, build_prompt, render_markdown)
- ✅ `scripts/cmd_profile.py` — list/show/validate профилей (NEW v1.0)
- ✅ `scripts/cmd_{auto,manual,publish}.py` — стабы для Phase 2/3/4
- ✅ `scripts/state.py` — идемпотентность (path: `state/<profile>/<slug>.json`)
- ✅ `scripts/slugify.py` — копия publisher_skill
- ✅ `scripts/llm_factory.py` — обёртка над wish_librarian/agent/ai/factory (lazy import + fallback)
- ✅ `scripts/validate_script.py` — валидация сценария
- ✅ `scripts/_video_common.py` — load_env, paths, now_iso, MITM bypass
- ✅ Override-матрица в `cmd_script.py:resolve_params()`
- ✅ `prompts/script-generate.md` — документация LLM-промпта
- ✅ `prompts/profile-context.md` — NEW v1.0: инъекция профиля в промпт
- ✅ `sub-skills/profile-system.md` — NEW v1.0: override-матрица
- ✅ `sub-skills/script-mode.md` — C-режим детально
- ✅ `templates/script-{tiktok,youtube,vk,telegram,reels}.md` — 5 шаблонов
- ✅ `examples/lab-5-oshibok-karty-zhelaniy.md` — ПОЛНЫЙ эталон (30 сек, 6 шотов)
- ✅ 4 заглушки examples
- ✅ SKILL.md, README.md (этот CHANGELOG)
- ✅ 5 commands (script, profile, auto/manual/publish stubs)
- ✅ Verification V1.1–V1.11 (end-to-end checklist)

### Не реализовано (следующие фазы)
- ❌ Phase 2: A-режим (Pexels+Pixabay+ffmpeg+TTS → mp4) — стабы cmd_auto.py
- ❌ Phase 3: B-режим (yt-dlp + нарезка) — стабы cmd_manual.py
- ❌ Phase 4: публикация (R2 + Astro + 4 канала) — стабы cmd_publish.py
- ❌ Промпты clip-keywords.md, announce-text.md — стабы
- ❌ data/bgm_catalog.yaml, data/presets/9x16-h264.json — пустые
- ❌ ffmpeg-pipeline.md, auto-mode.md, manual-mode.md, publish-flow.md — стабы
- ❌ references/*.md — пустые

### Известные баги / особенности
- LLM-вызов использует singleton из WL (`get_ai_client(use_cache=True)`). Если WL-импорт падает → stub.
- YAML-парсинг в `cmd_profile.py` использует `yaml.safe_load` (требует `pyyaml` — есть в pip по умолчанию).
- Валидация читает JSON из frontmatter, fallback на regex `\`\`\`json ... \`\`\``.

### Следующая версия
**v0.2 — Phase 2 (A-режим).** Требует от kfigh: PEXELS_API_KEY, PIXABAY_API_KEY, YANDEX_SPEECHKIT_API_KEY.
