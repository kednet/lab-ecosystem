# Промпт: `/experts add {Имя|URL}` — собрать мини-черновик карточки эксперта

## Назначение

Из входа (имя или YouTube-ссылка) собрать **минимальную** карточку эксперта для сайта. **Не** полная биография — только то, что видно на карточке `/experts/{slug}/`. Остальное пользователь добавит вручную через `/experts edit`.

## Вход

- **Имя эксперта** (например, `"Марк Розин"`) **или**
- **YouTube-ссылка** (видео или канал, например, `"https://www.youtube.com/watch?v=ABC123"` или `"https://www.youtube.com/@expert_channel"`)

## Алгоритм

### Шаг 1. Определи тип входа

```
if вход начинается с "https://" and содержит "youtube.com" or "youtu.be":
    mode = "youtube"
else:
    mode = "name"
```

### Шаг 2. Slug

Используй `_slugify` из `lab_site/python-service/loaders/experts.py:204-221` (транслитерация кириллицы + lowercase + дефисы).

```python
from loaders.experts import _slugify
slug = _slugify(name)  # "Марк Розин" → "mark-rozin"
```

**Важно:** если у входа уже есть slug (например, в frontmatter эксперт-карточки или в имени канала YT) — используй его.

### Шаг 3. Проверка существующего файла

Если `experts/{slug}.md` уже существует:
- Прочитай, проверь `status` в frontmatter
- Если `status: published` → СТОП. Скажи «уже опубликован, правь через `/experts edit {slug}`»
- Если `status: draft` → спроси «Перезаписать черновик?»

### Шаг 4. Сбор данных

#### 4.1. Name-режим

**4.1.1. WebSearch** — серия из 3 запросов:

```
WebSearch: "{Имя}" официальный сайт
WebSearch: "{Имя}" биография
WebSearch: "{Имя}" "{специализация}" (если понятна из контекста)
```

**4.1.2. WebFetch** — топ-1 результат первого запроса (обычно это оф. сайт). Извлеки:

| Поле | Где искать |
|------|-----------|
| **name** | `<title>` или `og:title` или `<h1>` |
| **jobTitle** | первый `<p>` после `<h1>` или meta `og:description` |
| **description** | meta `description` или первый абзац `<article>` |
| **image** | meta `og:image` или `<img>` в hero |
| **url** | текущий URL |
| **email** | текст страницы "mailto:" или regex `[\w.-]+@[\w.-]+\.\w+` |
| **sameAs** | все `<a>` ссылающиеся на vk.com, t.me, youtube.com, facebook.com, instagram.com |

Если оф. сайт не нашёлся — пропусти шаг, оставь пустые поля.

**4.1.3. YouTube (1 цитата)** — `parse_youtube.py` паттерн:

```python
# 1) Найди топ-1 видео по запросу
videos = yt_search_videos(f"{name} лекция интервью", max_results=5)

# 2) Возьми самое популярное
if videos:
    top = videos[0]
    # 3) Получи транскрипт
    snippets = yt_get_transcript(top['id'])
    # 4) Склей первые 8000 символов
    text = transcript_to_text(snippets, max_chars=8000)
    # 5) Через YandexGPT-фабрику вытащи 1 цитату + контекст
    quote_data = llm_extract_quote(name, text)
```

Промпт для LLM (YandexGPT через `wish_librarian/agent/ai/factory.py`):

```
Найди в транскрипте видео ОДНУ яркую цитату {Имя} (1-2 предложения, до 200 слов),
которая лучше всего раскрывает его/её подход.
Верни JSON:
{"quote": "...", "context": "название видео / лекция / интервью", "year": 2024}
```

Если видео нет или транскрипт пустой — оставь цитату пустой, пользователь добавит руками.

#### 4.2. YT-режим (URL)

**4.2.1. Парсинг URL:**

```
youtube.com/watch?v=VIDEO_ID         → mode = "video"
youtube.com/@CHANNEL_HANDLE          → mode = "channel"
youtube.com/channel/CHANNEL_ID       → mode = "channel"
youtu.be/VIDEO_ID                    → mode = "video"
```

**4.2.2. Извлечение данных:**

- Если **video**:
  - `videos.list?part=snippet&id=VIDEO_ID` → `snippet.channelTitle`, `snippet.title`, `snippet.description`
  - Из description вытащи соцсети (regex `https?://(vk\.com|t\.me|youtube\.com|...)[\w/._-]+`)
  - `channels.list?part=snippet,statistics&id=CHANNEL_ID` → реальное имя канала, фото, подписчики
  - Транскрипт → 1 цитата как в 4.1.3
- Если **channel**:
  - `channels.list?part=snippet,statistics&id=...` → channelTitle, description, thumbnails
  - Имя канала = кандидат в `name`. Подтверди через WebSearch `"{channelTitle}" психолог` (или другая ниша).

### Шаг 5. Генерация `experts/{slug}.md`

Заполни шаблон `templates/expert-card.md` **по минимуму**, но **со всеми обязательными полями**:

```markdown
---
slug: {slug}
name: "{Имя}"              # обязательно, кириллица если есть
type: expert
status: draft              # draft → published после /experts edit
generated_at: {ISO}
tags: [тэг1, тэг2]         # список, не inline #тэг
score: 0                   # пользователь поставит сам
---

# {Имя}

**{Должность / главная роль}**            # ← КРИТИЧНО для парсера

> {Краткое описание — 1-2 предложения, что нашлось через WebFetch}

![{Имя}]({URL фото или пусто})

## 📋 Основное

| Поле | Значение |
|------|----------|
| **ФИО** | {Имя} |
| **Должность / главная роль** | {jobTitle} |
| **Сфера** | {ниша} |
| **Специализация** | {knowsAbout через запятую} |
| **Сайт** | [{url}]({url}) |
| **Email** | {email или пусто} |

## 🎓 Образование и регалии
- {пусто — пользователь добавит сам}

## 🎙️ Медиа

- [{platform}]({url})         # все найденные соцсети

## 💬 Цитаты

> «{найденная цитата}»
> — {context}, {year}

## 🔗 Связь с Лабораторией желаний
- **Книги в библиотеке WL:** нет (проверить через grep C:\Users\kfigh\wish_librarian\output\*\summary.md)

## Schema.org

```json
{
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "{Имя}",
  "jobTitle": "{должность}",
  "url": "{url}",
  "image": "{image_url}",
  "sameAs": [{список соцсетей}],
  "knowsAbout": [{специализации}]
}
```
```

### Шаг 6. Валидация через парсер lab_site

```python
import sys
sys.path.insert(0, r"C:\Users\kfigh\lab_site\python-service")
from loaders.experts import load_expert

card = load_expert('{slug}')
if card is None:
    print("ERROR: парсер не смог прочитать файл")
else:
    print(f"✅ name: {card.name}")
    print(f"   jobTitle: {card.jobTitle or '❌ ПУСТО'}")
    print(f"   description: {(card.description or '')[:80] or '❌ ПУСТО'}")
    print(f"   image: {card.image or '❌ ПУСТО'}")
    print(f"   tags: {card.tags or '❌ ПУСТО'}")
    print(f"   quotes: {len(card.quotes)} шт")
    print(f"   sameAs: {len(card.sameAs)} ссылок")
```

### Шаг 7. Вывод пользователю

```
✅ Черновик: expert-reviews-hub/experts/{slug}.md (status: draft)

📊 Что нашлось автоматически:
  • Имя: {name}
  • Должность: {jobTitle или пусто}
  • Фото: {image_url или 'плейсхолдер'}
  • Соцсети: {N ссылок}
  • Цитаты: {N шт}

⚠️ Что нужно заполнить вручную (/experts edit {slug}):
  • {список пустых критичных полей}

👉 Дальше:
  1. Скажи «правь {секция}» — поправлю точечно
  2. Скажи «готово» — переведу в status: published, можно деплоить
  3. Скажи «отмена» — удалю черновик
```

## ⚠️ Этические ограничения

- **Не выдумывай факты.** Если что-то не нашлось через WebFetch/WebSearch — оставляй пустое поле, пользователь добавит.
- **Email — только публичный** с сайта эксперта (видимый без логина).
- **Фото — только если есть на оф. сайте** (используй прямую ссылку, не google-поиск).
- **Цитата — только дословная из транскрипта**, не пересказ.
- **YMYL-контент:** если эксперт — психолог/врач/коуч, добавь тег `психолог` или `коуч` — на сайте покажется дисклеймер автоматически.

## 🔧 Что используем из существующего кода

| Что | Где | Зачем |
|-----|-----|-------|
| `_slugify` | `lab_site/python-service/loaders/experts.py:204-221` | Транслитерация |
| `load_expert` | `lab_site/python-service/loaders/experts.py:225-306` | Валидация черновика |
| `urllib.request + ssl._create_unverified_context()` | `expert-reviews-hub/scripts/parse_youtube.py:157-175` | Обход корп. MITM |
| `yt_search_videos`, `yt_get_transcript`, `transcript_to_text` | `parse_youtube.py:178-227` | YT-поиск и транскрипт |
| `summarize_with_ai` | `parse_youtube.py:314-377` | YandexGPT-фабрика |
| `get_llm_client(provider="yandex")` | `wish_librarian/agent/ai/factory.py` | LLM-обёртка |
| Шаблон | `expert-reviews-hub/templates/expert-card.md` | Скелет карточки |
