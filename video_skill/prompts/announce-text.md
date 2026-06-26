# Генерация анонсов — Video Creator Skill v1.0 (Phase 4 STUB)

Phase 1: ЗАГЛУШКА.
Phase 4: генерирует тексты анонсов для 4 каналов (VK/TG/OK/Дзен) с учётом профиля.

## Алгоритм
1. На вход: `script` (dict), `profile` (dict), `mp4_url`
2. LLM-генерация 4 адаптаций (по `templates/post-channels/detector.json` как образец)
3. Сохранить в `publisher_skill/templates/post-channels/video-<slug>.json`
4. Вызвать `publisher_skill/scripts/post_channels.py --content=video-<slug> --channels=vk,tg,ok,zen`

## Адаптации под каналы
- **VK** — развёрнутый текст, эмодзи, без URL в attachments (URL в тексте)
- **TG** — короткий, HTML-разметка, inline_keyboard с URL-кнопкой
- **OK** — эмодзи, тёплый тон, без агрессивного маркетинга
- **Дзен (RSS)** — заголовок + описание, без хештегов, длинный текст

Phase 4 — будет реализован в `scripts/announce_video.py`.
