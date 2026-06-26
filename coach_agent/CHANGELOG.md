# Changelog

## Phase 8 — Production Hardening (2026-06-10)

Закрывает production-ready дыры из аудита: crisis_flag persistence, crisis
follow-up через 24ч, rate-limit middleware, AI cost budget, observability
(health/ai, log fix), CI, runbook.

### Safety
- **`session.crisis_flag` теперь персистится** — после crisis-сообщения
  `mark_session_crisis(session_id)` ставит флаг в D1. Помогает в аудите и
  отчётах, не теряется при перезапуске.
- **Crisis follow-up через 24ч** — `agent/services/crisis_followup.py`:
  фоновый сервис раз в час ставит аудит-метку `followed_up_at=now()` на
  crisis-логи старше 24ч. **Мягкий follow-up** = НЕ сообщение клиенту
  (избегаем re-traumatization), а сигнал для оператора.
- **Tool-dispatch graceful degradation** — exception в `tools.dispatch` не
  валит запрос: AI получает пометку `⚠️ ошибка tool: <name>` и продолжает
  диалог. `log.exception` сохраняет stacktrace.

### Observability
- **Новый эндпоинт `GET /health/ai`** — всегда 200, возвращает тип AI клиента
  (`fake` | `claude` | `yandex` | `unconfigured`) и `ok: bool`. Для
  мониторинга (не падает liveness).
- **`GET /health` теперь 503** если `ai_client is None` И `AI_FAKE_MODE` пуст.
  k8s/Render сразу видят unhealthy.
- **Log stacktraces** — 13 ключевых мест `log.error(error=str(e))` →
  `log.exception(...)`: d1_client (sync+async), claude_client, yandex_client,
  session.py (workbook/ai), channels/vk.py, main.py.
- **MITM-warning на каждом старте** — `app.mitm_enabled` логируется
  с `verify_ssl=False` / SOCKS5. Оператор видит в логах при деплое.
- **Admin-token weak warning** — `app.admin_token_weak` в production при
  пустом `ADMIN_TOKEN` (fallback на имя сервиса).

### Cost control
- **Rate-limit middleware** — `agent/api/middleware/ratelimit.py`:
  in-memory sliding window per (X-Client-Id, IP). 30 req/min per client,
  5 req/min per IP. 429 + `Retry-After`. Whitelist: `/health*`, `/docs`,
  `/admin/*`. Для multi-pod → Redis (Phase 9+).
- **Per-session cost budget** — `SessionService._session_cost: dict[int, float]`,
  budget $1/сессия. Превышение → friendly text, AI НЕ вызывается. Сброс
  на новую сессию.

### Reliability
- **Dead code удалён** — `_handle_workbook_stub` удалён; `_handle_release_stub`
  заменён на полноценный `_handle_release` с `update_desire_status`.

### CI
- **GitHub Actions** — `.github/workflows/test.yml`: `lint` (ruff) +
  `test` (pytest matrix 3.11/3.12, `AI_FAKE_MODE=true`).

### Documentation
- **RUNBOOK.md** — операционный runbook: мониторинг, деплой, rollback,
  crisis response, cost drain, rate-limit incident, known weaknesses.
- **CHANGELOG.md** — этот файл.
- **README.md** — обновлён под Phase 7+8.

---

## Phase 7 — VK Channel (Long Poll) (2026-06-09)

- VK Long Poll runner (`agent/channels/vk.py`): group messages → MessageBus.
- ClientChannel-таблица (Phase 5) для multi-channel клиентов.
- Auto-link: если VK peer уже привязан к client_id — продолжаем, иначе создаём.
- Graceful shutdown: `asyncio.Event` + `vk_runner.stop()` в lifespan.

---

## Phase 6 — Telegram Bot (Webhook) (2026-06-08)

- Telegram webhook handler: `POST /telegram/webhook` (X-Telegram-Bot-Api-Secret-Token).
- Long-form сообщения (Telegram limit 4096) разбиваются на чанки.
- Inline-кнопки завершения сессии: «Сохранить» / «Завершить».
- MessageBus: унифицированный диалог между web/TG/VK.

---

## Phase 5 — Multi-Channel Foundations (2026-06-07)

- `MessageBus` + `ChannelRouter` для маршрутизации по `channel`.
- `ClientChannelRow` (1 клиент ↔ N каналов).
- `find_client_by_channel(channel, external_id)`.

---

## Phase 4 — Workbook Library (2026-06-06)

- Воркбуки из Markdown (`agent/library/`).
- 3 книги по умолчанию: `atomic_habits`, `deep_work`, `mindset`.
- `WorkbookService` с in-progress / paused / completed состояниями.
- Step-by-step прохождение с AI-reflection после каждого ответа.

---

## Phase 3 — Detector + Desires (2026-06-05)

- `DetectorService`: scoring желания (momentum / clarity / alignment / realism).
- Verdict: `go` | `investigate` | `reconsider` | `release`.
- Desires API: create, list, mark done/skipped/release.
- `crisis_flag` в `SessionRow` (Phase 8: теперь персистится).

---

## Phase 2 — Crisis Detection (2026-06-04)

- 4 regex-паттерна: `suicide`, `violence`, `self_harm`, `distress`.
- Инвариант: **AI не вызывается при crisis** — мгновенный шаблонный ответ.
- `crisis_log` хранит **только SHA-256 хэш**, не текст.
- FSM-transition в `S_CRISIS_STOP`.

---

## Phase 1 — State Machine + Tones (2026-06-03)

- FSM: `S_NEW → S_ONBOARDING_TONE → S_ONBOARDING_START → S_DIALOG →
  S_DESIRE_CREATE → S_DIALOG → S_END_SAVE / S_END_COMPLETE → S_IDLE_SAVED`.
- 4 тона: `warm`, `direct`, `socratic`, `analytic`. Intensity 1-5.
- Claude-клиент + YandexGPT-fallback.

---

## Phase 0 — FastAPI Skeleton (2026-06-02)

- FastAPI app, lifespan, structlog.
- 9 таблиц D1: client, client_channel, desire, desire_step, session,
  message, workbook_run, crisis_log, tone_profile + schema_meta.
- Smoke-эндпоинты: `/health`, `/health/d1`, `/admin/migrate`.
- Render Blueprint + Cron-keepalive.

---

_Phase progression intentionally additive: каждый Phase оставляет предыдущие
тесты зелёными и расширяет функционал._
