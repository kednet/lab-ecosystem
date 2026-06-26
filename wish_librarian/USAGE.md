# 📚 WishLibrarian — Полная инструкция

> ИИ-агент «Библиотекарь желаний» — парсит саморазвивающие книги с koob.ru, LiveLib,
> Лабиринта, Литреса и др., генерирует конспект, воркбук, советы, находит отзывы
> и научные статьи, отдаёт в `.md`/`.txt`/`.html`/`.pdf`/`.epub`/`.docx`.

---

## 📑 Содержание

1. [Быстрый старт (5 минут)](#-быстрый-старт-5-минут)
2. [Установка](#-установка)
3. [Конфигурация `.env`](#-конфигурация-env)
4. [Выбор AI-провайдера](#-выбор-ai-провайдера)
5. [CLI — все команды](#-cli--все-команды)
6. [Telegram-бот](#-telegram-бот)
7. [Структура папок с книгами](#-структура-папок-с-книгами)
8. [Добавление нового сайта-источника](#-добавление-нового-сайта-источника)
9. [Кеш AI-ответов](#-кеш-ai-ответов)
10. [Дедупликация по ISBN](#-дедупликация-по-isbn)
11. [Экспорт книг](#-экспорт-книг)
12. [Поиск по библиотеке](#-поиск-по-библиотеке)
13. [Диагностика `doctor`](#-диагностика-doctor)
14. [Частые вопросы](#-частые-вопросы)
15. [Где что лежит](#-где-что-лежит)

---

## 🚀 Быстрый старт (5 минут)

```bash
# 1. Клонировать и перейти в каталог
git clone <repo> && cd wish_librarian

# 2. Создать venv
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # Linux/Mac

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Скопировать .env
cp .env.example .env
# отредактировать .env (см. раздел «Конфигурация»)

# 5. Проверить установку
python -m agent.cli --doctor

# 6. Обработать первую книгу
python -m agent.cli --url "https://www.koob.ru/zeland/level1" --ai yandex
```

Готово. Книга появится в `output/library/Зеланд_Трансерфинг_реальности_Степень_I_2004/`.

---

## 💾 Установка

### Требования

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| Python    | 3.10    | 3.12+        |
| ОЗУ       | 256 МБ  | 512 МБ       |
| Диск      | 1 ГБ    | 5 ГБ+        |
| Сеть      | стабильный интернет | |

### Зависимости (уже в `requirements.txt`)

```
pydantic>=2, pydantic-settings, beautifulsoup4, lxml, requests, httpx,
loguru, tenacity, anthropic, click, rich, pyyaml, aiogram>=3
```

Опционально: `pandoc` (системный пакет) — для экспорта в PDF/EPUB/DOCX.

### Проверка после установки

```bash
python -m agent.cli --doctor
```

Если всё ✅ — можно работать.

---

## ⚙️ Конфигурация `.env`

Все настройки живут в `.env` в корне проекта. Полный список (см. `.env.example`):

### Провайдер ИИ (обязательно)

```env
# Какой ИИ использовать. Варианты: claude | yandex | gigachat | fallback
AI_PROVIDER=claude
```

### Anthropic Claude (если `AI_PROVIDER=claude`)

```env
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-5
CLAUDE_MAX_TOKENS=4096
CLAUDE_TEMPERATURE=0.7
```

→ Ключ: <https://console.anthropic.com/>

### YandexGPT (если `AI_PROVIDER=yandex`)

```env
YANDEX_API_KEY=AQVNxxxxx...
YANDEX_FOLDER_ID=b1gxxxxx...
YANDEX_MODEL=yandexgpt-lite
```

→ Ключ: <https://console.yandex.cloud/> → Service Account → API Key
→ Folder ID: header в Yandex Cloud → выбрать каталог → скопировать ID

### GigaChat (если `AI_PROVIDER=gigachat`)

```env
GIGACHAT_AUTHORIZATION_KEY=...   # base64(client_id:client_secret)
GIGACHAT_SCOPE=GIGACHAT_API_PERS # PERS для физлиц, CORP/B2B для компаний
GIGACHAT_MODEL=GigaChat          # GigaChat | GigaChat-Pro | GigaChat-Max
# Если корпоративный MITM мешает TLS:
GIGACHAT_VERIFY_SSL=false
```

→ Ключ: <https://developers.sber.ru/> → GigaChat API → Создать ключ

### Fallback (Yandex → GigaChat)

```env
AI_PROVIDER=fallback
# Нужны ОБА ключа: Yandex и GigaChat (либо один — тогда используется только он)
YANDEX_API_KEY=...
GIGACHAT_AUTHORIZATION_KEY=...
```

При сбое Yandex (HTTP 5xx/429/timeout) — автоматически вызывается GigaChat.

### Партнёрские программы (опционально)

```env
LITRES_PARTNER_ID=...     # Литрес
LABIRINT_PARTNER_ID=...   # Лабиринт
OZON_PARTNER_ID=...       # Ozon
```

### Пути и поведение

```env
OUTPUT_DIR=./output/library     # куда складывать книги
CACHE_DIR=./cache               # HTTP-кеш и AI-кеш
LOGS_DIR=./logs
REQUEST_DELAY=1.0               # пауза между HTTP-запросами (сек)
REQUEST_TIMEOUT=30
MAX_RETRIES=3
LOG_LEVEL=INFO
```

### Генерация контента

```env
ENABLE_COVER_DOWNLOAD=true
ENABLE_REVIEWS_SEARCH=true
ENABLE_SCIENTIFIC_SEARCH=true
SUMMARY_LANGUAGE=ru
```

---

## 🤖 Выбор AI-провайдера

| Провайдер   | Плюсы                                | Минусы                          | Когда выбирать |
|-------------|--------------------------------------|----------------------------------|----------------|
| `claude`    | Лучшее качество, контекст 200k       | Нужен VPN, дорого                 | Качество критично |
| `yandex`    | Дешевле Claude, нет VPN              | Более формальный стиль            | Основной fallback |
| `gigachat`  | Без VPN, в РФ                        | Лимиты на бесплатный тариф        | Из РФ без VPN |
| `fallback`  | Устойчивость: Yandex→GigaChat        | Дороже (две подписки)             | Продакшн |

Переключение на лету без правки `.env`:

```bash
python -m agent.cli --ai yandex --url <URL>
python -m agent.cli --ai gigachat --url <URL>
python -m agent.cli --ai fallback --url <URL>
```

---

## 🖥 CLI — все команды

### Главный флаг `--help`

```bash
python -m agent.cli --help
```

### Обработка одной книги

```bash
python -m agent.cli --url "https://www.koob.ru/zeland/level1"
```

### Батч (несколько URL)

В аргументах:
```bash
python -m agent.cli --url "URL1" --url "URL2" --url "URL3"
```

В файле (по одному на строку, `#` — комментарий):
```bash
python -m agent.cli --file urls.txt
```

### Полезные флаги

| Флаг | Что делает |
|------|------------|
| `--force` | Перепарсить даже если уже обработано |
| `--parse-only` | Только парсинг, без AI (экономия токенов) |
| `--no-ai-cache` | Игнорировать AI-кеш, всегда звать модель |
| `--ai {claude\|yandex\|gigachat\|fallback}` | Провайдер на лету |
| `--test` | Проверить AI-клиент и выйти |
| `--doctor` | Самодиагностика |
| `--list-sources` | Все поддерживаемые сайты |
| `--query "привычки"` | Поиск по библиотеке |
| `--export "pdf,epub"` | Экспортировать все книги в форматы |

### Примеры

```bash
# Перепарсить без AI
python -m agent.cli --url <URL> --parse-only

# Проверить подключение к GigaChat
python -m agent.cli --ai gigachat --test

# Найти все книги про привычки
python -m agent.cli --query "привычки"

# Экспортировать всю библиотеку в txt+html
python -m agent.cli --export "txt,html"
```

---

## 🤖 Telegram-бот

> Подробная пошаговая инструкция по созданию бота — в [TELEGRAM_BOT.md](./TELEGRAM_BOT.md).

Краткий старт:

```bash
set TELEGRAM_BOT_TOKEN=123456:ABC-DEF...        # Windows
export TELEGRAM_BOT_TOKEN=123456:ABC-DEF...     # Linux/Mac
python -m agent.telegram_bot
```

Команды в Telegram:

| Команда | Что делает |
|---------|------------|
| `/start`, `/help` | Справка |
| `/add <URL>` | Обработать книгу |
| `/cancel` | Отменить текущую обработку |
| `/list [N]` | Последние N книг |
| `/search <запрос>` | Поиск по библиотеке |
| `/book <название>` | Открыть summary.md |
| `/export <fmt> <название>` | Экспорт в txt/html/... |
| `/doctor` | Диагностика |

---

## 📂 Структура папок с книгами

После обработки в `OUTPUT_DIR/{Автор}_{Название}_{Год}_{ISBN-...}/` лежат:

```
📁 Зеланд_Трансерфинг_реальности_Степень_I_2004_ISBN-9785001467833/
├── metadata.json          ← всё о книге + пути + AI-провайдер
├── cover.jpg              ← обложка
├── summary.md             ← конспект (AI)
├── workbook.md            ← воркбук (AI)
├── practical_tips.md      ← практические советы (AI)
├── reviews.md             ← отзывы LiveLib + www.koob.ru
├── scientific.md          ← научные статьи с КиберЛенинки
├── buy_links.md           ← партнёрские ссылки
├── cover.jpg.note.md      ← (если обложку скачать не удалось)
└── raw/
    └── source.html        ← исходный HTML страницы
```

---

## 🗺 Добавление нового сайта-источника

Создайте YAML-карту в `agent/parsers/sites/`. Минимум:

```yaml
name: mysite
display: "Мой Сайт"
host_patterns:
  - "mysite.ru"
encoding: utf-8
selectors:
  title:           "css:h1.book-title"
  author:          "css:a.author"
  year:            "regex_in:css:span.year:\\d{4}"
  cover_url:       "css:img.cover@src"
  short_description: "css:div.description"
  isbn:            "@jsonld:isbn"
  chapters:        ["css:ol.chapters > li", "css:ul.chapters > li"]
  key_ideas:       "css:ul.ideas > li"
  quotes:          "css:blockquote.quote"
```

Поддерживаемые префиксы селекторов:

| Префикс | Пример | Смысл |
|---------|--------|-------|
| `css:` | `css:h1.title` | CSS-селектор |
| `@og:` | `@og:title` | `<meta property="og:title" content="…">` |
| `@content:` | `@content:meta[name=author]` | `<meta name=author content=…>` |
| `@attr:` | `@attr:img.src` | атрибут элемента (например, `src` у первой `<img>`) |
| `@split_title:` | `@split_title:css:h1:-:-` | разбить заголовок по ` - ` (автор / название) |
| `@url_slug:` | `@url_slug:` | slug из URL |
| `@jsonld:` | `@jsonld:isbn` | поле из JSON-LD `<script type="application/ld+json">` |
| `regex_in:` | `regex_in:css:div.year:\\d{4}` | regex по тексту элемента |

После создания карты перезапустите процесс — она подхватится автоматически.

```bash
python -m agent.cli --list-sources   # увидите ваш новый сайт
```

---

## 💾 Кеш AI-ответов

Каждый AI-ответ сохраняется в `cache/ai_responses/{fingerprint}/`.

При повторной обработке той же книги (например, перепарсили и обложка обновилась)
**AI-вызов не делается** — читается закешированный конспект.

Управление:

```bash
# Всегда вызывать AI заново
python -m agent.cli --url <URL> --no-ai-cache

# Очистить кеш одной книги
# (вызывается из Python)
python -c "from agent.models import BookInfo; \
           from agent.storage import ai_cache; \
           b = BookInfo(title='...', author='...', year=..., isbn='...'); \
           ai_cache.clear_cache_for(b)"
```

Версии промтов (`PROMPT_VERSIONS` в `agent/storage/ai_cache.py`) автоматически
инвалидируют кеш при изменении формулировок.

---

## 🔁 Дедупликация по ISBN

Если две книги имеют **одинаковый ISBN** или **одинаковые (title, author, year)**,
агент не создаст вторую папку — он присоединит новые файлы к существующей.

Fingerprint считается в `agent/utils/normalize.py::book_fingerprint()`:

- ISBN есть → `isbn:9785001467833`
- ISBN нет → `fp:sha1(normalize(title)+normalize(author)+year)[:12]`

Поведение в `agent/librarian.py::process_book()`:

```
⚠️  Эта книга уже есть под именем «Зеланд_..._2004_ISBN-9785001467833» (fingerprint совпал)
```

---

## 📤 Экспорт книг

### Из CLI (все книги разом)

```bash
python -m agent.cli --export "txt,html"           # txt + html
python -m agent.cli --export "pdf,epub,docx"      # нужны pandoc
python -m agent.cli --export "txt,html,pdf,epub"  # всё что можно
```

### Из Python (одна книга)

```python
from pathlib import Path
from agent.export import export_book

folder = Path("output/library/Зеланд_Трансерфинг_2004_...")
files = export_book(folder, ["txt", "html", "pdf"])
for f in files:
    print(f)
```

### Форматы

| Формат | Нужен pandoc? |
|--------|---------------|
| `txt`  | нет (всегда работает) |
| `html` | нет (собственный мини-конвертер) |
| `pdf`  | да (`apt install pandoc` / `brew install pandoc` / скачать с [pandoc.org](https://pandoc.org/)) |
| `epub` | да |
| `docx` | да |

---

## 🔎 Поиск по библиотеке

```bash
python -m agent.cli --query "трансерфинг"
```

Из Python:

```python
from pathlib import Path
from agent.search import search_library

results = search_library("привычки", Path("./output/library"))
for folder, score, snippet in results:
    print(f"{score:3d}  {folder.name}  {snippet[:80]}")
```

Алгоритм: TF (частота токенов) + буст за совпадение в title/author.

---

## 🩺 Диагностика `doctor`

```bash
python -m agent.cli --doctor
```

Проверяет:
1. Python и платформа
2. Все 13+ зависимостей
3. Карты парсера (загружено N шт.)
4. AI-провайдер (отвечает ли на тест)
5. Использование диска (output/cache/logs)
6. Количество обработанных книг
7. Рекомендации

---

## ❓ Частые вопросы

### «Нет ключей для AI-провайдера»
Заполните `.env` (см. раздел «Конфигурация»). Для провайдера Claude —
`ANTHROPIC_API_KEY`, для Yandex — `YANDEX_API_KEY` + `YANDEX_FOLDER_ID`,
для GigaChat — `GIGACHAT_AUTHORIZATION_KEY`.

### «GigaChat: SSL verify failed»
Это корпоративный MITM. Добавьте в `.env`:
```env
GIGACHAT_VERIFY_SSL=false
```

### «httpx: SOCKS proxy error»
Библиотека `httpx` не умеет в SOCKS4 (от VPN-клиента). Отключите VPN или
добавьте HTTP-прокси: `set HTTPS_PROXY=http://127.0.0.1:8080`.

### «Telegram-бот не стартует»
Проверьте:
```bash
python -m agent.cli --doctor         # AI-провайдер работает?
echo %TELEGRAM_BOT_TOKEN%            # токен установлен?
```

### «Как удалить дубликаты книг?»
Уже не должно быть (fingerprint). Если есть — удалите папки вручную,
оставив одну.

### «Где логи?`
`logs/agent.log` (создаётся автоматически). Формат — `loguru`.

### «Как добавить новый сайт?»
YAML-карта в `agent/parsers/sites/` (см. раздел «Добавление нового сайта»).

### «Книги нет в библиотеке, но она в /list»
Удалите папку-пустышку без `summary.md`.

---

## 🗂 Где что лежит

```
wish_librarian/
├── .env                    ← конфигурация (секреты!)
├── .env.example            ← шаблон .env
├── requirements.txt
├── agent/
│   ├── cli.py              ← CLI (Click)
│   ├── librarian.py        ← главный оркестратор WishLibrarian
│   ├── config.py           ← pydantic Settings
│   ├── models.py           ← BookInfo, BookAssets, …
│   ├── doctor.py           ← /doctor
│   ├── search.py           ← /query
│   ├── export.py           ← /export
│   ├── telegram_bot.py     ← /start, /add, /list, …
│   ├── ai/                 ← AI-клиенты
│   │   ├── base.py         ← BaseAIClient, AIClientError
│   │   ├── claude_client.py
│   │   ├── yandex_client.py
│   │   ├── gigachat_client.py
│   │   ├── fallback.py     ← Yandex → GigaChat
│   │   └── factory.py      ← get_ai_client()
│   ├── parsers/            ← парсеры сайтов
│   │   ├── koob_parser.py
│   │   ├── universal_parser.py
│   │   ├── llm_parser.py   ← LLM-стратегия для неизвестных сайтов
│   │   ├── reviews_parser.py
│   │   ├── scientific_parser.py
│   │   ├── affiliate_links.py
│   │   ├── prompts.py
│   │   └── sites/          ← YAML-карты сайтов
│   ├── storage/            ← работа с файлами
│   │   ├── file_manager.py
│   │   ├── ai_cache.py     ← кеш AI-ответов
│   │   └── templates.py
│   └── utils/
│       ├── normalize.py    ← fingerprint, нормализация
│       ├── http_client.py
│       └── logger.py
├── output/library/         ← результат (книги)
├── cache/                  ← HTTP-кеш + AI-кеш
├── logs/                   ← логи
└── tests/                  ← тесты (33 теста, все ✅)
    ├── test_koob_parser.py
    ├── test_universal_parser.py
    ├── test_extras.py
    └── test_ai_factory.py
```

---

## 🧪 Запуск всех тестов

```bash
python tests/test_koob_parser.py        # 6 тестов парсера koob
python tests/test_universal_parser.py  # 7 тестов universal parser
python tests/test_extras.py            # 12 тестов новых модулей
python tests/test_ai_factory.py        # 8 тестов AI-провайдеров
```

Итого: **33 теста**, все зелёные.

---

См. также: [TELEGRAM_BOT.md](./TELEGRAM_BOT.md) — пошаговая инструкция по
созданию и деплою Telegram-бота.
