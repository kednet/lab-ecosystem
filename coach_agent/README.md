# WishCoach

ИИ-коуч для подписчиков **Лаборатории желаний** (сообщество ВК `pulabru`).
Премиум-фича подписки сайта `app.pulab.online`.

**PRD:** [PRD.md](./PRD.md)
**Runbook:** [RUNBOOK.md](./RUNBOOK.md) — операционные инциденты, мониторинг, known weaknesses
**Changelog:** [CHANGELOG.md](./CHANGELOG.md) — история по фазам

---

## Текущая фаза: **Phase 8 — Production Hardening** ✅

### Phase 0-7: каркас, AI, детектор, workbook, multi-channel

- ✅ **Phase 0** — FastAPI + D1 migrations + smoke endpoints
- ✅ **Phase 1** — State machine + tones (warm/direct/socratic/analytic) + Claude + YandexGPT
- ✅ **Phase 2** — Crisis detection (4 regex, hash-only storage, AI-инвариант)
- ✅ **Phase 3** — Detector (4 модуля scoring) + desires
- ✅ **Phase 4** — Workbook library (3 книги, step-by-step + AI reflection)
- ✅ **Phase 5** — Multi-channel foundations (MessageBus + ChannelRouter)
- ✅ **Phase 6** — Telegram Bot (webhook + inline-buttons)
- ✅ **Phase 7** — VK Long Poll runner + ClientChannel

### Phase 8: production hardening

- ✅ **Crisis flag persistence** — `mark_session_crisis` пишет в D1
- ✅ **Crisis follow-up (24ч soft)** — `agent/services/crisis_followup.py`
- ✅ **Rate-limit middleware** — 30 req/min per client, 5 req/min per IP
- ✅ **AI cost budget** — $1/сессия, accumulator в SessionService
- ✅ **Log stacktraces** — 13 мест `log.error(error=str(e))` → `log.exception(...)`
- ✅ **Health observability** — `GET /health/ai`, 503 при unconfigured AI
- ✅ **MITM/admin warnings** — `app.mitm_enabled`, `app.admin_token_weak`
- ✅ **CI** — GitHub Actions: ruff + pytest matrix 3.11/3.12
- ✅ **Dead code removed** — `_handle_workbook_stub` удалён, `_handle_release` полный
- ✅ **Tool-dispatch graceful degradation** — exception → `⚠️ ошибка tool: <name>`

**Tests:** 260 passed, 1 pre-existing socks5h fail, 2 skipped

---

## Локальный запуск

```bash
# 1. Клонировать и установить
cd C:/Users/kfigh/coach_agent
python -m venv .venv
.venv/Scripts/activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -e ".[dev,ai]"

# 2. Скопировать и заполнить .env
cp .env.example .env
# отредактировать .env: CF_* , VERIFY_SSL=false, ANTHROPIC_API_KEY

# 3. Запустить (с AI ключами)
uvicorn agent.main:app --reload --port 8000

# 3b. Или fake-mode (без ключей)
AI_FAKE_MODE=true uvicorn agent.main:app --reload --port 8000
```

Открыть:
- http://localhost:8000/ — корневой info + список эндпоинтов
- http://localhost:8000/health — liveness/readiness
- http://localhost:8000/health/ai — тип AI клиента
- http://localhost:8000/docs — Swagger UI

## Эндпоинты (Phase 8)

### Public
- `GET  /` — корневой info
- `GET  /health` — 200 ok / 503 ai_unconfigured / 503 d1_fail
- `GET  /health/ai` — тип AI клиента (для мониторинга)
- `GET  /health/d1` — строгий readiness D1
- `GET  /docs`, `/redoc`, `/openapi.json` — Swagger UI

### Coach (требует `X-Client-Id`)
- `POST /coach/message` — главный диалог
- `POST /coach/onboarding/tone` — выбор тона
- `POST /coach/onboarding/start` — выбор старта
- `POST /coach/tone` — смена тона
- `POST /coach/end` — завершить сессию (save/complete)
- `GET  /coach/session` — текущее состояние
- `POST /coach/desire` — создать желание
- `GET  /coach/desires` — список активных желаний
- `GET  /coach/workbook/list` — список воркбуков
- `POST /coach/workbook/start` — начать воркбук
- `POST /coach/workbook/answer` — ответить на шаг
- `GET  /coach/workbook/progress` — прогресс

### Admin (требует `X-Admin-Token`)
- `POST /admin/migrate` — применить миграции D1

### Channels
- `POST /telegram/webhook` — Telegram updates (X-Telegram-Bot-Api-Secret-Token)

## Применить миграции

Через эндпоинт:
```bash
curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" http://localhost:8000/admin/migrate
```

Или скриптом:
```bash
python -c "from agent.storage.migrations import apply_migrations; print(apply_migrations())"
```

## Тесты

```bash
# Все тесты (260 passed)
AI_FAKE_MODE=true python -m pytest tests/ -v

# Lint
python -m ruff check agent/ tests/
```

CI: GitHub Actions (`.github/workflows/test.yml`) — lint + test matrix
python 3.11/3.12 на каждый push в `main`.

## Деплой на Render

1. Push в `main` → Render автодеплой
2. После деплоя:
   ```bash
   curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" $RENDER_EXTERNAL_URL/admin/migrate
   ```
3. Render Cron (`wishcoach-keepalive`) пингует `/health` каждые 14 мин

Подробнее: [RUNBOOK.md](./RUNBOOK.md) § Деплой.

---

## Архитектура (Phase 8)

```
coach_agent/
├── agent/
│   ├── main.py              # FastAPI app + lifespan + /health* + middleware
│   ├── config.py            # Settings (pydantic) + MITM globals
│   ├── utils.py             # structlog
│   ├── ai/                  # Claude, YandexGPT, Fake
│   ├── core/                # FSM, detector, onboarding, session, workbook
│   ├── channels/            # Web/TG/VK adapters + router
│   ├── services/            # Phase 8: crisis_followup
│   │   └── crisis_followup.py
│   ├── api/                 # FastAPI routers + middleware (ratelimit)
│   │   └── middleware/
│   │       └── ratelimit.py
│   ├── storage/
│   │   ├── d1_client.py     # HTTP-обёртка Cloudflare D1
│   │   ├── d1_client_async.py
│   │   ├── migrations.py    # 9 таблиц + apply_migrations()
│   │   └── repository.py    # Repository + crisis methods (Phase 8)
│   ├── library/             # Phase 4+ (workbooks)
│   └── scheduler/           # (Phase 9+)
├── tests/                   # 260 passed
├── .github/
│   └── workflows/
│       └── test.yml         # CI: lint + test matrix 3.11/3.12
├── PRD.md
├── RUNBOOK.md               # Phase 8: операционный runbook
├── CHANGELOG.md             # Phase 0-8
├── pyproject.toml
├── render.yaml              # деплой + Cron
├── .env.example
├── .gitignore
└── README.md
```

---

## Безопасность

- **Crisis-detection**: `crisis_log` хранит **только SHA-256 хэш**, не текст.
- **Rate-limit**: 30 req/min per X-Client-Id, 5 req/min per IP. 429 + Retry-After.
- **Admin-эндпоинты**: `X-Admin-Token` (Phase 9+ → JWT).
- **Секреты**: только в `.env` / Render Dashboard, НЕ в коде, НЕ в git.
- **Корпоративный MITM**: `VERIFY_SSL=false` обязательно на рабочей машине
  (TLS-MITM уронит все запросы). `log.warning("app.mitm_enabled")` на старте.

**Known weaknesses:** см. [RUNBOOK.md § 8](./RUNBOOK.md#8-auth-debt-known-weaknesses)
(auth-debt, MITM, in-memory rate-limit, soft follow-up).

---

## Phase 9+ (roadmap)

- JWT / magic-link auth (заменить X-Client-Id)
- Redis-based rate limit (для multi-pod)
- Real crisis follow-up messaging (opt-in)
- Per-user cost budget через D1
- Prometheus / OpenTelemetry
- Production-grade `verify_ssl=True` enforcement
