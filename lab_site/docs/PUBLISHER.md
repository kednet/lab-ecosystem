# Publisher — публикация книг и экспертов в соцсетях

> Документация встроенного в `lab_site/` Publisher-агента.
> Публикует конспекты книг и карточки экспертов в **ВКонтакте** + **Telegram-канал** с уведомлением админу для модерации.

---

## Зачем

`lab_site/` — это рабочий сайт Лаборатории желаний (`app.pulab.online`). Когда `wish_librarian` генерирует конспект новой книги, мы хотим:

1. **AI-копирайтер** генерирует пост под ВК (1000-1500 символов) и Телеграм (600-900).
2. **Опубликовать** в группу VK (id 237295798) и в TG-канал (`@wishlab_channel`).
3. **Уведомить админа** в личку с inline-кнопками `[🗑 Удалить VK] [🗑 Удалить TG] [✅ Подтвердить]`.
4. **State-машина** отслеживает переходы и не даёт опубликовать дважды.

То же самое — для **новых экспертов** (после того, как Reviews Hub соберёт их карточки).

---

## Архитектура

```
┌─────────────────┐
│ WishLibrarian   │  ← конспекты в output/library/{slug}/
│   output/       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐    copywrite     ┌──────────────────┐
│   Worker         │ ──────────────▶ │  python-service  │
│  (Hono + KV)     │ ◀──────────────  │   (FastAPI)       │
│                  │   {vk, tg, meta} │  copywriter.py    │
│                  │                  └──────────────────┘
│  social_vk.ts    │  wall.post              ▲
│  social_tg.ts    │  sendMessage            │ AI (lazy)
│  publish_state   │  deleteMessage          │
└────────┬─────────┘
         │
         ▼
   ┌─────────┐         ┌──────────┐
   │   VK    │         │ Telegram │
   │ group   │         │ channel  │
   └─────────┘         └──────────┘
         │
         ▼  notify (inline buttons)
   ┌──────────────────┐
   │ Admin (TG private)│
   │ [Удалить VK]      │
   │ [Удалить TG]      │
   │ [Подтвердить]     │
   └──────────────────┘
         │ callback
         ▼
   /internal/tg/callback
```

### Файлы

| Путь | Что делает |
|------|-----------|
| `worker/src/routes/social.ts` | Оркестратор: `POST /internal/publish` |
| `worker/src/routes/notifications.ts` | Callback от TG: `POST /internal/tg/callback` |
| `worker/src/lib/social_vk.ts` | `VKAdapter.publishPost/editPost/deletePost` |
| `worker/src/lib/social_tg.ts` | `TelegramAdapter.sendToAdmin/Channel/...` |
| `worker/src/lib/publish_state.ts` | State-машина + KV-обёртка |
| `python-service/copywriter.py` | `SocialCopywriter` — AI-генератор |
| `python-service/main.py` | `POST /internal/copywrite` (для Worker) |
| `src/pages/experts/*` | Каталог + карточки экспертов (Astro) |
| `src/lib/experts.ts` | Загрузчик JSON для SSG |
| `scripts/sync_reviews_hub.py` | Синхронизация expert-reviews-hub → `src/data/` |

---

## State-машина

```
States: NEW → COPIES_GENERATED → VK_POSTED → TG_POSTED → NOTIFIED → PUBLISHED
                                  │            │            │           │
                                  ▼            ▼            ▼           ▼
                              FAILED       FAILED       FAILED      ←
                                                                 (rollback)
```

**KV-ключи** (`lib/kv.ts`):
- `publish:{kind}:{slug}` — основная запись (TTL 30 дней)
- `publish:dry-run:{kind}:{slug}` — dry-run запись
- `social:vk:{slug}` — отдельно кешированный VK-пост (быстрый доступ)
- `social:tg:{slug}` — отдельно TG-сообщение

`kind ∈ {book, expert}`. Переходы валидируются в `publish_state.ts:canTransition()`.

---

## Использование

### 1. Генерация и dry-run

```bash
# Сухой прогон — без реальных VK/TG вызовов (env без токенов → dev-mode моки)
curl -X POST http://127.0.0.1:8787/internal/publish \
  -H "Authorization: Bearer $PYTHON_SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"kind":"book","slug":"transerfing-realnosti","dryRun":true}'
```

Ответ:
```json
{
  "ok": true,
  "dryRun": true,
  "steps": ["COPIES_GENERATED", "VK_POSTED", "TG_POSTED", "NOTIFIED", "PUBLISHED (dry-run)"],
  "record": { "state": "PUBLISHED", "vk": {...mock}, "tg": {...mock}, ... }
}
```

В логах Worker увидите:
```
[vk:dev] would publish: length=1240 fromGroup=true link=https://...
[tg:dev] would send to @wishlab_channel length=820
[tg:dev] would send to 123456789 (admin) length=350
```

### 2. Боевой прогон

Тот же запрос, но `dryRun: false`. **Требуются** секреты в `wrangler secret put`:
- `VK_GROUP_TOKEN` — токен сообщества VK
- `VK_GROUP_ID` — `237295798`
- `TELEGRAM_BOT_TOKEN` — бот для анонсов
- `TELEGRAM_ADMIN_ID` — личный chat_id админа
- `TELEGRAM_CHANNEL_ID` — `@wishlab_channel` (или числовой id)

После публикации админ получит сообщение в личку:
```
✅ Опубликовано

📚 transerfing-realnosti
Книга, которая меняет отношение к реальности...

VK: https://vk.com/wall...
TG: https://t.me/wishlab_channel/...

[🗑 Удалить VK]  [🗑 Удалить TG]
[✅ Подтвердить]
```

### 3. Модерация через TG-кнопки

| Кнопка | Callback | Действие |
|--------|----------|----------|
| 🗑 Удалить VK | `del_vk:book:slug` | `wall.delete` → обновление state |
| 🗑 Удалить TG | `del_tg:book:slug` | `deleteMessage` → обновление state |
| ✅ Подтвердить | `confirm:book:slug` | state → `PUBLISHED` |

Если оба поста удалены — state → `FAILED` с пометкой "Удалено вручную".

### 4. Повторная публикация (force)

```bash
curl -X POST http://127.0.0.1:8787/internal/publish \
  -H "..." \
  -d '{"kind":"book","slug":"x","force":true,"dryRun":false}'
```

`force=true` сбрасывает state в `NEW` и перепрогоняет весь pipeline.

### 5. Статус и список

```bash
# Статус одной сущности
GET /internal/publish/status?kind=book&slug=transerfing-realnosti
GET /internal/publish/status?kind=book&slug=...&dryRun=true

# Список (фильтры)
GET /internal/publish/list?kind=book&state=PUBLISHED&limit=50
GET /internal/publish/list?kind=expert&state=FAILED
```

---

## AI-копирайтер

`python-service/copywriter.py` использует `wish_librarian/agent/ai/factory.py` для генерации текстов:

- **VK** (1000-1500 символов): интрига в первой строке, эмодзи, хештеги, ссылка.
- **TG** (600-900 символов): короче, акцент на практику.
- **Meta description** (≤155 символов): для `<meta name="description">`.

**Fallback** (если AI недоступен или `AI_PROVIDER` не задан): шаблонные строки с подстановкой slug/названия — пайплайн не падает, просто пост будет generic.

Промпты — в `copywriter.py:PROMPT_VK/PROMPT_TG/PROMPT_META`. Менять можно без перезапуска Worker — python-service подхватит при следующем вызове `/internal/copywrite`.

### Запуск с AI

В `python-service/.env`:
```env
AI_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
# или
AI_PROVIDER=yandex
YANDEX_API_KEY=...
YANDEX_FOLDER_ID=...
# или
AI_PROVIDER=gigachat
GIGACHAT_CREDENTIALS=...
```

Без AI — `fallbackOnly=true` (или AI просто не сконфигурирован):
```python
from copywriter import SocialCopywriter
cw = SocialCopywriter()  # lazy AI
result = cw.vk_announcement(book)  # fallback
```

---

## Секреты (production)

`wrangler secret put` (по одному):
```bash
cd worker
wrangler secret put VK_GROUP_TOKEN
wrangler secret put VK_GROUP_ID
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put TELEGRAM_ADMIN_ID
wrangler secret put TELEGRAM_CHANNEL_ID
wrangler secret put PYTHON_SERVICE_URL  # https://lab-site-python.onrender.com
wrangler secret put PYTHON_SERVICE_TOKEN
```

В `wrangler.toml [vars]` только несекретные значения (уже добавлено в дев-режиме).

---

## Пайплайн публикации книги (типичный)

1. **WishLibrarian** генерирует конспект в `C:\Users\kfigh\wish_librarian\output\library\{slug}\`
2. **User** жмёт "Опубликовать" в UI (или admin вызывает `POST /internal/publish`)
3. **Worker** → `python-service /internal/copywrite` → генерирует `vk`, `tg`, `meta_description`
4. **Worker** → `VKAdapter.publishPost` → `wall.post` → возвращает `post_id`, `url`
5. **Worker** → `TelegramAdapter.sendToChannel` → `sendMessage` → возвращает `message_id`, `url`
6. **Worker** → `TelegramAdapter.sendToAdmin` с inline-кнопками → админ видит в личке
7. **Admin** жмёт `✅ Подтвердить` → TG callback `/internal/tg/callback` → state → `PUBLISHED`

---

## Сценарии

### "Добавился новый эксперт"

```bash
# 1. Reviews Hub собирает данные
python "C:\Users\kfigh\expert-reviews-hub\skills\expert-reviews-hub\scripts\expert_add.py" mark-rozin

# 2. Синхронизировать в lab_site
python scripts/sync_reviews_hub.py --experts --reviews

# 3. Build Astro
npm run build

# 4. Dry-run публикации
curl -X POST http://127.0.0.1:8787/internal/publish \
  -H "..." -d '{"kind":"expert","slug":"mark-rozin","dryRun":true}'

# 5. Если текст ОК → боевая публикация (без dryRun)
curl -X POST http://127.0.0.1:8787/internal/publish \
  -H "..." -d '{"kind":"expert","slug":"mark-rozin"}'
```

### "Книга в WL, но не опубликована"

```bash
# Проверить статус
curl "http://127.0.0.1:8787/internal/publish/status?kind=book&slug=transerfing-realnosti"
# → {"ok":true,"record":null} — никогда не публиковалась

# Запустить пайплайн
curl -X POST http://127.0.0.1:8787/internal/publish \
  -H "..." -d '{"kind":"book","slug":"transerfing-realnosti","dryRun":false}'
```

### "Опубликовали с опечаткой"

```bash
# 1. Удалить через TG-кнопку (админ)
# 2. Или принудительно:
curl -X POST http://127.0.0.1:8787/internal/publish/confirm \
  -H "..." -H "Content-Type: application/json" \
  -d '{"kind":"book","slug":"x","action":"del_vk"}'
curl -X POST http://127.0.0.1:8787/internal/publish/confirm \
  -H "..." -H "Content-Type: application/json" \
  -d '{"kind":"book","slug":"x","action":"del_tg"}'

# 3. Сгенерировать заново с force
curl -X POST http://127.0.0.1:8787/internal/publish \
  -H "..." -d '{"kind":"book","slug":"x","force":true,"dryRun":false}'
```

---

## Мониторинг

```bash
# Сколько опубликовано за неделю
curl "http://127.0.0.1:8787/internal/publish/list?state=PUBLISHED&limit=100" | jq

# Какие упали (FAILED)
curl "http://127.0.0.1:8787/internal/publish/list?state=FAILED" | jq '.records[] | {slug, error, updatedAt}'

# Что в dry-run (превью)
curl "http://127.0.0.1:8787/internal/publish/list?dryRun=true" | jq
```

Также — `wrangler tail` показывает live-логи:
```bash
cd worker && npx wrangler tail --format=pretty
```

---

## Известные ограничения

1. **Нет retry** при сбое VK/TG API. Если `wall.post` упал — state → FAILED, ручной retry через `force=true`.
2. **VK фото** — первая версия без прикрепления обложки. Картинка добавится отдельным шагом через `photos.getWallUploadServer` + `wall.post` с `attachments`.
3. **Telegram WebApp preview** — TG сам подтягивает `link_preview` из ссылки в посте (если не `disable_web_page_preview`).
4. **Cron авто-публикации** — пока нет. Публикация только ручная или по запросу пользователя. Cron добавится в отдельной фазе.

---

## Что не делаем

- ❌ **Оплата** (ЮKassa) — отдельный план.
- ❌ **Чат** (Durable Objects) — отдельный план.
- ❌ **Email-рассылка подписчикам** — отдельная задача.
- ❌ **A/B-тесты** постов — после стабилизации.

---

## Связи

- [WishLibrarian project](../wish_librarian) — источник конспектов
- [Expert & Reviews Hub](../expert-reviews-hub) — источник экспертов и отзывов
- [SEO Advisor skill](../seo-advisor-skill) — SEO-пакет
- [VK community «ЛАБОРАТОРИЯ ЖЕЛАНИЙ»](https://vk.com/club237295798) — группа для анонсов (id=237295798)
- [lab_site PRD](https://app.pulab.online) — продакшн-сайт
