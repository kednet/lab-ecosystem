# Publisher Skill

Агент-анонсировщик для экосистемы «Лаборатория желаний».
Превращает готовые артефакты **WishLibrarian** в страницу на сайте **lab_site**, деплоит её и анонсирует в **Telegram + VK + email**, уведомляя админа.

## Что делает

```
WishLibrarian (книга обработана)
    ↓ артефакты в output/library/<slug>/
Publisher
    ├─ render  → Astro-страница + SEO-пакет (через seo-advisor-skill)
    ├─ deploy  → Cloudflare Pages
    ├─ announce → Telegram-канал + VK-группа + email
    └─ notify  → @kfigh в личку: «готово, ссылка, превью»
```

## Структура (v0.3, 39 файлов)

```
publisher_skill/
├── SKILL.md              # оркестратор (загружается Claude-скилом)
├── README.md             # этот файл
├── CHANGELOG.md
├── commands/             # готовые рецепты
│   └── publish-book.md
├── sub-skills/           # render / deploy / announce / notify-admin
├── prompts/              # шаблоны анонсов (vk / tg / email)
├── templates/            # Astro-шаблон + announcement-vk/tg/email + seo-bundle
├── scripts/              # Python-исполнители (13 файлов)
│   ├── render_book.py        # Stage 1: WL → Astro
│   ├── seo_optimize.py       # Stage 1.5: SEO-пакет
│   ├── deploy_pages.py       # Stage 2: build + wrangler
│   ├── post_telegram.py      # Stage 3a
│   ├── post_vk.py            # Stage 3b
│   ├── send_email.py         # Stage 3c
│   ├── notify_admin.py       # Stage 4
│   ├── watch_wl_output.py    # автотриггер (фон)
│   ├── rollback_book.py      # откат деплоя
│   ├── state.py              # идемпотентность
│   ├── slugify.py            # общий с seo-advisor-skill
│   ├── post_channels.py      # NEW v0.3: универсальный VK/TG/OK/Zen + private moderation
│   ├── pending_store.py      # NEW v0.3: JSON-черновики для модерации
│   ├── publisher_bot.py      # NEW v0.3: @WLPostingbot модератор (aiogram)
│   ├── publisher_private.sh  # NEW v0.3: VPS-helper через proxychains4
│   └── diag_admin_id_aiogram.py  # NEW v0.3: диагностика admin chat_id
├── data/
│   ├── channels.yaml
│   ├── source-weights.md
│   └── email_list.txt        # 1 email на строку
├── examples/
├── state/                # {slug}.json — идемпотентность
├── tmp/                  # превью, скриншоты, логи, private_pending/
├── .env.example
└── scripts/.watched.json # генерируется watcher-ом
```

## Запуск (v0.2)

### Однократный полный цикл

```bash
# Через SKILL-скил в чате:
/publish transerfing-realnosti

# Или поэтапно:
python scripts/render_book.py transerfing-realnosti
python scripts/seo_optimize.py transerfing-realnosti
python scripts/deploy_pages.py transerfing-realnosti
python scripts/post_telegram.py transerfing-realnosti
python scripts/post_vk.py transerfing-realnosti
python scripts/send_email.py transerfing-realnosti
python scripts/notify_admin.py transerfing-realnosti
```

### Dry-run / preview

```bash
python scripts/render_book.py transerfing-realnosti --dry-run
python scripts/seo_optimize.py transerfing-realnosti --dry-run
python scripts/post_telegram.py transerfing-realnosti --dry-run
```

### Только одна стадия

```bash
python scripts/render_book.py <slug>           # только render
python scripts/deploy_pages.py <slug> --no-build --skip-check
python scripts/send_email.py <slug> --to=me@example.com
```

### Watcher (фон)

```bash
# Один проход:
python scripts/watch_wl_output.py --once

# Фон, polling каждые 60 сек:
python scripts/watch_wl_output.py

# С другим интервалом:
python scripts/watch_wl_output.py --interval=30 --dry-run
```

### Rollback

```bash
# Показать историю deploy-ов:
python scripts/rollback_book.py <slug> --list

# Откатить к предыдущему:
python scripts/rollback_book.py <slug> --yes

# К конкретному commit:
python scripts/rollback_book.py <slug> --to=abc123 --yes
```

### State

```bash
python scripts/state.py show <slug>
python scripts/state.py reset <slug> --force
python scripts/state.py mark <slug> tg failed --error="rate limit"
```

## Зависимости

- **WishLibrarian** — `wish_librarian/output/library/<slug>/` (вход).
- **lab_site** — `C:/Users/kfigh/lab_site/` (целевой сайт, Cloudflare Pages).
- **Cloudflare API** — токен в `.env`.
- **Telegram Bot** + **VK API** + **SMTP** — токены в `.env`.
- **seo-advisor-skill** (опционально) — `C:/Users/kfigh/seo-advisor-skill/scripts/slugify.py` импортируется on-demand.

## Конфиг

См. `.env.example`. Секреты: `CF_API_TOKEN`, `TG_BOT_TOKEN`, `TG_ADMIN_CHAT_ID`, `VK_ACCESS_TOKEN`, `SMTP_*`, `EMAIL_FROM`, `EMAIL_LIST`.

## Changelog

См. [CHANGELOG.md](./CHANGELOG.md).

## Известные ограничения (v0.2)

- `watch_wl_output.py` запускается вручную (Phase 3+ — cron / Windows Task Scheduler)
- `send_email.py` использует `verify_mode = CERT_NONE` (корпоративный MITM); в Phase 3+ добавить `cert pinning`
- AI-генерация текста анонсов (лид, цитата) — Phase 3+ через `wish_librarian/agent/ai/factory.py`
- `seo_optimize.py` использует встроенный список LSI-семян (Phase 3+ → динамическая генерация)
- Нет тестов и CI (Phase 3+ → pytest + GitHub Actions)

---

## v0.3 — Telegram: 2 канала + модерация (2026-06-18)

В дополнение к автопубликации в `@pulabru` скилл умеет слать превью в **приватный канал** через **ручную модерацию в личке**.

### Что добавлено

- **Канал `private`** в `post_channels.py` — не публикует напрямую, а шлёт **превью в личку админа** с inline-кнопками `✅ Одобрить / ✏️ Править / ❌ Отклонить`
- **`scripts/pending_store.py`** — JSON-хранилище draft'ов в `tmp/private_pending/<uuid>.json`
- **`scripts/publisher_bot.py`** — отдельный polling-бот @WLPostingbot (aiogram 3.29), слушает нажатия кнопок
- **`scripts/publisher_private.sh`** — helper для запуска на VPS через `proxychains4`
- **`scripts/diag_admin_id.py`** + **`diag_admin_id_aiogram.py`** — диагностика `TG_ADMIN_CHAT_ID` (если бот «не узнаёт» админа)

### Архитектура

```
┌─────────────────────────────────────────────────────────────────────┐
│  ЛОКАЛКА (C:/Users/kfigh/publisher_skill)                          │
│                                                                     │
│  python post_channels.py --content detector --channels tg           │
│      ↓ urllib напрямую                                              │
│  TG @pulabru (публичный) — автопубликация                           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  VPS 194.226.97.7 (/opt/publisher/)                                 │
│                                                                     │
│  proxychains4 + post_channels.py --channels private                 │
│      ↓ urllib через SOCKS5 (Estonia proxy)                          │
│  @WLPostingbot шлёт превью в личку @kednet                         │
│      ↓ inline-кнопки                                                │
│  ✅ → TG private channel «Лаборатория желаний pulab.ru»             │
│  ✏️ → бот ждёт новый текст                                         │
│  ❌ → отмена                                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Команды

#### Публичный канал (с локалки)
```bash
cd C:/Users/kfigh/publisher_skill
python scripts/post_channels.py --content detector --channels tg
# → пост сразу в @pulabru
```

#### Приватный канал (с VPS)
```bash
ssh -i ~/.ssh/lab_vps root@194.226.97.7 '/opt/publisher/scripts/publisher_private.sh'
# → превью в личку @WLPostingbot
# → в Telegram нажать ✅/✏️/❌
```

#### Оба сразу
1. Сначала публичный с локалки (`--channels tg`)
2. Потом приватный с VPS (`publisher_private.sh`)
3. Нажать ✅ в личке

### Переменные `.env`

```bash
# Публичный канал
TG_BOT_TOKEN=TG_BOT_TOKEN_REDACTED
TG_CHANNEL_ID=@pulabru

# Приватный канал + модерация
TG_CHANNEL_PRIVATE_ID=-1003358741340
TG_ADMIN_CHAT_ID=779991878       # @kednet — превью + кнопки
TG_ADMIN_USERNAME=@kednet

# SOCKS5 (на VPS обязательно через proxychains4; на локалке — только для tg)
TELEGRAM_PROXY_URL=socks5://oyqAWo:pSD478@212.102.145.155:9264
TELEGRAM_PROXY_URL_BACKUP=socks5://Xpjjaa:4j8MVf@68.209.61.136:8000
```

### Сервис на VPS

```bash
# Статус
systemctl status wl-tg-posting.service

# Логи
journalctl -u wl-tg-posting -f

# Рестарт
systemctl restart wl-tg-posting.service
```

systemd unit `wl-tg-posting.service`:
- `ExecStart=/opt/wl/.venv/bin/python /opt/publisher/scripts/publisher_bot.py`
- `MemoryMax=250M`
- `Restart=always`, `RestartSec=10`

### Подводные камни ⚠️

1. **`.env` inline-комментарии** ломают значения: `KEY=value # comment` → парсер берёт всё вместе с комментарием. В `load_env()` обрезать через `v.split("#", 1)[0].strip()`. И писать комментарии на отдельной строке.
2. **`--channels private` запускать ТОЛЬКО с VPS через `proxychains4`**. Иначе `pending_store` создаёт файл в локальной папке, а бот @WLPostingbot его не видит → «Пост не найден».
3. **aiogram + urllib в одном боте обходит SOCKS5**: `urllib.request.urlopen` идёт мимо `AiohttpSession(proxy=...)` и падает на VPS. Использовать только `bot.send_message`/`bot.send_photo`.
4. **HTML-парсинг ломается на `<urlopen ...>`** (Python repr упавшего URLError). В `edit_text` оборачивать текст ошибки в `html.escape()`.

### Диагностика

Если бот отвечает «Если у тебя есть права админа — напиши @kednet»:
1. Остановить сервис: `systemctl stop wl-tg-posting.service`
2. Запустить диагностику: `/opt/wl/.venv/bin/python scripts/diag_admin_id_aiogram.py`
3. Написать боту `/start` — диагностика покажет твой `chat.id` и сравнит с `.env`
4. Если не совпадает — поправить `TG_ADMIN_CHAT_ID` в `.env`, перезапустить: `systemctl start wl-tg-posting.service`

### Структура после v0.3

```
publisher_skill/
├── ... (старое)
└── scripts/
    ├── ... (старые)
    ├── post_channels.py            # +канал "private" → шлёт превью
    ├── pending_store.py            # NEW: JSON-черновики
    ├── publisher_bot.py            # NEW: @WLPostingbot модератор
    ├── publisher_private.sh        # NEW: VPS-helper через proxychains4
    └── diag_admin_id_aiogram.py    # NEW: диагностика admin chat_id
```
