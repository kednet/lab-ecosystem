# Настройка постинга в Яндекс.Дзен для Лаборатории Желаний

> Целевой домен: **https://app.pulab.ru**
> RSS-лента: **https://app.pulab.ru/detector/feed.xml**

## Что уже сделано

1. В `publisher_skill/scripts/post_channels.py` доработан адаптер Дзена:
   - генерирует RSS с `content:encoded` (полный HTML-контент),
   - добавляет `<enclosure>` + `<media:thumbnail>` для обложки,
   - хранит последние 10 материалов (не перезаписывает одной записью),
   - `guid` стабильный — не создаёт дубли при обновлении,
   - fallback-обложка: `https://app.pulab.ru/cover.jpg`.
2. В `templates/post-channels/detector.json` заменена ссылка на существующий `cover.jpg`.
3. Файл `lab_site/public/detector/feed.xml` готов к деплою на VPS.

---

## Пошаговая настройка в Дзен Studio

### 1. Открыть Дзен Studio

- Перейти на https://studio.dzen.ru (авторизоваться под аккаунтом, к которому будет привязан канал).

### 2. Добавить канал по RSS

1. **Каналы** → **Добавить канал**.
2. Выбрать **Внешний RSS**.
3. Вставить URL: `https://app.pulab.ru/detector/feed.xml`.
4. Нажать **Подключить** / **Продолжить**.

### 3. Подтвердить право на домен `app.pulab.ru`

Дзен предложит один из способов верификации. Рекомендуется **HTML-файл**:

1. Скачать предложенный файл, например `dzen-XXXXXX.html`.
2. Положить его в `C:\Users\kfigh\lab_site\public\`.
3. Пересобрать и задеплоить сайт.
4. Убедиться, что файл открывается по `https://app.pulab.ru/dzen-XXXXXX.html`.
5. Вернуться в Studio и нажать **Подтвердить**.

Альтернатива — метатег в `<head>` на главной. Для Astro добавить в `src/layouts/...` или в `src/pages/index.astro`:

```astro
<head>
  <meta name="dzen-verification" content="ЗНАЧЕНИЕ_ИЗ_STUDIO" />
</head>
```

### 4. Настроить канал

- **Название канала**: `ЛАБОРАТОРИЯ ЖЕЛАНИЙ` (или «Детектор желаний»).
- **Описание**: коротко — про тест, психологию желаний, книги.
- **Аватар / логотип**: загрузить `cover.jpg` или отдельный логотип.
- **Тематика**: Психология, саморазвитие, отношения.

### 5. Настроить импорт статей

В настройках RSS-канала Дзена:

- источник: `https://app.pulab.ru/detector/feed.xml`
- период обновления: автоматически (обычно каждые 15–60 минут)
- после подключения Дзен сам подтянет статьи из `<item>`.

**Важно:** Дзен не публикует автоматически — он импортирует в черновики. Каждую статью нужно:
1. Открыть в черновиках.
2. Проверить обложку, анонс, ссылку.
3. Нажать **Отправить на модерацию** / **Опубликовать**.

### 6. Что будет в импортированной статье

Из RSS Дзен возьмёт:
- `<title>` → заголовок статьи
- `<description>` → короткое описание / анонс
- `<content:encoded>` → основной текст (HTML с абзацами и ссылками)
- `<enclosure>` + `<media:thumbnail>` → обложка
- `<link>` → источник (ссылка на `app.pulab.ru/detector/`)

---

## Как публиковать новый материал в Дзен

После того как канал настроен, повторный постинг делается одной командой:

```powershell
cd C:\Users\kfigh\publisher_skill
python scripts/post_channels.py --content detector --channels zen
```

Затем обязательно:

```powershell
cd C:\Users\kfigh\lab_site
npm run build
.\deploy-vps.ps1 -VpsHost 89.108.88.74
```

> **Важно:** `deploy-vps.ps1` сейчас не работает автоматически:
> 1. Его encoding был повреждён — пересохранён с BOM.
> 2. В PATH нет `rsync` — скрипт требует Git for Windows/WSL.
>
> Ручная альтернатива (из `lab_site/dist`):
> ```bash
> cd /c/Users/kfigh/lab_site/dist
> ssh -i ~/.ssh/lab_vps deploy@89.108.88.74 "rm -rf /var/www/lab-site/dist/*; mkdir -p /var/www/lab-site/dist"
> tar czf - . | ssh -i ~/.ssh/lab_vps deploy@89.108.88.74 "tar xzf - -C /var/www/lab-site/dist"
> ssh -i ~/.ssh/lab_vps deploy@89.108.88.74 "sudo nginx -t && sudo systemctl reload nginx"
> ```

После деплоя RSS обновится на `https://app.pulab.ru/detector/feed.xml`, Дзен подтянет новый `<item>` в черновики.

> Примечание: сейчас RSS заточен под `/detector/`. Если захочешь отдельную ленту для блога / аудио / книг — нужно будет расширить `post_channels.py` и Astro-роутинг.

---

## Проверки

- RSS доступен: `https://app.pulab.ru/detector/feed.xml`
- XML валиден (проверено через `xml.etree.ElementTree`).
- Обложка доступна: `https://app.pulab.ru/cover.jpg`

## Возможные проблемы

| Симптом | Решение |
|---------|---------|
| Дзен не видит RSS | Проверить, что `feed.xml` отдаёт `Content-Type: application/rss+xml; charset=utf-8`. В nginx добавить: `types { application/rss+xml rss xml; }`. |
| Обложка не подтягивается | Убедиться, что `cover.jpg` отдаётся с `Content-Length` и `image/jpeg`. |
| Дзен не публикует автоматически | Это нормально — Дзен импортирует в черновики, публикация ручная. |
| Дубли статей | `guid` стабильный, но если поменять `title`, Дзен создаст новый материал. |

---

## Следующие шаги (опционально)

1. Создать отдельные RSS-ленты для `/audio/`, `/library/`, `/blog/`.
2. Добавить `<category>` в `<item>` для лучшей индексации.
3. Настроить автоматический постинг по расписанию (через `CronCreate` или планировщик VPS).
4. Подключить аналитику Дзена для отслеживания переходов.
