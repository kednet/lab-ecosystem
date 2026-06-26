# Подскил: EXPERTS WIZARD (добавление эксперта на сайт)

## Назначение

Полуавтоматический пайплайн «дай имя или YouTube-ссылку → черновик карточки → ручная правка → деплой на сайт» для раздела `/experts/` на lab_site. Три команды вместо одной жирной `/expert card`:

| Команда | Что делает |
|---------|-----------|
| `/experts add "Имя"` или `/experts add "https://youtube.com/..."` | Собрать мини-черновик (имя, 1-2 цитаты, соцсети, фото), сохранить в `experts/{slug}.md` со `status: draft` |
| `/experts edit {slug}` | Показать черновик, подсветить пустые обязательные поля, принять правки |
| `/experts deploy {slug}` | По команде «готово»: sync в lab_site + build + tar + scp на VPS + smoke-проверки |

## Принципы

1. **Минимум автоматики** — `/experts add` НЕ собирает 50 регалий, 20 книг, schema.json целиком. Только базовый скелет, который видно на сайте. Остальное — руками в `/experts edit`.
2. **Один проход = одна правка** — после `/experts add` пользователь смотрит черновик, говорит что менять, я патчу по секциям.
3. **Деплой = явная команда** — `/experts deploy` запускается только когда пользователь сказал «готово». Никаких автодеплоев.
4. **Идемпотентность** — повторный `/experts add {slug}` для существующего файла = warning + предложение править в `/experts edit`. Никаких молчаливых перезаписей.
5. **draft / published** — статус в frontmatter. `draft` нельзя деплоить. `published` = готово к продакшну.

## Алгоритм по командам

### 1. `/experts add {Имя|URL}`

Загрузи: `prompts/expert-add.md`.

Краткий алгоритм:
1. Определи вход: имя vs YouTube-ссылка (`https://(www.|m.)?youtube.com` или `youtu.be`).
2. Slug через `_slugify` (из `lab_site/python-service/loaders/experts.py:204-221`, чтобы совпадало с парсером).
3. Проверь `experts/{slug}.md` — если есть, спроси «перезаписать?».
4. **Name-режим:**
   - WebSearch: `"{Имя}" официальный сайт` + `"{Имя}" биография`
   - WebFetch первого результата → bio, фото, должность, соцсети
   - YouTube: топ-1 видео по запросу `"{Имя}" лекция интервью` → транскрипт → 1 цитата через YandexGPT-фабрику из `wish_librarian/agent/ai/factory.py`
5. **YT-режим (URL):**
   - Извлеки `video_id` или `channel_id`
   - `videos.list` или `channels.list` → channelTitle как `name` кандидат
   - Транскрипт → 1 цитата
   - WebSearch по channelTitle → подтвердить личность
6. Сгенерируй `experts/{slug}.md` по `templates/expert-card.md` со всеми обязательными полями:
   - `name:` в frontmatter (не пустое, кириллица если возможно)
   - `slug: {slug}` в frontmatter
   - `tags:` списком в frontmatter (НЕ inline `#тэг`)
   - `status: draft`
   - столбец `**Должность / главная роль**` в `## 📋 Основное`
   - блок `## Schema.org` с JSON-LD Person (минимально: name, jobTitle, url, sameAs, knowsAbout, image)
7. Валидация: `load_expert('{slug}')` из `lab_site/python-service/loaders/experts.py:225-306` → выведи пустые поля.
8. Покажи пользователю что нашлось, попроси сказать «готово» или «правь X».

### 2. `/experts edit {slug}`

Загрузи: `prompts/expert-edit.md`.

Краткий алгоритм:
1. Прочитай `experts/{slug}.md` → покажи пользователю.
2. Прогони `load_expert('{slug}')` → список пустых полей (description, jobTitle, image, email, sameAs, knowsAbout, quotes, tags, score).
3. Подсвети что **критично** для рендера (без этого страница пустая):
   - `name` в frontmatter
   - `tags` (хотя бы 1 тег)
   - `image` (если нет — будет fallback-аватар с инициалом)
   - `description` (если пусто — пустая карточка)
   - хотя бы 1 цитата в `## 💬 Цитаты`
4. Если пользователь говорит «добавь секцию X» или «замени Y на Z» — Edit точечно.
5. Если пользователь говорит «готово» → замени `status: draft` → `status: published` в frontmatter. Скажи «теперь `/experts deploy {slug}`».

**НЕ делаем:** AI-суммаризация всего профиля, авто-добавление регалий, поиск фото в гугле. Только ручные правки.

### 3. `/experts deploy {slug}`

Загрузи: `prompts/expert-deploy.md`.

Запускает `python lab_site/scripts/deploy_experts.py {slug}`:

1. Preflight (slug существует, `status: published`, ssh-ключ на месте, ssh-ping до VPS).
2. `python lab_site/scripts/sync_reviews_hub.py --experts --verbose`.
3. `cd lab_site && npm run build` (~60-90 сек с `prebuild: sitemap+spheres`).
4. `python C:/Users/kfigh/temp/rebuild_deploy.py` → `C:/Users/kfigh/temp/lab-site-deploy.tar.gz`.
5. `scp -i ~/.ssh/lab_vps lab-site-deploy.tar.gz root@89.108.88.74:/tmp/`.
6. Атомарная распаковка на VPS с backup + `chown -R deploy:deploy`.
7. 4 smoke-проверки через `curl`.
8. Печать команды отката.

**Не трогает:** lab-api (Node-воркер), nginx config, `/etc/lab-site.env`.

## Связь с `/experts/` (страница lab_site)

После первого успешного `/experts deploy` нужно переключить `lab_site/src/pages/experts/index.astro:32`:

```diff
- const isComingSoon = true;
+ const isComingSoon = false;
```

Сделать один раз отдельным коммитом + деплоем до первого `/experts deploy` ИЛИ в рамках первого деплоя. Без этого каталог покажет заглушку, даже если JSON-ы экспертов валидные.

## 🔗 Интеграция

### С lab_site

- Парсер: `lab_site/python-service/loaders/experts.py` — единственный источник истины.
- Синхронизация: `lab_site/scripts/sync_reviews_hub.py` — вызывается из deploy.
- Лоадер: `lab_site/src/lib/experts.ts` — `import.meta.glob` для SSG.
- Страницы: `lab_site/src/pages/experts/index.astro`, `[slug].astro`.

### С expert-reviews-hub

- Парсер YouTube: `scripts/parse_youtube.py` — паттерн urllib+ssl, youtube_transcript_api, YandexGPT-фабрика.
- Шаблон: `templates/expert-card.md` (Markdown-скелет).
- Schema: `templates/expert-schema.json` (JSON-LD Person).
- Существующий подскил: `sub-skills/experts.md` — НЕ ломаем, wizard живёт рядом.

### С wish_librarian

- LLM-фабрика: `wish_librarian/agent/ai/factory.py:get_llm_client(provider="yandex")` — для 1 цитаты.
- WL output (`C:\Users\kfigh\wish_librarian\output\`) — НЕ читаем в этой версии. В будущем — `/experts link` найдёт упоминания.

## ⚠️ Что НЕ делаем в wizard (явно)

- ❌ Полная биография (только краткая для карточки)
- ❌ 50 регалий (только то что WebFetch найдёт)
- ❌ Список всех книг эксперта (только если есть в WL)
- ❌ Подкасты/курсы/VK (только основное)
- ❌ Скоринг авторитетности (score = 0 или ставит пользователь)
- ❌ Упоминания в СМИ (отдельный режим `/expert mentions`)
- ❌ Связь с книгами WL (отдельный режим `/expert link`)

Это всё есть в существующих режимах `/expert card/mentions/resources/link`. Wizard — лёгкий путь «черновик на сайт за 15 минут», не замена полному сбору данных.

## 🚀 Быстрый старт

```
/experts add "Марк Розин"
# → черновик experts/mark-rozin.md со status: draft

/experts edit mark-rozin
# → пользователь правит руками, говорит «готово»

/experts deploy mark-rozin
# → sync + build + tar + scp + smoke
```

Или с YouTube-ссылкой:

```
/experts add "https://www.youtube.com/watch?v=ABC123"
# → извлечь video_id → channelTitle → 1 цитата → черновик

/experts edit abc-author
/experts deploy abc-author
```

## 📚 Дополнительно

- `prompts/expert-add.md` — детальный алгоритм сбора
- `prompts/expert-edit.md` — что подсвечивать при правке
- `prompts/expert-deploy.md` — деплой-инструкция
- `scripts/add_expert.py` — CLI для `/experts add`
- `../lab_site/scripts/deploy_experts.py` — CLI для `/experts deploy`
