# Publisher Skill — Changelog

## v0.3 — Telegram: 2 канала + ручная модерация (2026-06-18)

Расширение Telegram-канала. К автопубликации в `@pulabru` добавляется приватный канал с модерацией через inline-кнопки в личке админа.

Добавлено:

- ✅ Канал `private` в `scripts/post_channels.py` — НЕ публикует напрямую, а шлёт превью в личку админа с inline-кнопками ✅/✏️/❌
- ✅ `scripts/pending_store.py` — JSON-хранилище draft-постов в `tmp/private_pending/<uuid>.json`
- ✅ `scripts/publisher_bot.py` — отдельный polling-бот @WLPostingbot (aiogram 3.29) с командами `/start`, `/pending`, `/help`
- ✅ `scripts/publisher_private.sh` — helper для запуска `post_channels.py` на VPS через `proxychains4`
- ✅ `scripts/diag_admin_id_aiogram.py` — диагностика `TG_ADMIN_CHAT_ID` (когда бот «не узнаёт» админа)
- ✅ systemd-юнит `wl-tg-posting.service` на VPS 194.226.97.7 (`/opt/publisher/`)

Сервисная инфраструктура:

- ✅ SOCKS5-прокси для Telegram API на российском VPS (Estonia 212.102.145.155:9264 + Нидерланды 68.209.61.136:8000 failover)
- ✅ `proxychains4` + `/etc/proxychains4.conf` на VPS (SOCKS5 → api.telegram.org)
- ✅ Все 3 TG-бота (@WLDetectorbot, @WLBBibliobot, @WLPostingbot) работают через единый SOCKS5

Изменено:

- 📝 `scripts/post_channels.py` — добавлена функция `post_tg_private()` с обработкой HTTP 403 «bot blocked by user»
- 📝 `scripts/publisher_bot.py` — `_publish_to_private()` переписан с `urllib.request.urlopen` на `bot.send_message`/`bot.send_photo` (aiogram-сессия идёт через SOCKS5; urllib обходит прокси)
- 📝 `.env` — комментарии вынесены на отдельные строки (инлайн `#` ломал парсер, забирал `# ...` в значение переменной)
- 📝 `README.md` — добавлен раздел v0.3 с архитектурой, командами, переменными, подводными камнями

Подводные камни (учтены в коде):

1. `.env` inline-комментарии ломают значения: `KEY=value # comment` → парсер берёт всё вместе с комментарием. Фикс: `v.split("#", 1)[0].strip()` в `load_env()`.
2. `post_channels.py --channels private` запускать ТОЛЬКО с VPS через `proxychains4`, иначе `pending_store` создаёт файл в локальной папке, бот @WLPostingbot его не видит.
3. `urllib.request.urlopen` внутри aiogram-бота обходит `AiohttpSession(proxy=...)`. Использовать только `bot.send_*`.
4. `edit_text(parse_mode=HTML)` ломается на Python-repr `<urlopen error ...>` — оборачивать текст ошибки в `html.escape()`.

Текущий размер: **39 файлов, ~310 КБ**.

## v0.2 — email + watcher + rollback + SEO-интеграция (2026-06-11)

Расширение MVP. Добавлено:

- ✅ `templates/announcement-email.html` — HTML-вёрстка дайджеста (cover + bullets + quote + CTA + footer)
- ✅ `scripts/send_email.py` — SMTP-рассылка с per-recipient `To:`, rate-limit, plain-text fallback
- ✅ `scripts/watch_wl_output.py` — фоновый watcher: polling wish_librarian/output/library/ каждые N сек, авто-publish готовых книг
- ✅ `scripts/rollback_book.py` — `wrangler pages deployment rollback` к предыдущему/указанному commit
- ✅ `scripts/seo_optimize.py` — генератор полного SEO-пакета с LSI, FAQPage, canonical, slugify из seo-advisor-skill
- ✅ Интеграция `seo_optimize.py` в `render_book.py:build_seo_bundle` (с fallback на старую заглушку)
- ✅ `data/email_list.txt` — placeholder для списка подписчиков (1 email на строку)
- ✅ `scripts/.watched.json` — автогенерируется watcher-ом, хранит уже опубликованные slug-и

Изменено:

- 📝 `CHANGELOG.md`, `README.md`, `SKILL.md` обновлены до v0.2
- 📝 `commands/publish-book.md` — добавлены новые опции (`--channels=email`, упоминания watch/rollback)

Текущий размер: **32 файла, ~210 КБ**.

## v0.1 — MVP (2026-06-11)

- ✅ `SKILL.md` — оркестратор с 12 маршрутами команд
- ✅ `README.md` + `CHANGELOG.md`
- ✅ `commands/publish-book.md` — рецепт полного цикла
- ✅ `sub-skills/render.md`, `deploy.md`, `announce.md`, `notify-admin.md`
- ✅ `prompts/vk-post.md`, `tg-post.md`, `email-digest.md`
- ✅ `templates/book-page-astro.astro`, `announcement-vk.md`, `announcement-tg.md`, `seo-bundle.json`
- ✅ `scripts/render_book.py` — собирает артефакты WL в Astro-страницу
- ✅ `scripts/deploy_pages.py` — `wrangler pages deploy` + check 200
- ✅ `scripts/post_telegram.py` — публикация в TG-канал
- ✅ `scripts/post_vk.py` — публикация в VK-группу `pulabru`
- ✅ `scripts/notify_admin.py` — уведомление @kfigh в личку
- ✅ `scripts/state.py` — идемпотентность через `state/<slug>.json`
- ✅ `scripts/slugify.py` — общий с seo-advisor-skill
- ✅ `data/channels.yaml` — конфиг каналов
- ✅ `examples/published-transerfing.md` — образец успешной публикации

## v1.0 (план)

- Полная интеграция со всеми агентами (включая Expert & Reviews Hub для блока отзывов)
- Watcher в фоне как системный сервис (через cron Render / Windows Task Scheduler)
- Rollback + история deploy-ов
- Email-шаблоны с AI-генерацией лида и буллетов (через AI factory WL)
- A/B-тестирование анонсов (TG vs VK эффективность)
- Тесты + CI (GitHub Actions)
- Метрики: время публикации, error rate, conversion из анонса
