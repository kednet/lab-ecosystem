# /image publish

**Реализовано в Phase 3 (v1.2) + v1.4 (multi-provider storage) + v1.3 (hardened LLM).**

## Что делает

Автопубликация upscaled JPEG в 4 канала (VK / Telegram / OK / Дзен-RSS) через `publisher_skill/scripts/post_channels.py`.

Pipeline:
1. **Загрузка в storage** — R2 или Yandex Object Storage (через `scripts/upload_storage.py`). Получаем публичный `https://` URL.
2. **Генерация 4 адаптаций поста** — YandexGPT через `scripts/announce_text.py` с per-channel валидацией (v1.3).
3. **Сборка JSON-контента** — `scripts/build_post_content.py` пишет в `tmp/post-channels/<slug>.json` в формате `post_channels.py`.
4. **Вызов post_channels.py** — subprocess, dry-run или live. UTF-8 encoding.
5. **Update state** → `status=published`, поля `published_url`, `published_at`, `channels_posted`.

## Использование

```bash
# Dry-run (по умолчанию storage=auto, channels=vk)
python scripts/image.py publish lab/5-oshibok-karty-zhelanii --profile=lab --dry-run

# Live в ВК
python scripts/image.py publish lab/5-oshibok-karty-zhelanii --profile=lab --channels vk

# Live во все 4 канала (TG/OK скипнутся без токенов)
python scripts/image.py publish lab/5-oshibok-karty-zhelanii --profile=lab --channels vk,tg,ok,zen

# Live с указанием live-url (для og:image)
python scripts/image.py publish lab/5-oshibok-karty-zhelanii --profile=lab \
    --live-url https://app.pulab.ru/posts/5-oshibok

# Выбрать storage provider
python scripts/image.py publish lab/5-oshibok-karty-zhelanii --profile=lab \
    --storage yandex --dry-run

# Force (повтор после published)
python scripts/image.py publish lab/5-oshibok-karty-zhelanii --profile=lab --force
```

## Требования

### Storage (минимум один)

- **R2** (`R2_*`): см. `data/r2.example.yaml` (Cloudflare)
- **Yandex Object Storage** (`YANDEX_STORAGE_*`): см. `data/yandex-storage.example.yaml` (рекомендую для РФ)
- `pip install boto3`
- Без токенов — fallback на `file://` URL (только dry-run, live постинг невозможен)

### Каналы (publisher_skill)

- `VK_ACCESS_TOKEN` — **уже есть** в `publisher_skill/.env`
- `VK_GROUP_ID=237295798` — **уже зашит** в `post_channels.py`
- `TG_BOT_TOKEN` + `TG_CHANNEL_ID` — опционально (для Telegram)
- `OK_ACCESS_TOKEN` + `OK_GROUP_ID` — опционально (для Одноклассников)
- Дзен — без токена, только RSS в `lab_site/public/detector/feed.xml`

### Пайплайн

- Phase 2 сначала (`auto` команда) — нужен `status=upscaled` в state
- `llm_factory.py` (YandexGPT) — работает, ключ в `image_skill/.env`

## Состояния

| State status | Действие |
|---|---|
| `draft` / `prompt_ready` / `generated` / `saved` | Нужен Phase 2 (`auto`) сначала |
| `upscaled` | ✅ Готов к publish |
| `published` | Skip (используй `--force` для повтора) |
| `failed` | Сбрось через `state reset <slug_id>` и переделай |

## Пример вывода

```
🔧 Phase 3: storage upload ...jpg → images/lab/...jpg
  → Storage: Yandex Object Storage (provider=auto)
  ✓ Загружено в Yandex Storage: images/lab/...jpg → https://storage.yandexcloud.net/pulab-images/...
🔧 Phase 3: генерация 4 адаптаций поста (vk/tg/ok/zen)
  ✓ LLM сгенерировал 4 валидные адаптации
  ✓ JSON-контент: tmp\post-channels\lab_5-oshibok-karty-zhelanii.json
🔧 Phase 3: post_channels.py --content lab_5-oshibok-karty-zhelanii.json --channels vk [DRY-RUN]
📤 Публикация: 5 ошибок карты желаний
   Каналы: vk
   Режим: DRY-RUN

→ VK:
  [DRY-RUN] VK: 5 ошибок, которые мешают вашей карте желаний работать...

✅ Phase 3 done!
   📁 C:\...\tmp\images\lab\5-oshibok-karty-zhelanii-vk_post-upscaled-texted-final.jpg
   🌐 https://storage.yandexcloud.net/pulab-images/images/lab/...jpg
   📤 Каналы: vk
   📋 state: lab/5-oshibok-karty-zhelanii → status=published
```

## Известные ограничения

- ❌ Live VK постинг требует ручного подтверждения kfigh (auto-mode classifier)
- ❌ YandexGPT JSON reliability ~30% (v1.3: retry + per-channel fallback решают)
- ❌ Без storage токенов — только dry-run
- ❌ TG/OK без токенов — скипаются с warning
- ❌ Дзен — без open API, только RSS (ручное добавление в Дзен Studio)

## Связано с

- [[SKILL]]
- [[sub-skill-publish-mode]] — детали storage/каналов
- [[publisher-skill-built]] — целевой интеграционный партнёр
- [[image-skill-v3-phase3-built]] — Phase 3 v1.2
- [[image-skill-v1.3-harden-llm]] — v1.3 hardened LLM
