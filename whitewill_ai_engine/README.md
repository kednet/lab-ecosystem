# Whitewill AI Engine — Demo MVP

**Презентация для Олега Торбосова (Whitewill) — 1–2 недели, два AI-модуля, 2 языка (RU + EN).**

---

## 🎯 Что демонстрируем

### Модуль 1: AI-консьерж
- Живой чат-бот на **Python + FastAPI + YandexGPT 5.1**
- Квалифицирует клиента по 6-шаговому сценарию
- Отвечает на **русском и английском** (YandexGPT + Yandex Translate)
- RAG по mock-базе объектов Whitewill (30 элитных объектов)
- Готовая интеграция с **Битрикс24** (mock-режим для демо)
- WebSocket для real-time общения + опционально Telegram

### Модуль 2: Off-market матчинг
- Крон-скрипт сканирует **10 кадастровых номеров** в ЦАО (mock-данные)
- Агрегирует сигналы: **смена собственника + обременения + ФССП + нотариат**
- ML-скоринг сигналов готовности к продаже (0–1)
- Уведомления в **Telegram брокеру** с кнопками
- Дашборд в **Streamlit** для презентации

---

## ⚡ Быстрый старт (5 минут)

```bash
# 1. Клонируем и устанавливаем
cd whitewill_ai_engine
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. Копируем env и заполняем (для demo достаточно mock-режима)
cp .env.example .env

# 3. Загружаем mock-данные
python -m src.demo.seed_data

# 4. Запускаем API консьержа
uvicorn src.concierge.server:app --reload --port 8001

# 5. В другом терминале — демо off-market
python -m src.offmarket.server

# 6. Открываем демо-дашборд
streamlit run src/demo/dashboard.py
```

---

## 🗂 Структура

```
whitewill_ai_engine/
├── src/
│   ├── concierge/           # Модуль 1: AI-консьерж
│   │   ├── server.py        # FastAPI приложение
│   │   ├── bot.py           # Ядро диалоговой логики
│   │   ├── prompts.py       # Промпты YandexGPT
│   │   ├── rag.py           # RAG по объектам Whitewill
│   │   ├── crm.py           # Интеграция с Битрикс24
│   │   └── schemas.py       # Pydantic-модели
│   ├── offmarket/           # Модуль 2: Off-market матчинг
│   │   ├── server.py        # Крон-скрипт
│   │   ├── scanner.py       # Сканер ЕГРН / ФССП
│   │   ├── scorer.py        # ML-скоринг
│   │   ├── notifier.py      # Telegram-бот
│   │   └── schemas.py
│   ├── shared/              # Общее
│   │   ├── config.py        # Настройки
│   │   ├── llm.py           # Обёртка YandexGPT
│   │   ├── db.py            # SQLAlchemy
│   │   └── i18n.py          # Локализация RU/EN
│   └── demo/                # Демо-инструменты
│       ├── seed_data.py     # Загрузка mock-данных
│       ├── dashboard.py     # Streamlit-дашборд
│       └── dialog_sim.py    # Симулятор диалогов
├── data/                    # Mock-данные
│   ├── properties.json      # 30 элитных объектов
│   ├── egrn_changes.json    # Изменения прав за 90 дней
│   ├── fssp_records.json    # Исполнительные производства
│   └── inheritance.json     # Наследственные дела
├── tests/                   # Тесты
├── docs/                    # Документация для презентации
│   ├── pitch.md             # Питч для Торбосова
│   └── architecture.md      # Архитектурная диаграмма
└── pyproject.toml
```

---

## 🛠 Стек

- **Backend:** Python 3.11 + FastAPI + WebSocket
- **LLM:** YandexGPT 5.1 Pro (через OpenAI-совместимый API Yandex Cloud)
- **Embeddings:** Yandex Cloud Vector Search (`text-search-doc`)
- **Storage:** SQLite (для demo) + опционально PostgreSQL
- **CRM:** Bitrix24 REST API (mock-режим)
- **Telegram:** python-telegram-bot
- **Dashboard:** Streamlit

---

## 💰 Стоимость пилота (production)

| Статья | Стоимость |
|---|---|
| YandexGPT (1000 диалогов) | ~4 000 ₽/мес |
| SpeechKit | ~8 000 ₽/мес |
| Vector Search | ~2 000 ₽/мес |
| Хостинг (Cloud Functions) | ~3 000 ₽/мес |
| **Итого** | **~25 000 ₽/мес** |

После успешного пилота → 1.2 млн ₽/мес подписка + 5% от доп. выручки.

---

## 📊 Демо-сценарий для Торбосова (15 минут)

1. **00:00–02:00** — Контекст: «38% сделок — арабоязычный капитал, сервис ручной, off-market на связях»
2. **02:00–07:00** — Живой диалог с AI-консьержем (RU → EN на лету)
3. **07:00–10:00** — Off-market дашборд: 10 кадастровых скорированы, топ-3 сделки готовы
4. **10:00–13:00** — Telegram-алерт с кнопками, который брокер видит в реальности
5. **13:00–15:00** — Бизнес-кейс: ROI 540–680% за первый год

Детальный питч — в `docs/pitch.md`.

---

## 🔐 Безопасность и комплаенс

- **152-ФЗ:** все данные хранятся в Yandex Cloud (РФ), mock-режим для demo не сохраняет ПДн
- **Эксклюзивность:** Whitewill — единственный клиент в элитке РФ на 6 месяцев
- **YandexGPT нативный стек:** нет зависимости от зарубежных LLM
