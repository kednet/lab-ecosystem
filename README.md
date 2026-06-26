# 🌌 Лаборатория желаний — открытая экосистема

> **Личный репозиторий вайбкодера:** ИИ-агенты, автономные пайплайны и продуктовые сервисы для женского комьюнити «Лаборатория желаний».

---

## 🧑‍💻 About / Обо мне

**Вайбкодер.** Строю автономные ИИ-пайплайны и продуктовые сервисы в коллаборации с Claude, YandexGPT, GigaChat и другими LLM. Верю в подход *vibe coding*: быстро проверять гипотезы кодом, итерировать с AI-агентами, держать фокус на пользовательской ценности, а не на инфраструктуре.

> *Vibe coder — building AI agents and autonomous pipelines for a women's community project.*

---

## 🏗️ Экосистема / The Ecosystem

Этот репозиторий — точка входа в набор связанных проектов. Каждый живёт в своей папке и имеет собственный README с подробностями.

### 🤖 Core AI-агенты / Ядро

| Проект | Папка | Что делает |
|---|---|---|
| **WishLibrarian** | [`wish_librarian/`](./wish_librarian) | ИИ-агент книжных конспектов. Мульти-LLM (Claude / YandexGPT / GigaChat), Telegram + VK боты, детектор желаний 20 вопросов |
| **Coach Agent** | [`coach_agent/`](./coach_agent) | Премиум ИИ-коуч: 4 нейтральных тона × 5 интенсивностей, воркбуки из WL |
| **Experiments Bot** | [`experiments_bot/`](./experiments_bot) | TG-бот для участниц: фиксация экспериментов «к себе нежно», FSM 5 шагов |
| **Expert & Reviews Hub** | [`expert-reviews-hub/`](./expert-reviews-hub) | Парсинг отзывов LiveLib / Литрес / VK, веса litres/own = 1.5 |

### 🎨 Контент-скилы / Content Skills

| Проект | Папка | Что делает |
|---|---|---|
| **Image Skill** | [`image_skill/`](./image_skill) | Генерация изображений YandexART + Pillow postprocess, 5 форматов × 5 профилей, R2/Yandex storage |
| **Audio Skill** | [`audio_skill/`](./audio_skill) | PDF→YAML→Yandex SpeechKit (zahar/ermil/alena/...), SSML-озвучка книжных саммари |
| **Video Skill** | [`video_skill/`](./video_skill) | 5 профилей видео-контента (lab/wl/coach/experts/market), YandexGPT-сценарии |
| **Publisher Skill** | [`publisher_skill/`](./publisher_skill) | Универсальный постер VK/TG/OK/Zen, 5 стадий + watcher + rollback |
| **Content Ideas** | [`content_ideas_skill/`](./content_ideas_skill) | Генератор идей из книг WL, банк из 29+ идей |
| **Lead Generator** | [`lead_generator_skill/`](./lead_generator_skill) | Парсер ОК/Дзен/ads.vk/tgstat, сегменты ж 25–50+ |

### 🛠️ Продуктовые сервисы / Product Surfaces

| Проект | Папка | Что делает |
|---|---|---|
| **Lab Site** | [`lab_site/`](./lab_site) | Astro-сайт [app.pulab.ru](https://app.pulab.ru): детектор, эксперименты, /audio/, /library/, paywall, VK Mini App |
| **Wish Market** | [`wish_market/`](./wish_market) | Маркет желаний: VK Mini App + каталог + paywall, запуск 01.08.2026 |
| **Lab Landings** | [`lab_landings/`](./lab_landings) | Лендинги для сообщества |
| **Experiments VK App** | [`experiments_vk_app/`](./experiments_vk_app) | VK Mini App для /experiments/ |
| **Detector VK App** | [`detector_vk_app/`](./detector_vk_app) | VK Mini App для детектора желаний |

### 🧩 Инфраструктура / Infra & Tooling

| Проект | Папка | Что делает |
|---|---|---|
| **SEO Advisor** | [`seo-advisor-skill/`](./seo-advisor-skill) | 12 режимов SEO-оптимизации, интеграция с WL/Publisher/Coach |
| **English Skill** | [`english_skill/`](./english_skill) | 12 недель × 7 дней, IT-глоссарий 80+244 фраз, 9 CLI-команд |
| **Excel Skill** | [`excel_skill/`](./excel_skill) | 8 скриптов: inspect/vlookup/sum/dedupe/fill/csv/json/count |
| **Lottie Skill** | [`lottie_skill/`](./lottie_skill) | Анимации для VK/TG |
| **Chief Agent** | [`chief-agent/`](./chief-agent) | Оркестратор нескольких скилов |
| **Whitewill AI Engine** | [`whitewill_ai_engine/`](./whitewill_ai_engine) | Консьерж-API + Streamlit-демо для консульства недвижимости |

### 📂 Прочее / Misc

- [`plans/`](./plans) — дизайн-документы и роадмапы
- [`temp/`](./temp) — временные артефакты сессий
- [`book_project/`](./book_project) — ранний прототип книжного пайплайна

---

## 🚀 Быстрый старт / Quick Start

Каждый подпроект автономен. Общий шаблон:

```bash
# Python-скилы (wish_librarian, image_skill, audio_skill, ...)
cd <project>
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # заполнить ключи
python run.py --help

# Astro-проекты (lab_site)
cd lab_site
npm install
npm run dev
```

⚠️ **Корпоративный MITM-прокси.** Машина за TLS-MITM + системным SOCKS5 `127.0.0.1:10808`. Python-проекты требуют `PySocks` и `*_VERIFY_SSL=false` в `.env`.

---

## 🧠 Стек / Stack

**LLM & AI**
- Claude (Anthropic), YandexGPT, GigaChat — мульти-провайдер с fallback
- YandexART — генерация изображений
- Yandex SpeechKit — озвучка (zahar, ermil, alena, filipp, jane, madirus)

**Backend**
- Python 3.11+ (FastAPI, aiogram, aiohttp, Pillow, Playwright)
- Node.js 22 (Astro, Hono, undici, ws)
- SQLite (Astro DB), PostgreSQL (планируется в wish_market)

**Frontend**
- Astro 4 + Tailwind CSS, vanilla JS
- VK Mini Apps (`@vkontakte/vk-bridge`), Telegram WebApp

**Storage & Deploy**
- Cloudflare R2, Yandex Object Storage
- VPS Reg.ru (89.108.88.74), Nginx, systemd

**Integrations**
- VK API (wall.post, messages, mini-apps), Telegram Bot API
- ЮKassa (paywall), Дзен RSS, Pinterest

---

## 📐 Архитектурные принципы / Principles

1. **Skill-first.** Каждая capability — отдельный CLI-скил с собственным README, тестами, примерами.
2. **Один pipeline, разные провайдеры.** LLM, storage, TTS — за абстракциями с fallback-цепочкой.
3. **Локальный-first.** Все скилы работают без облака; облако — только по флагу.
4. **Идемпотентность.** Повторный запуск = тот же результат, без дублей.
5. **Sanity-check перед планом.** Утренняя память может отставать — сначала проверить на сервере, потом планировать.

---

## 🤝 Contributing

Это личный репозиторий вайбкодера, но идеи и баг-репорты приветствуются через Issues.

*This is a personal vibe-coder repo, but ideas and bug reports are welcome via Issues.*

---

## 📄 License

MIT (если не указано иное в подпроекте).

---

## 📊 Статус / Status

Активная разработка с начала 2026. Каждый скил в `v0.x → v1.x` стадии. Главный публичный продукт — [app.pulab.ru](https://app.pulab.ru).

*Active development since early 2026. Each skill is in `v0.x → v1.x`. Main public product: app.pulab.ru.*