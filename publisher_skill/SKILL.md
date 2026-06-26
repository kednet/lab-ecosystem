---
name: Publisher
description: Агент-анонсировщик для экосистемы «Лаборатория желаний». Берёт готовые артефакты WishLibrarian (summary.md, cover.jpg, metadata.json), рендерит страницу книги в lab_site, деплоит на Cloudflare Pages и анонсирует в Telegram-канал + VK-группу + email-рассылку + уведомляет админа @kfigh. Поддерживает dry-run, пошаговое выполнение (render/deploy/announce), идемпотентность через state/<slug>.json, 2 Telegram-канала (публичный авто + приватный с модерацией). Триггеры: ручной /publish, watcher на wish_librarian/output/library, cron раз в сутки.
allowed-tools:
  - Read
  - Write
  - Bash
  - WebFetch
  - Glob
  - Grep
  - WebSearch
  - mcp__playwright__browser_navigate
  - mcp__playwright__browser_take_screenshot
  - mcp__playwright__browser_snapshot
---

# Publisher Skill v0.3

Ты — **оркестратор публикации** в экосистеме «Лаборатории желаний».
Связка: **WishLibrarian → Publisher → lab_site (Cloudflare Pages) → каналы анонса (TG/VK/email/private) → @kfigh**.

Не дублируешь WL (обработка книг), SEO Advisor (мета/Schema), Expert & Reviews Hub (отзывы),
lab_site (деплой-инфра). Только **оркеструешь** между ними.

## 🎯 РЕЖИМЫ РАБОТЫ

Определи режим по первому запросу:

| Маршрут | Команда | Что делает |
|---------|---------|------------|
| `/publish <slug>` | полный цикл | render → SEO → deploy → announce → admin-notify |
| `/publish --dry-run <slug>` | превью | всё, кроме реальных VK/TG/email/deploy; PNG-превью + план |
| `/publish --only=render <slug>` | только рендер | склейка артефактов WL в Astro-страницу |
| `/publish --only=seo <slug>` | только SEO-пакет | `seo_optimize.py` → seo-bundle.json |
| `/publish --only=deploy <slug>` | только деплой | build + wrangler pages deploy + check 200 |
| `/publish --only=announce <slug>` | только анонс | TG + VK + email (если не отправлено ранее) |
| `/publish --channels=vk,tg,private <slug>` | выборочные каналы | пропустить email / email+tg / private и т.д. |
| `/publish --channels=private <slug>` | модерация | превью в личку @kednet; кнопки ✅/✏️/❌ в @WLPostingbot |
| `/publish --channels=tg <slug>` | только публичный | пост в @pulabru |
| `/republish <slug>` | обновление | re-render → re-deploy → анонс-апдейт «обновлено» |
| `/announce <slug> --channels=vk,tg` | точечный анонс | без ре-деплоя, только в указанные каналы |
| `/preview <slug>` | локальный preview | HTML + PNG + draft-анонсы в `tmp/<slug>-preview/` |
| `/status <slug>` | отчёт | state[slug]: что задеплоено, куда анонсировано, когда |
| `/rollback <slug>` | откат | wrangler pages deployment rollback на предыдущий commit |
| `/watch` | фоновый режим | watch_wl_output.py запускается в фоне |
| `/cron` | режим расписания | «опубликуй всё, что накопилось за 24ч» (через watcher) |

**NB:** в v0.3 реализованы `/publish` (полный + dry-run + --only + --channels=), `/preview`, `/status`, `/rollback`, `/watch`, модерация через `--channels=private`.
НЕ реализованы: `/republish` (Phase 4+), `/cron` (через cron Render).

## 🧠 АЛГОРИТМ `/publish <slug>`

### Шаг 0. Идемпотентность
- Прочитай `state/<slug>.json` (если есть). Что уже сделано — не повторяй.
- Если `status == "published"` и не было `--force` → «уже опубликовано <дата>. Используй /republish для апдейта».

### Шаг 1. Собрать артефакты WL
- `wish_librarian/output/library/<slug>/` должен содержать:
  - `metadata.json` (title, author, year, isbn, slug)
  - `cover.jpg` (или `cover.png`)
  - `summary.md`
  - `practical_tips.md`
  - `reviews.md`
  - `workbook.md`
  - `buy_links.md`
  - `scientific.md` (опционально)
- Если чего-то не хватает → СТОП, список недостающего, ссылка на WL.

### Шаг 2. Render (подскил `sub-skills/render.md`)
- Скопировать артефакты в `lab_site/src/data/books/<slug>/`.
- Сгенерировать `lab_site/src/data/books/<slug>.json` для `import` (Astro-паттерн как `blog.json`).
- Сгенерировать `lab_site/src/pages/books/<slug>.astro` по шаблону `templates/book-page-astro.astro`.
- Записать `state[slug].rendered_at = now()`, `state[slug].page_path = "..."`.

### Шаг 3. SEO-пакет (вызов seo-advisor-skill)
- Вызвать режим `/seo optimize <URL будущей страницы>` (можно по локальному file://).
- Получить: title, description, og:image, JSON-LD `Book` + `FAQPage`.
- Записать в `seo-bundle.json` рядом со страницей.
- Включить в `state[slug].seo = {...}`.

### Шаг 4. Deploy (подскил `sub-skills/deploy.md`)
- `cd lab_site && npm run build` → `dist/`.
- `wrangler pages deploy dist --project-name=pulab` (или через `scripts/deploy_pages.py`).
- GET новой страницы → проверить HTTP 200.
- Скриншот через Playwright → `tmp/<slug>-deploy.png`.
- В `state[slug].deployed_at = now()`, `state[slug].live_url = "https://pulab.online/books/<slug>"`.

### Шаг 5. Announce (подскил `sub-skills/announce.md`)
- Прочитать `state[slug].channels_posted` (если есть).
- Шаг 5.1: Telegram-канал → `post_telegram.py` (cover + 3 идеи + ссылка). Пометить `state[slug].channels_posted.tg = now()`.
- Шаг 5.2: VK-группа `pulabru` → `post_vk.py` (cover + пост). Пометить.
- Шаг 5.3: Email-рассылка → `send_email.py` (если не отправлено). Пометить.
- Шаг 5.4: если хоть один упал → `state[slug].channels_failed = [...]` + admin-алерт.

### Шаг 5.5 (v0.3+) Telegram: 2 канала + модерация

В v0.3 добавлен второй TG-канал `private` с ручной модерацией. Используется `scripts/post_channels.py` — **универсальный постер** (вместо отдельных `post_telegram.py` / `post_vk.py`).

**Два канала — разные режимы:**

| Канал | Ключ | Режим | Где запускать |
|-------|------|-------|---------------|
| `@pulabru` | `tg` | автопубликация | с локалки |
| `Лаборатория желаний pulab.ru` (приватный, `-1003358741340`) | `private` | превью в личку + inline-кнопки | с VPS через `proxychains4` |

**Команды:**

```bash
# Только публичный (с локалки):
python scripts/post_channels.py --content detector --channels tg

# Только приватный (с VPS):
ssh -i ~/.ssh/lab_vps root@194.226.97.7 '/opt/publisher/scripts/publisher_private.sh'
# → в Telegram нажать ✅/✏️/❌ в @WLPostingbot

# Оба сразу (сначала tg с локалки, потом private с VPS)
```

**Бот-модератор @WLPostingbot** (на VPS, systemd `wl-tg-posting.service`):
- Команды: `/start`, `/pending`, `/help`
- Inline-кнопки: ✅ Одобрить / ✏️ Править / ❌ Отклонить
- Pending-файлы: `/opt/publisher/tmp/private_pending/<uuid>.json`

**⚠️ Подводные камни:**

1. **`--channels private` запускать ТОЛЬКО с VPS** через `proxychains4`. Локально `pending_store` создаст файл в `C:\Users\kfigh\publisher_skill\tmp\private_pending\`, а бот @WLPostingbot его не увидит.
2. **`.env` inline-комментарии** (`KEY=value # comment`) ломают значения. В `load_env()` обрезать `v.split("#", 1)[0].strip()`. В `.env` комментарии выносить на отдельные строки.
3. **`urllib.request.urlopen` внутри aiogram-бота обходит SOCKS5** — `_publish_to_private()` использует `bot.send_message`/`bot.send_photo` (aiogram-сессия идёт через `AiohttpSession(proxy=...)`).
4. **HTML-парсинг** `edit_text(parse_mode=HTML)` ломается на `<urlopen error ...>` — оборачивать текст ошибки в `html.escape()`.

**Диагностика** (если бот «не узнаёт» админа):

```bash
ssh -i ~/.ssh/lab_vps root@194.226.97.7
systemctl stop wl-tg-posting.service
/opt/wl/.venv/bin/python /opt/publisher/scripts/diag_admin_id_aiogram.py
# → написать боту /start, увидеть свой chat.id
# → если не совпадает с .env — поправить TG_ADMIN_CHAT_ID
systemctl start wl-tg-posting.service
```

### Шаг 6. Notify admin
- `notify_admin.py` → @kfigh в TG: «Книга «<title>» опубликована ✅
  - URL: https://pulab.online/books/<slug>
  - TG ✓, VK ✓, email ✓
  - Превью: file://tmp/<slug>-deploy.png
  - Время: <duration> сек».

### Шаг 7. Финал
- `state[slug].status = "published"`, `state[slug].published_at = now()`.
- Лог: `log.info("publisher.published", slug=<slug>, duration=<sec>)`.

## 📂 ГДЕ ЧТО

```
publisher_skill/
├── SKILL.md              # этот файл (оркестратор)
├── README.md             # человеческое описание
├── CHANGELOG.md
├── commands/             # готовые рецепты
│   └── publish-book.md
├── sub-skills/           # детали каждой стадии
│   ├── render.md
│   ├── deploy.md
│   ├── announce.md
│   └── notify-admin.md
├── prompts/              # промпты для AI-генерации анонсов
│   ├── vk-post.md
│   ├── tg-post.md
│   └── email-digest.md
├── templates/            # шаблоны
│   ├── book-page-astro.astro
│   ├── announcement-vk.md
│   ├── announcement-tg.md
│   └── seo-bundle.json
│   └── post-channels/    # NEW v0.3: JSON-контент для post_channels.py
│       └── detector.json
├── scripts/              # Python-исполнители
│   ├── render_book.py
│   ├── deploy_pages.py
│   ├── post_telegram.py          # устаревший, заменён post_channels.py
│   ├── post_vk.py                # устаревший, заменён post_channels.py
│   ├── post_channels.py          # NEW v0.3: VK/TG/OK/Zen/private — универсальный
│   ├── pending_store.py          # NEW v0.3: JSON-черновики для модерации
│   ├── publisher_bot.py          # NEW v0.3: @WLPostingbot модератор (aiogram)
│   ├── publisher_private.sh      # NEW v0.3: VPS-helper через proxychains4
│   ├── diag_admin_id_aiogram.py  # NEW v0.3: диагностика admin chat_id
│   ├── send_email.py
│   ├── notify_admin.py
│   ├── watch_wl_output.py
│   ├── rollback_book.py
│   ├── state.py          # идемпотентность
│   └── slugify.py        # общий с seo-advisor-skill
├── data/
│   ├── channels.yaml     # TG/VK/email-конфиг
│   └── source-weights.md
├── examples/             # образцы успешных публикаций
├── state/                # {slug}.json — идемпотентность
└── tmp/                  # превью, скриншоты, логи, private_pending/
```

## 🔗 СВЯЗИ

- **WishLibrarian** — источник артефактов. Watcher следит за `wish_librarian/output/library/<slug>/`.
- **SEO Advisor** — генератор `title/desc/og/Schema/FAQ` для каждой страницы. Вызывается из render/deploy.
- **Expert & Reviews Hub** — пригодится для блока «отзывы экспертов» в шаблоне страницы (Phase 2+).
- **lab_site** — целевой сайт. Publisher пишет в `lab_site/src/pages/books/<slug>.astro` + `lab_site/src/data/books/`.
- **Cloudflare Pages** — хостинг. `wrangler pages deploy` или KV-upload.
- **Telegram Bot / VK API / SMTP** — каналы анонса.

## ⚙️ КОНФИГ (.env)

```bash
# lab_site
LAB_SITE_ROOT=C:/Users/kfigh/lab_site
WL_OUTPUT_ROOT=C:/Users/kfigh/wish_librarian/output/library

# Cloudflare Pages
CF_ACCOUNT_ID=...
CF_API_TOKEN=...
CF_PAGES_PROJECT=pulab

# Telegram — публичный канал (автопубликация)
TG_BOT_TOKEN=...
TG_CHANNEL_ID=@pulabru
TG_ADMIN_CHAT_ID=...          # @kfigh личка

# Telegram — приватный канал (v0.3+, модерация)
TG_CHANNEL_PRIVATE_ID=-1003358741340
TG_ADMIN_USERNAME=@kednet

# SOCKS5 прокси (v0.3+, нужен на VPS для api.telegram.org)
TELEGRAM_PROXY_URL=socks5://...
TELEGRAM_PROXY_URL_BACKUP=socks5://...

# VK
VK_ACCESS_TOKEN=...
VK_GROUP_ID=237295798    # pulabru

# Email
SMTP_HOST=...
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
EMAIL_FROM="Лаборатория желаний <noreply@pulab.online>"
EMAIL_LIST=lab_subscribers.txt
```

**⚠️ Не пиши инлайн-комментарии** (`KEY=value # comment`) — Python-парсер в `load_env()` возьмёт `# comment` в значение. Комментарии выносить на отдельные строки.

## 🚦 СТАТУСЫ В state/<slug>.json

```json
{
  "slug": "transerfing-realnosti",
  "status": "rendering | deploying | announcing | published | failed",
  "rendered_at": "2026-06-11T10:00:00Z",
  "deployed_at": null,
  "published_at": null,
  "live_url": null,
  "page_path": "lab_site/src/pages/books/transerfing-realnosti.astro",
  "seo": null,
  "channels_posted": {
    "tg": null,
    "vk": null,
    "email": null
  },
  "channels_failed": [],
  "error": null
}
```

## 🚧 ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ (v0.3)

- НЕ реализованы: `/republish` (Phase 4+), `/cron` через cron Render.
- `post_telegram.py` и `post_vk.py` помечены как устаревшие — рекомендуется `post_channels.py --channels=tg,vk`.
- `post_channels.py --channels=private` запускается ТОЛЬКО с VPS (proxychains4); для локалки --channels=tg,vk,ok,zen.
- Бот-модератор @WLPostingbot требует, чтобы `TG_ADMIN_CHAT_ID` совпадал с chat.id аккаунта, который реально пишет боту. Иначе бот отвечает «напиши @kednet».

См. CHANGELOG.md.
