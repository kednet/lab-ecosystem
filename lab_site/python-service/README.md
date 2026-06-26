# lab-site-python

FastAPI-сервис для генерации книжных конспектов. Запускается на Render.com (Free tier) и общается с Cloudflare Worker через callback'и.

## Архитектура

```
┌──────────┐     POST /internal/jobs/{id}/progress       ┌────────────────┐
│ Worker   │ ◄─────────────────────────────────────────  │ python-service │
│ (Cloud-  │     POST /internal/jobs/{id}/done           │ (Render.com)   │
│  flare)  │ ──────────────────────────────────────────► │ FastAPI        │
└────┬─────┘                                              └───────┬────────┘
     │ GET /internal/jobs/pending (каждые 2 сек)                  │
     └──────────────────────────────────────────────────────────►  │
                                                                  │
                                                            ┌─────▼─────┐
                                                            │ WishLibra-│
                                                            │ rian (CLI)│
                                                            └─────┬─────┘
                                                                  │
                                                            ┌─────▼─────┐
                                                            │ /tmp/wl-  │
                                                            │ output/   │
                                                            │ {jobId}/  │
                                                            └───────────┘
                                                                  │
                                              Worker читает файлы ▲
                                              и кладёт в R2        │
```

## Локальная разработка

```bash
# 1. Виртуальное окружение
python -m venv .venv
source .venv/bin/activate        # bash
# .venv\Scripts\activate          # Windows

# 2. Зависимости
pip install -r requirements.txt

# 3. Конфиг
cp .env.example .env
# отредактировать .env:
#   WORKER_CALLBACK_URL=http://127.0.0.1:8787
#   PYTHON_SERVICE_TOKEN=dev-test-token

# 4. Запустить
uvicorn main:app --reload --port 8003

# 5. Проверить
curl http://127.0.0.1:8003/health
```

**Важно:** WishLibrarian импортируется из `../wish_librarian/agent/`. Убедись, что там настроен `.env` с API-ключами (Claude/Yandex/GigaChat) и установлены его зависимости.

## Деплой на Render.com

1. Залей `lab_site/` в Git-репо.
2. На https://dashboard.render.com → New → Blueprint → укажи репо.
3. Render найдёт `python-service/render.yaml` и предложит создать сервис.
4. Задай секреты в Environment:
   - `WORKER_CALLBACK_URL` = `https://lab-site-api.{account}.workers.dev` (после деплоя Worker'а)
   - `PYTHON_SERVICE_TOKEN` = та же строка, что в Worker (`wrangler secret put PYTHON_SERVICE_TOKEN`)
5. Дождись деплоя. URL будет `https://lab-site-python.onrender.com`.

## UptimeRobot (чтобы Free tier не засыпал)

Render.com засыпает после 15 мин неактивности. Cold start ~30 сек.

Настрой пинг каждые 14 минут:
- URL: `https://lab-site-python.onrender.com/health`
- Тип: HTTP
- Интервал: 14 мин

Бесплатно до 50 пингов.

## Endpoints

### GET /health
Liveness probe + статус in-flight jobs.

### POST /internal/heartbeat
Для UptimeRobot (отвечает 200).

### POST /internal/process-now
Ручной запуск (для дебага, минуя очередь):
```bash
curl -X POST http://localhost:8003/internal/process-now \
  -H "Authorization: Bearer dev-test-token" \
  -H "Content-Type: application/json" \
  -d '{"jobId":"test1","userId":"u1","bookQuery":"https://www.koob.ru/...","queryType":"url"}'
```

## Логи

```bash
# На Render
render logs -s lab-site-python

# Локально
tail -f logs/python-service.log
```

Логируются:
- `[jobId] start: url=...` — начало
- `[jobId] WL done: ...` — конец
- `Worker callback N: ...` — проблемы с Worker
- `WL done` или `WL failed: ...` — статус WL

## Известные ограничения

- **Free tier засыпает** — 30 сек cold start после 15 мин простоя. UptimeRobot помогает, но не 100%.
- **MAX_CONCURRENT_JOBS=2** — WL использует синхронные HTTP-вызовы к AI, ~1-3 мин на книгу.
- **`queryType: title`** — пока просто добавляет в koob.ru search. Реальный поиск по названию требует парсинга LiveLib/Litres — будет в Фазе 5.
- **No retry** — если WL упал, нужно пересоздать job.
