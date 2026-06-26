# Lead Generator Skill v0.1

Скил лидогенерации для проектов на российском рынке (2026). Специализация: **«Лаборатория желаний»** (ниша «психология / саморазвитие / работа с желаниями»), женская ЦА 25-50+, форма **НПД (самозанятый)**, тон **честный анти-маркетинг**.

> **Главная идея:** ОК + Дзен = основа 50-60% бюджета (дешёвые каналы для ЦА 35-55), остальное — усиление.

---

## 🚀 Быстрый старт (3 шага)

### 1. Запуск скила

```bash
# В Claude Code (после установки в ~/.claude/skills/)
/lead
```

Скил подключён через symlink:
- Исходники: `C:\Users\kfigh\lead_generator_skill\`
- Ссылка Claude: `C:\Users\kfigh\.claude\skills\lead-generator-skill\`

### 2. Типовой сценарий

```
/lead стратегия-сегменты "подписка 590" 50000 "50 подписок в месяц"
```

→ Получите: мульти-сегментную стратегию, распределение бюджета по каналам, креативы, воронку, юр-чек-лист, KPI.

### 3. Проверка скриптами

```bash
cd C:\Users\kfigh\lead_generator_skill
PYTHONIOENCODING=utf-8 python scripts/budget_calculator.py --goal 50 --avg-check 590
```

> **Важно для Windows:** все Python-скрипты запускать с префиксом `PYTHONIOENCODING=utf-8`, иначе будет `UnicodeEncodeError` на эмодзи/кириллице.

---

## 📚 22 команды скила

### Стратегия и аудитория

| Команда | Что делает | Пример |
|---------|-----------|--------|
| `/lead анализ` | Аудит текущей воронки | `/lead анализ` |
| `/lead стратегия-сегменты` | Мульти-сегментная стратегия с бюджетом | `/lead стратегия-сегменты "подписка 590" 50000 "50 подписок"` |
| `/lead add-segment` | Добавить новый сегмент ЦА (например, 55+) | `/lead add-segment "ж 55-70, пенсия, внуки"` |

### Оффер и креативы

| Команда | Что делает | Пример |
|---------|-----------|--------|
| `/lead оффер` | Сформулировать оффер (триал, пакет, цена) | `/lead оффер "подписка 590"` |
| `/lead креативы` | Сгенерировать 5-10 креативов под каналы | `/lead креативы "сегмент B, ОК+VK"` |
| `/lead лидмагнит` | Идея + структура PDF-магнита (15 стр) | `/lead лидмагнит "7 шагов к своим желаниям"` |
| `/lead возражения` | Скрипт обработки 5-7 возражений | `/lead возражения "дорого / не верю / нет времени"` |
| `/lead quiz` | Квиз-воронка (8-10 вопросов) | `/lead quiz "Какое у вас истинное желание"` |

### Воронка и каналы

| Команда | Что делает | Пример |
|---------|-----------|--------|
| `/lead воронка` | Вся цепочка от магнита до подписки | `/lead воронка "PDF → email → триал → подписка"` |
| `/lead avito` | Объявление + скрипт для Авито | `/lead avito "консультация 2900"` |
| `/lead dzen` | Статья + заголовок для Дзена | `/lead dzen "Почему карты желаний не работают"` |
| `/lead webinar` | Сценарий вебинара + слайды | `/lead webinar "5 техник для мамы 30+"` |
| `/lead seo-funnel` | SEO-страница + магнит + подписка | `/lead seo-funnel "как найти своё желание"` |
| `/lead reviews-pack` | Блок доверия (отзывы) из парсера | `/lead reviews-pack "карта желаний"` |

### Юридический блок

| Команда | Что делает | Пример |
|---------|-----------|--------|
| `/lead compliance` | Проверка креатива на ФАС + 152-ФЗ + 54-ФЗ | `/lead compliance "Текст рекламы..."` |
| `/lead crisis` | Антикризисный сценарий (жалоба, ФАС, бан) | `/lead crisis "жалоба на эзотерику"` |
| `/lead audit` | Полный аудит рекламной кампании | `/lead audit --channels "ok,dzen,vk"` |

### Аналитика

| Команда | Что делает | Пример |
|---------|-----------|--------|
| `/lead benchmark` | CPL-бенчмарки по каналам/сегментам | `/lead benchmark --channel ok` |
| `/lead seasonal` | Сезонный календарь (праздники, спады) | `/lead seasonal --month march` |

### Интеграции

| Команда | Что делает | Пример |
|---------|-----------|--------|
| `/lead magnet-from-wl` | Книга из WishLibrarian → PDF-магнит → воронка | `/lead magnet-from-wl "Женщины, которые бегут"` |

### 🕵️ Разведка конкурентов (NEW)

| Команда | Что делает | Источник |
|---------|-----------|----------|
| `/lead spy` | Полный spy-отчёт по 1 конкуренту (каналы, креативы, офферы, тон) | `/lead spy "Имя конкурента"` |
| `/lead spy-trends` | Тренды ниши: топ офферов, заголовков, тонов | `/lead spy-trends "психология женщин"` |
| `/lead spy-reviews` | Боли и триггеры из отзывов + цитаты для рекламы | `/lead spy-reviews "карта желаний"` |

---

## 🎯 4 сегмента ЦА (ядро)

| Сегмент | Возраст | Доля | Главные каналы | LTV |
|---------|---------|------|----------------|-----|
| **A** | 25-34 мамы/карьеристки | 25% | VK, TG, Yappy | 4 мес |
| **B** ⭐ | 35-44 на перекрёстке | 35% | ОК, Дзен, VK | 6 мес |
| **C** | 45-55 опустевшее гнездо | 25% | ОК, Дзен, Авито | 8 мес |
| **D** | 55-65 активная пенсия | 15% | ОК, Дзен, Авито | 10 мес |

> Добавить сегмент 65+ → `/lead add-segment "ж 65+, зрелость"`

---

## 📡 Каналы (CPL подписки, 2026)

| Канал | CPL магнита | CPL подписки | Роль |
|-------|-------------|--------------|------|
| **ОК Реклама** ⭐ | 40-120 ₽ | **400-1000 ₽** | ОСНОВА |
| **Дзен (продвижение)** ⭐ | 80-200 ₽ | **400-1000 ₽** | ОСНОВА |
| **Дзен (органика)** ⭐ | 0-50 ₽ | **300-700 ₽** | ОСНОВА (долгоиграющий) |
| VK Реклама (new) | 80-250 ₽ | 600-1500 ₽ | Усиление |
| Посевы TG (микро) | 30-100 ₽ | 400-800 ₽ | Усиление |
| Я.Директ (РСЯ) | 60-180 ₽ | 500-1200 ₽ | Усиление |
| Я.Директ (поиск) | — | 1200-2500 ₽ | Горячий |
| Yappy | — | 500-1500 ₽ | Нишевый |
| Авито (услуги) | 150-500 ₽ | 800-2000 ₽ | Нишевый |
| Вебинар | 80-250 ₽ | 1000-3000 ₽ | Дожим (5-15% конверсия) |

> **Правило:** для подписочной модели с LTV 3500-5000 ₽ → целевой CAC 700-900 ₽, не выше 1180 ₽.

---

## 🐍 9 Python-скриптов (6 + 3 spy-парсера)

### 1. `budget_calculator.py` — расчёт бюджета

```bash
PYTHONIOENCODING=utf-8 python scripts/budget_calculator.py --goal 50 --avg-check 590
```

→ Показывает: диапазоны бюджета по каналам, ожидаемую выручку, ROI.

### 2. `segment_recommender.py` — подбор каналов по сегментам

```bash
# По всем сегментам
PYTHONIOENCODING=utf-8 python scripts/segment_recommender.py --goal 50 --avg-check 590

# Только сегмент B
PYTHONIOENCODING=utf-8 python scripts/segment_recommender.py --segment b --goal 30
```

### 3. `cpl_benchmark.py` — справочник CPL

```bash
PYTHONIOENCODING=utf-8 python scripts/cpl_benchmark.py --channel ok
PYTHONIOENCODING=utf-8 python scripts/cpl_benchmark.py --segment c
```

### 4. `compliance_check.py` — проверка на ФАС + обязательные дисклеймеры

```bash
PYTHONIOENCODING=utf-8 python scripts/compliance_check.py "Ваш текст..." --psychology --paid-ad
```

→ Возвращает: скор 0-100, список нарушений, рекомендации.

### 5. `calc_unit_econ.py` — LTV/CAC/ROI

```bash
PYTHONIOENCODING=utf-8 python scripts/calc_unit_econ.py --avg-check 590 --months 6 --margin 0.7 --cac 900
```

### 6. `utm_generator.py` — UTM-метки

```bash
# Одна ссылка
PYTHONIOENCODING=utf-8 python scripts/utm_generator.py --source ok --medium cpm --campaign lab_jan --content emotional

# Набор для всех каналов × сегментов × креативов
PYTHONIOENCODING=utf-8 python scripts/utm_generator.py --set --campaign lab_b_q1 --segments "a,b,c,d" --creatives "emotional,rational,anti-marketing"
```

---

### 🕵️ Spy-парсеры (новые, легальные, бесплатные)

### 7. `spy_vk_ads.py` — креативы конкурентов в VK Ads Library

```bash
# Найти 30 креативов в нише
PYTHONIOENCODING=utf-8 python scripts/spy_vk_ads.py --query "карта желаний" --limit 30 --output vk_ads.csv
```

→ Дамп заголовков, рекламодателей, URL, фрагментов. Формат CSV для дальнейшего анализа.

### 8. `spy_tg_channels.py` — топ TG-каналов ниши через TGStat

```bash
# Топ-15 каналов в нише, мин. 3к подписчиков
PYTHONIOENCODING=utf-8 python scripts/spy_tg_channels.py --query "психология женщин" --min-subs 3000 --output tg_channels.csv
```

→ Название, подписчики, описание, URL.

### 9. `spy_reviews.py` — отзывы с otzovik (боли + триггеры)

```bash
# 30 отзывов на продукт/конкурента
PYTHONIOENCODING=utf-8 python scripts/spy_reviews.py --query "психолог онлайн" --site otzovik --limit 30 --output reviews.csv
```

→ Заголовок, текст, плюсы, минусы + авто-анализ топ-10 болей (частотность).

> **Внимание:** парсеры работают через `requests + BeautifulSoup`. Если VK/TGStat/Otzovik поменяют вёрстку — селекторы в скриптах нужно обновить (5-10 минут работы).

---

## 🔗 Интеграции

| Скил | Что берём | Команда |
|------|-----------|---------|
| **WishLibrarian** | Конспект книги → PDF-магнит | `/lead magnet-from-wl "Название книги"` |
| **SEO Advisor + Publisher** | SEO-страница + лендинг + деплой | `/lead seo-funnel "тема"` |
| **Expert & Reviews Hub** | Блок доверия (отзывы) | `/lead reviews-pack "тема"` |
| **Content Ideas** | Идеи постов (rule-based, 0 ₽) | Используется внутри `/lead креативы` |

---

## ✍️ Тон — честный анти-маркетинг

**Использовать:**
- ✅ «Без подписки», «без оплаты», «бесплатно скачать»
- ✅ Конкретные цифры: «за 21 день», «без воды», «5 шагов»
- ✅ «Я тоже так мучилась», «по-честному», «без мишуры»
- ✅ Истории из жизни, анти-глянцевые фото

**Избегать:**
- ❌ «Узнайте подробнее», «Не упустите», FOMO
- ❌ «100%», «гарантированно», «навсегда» (ФАС-бан)
- ❌ Глянец, ИИ-фото, «успешный успех»

---

## ⚖️ Юридический минимум (НПД, 2026)

1. **Маркировка ОРД** (347-ФЗ): токен ERID через Амбер / ОРД-маркер.
   - VK Реклама, ОК, Я.Директ — авто.
   - Telegram-посевы, ручные размещения — вручную через **Амбер**.
   - Штраф за отсутствие: **30 000-500 000 ₽**.

2. **Дисклеймеры** (для ниши «психология»):
   > «Материалы носят информационный характер. Результат индивидуален. Не является медицинской/психотерапевтической услугой.»

3. **152-ФЗ** (персональные данные): форма согласия + политика ПД (футер сайта).

4. **54-ФЗ** (онлайн-кассы): ЮKassa или Т-Касса (обе поддерживают НПД).

5. **Лимит НПД**: < 2.4 млн ₽/год, без сотрудников.

> **Проверить креатив:** `/lead compliance "текст..." --psychology --paid-ad`

---

## 📁 Структура скила

```
lead_generator_skill/
├── SKILL.md                        # главный (9.7 КБ)
├── README.md                       # этот файл
├── prompts/        (8 файлов)      # логика команд
│   ├── audience_analysis.md
│   ├── offer_creation.md
│   ├── ad_copy.md
│   ├── funnel.md
│   ├── channel_strategy.md
│   ├── spy_competitor.md          # NEW
│   ├── spy_trends.md              # NEW
│   └── spy_reviews_pains.md       # NEW
├── templates/     (13 файлов)     # готовые форматы
│   ├── vk_ad.md
│   ├── ok_post.md
│   ├── tg_post.md
│   ├── yandex_direct.md
│   ├── lead_magnet.md
│   ├── compliance_npd.md
│   ├── crisis_playbook.md
│   ├── landing_checklist.md
│   ├── quiz_funnel.md
│   ├── dzen_article.md
│   ├── avito_ad.md
│   ├── webinar_scenario.md
│   └── strategy_ok_dzen.md
├── channels/       (8 файлов)     # специфика каналов
│   ├── vk_ads_new.md
│   ├── yandex_direct.md
│   ├── ok.md
│   ├── dzen.md
│   ├── telegram_seeding.md
│   ├── yappy.md
│   ├── avito.md
│   └── webinars.md
├── data/           (4 файла)      # бенчмарки, сегменты, сезон, закон
│   ├── benchmarks_ru_2026.md
│   ├── segment_playbook_ru.md
│   ├── seasonal_calendar_ru.md
│   └── legal_cheatsheet_npd.md
├── integrations/   (4 файла)      # WL / SEO+Publisher / Reviews / Content
│   ├── with_wishlibrarian.md
│   ├── with_seo_publisher.md
│   ├── with_expert_reviews.md
│   └── with_content_ideas.md
├── scripts/        (9 Python)     # утилиты (6 + 3 spy-парсера)
│   ├── budget_calculator.py
│   ├── cpl_benchmark.py
│   ├── compliance_check.py
│   ├── calc_unit_econ.py
│   ├── utm_generator.py
│   ├── segment_recommender.py
│   ├── spy_vk_ads.py             # NEW
│   ├── spy_tg_channels.py        # NEW
│   └── spy_reviews.py            # NEW
└── examples/                       # примеры стратегий
    └── strategy_50k_50_subs_2026-06-13.md
```

**Всего:** 46 файлов, ~520 КБ.

---

## 🎓 Примеры использования

### Пример 1: быстрый тест гипотезы

```
/lead оффер "триал 7 дней → подписка 590"
/lead креативы "сегмент B, ОК+VK, 3 шт"
/lead воронка "магнит → email → триал → подписка"
```

### Пример 2: масштабирование успешной связки

```
/lead benchmark --channel ok --segment b
/lead аудит "кампания lab_jan, CPL 750 ₽, 40 подписок"
/lead стратегия-сегменты "подписка 590" 100000 "100 подписок"
```

### Пример 3: запуск с нуля

```
/lead анализ
/lead add-segment "ж 55-70, внуки, дача"
/lead лидмагнит "7 шагов к своим желаниям"
/lead креативы "ОК+Дзен, все 4 сегмента"
/lead стратегия-сегменты "подписка 590" 30000 "30 подписок"
/lead compliance "все креативы..." --psychology --paid-ad
```

### Пример 4: разведка конкурентов

```bash
# Собрать базу
PYTHONIOENCODING=utf-8 python scripts/spy_vk_ads.py --query "психолог онлайн" --limit 30 --output spy_vk.csv
PYTHONIOENCODING=utf-8 python scripts/spy_tg_channels.py --query "психология" --min-subs 3000 --output spy_tg.csv
PYTHONIOENCODING=utf-8 python scripts/spy_reviews.py --query "карта желаний" --site otzovik --limit 30 --output spy_reviews.csv

# Запросить отчёт
/lead spy "Имя конкурента"
/lead spy-trends "психология женщин"
/lead spy-reviews "карта желаний"
```

---

## 🛠️ Установка и обновление

### Проверить, что скил подключён

```bash
ls -la C:\Users\kfigh\.claude\skills\lead-generator-skill
# Должен быть symlink → C:\Users\kfigh\lead_generator_skill
```

### Если symlink пропал (Windows)

```bash
# Создать заново (PowerShell от администратора)
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\lead-generator-skill" -Target "$env:USERPROFILE\lead_generator_skill"
```

### Обновить скил

1. Поправить файлы в `C:\Users\kfigh\lead_generator_skill\`
2. Перезапустить Claude Code
3. Скил подхватит изменения автоматически

---

## 🔍 Связанные скилы

- **Publisher Skill v0.2** — деплой лендингов, SEO-страниц
- **SEO Advisor v2.0** — оптимизация под Яндекс+Google
- **WishLibrarian** — книга → конспект → PDF-магнит
- **Expert & Reviews Hub** — парсинг отзывов для блока доверия
- **Content Ideas** — генерация идей постов
- **Audio Skill** — озвучка PDF-магнитов (аудио-воронка)
- **WishCoach** — премиум-ИИ-коуч для подписчиков

---

## 📞 Поддержка

- **Путь:** `C:\Users\kfigh\lead_generator_skill\`
- **Версия:** v0.2 (2026-06-13)
- **Автор:** сессия с Claude (lead-gen проект)
- **Связаться:** через Claude Code → `/lead аудит`

---

## 📜 Changelog

### v0.2 (2026-06-13) — Spy-модуль
- ➕ 3 spy-команды: `/lead spy`, `/lead spy-trends`, `/lead spy-reviews`
- ➕ 3 Python-парсера: `spy_vk_ads.py`, `spy_tg_channels.py`, `spy_reviews.py`
- ➕ 3 промпта в `prompts/`: `spy_competitor.md`, `spy_trends.md`, `spy_reviews_pains.md`
- 📚 Всего: 46 файлов, 22 команды, 9 скриптов

### v0.1 (2026-06-13)
- Первая версия, 41 файл
- 19 команд, 4+ сегмента, 8 каналов
- 6 Python-скриптов (все работают с PYTHONIOENCODING=utf-8)
- 4 интеграции (WL, SEO+Publisher, Reviews, Content Ideas)
- Тестовый прогон: стратегия на 50 000 ₽ / 50 подписок
- Юр-блок для НПД (ОРД, 152-ФЗ, 54-ФЗ, ФАС)
