# Chief Agent v1.0

Orchestrator and control panel for the 13 agents of the **Лаборатория желаний** project.

Runs on VPS `194.226.97.7` (Reg.ru, Russia) as a Node.js + Express service behind nginx.

## What it does

- **Registry** of 13 agents (8 on VPS today, 5 to be deployed in Wave 2)
- **Heartbeat** every 30 sec — pings systemd units, HTTP endpoints, state files
- **Action runner** — invokes CLI subprocesses (Python) or HTTP endpoints on demand
- **Job log** — full stdout/stderr in SQLite, audit_log for security events
- **Offline alerts** — TG notification when an agent goes from online → offline
- **Control UI** — Astro page at `https://app.pulab.online/chief/`

## Quick start

```bash
# 1. Install deps
cd /opt/chief-agent
npm ci --omit=dev

# 2. Configure
cp .env.example .env
nano .env  # set CHIEF_API_TOKEN, TG_BOT_TOKEN, TG_CHAT_ID

# 3. systemd
sudo cp systemd/chief-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now chief-agent
sudo systemctl status chief-agent

# 4. Smoke test
curl -s http://127.0.0.1:7070/api/health
```

## REST API

All endpoints except `/api/health` require `Authorization: Bearer $CHIEF_API_TOKEN`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness (no auth) |
| GET | `/api/agents` | List with status |
| GET | `/api/agents/:id` | Details + heartbeat |
| GET | `/api/agents/:id/actions` | Available commands |
| POST | `/api/agents/:id/run` | Run action `{actionId, params, dryRun, triggeredBy, triggeredByUser}` |
| GET | `/api/jobs?limit=&agent=&status=` | Log |
| GET | `/api/jobs/:id` | Job detail |
| POST | `/api/jobs/:id/cancel` | SIGTERM by pid |
| GET | `/api/system/services` | systemd units under Chief control |
| POST | `/api/system/restart/:service` | Restart service (allowlisted + audit_log) |

## Architecture

- **No build step** — plain CommonJS, runs directly from `/opt/chief-agent/src/`
- **better-sqlite3** with WAL — single file at `/opt/chief-agent/data/chief.db`
- **In-memory job queue** — one Mutex per agentId prevents concurrent runs
- **spawn Python** with `python -u` and `PYTHONIOENCODING=utf-8` for clean output

## Deploy waves

- **Wave 1 (8 agents, ready after deploy):** wishlibrarian, publisher, lab_site, coach, experiments_bot, video_skill, image_skill, audio_skill
- **Wave 2 (5 agents, after `scp` of skills to VPS):** seo_advisor, expert_reviews, lead_generator, content_ideas, wish_market

See `/opt/chief-agent/src/agents/registry.js` for the full list and `enabled` flags.

## Logs

```bash
journalctl -u chief-agent -f           # live
journalctl -u chief-agent -n 100       # last 100
```

DB is at `/opt/chief-agent/data/chief.db`. Inspect with `sqlite3`.
