# Промпт: `/experts deploy {slug}` — деплой карточки на прод

## Назначение

По команде пользователя «готово» запустить полный пайплайн: sync в lab_site → build → tar → scp на VPS → атомарная распаковка → smoke-проверки.

## Вход

- `{slug}` — slug эксперта
- Пользователь сказал «готово» в `/experts edit`

## Алгоритм

### Шаг 1. Запусти `python lab_site/scripts/deploy_experts.py {slug}`

Скрипт сам делает все проверки и шаги. Если нужно — спроси `--dry-run` для предпросмотра без реального деплоя.

### Шаг 2. Полный пайплайн (внутри deploy_experts.py)

1. **Preflight** — slug существует, `status: published`, ssh-ключ на месте, ssh-ping до VPS.
2. **Stage:** `python lab_site/scripts/sync_reviews_hub.py --experts --verbose` → пишет `lab_site/src/data/experts/{slug}.json` + обновляет `index.json`.
3. **Build:** `cd lab_site && npm run build` (~60-90 сек с `prebuild: sitemap+spheres`) → `dist/`.
4. **Tarball:** `python C:/Users/kfigh/temp/rebuild_deploy.py` → `C:/Users/kfigh/temp/lab-site-deploy.tar.gz` (~34 МБ).
5. **Upload:** `scp -i ~/.ssh/lab_vps lab-site-deploy.tar.gz root@89.108.88.74:/tmp/`.
6. **Распаковка на VPS (атомарно с backup):**
   ```bash
   BACKUP=/var/www/lab-site/dist.bak.experts-$(date +%Y%m%d-%H%M%S)
   cp -a /var/www/lab-site/dist "$BACKUP"
   rm -rf /var/www/lab-site/dist/_astro /var/www/lab-site/dist/experts /var/www/lab-site/dist/books
   tar -xzf /tmp/lab-site-deploy.tar.gz -C /var/www/lab-site/dist
   rm /tmp/lab-site-deploy.tar.gz
   chown -R deploy:deploy /var/www/lab-site/dist
   ```
7. **Smoke (4 проверки):**
   - `curl -sI https://app.pulab.ru/experts/` → 200
   - `curl -sI https://app.pulab.ru/experts/{slug}/` → 200
   - `curl -s https://app.pulab.ru/experts/ | grep -c 'expert-card__name'` ≥ 1
   - `curl -sI https://app.pulab.ru/_astro/hoisted.*.js` → 200 (нет white screen)
8. **Печать команды отката:**
   ```bash
   ssh -i ~/.ssh/lab_vps root@89.108.88.74 \
     'rm -rf /var/www/lab-site/dist && \
      mv /var/www/lab-site/dist.bak.experts-DATE /var/www/lab-site/dist && \
      chown -R deploy:deploy /var/www/lab-site/dist'
   ```

### Шаг 3. Вывод пользователю

```
✅ Деплой завершён за {N} сек
   Backup: /var/www/lab-site/dist.bak.experts-{DATE}
   Slug:   {slug}

🔍 Smoke:
   ✅ https://app.pulab.ru/experts/ → 200
   ✅ https://app.pulab.ru/experts/{slug}/ → 200
   ✅ Найдено превью экспертов: {N}
   ✅ _astro/*.js отдаётся (нет white screen)

👉 Проверь в браузере:
   https://app.pulab.ru/experts/
   https://app.pulab.ru/experts/{slug}/

⚠️ Откатить если что-то не так:
   ssh -i ~/.ssh/lab_vps root@89.108.88.74 'rm -rf /var/www/lab-site/dist && \
     mv /var/www/lab-site/dist.bak.experts-{DATE} /var/www/lab-site/dist && \
     chown -R deploy:deploy /var/www/lab-site/dist'
```

## ⚠️ Что НЕ делаем

- ❌ Не трогаем `lab-api` (Node-воркер) и nginx config
- ❌ Не перезапускаем nginx
- ❌ Не льём отдельно `experts/` (только всю `dist/` — иначе partial-deploy-pitfall = белый экран)
- ❌ Не делаем без `status: published`

## 🔧 Что используем

| Что | Где |
|-----|-----|
| `sync_experts` | `lab_site/scripts/sync_reviews_hub.py:69-107` |
| `npm run build` | `lab_site/package.json:12` |
| `rebuild_deploy.py` | `C:/Users/kfigh/temp/rebuild_deploy.py` |
| deploy-скрипт | `lab_site/scripts/deploy_experts.py` (создаётся в этом wizard) |
| SSH-ключ | `C:\Users\kfigh\.ssh\lab_vps` |
| VPS | `root@89.108.88.74` |

## 🩺 Диагностика проблем

| Симптом | Причина | Решение |
|---------|---------|---------|
| `experts/` показывает заглушку после деплоя | `isComingSoon = true` в `index.astro:32` | Отдельный коммит: `true → false`, пересобрать, передеплоить |
| Карточка эксперта пустая | не заполнены критичные поля | `/experts edit {slug}` → заполнить → передеплоить |
| `curl https://app.pulab.ru/experts/{slug}/` → 404 | `getStaticPaths` не подхватил slug | Проверить что `src/data/experts/{slug}.json` валиден, пересобрать |
| Белый экран на `/experts/` | partial-deploy-pitfall: залили только `experts/`, без `_astro/` | Перезалить всю `dist/` |
| 403 на `/experts/` | забыли `chown -R deploy:deploy` | SSH на VPS, выполнить `chown` |
| `lab-api` сломался | НЕ наш случай — wizard не трогает воркер |
