# Announce — анонс в каналы

## Вход

- `state[slug].deployed_at` установлен.
- `state[slug].live_url` валиден.
- `state[slug].channels_posted` (чтобы не дублировать).

## Каналы

### Telegram-канал (@pulaab_ru)

`scripts/post_telegram.py`:
1. Скачать `cover.jpg` из `lab_site/src/data/books/<slug>/cover.jpg`.
2. Загрузить через `sendPhoto` (multipart).
3. Подпись: `templates/announcement-tg.md` подставленной `{title}`, `{author}`, `{live_url}`, `{3_ideas}`.
4. `parse_mode: HTML`.

Пометить `state[slug].channels_posted.tg = now()`.

### VK-группа (pulabru, id=237295798)

`scripts/post_vk.py`:
1. Загрузить `cover.jpg` в фотоальбом группы (`photos.getWallUploadServer`).
2. Сохранить фото (`photos.saveWallPhoto`).
3. Создать пост (`wall.post`) с текстом `templates/announcement-vk.md` + attachment фото + `attachments: "https://pulab.online/books/<slug>"`.
4. `from_group: 1`.

Пометить `state[slug].channels_posted.vk = now()`.

### Email-рассылка (Phase 2+)

`scripts/send_email.py` (НЕ реализован в MVP v0.1):
- SMTP или SendGrid.
- HTML-шаблон `templates/announcement-email.html`.
- Список из `data/channels.yaml::email.list_file`.

## Идемпотентность

Каждый канал читает `state[slug].channels_posted.<chan>`.
Если `now()` уже стоит → пропускаем.
Команда для сброса: `state/<slug>.channels_posted = {tg:null,vk:null,email:null}`.

## Промпты для AI-генерации анонсов

- `prompts/tg-post.md` — короткий (≤400 символов), 3 буллета, ссылка.
- `prompts/vk-post.md` — длинный (до 2000 символов), 3 идеи + цитата + ссылка.
- `prompts/email-digest.md` — HTML-вёрстка, 5-7 абзацев.

## Секреты

- `TG_BOT_TOKEN`, `TG_CHANNEL_ID`
- `VK_ACCESS_TOKEN`, `VK_GROUP_ID=237295798`
- `SMTP_*`, `EMAIL_LIST` (Phase 2+)
