# /publish <slug> — полный цикл публикации

## Использование

```bash
# Полный цикл (v0.2)
#   render → seo_optimize → deploy → TG → VK → email → notify_admin
/publish transerfing-realnosti

# Dry-run (только render + SEO, без deploy/announce)
/publish transerfing-realnosti --dry-run

# Только одна стадия
/publish transerfing-realnosti --only=render      # render + seo
/publish transerfing-realnosti --only=seo          # только seo_optimize
/publish transerfing-realnosti --only=deploy       # build + wrangler
/publish transerfing-realnosti --only=announce     # TG + VK + email

# Только выбранные каналы анонса
/publish transerfing-realnosti --channels=vk,tg         # без email
/publish transerfing-realnosti --channels=email         # только email
/publish transerfing-realnosti --only=announce --channels=tg

# Force (перезаписать state, начать заново)
/publish transerfing-realnosti --force

# Watcher (фон)
/watch                                           # запустить watcher в фоне
/cron                                            # один проход: всё накопленное за сутки
```

## Что делает (полный цикл v0.2)

1. **Проверка артефактов WL** в `wish_librarian/output/library/<slug>/`:
   - `metadata.json` ✓
   - `cover.jpg` ✓
   - `summary.md` ✓
   - `practical_tips.md` ✓
   - `reviews.md` ✓
   - `workbook.md` ✓
   - `buy_links.md` ✓
   - `scientific.md` (опционально)
   - Если не хватает → СТОП, список.

2. **Render** (`scripts/render_book.py`) → `lab_site/src/pages/books/<slug>.astro` + `lab_site/src/data/books/<slug>.json` + копия артефактов в `lab_site/src/data/books/<slug>/`.

3. **SEO-пакет** (`scripts/seo_optimize.py`) → `seo-bundle.json`:
   - title / description (из первого абзаца summary.md)
   - og / twitter-card
   - LSI-слова (встречающиеся в summary.md из стартового набора)
   - FAQPage (5 вопросов)
   - Book + canonical URL
   - При наличии импортирует `slugify` из `seo-advisor-skill/scripts/`.

4. **Deploy** (`scripts/deploy_pages.py`) → `npm run build` + `wrangler pages deploy` + GET 200 + скриншот.

5. **Announce** (если не `--only=...`):
   - `scripts/post_telegram.py` — TG-канал: cover + 3 идеи + ссылка
   - `scripts/post_vk.py` — VK-группа `pulabru` (id=237295798): cover + пост + attachment
   - `scripts/send_email.py` — email-дайджест (HTML, 5-7 буллетов + quote + CTA)
   - Идемпотентность: каждый канал проверяет `state[slug].channels_posted.<chan>` и пропускает, если уже отправлено.
   - `--channels=vk,tg` ограничивает набор (например, без email).

6. **Notify admin** (`scripts/notify_admin.py`) → @kfigh в TG: «Книга опубликована ✅ — URL, превью, статусы каналов».

7. **State** → `state/<slug>.json` с финальным статусом `published`.

## Идемпотентность

- Повторный запуск `/publish <slug>` после `status: published` → "уже опубликовано <date>".
- Чтобы переотправить в каналы → `state[slug].channels_posted = {tg:null,vk:null,email:null}`.
- Чтобы начать полностью заново → `--force`.

## Файлы на выходе

| Файл | Что | Где |
|---|---|---|
| `lab_site/src/pages/books/<slug>.astro` | страница книги | lab_site |
| `lab_site/src/data/books/<slug>.json` | мета для `import` | lab_site |
| `lab_site/src/data/books/<slug>/` | артефакты WL (копия) | lab_site |
| `seo-bundle.json` | SEO-пакет | lab_site/src/data/books/<slug>/ |
| `tmp/<slug>-deploy.png` | скриншот после деплоя | publisher_skill |
| `tmp/<slug>-announce.txt` | тексты анонсов | publisher_skill |
| `state/<slug>.json` | финальный статус | publisher_skill |
