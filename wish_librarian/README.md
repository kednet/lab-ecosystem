# 📚 WishLibrarian — ИИ-агент «Библиотекарь желаний»

Автоматический сборник книг по саморазвитию и исполнению желаний. Парсит книги с Koob.ru, генерирует конспекты и воркбуки через AI, собирает научные статьи, отзывы и партнёрские ссылки — и складывает всё в структурированную библиотеку.

## 🤖 Провайдеры ИИ

WishLibrarian поддерживает **четыре** AI-провайдера на выбор через `AI_PROVIDER` в `.env`:

| Провайдер | Где взять ключ | Скорость | Качество текста | Доступ из РФ |
|-----------|----------------|----------|-----------------|--------------|
| **Claude** (Anthropic) | [console.anthropic.com](https://console.anthropic.com/settings/keys) | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⚠️ нужен VPN |
| **YandexGPT** | [console.yandex.cloud](https://console.yandex.cloud/) | ⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ |
| **GigaChat** (Сбер) | [developers.sber.ru](https://developers.sber.ru/) | ⭐⭐⭐ | ⭐⭐⭐ | ✅ |
| **fallback** | Yandex + GigaChat | — | — | ✅ |

Режим **`fallback`** сначала пробует YandexGPT, при сетевой/5xx/429 ошибке автоматически переключается на GigaChat. Самый надёжный режим для продакшна.

## 🚀 Возможности

- **Универсальный парсер** книг — поддержка koob.ru, livelib, labirint, litres, author.today + любой сайт с Open Graph / Schema.org (декларативно, через YAML-карты)
- **LLM-стратегия для неизвестных сайтов** — если YAML-карта не сработала и OG-фолбэк дал мало полей, отправляет обрезанный HTML в LLM и парсит JSON-ответ
- **Конспекты** через AI по единому шаблону
- **Воркбуки** с практическими упражнениями (v2: 10 секций — самоанализ, **поля для рукописных ответов**, практика, **кейс-сценарии**, **if-then планы**, 4-недельный план, **30-дневный трекер привычек**, рефлексия, бонус-микро-привычки)
- **Научные статьи** с КиберЛенинки
- **Отзывы** с LiveLib + www.koob.ru
- **Партнёрские ссылки** на Литрес, Лабиринт, Ozon
- **Кеш AI-ответов** — повторный вызов той же книги читается с диска (по fingerprint + версии промта)
- **Дедупликация по ISBN** — одна книга = одна папка, даже если URL разные
- **Поиск по библиотеке** (`--query`) — TF-скоринг + буст за совпадение в title/author
- **Экспорт** (`--export`) в txt/html/pdf/epub/docx
- **Самодиагностика** (`--doctor`) — Python, зависимости, AI-провайдер, диск
- **Telegram-бот** — `/add URL`, `/list`, `/search`, `/book`, `/export`, `/template`, `/doctor`, inline-кнопки
- **Внешние шаблоны** (v2) — конспекты/воркбуки/советы в `.md` + YAML, легко править без кода
- **Стиль письма** (v2) — `WRITING_TONE` (FORMAL/CASUAL/COACHING) × `WRITING_LENGTH` × `WRITING_AUDIENCE` в `.env` или CLI
- **Fallback** между провайдерами AI
- **Авто-детект кодировки** (utf-8 / cp1251)
- **Обработка ошибок** — продолжает работу при сбоях
- **Логирование** в консоль и в файл

## 🌐 Поддерживаемые источники книг

Парсер автоматически определяет источник по URL. Чтобы посмотреть весь список:

```bash
python -m agent.cli --list-sources
```

| Карта            | Сайт                                  | URL-паттерн                                    |
|------------------|---------------------------------------|------------------------------------------------|
| `koob_www`       | Koob.ru (основной, www)               | `https://www.koob.ru/{author}/{book}`          |
| `koob_oko`       | Koob.ru (legacy oko)                  | `https://oko.koob.ru/{book}/`                  |
| `livelib`        | LiveLib.ru                            | `https://www.livelib.ru/book/{id}`             |
| `labirint`       | Лабиринт                              | `https://www.labirint.ru/books/{id}`           |
| `litres`         | Литрес                                | `https://www.litres.ru/book/...`               |
| `author_today`   | Author.Today                           | `https://author.today/...`                     |
| `generic`        | Любой сайт с Open Graph / JSON-LD     | `*`                                            |

### Добавить новый источник

Просто положите `.yaml` файл в `agent/parsers/sites/`. Пример:

```yaml
name: my_site
display: My Cool Bookstore
host_patterns:
  - "^https?://(www\\.)?mybookstore\\.com/"
encoding: utf-8
strategy: hybrid
selectors:
  title:
    - "css:h1.book-title"
    - "@og:title"
  author:
    - "css:.author a"
    - "@og:book:author"
  cover:
    - "@og:image"
  short_description:
    - "css:.description p"
    - "@content:meta[name=description]"
```

Доступные правила:

| Правило                       | Что делает                                                |
|-------------------------------|-----------------------------------------------------------|
| `css:селектор`                | `element.text`                                            |
| `css:ul > li`                 | `list[element.text]` (список)                             |
| `css:h2:has-text(слово)~ol li`| Найти `<h2>` с подстрокой, взять следующий `<ol><li>`     |
| `@attr:src:img`               | `<img src=...>`                                           |
| `@og:title`                   | `<meta property="og:title">`                              |
| `@og:book:author`             | `<meta property="og:book:author">`                        |
| `@content:meta[name=...]`     | `<meta name="..." content="...">`                         |
| `@split_title:first`/`last`   | Разбить `<title>` по ` - `                                |
| `@url_slug:1`                 | Первый сегмент URL-пути, humanize                         |
| `@jsonld:title`               | Извлечь из `<script type="application/ld+json">`          |
| `regex_in:title:паттерн`      | Поиск регулярки в `<title>`                               |
| `regex_in:full:паттерн`       | Поиск регулярки в полном тексте                           |

При следующем запуске карта подхватится автоматически.

## 📦 Установка

```bash
git clone <repo> wish_librarian
cd wish_librarian
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# отредактируйте .env
```

## 🛠 Использование

```bash
# Обработать одну книгу (провайдер берётся из .env → AI_PROVIDER)
python -m agent.cli --url "https://oko.koob.ru/transerfing_realnosti/"

# Переопределить провайдера на лету
python -m agent.cli --ai yandex --url "https://oko.koob.ru/..."
python -m agent.cli --ai gigachat --url "https://oko.koob.ru/..."
python -m agent.cli --ai fallback --url "https://oko.koob.ru/..."

# Несколько книг
python -m agent.cli --url "URL1" --url "URL2"

# Из файла
python -m agent.cli --file urls.txt

# Только парсинг без генерации
python -m agent.cli --url "URL" --parse-only

# Проверить подключение к активному провайдеру
python -m agent.cli --test
python -m agent.cli --ai yandex --test
```

## 📐 Шаблоны и стиль письма (v2)

WishLibrarian позволяет настраивать **структуру** конспекта/воркбука и **тон** AI-генерации.

### Шаблоны

Шаблон = markdown-файл с YAML-фронматтером. Внутри:
- `system_prompt` — переопределение системного промпта для AI
- `sections:` — декларативное описание секций (порядок, тип, кол-во)
- Тело — markdown с `{{плейсхолдерами}}` (`{{title}}`, `{{author}}`, `{{year}}`, …)

**Где ищется шаблон** (по приоритету):
1. `$TEMPLATES_DIR/{kind}/{name}.md` (если задана env-переменная)
2. `./templates/{kind}/{name}.md` (пользовательские)
3. `agent/templates/builtin/{kind}/{name}.md` (встроенные дефолты)
4. Хардкод-дефолт по `kind`

**Управление через `.env`:**
```ini
TEMPLATE_SUMMARY=summary_v2
TEMPLATE_WORKBOOK=workbook_v2
TEMPLATE_TIPS=tips_v1
TEMPLATES_DIR=                # опц. внешняя папка
```

**Через CLI:**
```bash
python -m agent.cli --list-templates                              # все шаблоны
python -m agent.cli --url "..." --template workbook_v2            # один шаблон
python -m agent.cli --url "..." --template-summary summary_v2 \
                          --template-workbook workbook_v2         # разные
```

**Через Telegram-бот:**
```
/template                              # показать текущие + список
/template workbook_v2                  # оба сразу
/template summary=summary_v2 workbook=my_coach_wb
/template default                      # сбросить на .env-дефолт
```

**Свой шаблон** — создайте файл `templates/workbook/my_coach_wb.md`:
```yaml
---
name: my_coach_wb
kind: workbook
version: v1
description: "Короткий воркбук на 2 недели"
system_prompt: |
  Ты — строгий коуч. Без воды. Каждое упражнение — действие,
  не вопрос «что я чувствую».
sections:
  - { id: sa, title: "🔍 Аудит", type: questions, count: 5 }
  - { id: af, title: "📝 Ответы", type: free, options: { lines_per_question: 3 } }
  - { id: ac, title: "✍️ Действия", type: actions, count: 3 }
  - { id: ht, title: "🔥 Трекер", type: habit_grid, options: { days: 14, habits: 2 } }
---

# ✍️ ВОРКБУК: {{title}}
...
```

### Стиль письма

Блок `## СТИЛЬ ПИСЬМА` приклеивается к system prompt. Любая смена стиля **автоматически** инвалидирует AI-кеш для книги (стиль — часть ключа кеша).

```ini
WRITING_TONE=coaching        # formal | casual | coaching
WRITING_LENGTH=medium        # short | medium | long
WRITING_AUDIENCE=general     # general | expert | teen
WRITING_LANGUAGE=ru
```

| Тон | Что значит |
|---|---|
| `FORMAL` | Академично, без сленга, минимум эмодзи |
| `CASUAL` | Разговорно, дружелюбно, можно «ты» |
| `COACHING` | Мотивирующе, «ты», призывы к действию |

### Структура воркбука v2 (10 секций)

1. **Заголовок** с указанием стиля
2. 🔍 **Упражнение 1. Самоанализ** (7 вопросов от LLM)
3. 📝 **Поля для ответов** — *4 подчёркнутые строки на вопрос* (пост-процессор)
4. ✍️ **Упражнение 2. Практика** (5 чекбоксов)
5. 🧩 **Кейс-сценарии** (3 мини-кейса: ситуация → «что бы ты сделал?»)
6. ⚡ **Планы «если — то»** (5 строк implementation intentions)
7. 📅 **Упражнение 3. Планирование** (4-недельный план)
8. 🔥 **Трекер привычек 30×3** — LLM даёт 3 названия через `[HABIT_NAMES]…[/HABIT_NAMES]`, пост-процессор строит таблицу
9. 💭 **Рефлексия через 30 дней** (7 вопросов)
10. 🎁 **Бонус: микро-привычки**

**PDF:** секция «Поля для ответов» рендерится через `Table` с `LINEBELOW` — получаются аккуратные линии для письма от руки. Трекер рендерится как обычная markdown-таблица (уже поддерживается в `agent/export.py`).

## 📁 Структура выходной папки

```
output/library/
└── {Автор}{Название}{Год}/
    ├── summary.md
    ├── workbook.md
    ├── reviews.md
    ├── practical_tips.md
    ├── scientific.md
    ├── buy_links.md
    ├── metadata.json     ← содержит ai_provider и ai_model
    ├── cover.jpg
    └── raw/source.html
```

## 🏗 Архитектура

```
agent/
├── config.py                # настройки из .env
├── librarian.py             # главный класс (использует self.ai)
├── cli.py                   # CLI
├── models.py                # pydantic-модели
├── utils/logger.py
├── parsers/
│   ├── base_parser.py
│   ├── koob_parser.py
│   ├── scientific_parser.py
│   ├── reviews_parser.py
│   └── affiliate_links.py
├── ai/
│   ├── base.py              # BaseAIClient, AIClientError
│   ├── claude_client.py     # Anthropic
│   ├── yandex_client.py     # Yandex Cloud Foundation Models
│   ├── gigachat_client.py   # Сбер GigaChat (с OAuth)
│   ├── fallback.py          # FallbackAIClient
│   ├── factory.py           # get_ai_client()
│   └── prompts.py
└── storage/
    ├── file_manager.py
    └── templates.py
```

## 🔑 Получение ключей

### Claude
1. Зарегистрируйтесь на [console.anthropic.com](https://console.anthropic.com/)
2. Перейдите в Settings → API Keys → Create Key
3. Скопируйте `sk-ant-...` в `ANTHROPIC_API_KEY`

### YandexGPT
1. Зарегистрируйтесь на [console.yandex.cloud](https://console.yandex.cloud/)
2. Создайте каталог (Folder), скопируйте его `folder_id` → `YANDEX_FOLDER_ID`
3. Сервисные аккаунты → Создать аккаунт → дать роль `ai.languageModels.user`
4. API-ключи → Создать API-ключ → скопировать в `YANDEX_API_KEY`

### GigaChat
1. Зарегистрируйтесь на [developers.sber.ru](https://developers.sber.ru/)
2. GigaChat API → Создать ключ (Authorization Key)
3. Скопируйте base64-строку в `GIGACHAT_AUTHORIZATION_KEY`

## ⚖️ Лицензия

MIT

## 📖 Документация

- **[USAGE.md](./USAGE.md)** — полная инструкция по установке, конфигурации, CLI-командам
- **[TELEGRAM_BOT.md](./TELEGRAM_BOT.md)** — пошаговое руководство по созданию и деплою Telegram-бота
- [`.env.example`](./.env.example) — шаблон конфигурации со всеми переменными

## 🎯 Этапы развития

| # | Что сделано | Где живёт |
|---|-------------|-----------|
| 1 | LLM-стратегия для парсинга незнакомых сайтов | `agent/parsers/llm_parser.py` |
| 2 | Дедуп по ISBN + нормализация заголовков | `agent/utils/normalize.py`, `agent/storage/file_manager.py` |
| 3 | Кеш AI-ответов (с инвалидацией по версии промта) | `agent/storage/ai_cache.py` |
| 4 | CLI polish: `--doctor`, `--query`, `--export`, `--no-ai-cache` | `agent/cli.py`, `agent/doctor.py` |
| 5 | Telegram-бот с 8 командами + inline-кнопки | `agent/telegram_bot.py` |
| 6 | Тесты (33 шт., все ✅), документация | `tests/`, `USAGE.md`, `TELEGRAM_BOT.md` |
| 7 | **Шаблоны v2 + style injection** (новое) — внешние `.md`+YAML шаблоны, 4 новых секции воркбука (поля, кейсы, if-then, трекер), style-селекторы в `.env` и CLI/Telegram | `agent/templates/`, `agent/ai/prompts.py`, `agent/storage/templates.py`, `agent/storage/ai_cache.py`, `agent/librarian.py` |

## 🧪 Запуск тестов

```bash
python tests/test_koob_parser.py        # 6 тестов парсера koob
python tests/test_universal_parser.py  # 7 тестов universal parser
python tests/test_extras.py            # 12 тестов новых модулей
python tests/test_ai_factory.py        # 8 тестов AI-провайдеров
python tests/test_templates.py         # 12 тестов системы шаблонов (v2)
```

Итого: **45 тестов, все зелёные**.
