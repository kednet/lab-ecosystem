# Notify Admin — отчёт админу @kfigh

## Когда

Всегда, в самом конце цикла `/publish`, **даже если announce упал**.

## Канал

`scripts/notify_admin.py` → **Telegram в личку** `TG_ADMIN_CHAT_ID` (НЕ в канал).

## Формат

```html
<b>📚 Опубликовано: {title}</b>

<i>{author}, {year}</i>

✅ Страница: <a href="{live_url}">pulab.online/books/{slug}</a>
📸 Превью: <a href="file://{preview_path}">скриншот</a>

Каналы анонса:
• Telegram ✓
• VK ✓
• email (Phase 2+)

Время публикации: {duration_sec} сек
Build: {build_duration_sec} сек
```

## Если что-то упало

```html
<b>❌ Ошибка публикации: {title}</b>

Slug: {slug}
Упало на стадии: {failed_stage}
Ошибка: {error}

Что сделано:
✅ Render
✅ Deploy
❌ Announce: VK API вернул 429 (rate limit)
```

## Запись в state

```json
{
  "admin_notified_at": "2026-06-11T10:10:00Z",
  "admin_notify_status": "ok | failed"
}
```
