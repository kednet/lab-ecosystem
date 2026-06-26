# Публикация (Phase 4) — Video Creator Skill v1.0

Phase 1: ЗАГЛУШКА. Phase 4: интеграция с `publisher_skill/scripts/post_channels.py`.

## План

1. **upload_r2** — `python scripts/upload_r2.py tmp/out/<slug>.mp4 --key=<slug>.mp4`
2. **render_video** — генерирует `lab_site/src/pages/video/<slug>.astro` + добавляет в `lab_site/src/data/videos.ts`
3. **Astro build + deploy** — `publisher_skill/scripts/deploy_pages.py`
4. **announce_video** — вызывает `publisher_skill/scripts/post_channels.py --content=video-<slug> --channels=vk,tg,ok,zen`
5. **notify_admin** — `publisher_skill/scripts/notify_admin.py`

## Адаптация текстов под каналы

Шаблон `publisher_skill/templates/post-channels/video-<slug>.json`:
```json
{
  "title": "...",
  "url": "https://app.pulab.ru/video/<slug>/",
  "image": "https://app.pulab.ru/og/<slug>.png",
  "hashtags": ["#лабжеланий", "..."],
  "zen_title": "...",
  "vk": "...",
  "tg": "...",
  "ok": "...",
  "zen": "..."
}
```

## OG-картинка

`templates/og-video-profile.svg.j2` — Jinja-шаблон с переменными профиля (palette, accent_color, watermark).

## Требует от kfigh
- Cloudflare R2 (переиспользовать от audio_skill)
- 4 канала публикации: VK/TG/OK/Дзен (после получения токенов)

## Связано с
- `publisher_skill/scripts/post_channels.py` — адаптер 4 каналов
- `publisher_skill/scripts/deploy_pages.py` — build + scp на VPS
- `publisher_skill/scripts/notify_admin.py` — admin-уведомление
- План: `C:/Users/kfigh/.claude/plans/video-skill-universal-2026-06-17.md` (секция 6)
