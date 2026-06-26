# /video publish <slug_id> --channels=vk,tg,ok,zen

**Phase 4 — ЗАГЛУШКА. Реализация отложена.**

Будет: загрузить mp4 в Cloudflare R2 → создать Astro-страницу видео → опубликовать в 4 канала (VK/TG/OK/Дзен) → уведомить админа.

## Требования для реализации

- `CF_ACCOUNT_ID`, `CF_R2_BUCKET=pulab-video` — Cloudflare R2
- `TG_BOT_TOKEN`, `VK_ACCESS_TOKEN`, `OK_ACCESS_TOKEN` — токены ботов
- Astro-проект (`C:/Users/kfigh/lab_site`) с шаблоном страницы видео
- `publisher_skill/scripts/post_channels.py` — multi-channel адаптер (готов)
- `publisher_skill/scripts/deploy_pages.py` — деплой (готов)
- `seo-advisor-skill` — SEO-пакет для страницы видео

## План реализации (Phase 4)

1. Прочитать `state/<profile>/<slug>.json` — должен быть `status="rendered"` (или `mixed`/`exported`)
2. Загрузить mp4 в R2 через `upload_r2.py` (boto3 + endpoint)
3. Создать `tmp/pages/<profile>/<slug>.md` с frontmatter (`title`, `description`, `og_image`, `video_url`, `date`)
4. Прогнать `seo-advisor-skill` → добавить FAQ, Schema.org/VideoObject, OG-теги
5. Скопировать в `lab_site/src/pages/videos/<slug>.astro`
6. `npm run build` + `scp dist/ vps:/var/www/lab-site/dist/`
7. Опубликовать через `post_channels.py` (multi-channel adapter):
   - VK: пост с превью + ссылка на Astro
   - TG: сообщение + видео (если ≤50MB) или ссылка
   - OK: пост + видео
   - Zen: RSS-фид автоматом подхватит из `lab_site/dist/rss.xml`
8. `notify_admin.py` — уведомление в Telegram-админ-чат
9. Обновить `state/<profile>/<slug>.json` → `status="published"`, `channels_posted={...}`

## Алгоритм (после реализации)

```
1. resolve publish args (--slug, --channels, --no-seo)
2. load state — должен быть rendered
3. upload_r2(local_mp4, slug) → r2_url
4. render_page({slug, profile, r2_url, ...}) → markdown с frontmatter
5. seo_advisor.optimize(page_md) → +FAQ +Schema +OG (если --no-seo: skip)
6. lab_site: copy → npm run build → scp tar to VPS
7. for channel in [vk, tg, ok, zen]:
   - post_channels.publish(channel, {title, url, video_url, hashtags, ...})
   - state.mark_channel_posted(channel, ok)
8. notify_admin(slug, profile, channels)
9. state.update(status=published, channels_posted=...)
```

## Связано с

- `sub-skills/publish-flow.md` — детали публикации
- `publisher_skill/scripts/post_channels.py` — multi-channel адаптер
- `publisher_skill/scripts/deploy_pages.py` — деплой
- `publisher_skill/scripts/notify_admin.py` — уведомления
- `seo-advisor-skill` — SEO-пакет
- `lab_site/src/pages/videos/` — Astro-страницы
