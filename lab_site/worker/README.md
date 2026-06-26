# lab-site-api

Cloudflare Worker для сайта «ЛАБОРАТОРИЯ ЖЕЛАНИЙ». Бэкенд для трекера, генерации конспектов, аутентификации и оплаты.

## Стек

- **Runtime:** Cloudflare Workers (V8 isolate)
- **Router:** [Hono](https://hono.dev/)
- **Хранилище:** Cloudflare KV (для трекера, лимитов, статуса генераций)
- **Файлы:** Cloudflare R2 (сгенерированные конспекты, обложки)
- **Email:** Resend (magic-link коды)
- **Платежи:** ЮKassa
- **AI-генерация:** Python-сервис на Render.com (вызывает WishLibrarian)

## Разработка

```bash
# 1. Установить зависимости
npm install

# 2. Запустить локальный dev-сервер (Miniflare эмулирует KV/R2/Cron)
npm run dev
# → http://127.0.0.1:8787

# 3. Проверить типы
npm run typecheck
```

Для локальной разработки **не нужны** реальные KV namespace в Cloudflare — Miniflare создаёт эфемерные. Но R2 bucket создать придётся.

## Создание ресурсов в Cloudflare (один раз)

```bash
# Логин в Cloudflare
npx wrangler login

# KV namespace
npx wrangler kv:namespace create LAB_KV
# → выведет "id = ...". Вставить в wrangler.toml [[kv_namespaces]] id и preview_id.
npx wrangler kv:namespace create LAB_KV --preview

# R2 bucket
npx wrangler r2 bucket create lab-books
# → раскомментировать [[r2_buckets]] в wrangler.toml
```

## Деплой

```bash
# Установить секреты (для production)
npx wrangler secret put JWT_SECRET              # случайная строка 64+ символов
npx wrangler secret put RESEND_API_KEY          # из resend.com
npx wrangler secret put YOOKASSA_SHOP_ID        # из yookassa.ru
npx wrangler secret put YOOKASSA_SECRET_KEY     # из yookassa.ru
npx wrangler secret put PYTHON_SERVICE_URL      # https://lab-site-python.onrender.com
npx wrangler secret put PYTHON_SERVICE_TOKEN    # общий токен для callback

# Деплой
npm run deploy
# → https://lab-site-api.{account}.workers.dev
```

В `wrangler.toml` для production поменять `FRONTEND_ORIGIN` на `https://app.pulab.online`.

## Структура

```
src/
├── index.ts                  # Hono router
├── types.ts                  # Env, helpers (json, error, corsOrigin)
├── middleware/
│   └── cors.ts               # CORS для FRONTEND_ORIGIN
├── routes/                   # (добавятся в Фазе 1+)
│   ├── auth.ts
│   ├── tracker.ts
│   ├── generate.ts
│   ├── checkout.ts
│   ├── webhook-yookassa.ts
│   └── internal.ts
└── lib/                      # (добавятся в Фазе 1+)
    ├── kv.ts
    ├── jwt.ts
    ├── email.ts
    ├── yookassa.ts
    ├── quota.ts
    └── slug.ts
```

## Фазы разработки

- ✅ **Фаза 0:** каркас (Hono + CORS + health check)
- ⏳ **Фаза 1:** аутентификация (magic-link через Resend)
- ⏳ **Фаза 2:** трекер желаний
- ⏳ **Фаза 3:** генерация конспектов (python-service)
- ⏳ **Фаза 4:** ЮKassa
- ⏳ **Фаза 5:** полировка
