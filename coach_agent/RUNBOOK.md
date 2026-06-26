# WishCoach — Runbook

Операционный runbook для продакшн-инцидентов. Для разработки см. [README.md](./README.md).

**Stack:** FastAPI · Cloudflare D1 · Claude / YandexGPT · Render.com

---

## 1. Мониторинг

### Health checks

| Endpoint | Status | Что проверяет |
|---|---|---|
| `GET /health` | 200 ok / 503 ai_unconfigured / 503 d1_fail | Liveness + readiness |
| `GET /health/ai` | 200 always | Тип AI клиента (для алертов) |
| `GET /health/d1` | 200 / 503 | Строгий readiness к D1 |

Render Cron (`wishcoach-keepalive`) пингует `/health` каждые 14 мин — если
5xx → Render помечает сервис как unhealthy.

### Что мониторить

- **5xx rate** — `error_count / request_count`. Алерт > 1%.
- **AI-бюджет** — `log.warning("session.cost_budget_exceeded")`. Если
  срабатывает часто → клиент гоняет цикл или AI-цикл слишком длинный.
- **Crisis events** — `log.warning("crisis.detected")`. Каждый = шаблонный
  ответ + crisis_log запись.
- **Rate-limit блокировки** — `log.warning("ratelimit.blocked")`. Алерт
  > 100/час = спам или bot.
- **D1 5xx** — `log.error("d1.error")`. Алерт = проверить CF status page.

---

## 2. Деплой

### Render.com (auto-deploy)

1. Push в `main` → Render автодеплой.
2. После деплоя проверить `/health` (200).
3. Если менялась схема D1:
   ```bash
   curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" $RENDER_URL/admin/migrate
   ```
4. Проверить `/health/ai` — `ai: "claude" | "yandex"`, `ok: true`.

### Откат

Render Dashboard → Manual Deploy → выбрать предыдущий коммит.
**NB:** миграции D1 additive-only (Phase 9+ будет downgrade).

---

## 3. Crisis Response

### Обнаружение

- Crisis-сообщение → `crisis.detected` в логах, запись в `crisis_log`
  (только SHA-256 хэш, **НЕ текст**), FSM → `S_CRISIS_STOP`.
- Шаблонный ответ с горячими линиями (8-800-2000-122, 112).
- `session.crisis_flag = 1` (Phase 8 — теперь персистится в D1).

### Follow-up через 24ч

`agent/services/crisis_followup.py` — фон, цикл 1 час:
1. Выбирает crisis-логи старше 24ч с `followed_up_at IS NULL`.
2. Ставит аудит-метку `followed_up_at = now()`.
3. **НЕ пишет клиенту** — это только сигнал для оператора.

### Действия оператора

1. Открыть Render Logs → `grep "crisis.detected"`.
2. Найти client_id + session_id.
3. (Опционально) связаться через админ-канал, **НЕ через коуча**.
4. Лог операторского действия: `client_log` (Phase 9+).

---

## 4. Cost Drain (AI-бюджет)

### Что это

Per-session budget: $1/сессия (настраивается через
`SessionService._session_cost_budget`). При превышении:
- AI НЕ вызывается.
- Возвращается friendly text: `«⏸ AI-бюджет этой сессии исчерпан...»`.

### Если клиент жалуется

1. Открыть `/coach/session?client_id=X` — посмотреть `total_cost_usd`.
2. Если действительно > $1 — поведение корректное.
3. Если нет — баг в `_session_cost` accumulator → написать issue.

### Если ВСЕ клиенты упираются в budget

- Поднять `_session_cost_budget` в `agent/core/session.py` (деплой).
- Или: проверить нет ли runaway loop в `_call_ai` (не должны расти cost без
  реальных AI-вызовов).

---

## 5. Rate-Limit Incident

### Симптомы

`log.warning("ratelimit.blocked", key="cid:X", path="/coach/message")`
с repeat-паттерном = спам-клиент.

### Действия

1. `grep "ratelimit.blocked"` → найти `cid:X`.
2. Проверить: этот client_id — легитимный клиент?
3. Если да → порекомендовать клиенту снизить частоту.
4. Если нет → возможно бот → добавить IP в firewall (Cloudflare).
5. Если массовый инцидент (> 50 уникальных `cid` в час) → временно
   поднять `PER_CLIENT_LIMIT` в `agent/api/middleware/ratelimit.py`.

### Лимиты (Phase 8)

- `PER_CLIENT_LIMIT = 30 req/min` (с `X-Client-Id`)
- `PER_IP_LIMIT = 5 req/min` (без `X-Client-Id`, например `/admin/*`)

---

## 6. D1 Outage

### Симптомы

`log.error("d1.error")` или `/health/d1` = 503.

### Действия

1. Проверить https://www.cloudflarestatus.com/.
2. Если CF-wide — приложение деградирует gracefully (RateLimitMiddleware
   пропускает, но SessionService не сможет сохранять сессии → 503).
3. Если только наш account → проверить CF_API_TOKEN не истёк.
4. Сбросить token: Render Dashboard → Environment → `CF_API_TOKEN`.

### Mitigation

Приложение не падает (rate-limit + middleware работают), но AI-диалог
невозможен без D1. Если outage > 30 мин → рассмотреть maintenance mode
(вернуть 503 с `detail: "maintenance"`).

---

## 7. VK / Telegram Channel Outage

### VK Long Poll

- `log.error("vk.longpoll_crashed")` — runner упал.
- Auto-reconnect: НЕТ (Phase 8). Нужно рестартить сервис.
- Mitigation: `Manual Deploy` в Render или просто ждать следующего
  деплоя (cron keepalive не поможет).

### Telegram Webhook

- Webhook 4xx (кроме 4xx от Telegram retry) → проверить `TELEGRAM_WEBHOOK_SECRET`.
- Если Telegram меняет URL → переустановить webhook:
  ```bash
  curl "https://api.telegram.org/bot${TG_TOKEN}/setWebhook?url=${RENDER_URL}/telegram/webhook&secret_token=${TG_SECRET}"
  ```

---

## 8. Auth-Debt (Known Weaknesses)

> Phase 8 — **намеренно НЕ реализовано**. Документируем для прозрачности.
> Remediation → Phase 9+.

### W1: `X-Client-Id` без аутентификации

**Проблема:** любой может поставить `X-Client-Id: 1` и писать от имени
клиента 1.

**Remediation (Phase 9+):**
- Magic-link через email (отправили → клиент перешёл → JWT).
- Или Telegram Login Widget + JWT.
- Или Cloudflare Access (для admin-эндпоинтов уже частично).

**Сейчас:** rate-limit по `X-Client-Id` снижает blast radius, но не
устраняет проблему.

### W2: `ADMIN_TOKEN` fallback на `render_service_name`

**Проблема:** если `ADMIN_TOKEN` пуст, защита = просто имя сервиса
(guessable). В production это **логируется как warning** при старте, но
не enforced.

**Remediation (Phase 9+):** require `ADMIN_TOKEN` в production.
Сейчас: `log.warning("app.admin_token_weak")` на старте.

### W3: `verify_ssl=False` (MITM)

**Проблема:** корпоративный MITM = весь TLS расшифровывается. Чувствительные
запросы (CF API tokens) видны MITM-прокси.

**Remediation (Phase 9+):** certificate pinning + per-host whitelist для
критичных эндпоинтов (CF D1, Anthropic, Yandex).

**Сейчас:** `log.warning("app.mitm_enabled")` на старте.

### W4: Crisis follow-up — только аудит, не действие

**Проблема:** через 24ч после crisis ставится метка, но клиенту
никто не пишет. Может быть недружественно, если клиент в реальной
беде.

**Remediation (Phase 9+):** opt-in флаг `crisis_followup_enabled` в
client → через 24ч отправлять сообщение (через TG/VK) с предложением
помощи + горячие линии. Только с product-одобрения.

### W5: In-memory rate-limit (single pod)

**Проблема:** на multi-pod каждый процесс имеет свой счётчик → лимит
фактически ×N.

**Remediation (Phase 9+):** Redis-based rate limit (например,
`fastapi-limiter`).

---

## 9. Disaster Recovery

### Полный откат D1

Phase 8 — миграции additive-only. Полный откат = restore из бэкапа D1
(через `wrangler d1 backup` или Render cron).

### Потеря ANTHROPIC_API_KEY

1. Render Dashboard → Environment → `ANTHROPIC_API_KEY`.
2. Redeploy.
3. Проверить `/health/ai` — `ai: "claude", ok: true`.

Если ключ утечёт → сразу revoke в Anthropic console + rotate.

### Потеря CF_API_TOKEN

То же самое + rotate в Cloudflare Dashboard.

---

## 10. Контакты

- **Owner:** @kfigh
- **PRD:** [PRD.md](./PRD.md)
- **AI cost dashboard:** https://console.anthropic.com/
- **CF status:** https://www.cloudflarestatus.com/
- **Render status:** https://status.render.com/

_Последнее обновление: 2026-06-10 (Phase 8)._
