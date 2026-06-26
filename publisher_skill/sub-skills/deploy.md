# Deploy — Astro build → Cloudflare Pages

## Вход

- `lab_site/src/pages/books/<slug>.astro` (создан на стадии render).
- `state[slug].rendered_at` установлен.

## Алгоритм

### 1. `npm run build` в `lab_site/`

```bash
cd C:/Users/kfigh/lab_site
npm run build
```

→ `lab_site/dist/` (Astro static).

### 2. `wrangler pages deploy` или KV-upload

**Вариант A (Pages deploy):**
```bash
cd C:/Users/kfigh/lab_site
npx wrangler pages deploy dist --project-name=pulab
```

**Вариант B (KV upload, как делает `lab_site/scripts/upload-static.py`):**
```bash
python C:/Users/kfigh/lab_site/scripts/upload-static.py
```

MVP v0.1 использует **вариант A** (через `scripts/deploy_pages.py`).

### 3. Проверка HTTP 200

```bash
curl -I https://pulab.online/books/<slug> | head -1
```

Ожидаем: `HTTP/2 200`.

### 4. Скриншот через Playwright

```python
mcp__playwright__browser_navigate("https://pulab.online/books/<slug>")
mcp__playwright__browser_take_screenshot(
  filename="tmp/<slug>-deploy.png",
  fullPage=True
)
```

### 5. Записать state

```json
{
  "deployed_at": "2026-06-11T10:05:00Z",
  "live_url": "https://pulab.online/books/transerfing-realnosti",
  "build_duration_sec": 12.4,
  "deploy_method": "wrangler_pages",
  "preview_path": "tmp/transerfing-realnosti-deploy.png"
}
```

## Скрипт

`scripts/deploy_pages.py` — выполняет шаги 1–5.

## Откат (Phase 2+)

`wrangler pages deployment rollback` — откат на предыдущий commit.

## Секреты

- `CF_ACCOUNT_ID`
- `CF_API_TOKEN`
- `CF_PAGES_PROJECT=pulab`
