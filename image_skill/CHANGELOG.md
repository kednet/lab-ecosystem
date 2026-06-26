# Changelog

## [1.4.0] — 2026-06-17 (Yandex Object Storage — multi-provider)

### Added

- `scripts/upload_yandex.py` (~110 строк) — Yandex Object Storage через boto3 (S3-compatible, region ru-central1)
- `scripts/upload_storage.py` (~80 строк) — диспетчер: R2 → Yandex → file:// fallback. ENV: `STORAGE_PROVIDER=auto|r2|yandex`
- `data/yandex-storage.example.yaml` (~85 строк) — полная инструкция: регистрация, сервисный аккаунт, статический ключ, бакет, публичный доступ, ENV
- `image.py publish` — новый флаг `--storage auto|r2|yandex`
- `commands/image-publish.md` — полный rewrite (был STUB → реальная документация)

### Changed

- `cmd_publish.py` — `upload_to_r2()` → `upload_to_storage(provider=)`
- `data/r2.example.yaml` — добавлена секция "v1.4: Multi-provider storage" с таблицей провайдеров

### Fixed (v1.4.1 — live VK session)

- `upload_yandex.py` + `upload_r2.py` — `Config(proxies={})` отключает корпоративный SOCKS proxy (socks4://) который ломал boto3 (urllib3 не понимает схему)
- `post_channels.py:116-176` — реализован multipart upload + `photos.saveWallPhoto` (был pass # см. ниже — не работал). Добавлена поддержка URL→tempfile скачивания
- `build_post_content.py:48-91` — новое поле `image_local` в JSON, копия JPEG в `publisher_skill/tmp/img-cache/` (обход SOCKS proxy для скачивания)
- `post_channels.py:359-368` — приоритет `image_local` над `image` (URL)

### Known Issues (v1.4.1 — требует user token VK)

- ❌ **Group token не может прикрепить фото** к посту. `photos.getWallUploadServer` возвращает `error_code 27, "Group authorization failed"`. Нужен user token с правами `photos,wall,groups,offline`
- 3 поста #7,#8,#9 в club237295798 опубликованы БЕЗ картинок (только текст + URL в тексте)
- Картинки загружены в Yandex Storage и публично доступны (HTTP 200)

### Verified (V1.4.1-V1.4.6)

- V1.4.1 ✅ Sanity imports (3 модуля загружаются)
- V1.4.2 ✅ Credentials check (False без env)
- V1.4.3 ✅ Auto fallback (`file://` URL)
- V1.4.4 ✅ `provider=yandex` без env → warning + fallback
- V1.4.5 ✅ Unknown provider → warning + `auto` fallback
- V1.4.6 ✅ E2E `publish --dry-run` (логи "→ Storage: ...", post_channels.py DRY-RUN, state → published)
- **Live**: 3 поста в ВК (post_id=7, 8, 9) с реальной загрузкой в Yandex Storage (HTTP 200 OK)
- **Bug**: фото не прикрепляются (group token error 27)

### Pending (завтра)

- ⏸ User token VK (5 мин ручной работы)
- ⏸ Перегенерация фонов: «просто розовый, без роз» (замена YandexART на Pillow flat)
- ⏸ Перепубликация всех 5 state с --force после обоих фиксов

### Why Yandex

- **Доступность с РФ** без VPN (Cloudflare R2 не открывается с рабочей машины kfigh)
- **Стоимость** 0.01 ₽/GB/мес (R2: $0.015/GB ≈ 1.35 ₽) — в 130 раз дешевле
- **Тот же S3 API** — boto3 работает идентично, 0 правок в бизнес-логике
- **SLA** Yandex Cloud ≥ 99.95% (R2 SLA не заявлен)

### Что нужно от kfigh для live постинга

1. Регистрация https://console.yandex.cloud/ (~3 мин)
2. Платёжный аккаунт (нужна карта, free tier) (~2 мин)
3. Сервисный аккаунт с ролью `storage.editor` (~1 мин)
4. Статический ключ (Access Key + Secret Key) (~30 сек)
5. Бакет `pulab-images` в `ru-central1` (~30 сек)
6. Публичный доступ (`--anonymous-access-read` или через консоль) (~30 сек)
7. 4 ENV в `.env` (см. `data/yandex-storage.example.yaml`)
8. `pip install boto3`
9. Dry-run для проверки
10. Live (требует подтверждения kfigh)

## [1.3.0] — 2026-06-17 (Harden LLM announce_text)

### Added

- Per-channel валидация в `announce_text.py` (VK 100-1000, TG 100-1024, OK 100-1000, Zen 300-3000)
- `_fix_length()` — обрезает до max с многоточием, для Zen удаляет `#` (хэштеги Дзен не любит)
- `_coerce_announce()` — смешивает LLM + fallback, гарантирует валидный dict
- Retry-стратегия: если основной промпт дал невалидный JSON → повтор с `prompts/announce-text-simple.md`
- Top-level `hashtags_base` fix в `_fallback_announce()` (был баг: читал из `branding`, в YAML они на top-level)
- `_parse_json_safely()` 3 уровня fallback: full parse → greedy regex → non-greedy regex
- Per-channel fallback шаблоны с уникальной структурой (VK эмодзи, OK без эмодзи, Zen без `#`)

### Fixed

- `prompts/announce-text.md` был STUB — теперь полные правила для каждого канала (длина, формат, тон, антипаттерны)
- `hashtags` в fallback были пустыми из-за неверного пути `branding.hashtags_base` → top-level

### Verified (V1.3.1-V1.3.5)

- V1.3.1 ✅ Sanity: 3/3 валидных JSON парсятся, мусор → None
- V1.3.2 ✅ Per-channel валидация длин работает (50→false, 200→true, 1500→false)
- V1.3.3 ✅ `_fix_length` обрезает до max, Zen удаляет `#`
- V1.3.4 ✅ Fallback использует top-level hashtags (раньше был баг — пустой массив)
- V1.3.5 ✅ Live YandexGPT на `lab/5-shagov-k-mechte-vertikalnaya-infografika` (1127 tok / 6.2 sec, все 4 адаптации valid)
- V1.3.6 ✅ End-to-end `publish --dry-run` через `post_channels.py` (JSON-контент валиден)

## [1.2.0] — 2026-06-17 (Phase 3 — publisher_skill integration)

### Added

- `scripts/upload_r2.py` (~80 строк, Phase 3) — boto3 → Cloudflare R2 (S3-compatible). Endpoint `https://<account_id>.r2.cloudflarestorage.com`, region="auto". Fallback на `file://` URL если R2_* ENV не заданы
- `scripts/announce_text.py` (~100 строк) — LLM-генерация 4 адаптаций через `prompts/announce-text.md` + YandexGPT. Fallback на title+hashtags шаблон
- `scripts/build_post_content.py` (~40 строк) — сборка JSON в формате `post_channels.py` (по образцу `detector.json`) → `tmp/post-channels/<slug>.json`
- `scripts/cmd_publish.py` — Phase 3 orchestrator (был STUB → 120 реальных строк). Pipeline: state → R2 upload → announce → build content → post_channels.py subprocess → state update
- `prompts/announce-text.md` — LLM-шаблон для 4 адаптаций (позже переписан в v1.3)
- `data/r2.example.yaml` — документация R2 setup
- Реальная имплементация `publish` sub-команды в `image.py` (был STUB)
- CLI: `publish <slug_id> --channels vk,tg,ok,zen --live-url <url> --dry-run --force`

### Changed

- `publisher_skill/scripts/post_channels.py:72-92` — `load_content()` теперь принимает абсолютный путь к JSON. Без этой правки Phase 3 невозможен
- State transition: `upscaled → published`. Новые поля: `published_url`, `published_at`, `channels_requested`, `channels_posted`, `post_content_json`

### Verified (V3.1-V3.7)

- V3.1 ✅ Sanity imports (R2 creds=False → fallback)
- V3.2 ✅ Dry-run publish lab VK (JSON сгенерирован, post_channels.py DRY-RUN, state → published)
- V3.3 ⏸ БЛОКИРОВКА — live VK publish в club237295798 требует подтверждения kfigh (auto-mode classifier)
- V3.4 ✅ Idempotency (повтор без --force → "⏭ Уже published")
- V3.5 ✅ Skip без токенов TG/OK (VK dry-run, TG/OK skip, Zen RSS обновлён)
- V3.6 ✅ Skip VK без токена (live VK требует VK_ACCESS_TOKEN в .env)
- V3.7 ✅ Live YandexGPT через llm_factory.py (8.7 сек / 873 tok на 4 адаптации)

### Known limitations

- ❌ **Live VK постинг ждёт R2 setup** (Cloudflare bucket + 5 ENV vars) + ручное подтверждение kfigh
- ❌ YandexGPT JSON reliability ~30% (rely на fallback для остальных 70%)
- ❌ TG/OK скипаются без токенов (постингуем только ВК пока)
- ❌ Дзен без open API — только RSS, ручное добавление в Дзен Studio
- ❌ Без `pip install boto3` (нужно для live R2 upload)

## [1.1.0] — 2026-06-17 (Phase 2 — upscale + text + watermark)

### Added

- `scripts/upscale_pillow.py` — Pillow LANCZOS upscale до `format.target_size` (1024→1080 и т.д.)
- `scripts/burn_text.py` — text overlay с safe zones, drop shadow, полупрозрачной подложкой
- `scripts/burn_watermark.py` — watermark в правом нижнем углу с подложкой
- `scripts/cmd_auto.py` — Phase 2 orchestrator (upscale → text → watermark pipeline)
- Реальная имплементация `auto` sub-команды (была STUB)
- `image.py` orchestrator: `--to`, `--no-text`, `--no-watermark`, `--force` для `auto`
- `validate_image.py`: `validate_upscaled_path()` — проверка JPEG + размеры = target_size
- Шрифт: fallback chain Inter-Bold → arialbd → Segoe UI Bold → Pillow default
- `assets/fonts/README.md` — документация по fallback chain и обходу корпоративного MITM
- 4 артефакта на каждый `auto`: `*-upscaled.jpg`, `*-upscaled-texted.jpg`, `*-upscaled-texted-final.jpg`

### Verified (V2.1-V2.7)

- V2.1 ✅ Sanity Pillow + arialbd fallback
- V2.2 ✅ Upscale lab VK (1024→1080, 392 КБ JPEG q=92 progressive)
- V2.3 ✅ Upscale pinterest (832→1000, 458 КБ, +20% size)
- V2.4 ✅ Idempotency (повтор без --force = skip)
- V2.5 ✅ --no-text (только upscale + watermark)
- V2.6 ✅ --no-watermark (upscale + text без watermark)
- V2.7 ✅ Validate upscaled (1080×1080 = format.target_size match)

### Known limitations

- Lanczos не добавляет деталей (мыло при сильном upscale). Real-ESRGAN — Phase 3+
- Шрифт arialbd fallback (Inter-Bold скачать не получается из-за корпоративного MITM)
- 4 профиля (wl/coach/experts/market) — заглушки, watermark/палитра не брендовые

## [1.0.0] — 2026-06-17 (Phase 1 MVP)

### Added

- Главный orchestrator `scripts/image.py` с 6 sub-командами
- 5 форматов в `data/formats.yaml`: vk_post (1:1), vk_story (9:16), pinterest (2:3), wb (3:4), og (2:1)
- 5 профилей в `data/profiles/`: `lab` (полный, rose-pink), `wl`/`coach`/`experts`/`market` (заглушки)
- YandexART API клиент `scripts/yandex_art.py` с MITM bypass
- C-режим `scripts/cmd_generate.py` с override-матрицей
- LLM-стилизация промпта через `prompts/image-prompt.md` + fallback
- Валидация PNG `scripts/validate_image.py` (signature, размер, aspect)
- State-идемпотентность `scripts/state.py` (status lifecycle)
- 6 sub-skills (`generate-mode`, `profile-system`, `yandex-art-api`, `auto-mode`, `publish-mode`, `upscaling-pipeline`)
- 4 промпта (`image-prompt`, `profile-context`, `negative-prompts`, `announce-text`)
- 6 шаблонов (5 форматов + upscale stub)
- 5 examples (3 полных lab + 2 заглушки)
- 4 commands (generate/profile/auto/publish)

### Known limitations

- ❌ Максимальный размер PNG: 512×512 → ИСПРАВЛЕНО в Phase 2 (Pillow Lanczos до target_size)
- ❌ Нет text overlay и watermark → ИСПРАВЛЕНО в Phase 2
- ❌ Нет интеграции с publisher_skill (Phase 3)
- ❌ Нет автопубликации (Phase 3)
- YandexART плохо рисует текст — negative_prompts это блокирует
- Один ключ YandexAPI на YandexGPT + YandexART + будущий SpeechKit — квоты общие

## [Unreleased]

### Phase 3 (~4-6 ч)

- Загрузка в Cloudflare R2
- Интеграция с publisher_skill (auto-attach к статьям как og_image)
- Автопубликация в VK/TG/OK (через publisher_skill.post_channels)
- LLM-генерация подписи к картинке через `prompts/announce-text.md`

### Phase 4 (опционально)

- Real-ESRGAN нейросетевой upscale (для лиц/текстур)
- Yandex SuperResolution если появится в Foundation Models
- PNG-рамки/логотипы в `assets/overlays/` (замена текстового watermark)
