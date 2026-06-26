# Kednet Agent — мост Kednet ↔ Chief Agent

Persistent WebSocket-клиент. Связывает Chief (на VPS `89.108.88.74:7070`) с локальными Python-скиллами в `C:\Users\kfigh\`.

## Что делает

- Держит long-lived WS `ws://89.108.88.74:7070/ws`.
- Авторизуется через `KEDNET_AGENT_TOKEN` в hello-сообщении.
- По команде `run` от Chief — spawn'ит `.venv\Scripts\python.exe -u <script> [args]` в указанном `cwd`, стримит stdout/stderr чанками, шлёт `artifact` и `exit`.
- По команде `scaffold` от Chief — создаёт папку `C:\Users\kfigh\<agent_id>\` и пишет `agent.py` + `requirements.txt` + `README.md`.
- Ping/pong каждые 30 сек.
- Auto-reconnect 5/10/30/60 сек при обрыве.
- Сканирует `C:\Users\kfigh\` при старте → шлёт `skillsDetected[]` в Chief.

## Структура

```
kednet_agent/
├── kednet_agent.py              # этот файл (запускается)
├── kednet_agent.config.json     # chiefUrl, token, skillsDir
├── requirements.txt             # websockets==12.0
├── README.md                    # ← вы здесь
├── logs/                        # auto-create
│   └── kednet_agent.log
└── nssm/
    └── install-kednet-agent.ps1 # установка как Windows-сервис
```

## Установка

### 1. Установить зависимости

```powershell
cd C:\Users\kfigh\kednet_agent
C:\Users\kfigh\AppData\Local\Programs\Python\Python312\python.exe -m pip install --target=.\vendor websockets==12.0
```

> Если `pip` ругается на TLS — добавьте `--trusted-host pypi.org --trusted-host files.pythonhosted.org` (корпоративный MITM).
> Альтернатива: `--proxy http://127.0.0.1:10808` (если активен SOCKS5, но pip понимает только HTTP-proxy — используйте `cntlm` или аналог).

### 2. Положить правильный токен

Откройте `kednet_agent.config.json` и замените `token` на значение `KEDNET_AGENT_TOKEN` из `/opt/chief-agent/.env` на VPS:

```powershell
ssh -i $HOME\.ssh\lab_vps root@89.108.88.74 "grep KEDNET_AGENT_TOKEN /opt/chief-agent/.env"
```

### 3. Установить как Windows-сервис (nssm)

```powershell
# Скачать nssm (https://nssm.cc/download) → распаковать, например в C:\Tools\nssm-2.24\
.\nssm\install-kednet-agent.ps1 -NssmPath C:\Tools\nssm-2.24\win64\nssm.exe
```

Скрипт автоматически:
- `nssm install KednetAgent` → python.exe + kednet_agent.py
- `nssm set KednetAgent AppDirectory` → C:\Users\kfigh\kednet_agent
- `nssm set KednetAgent AppStdout/Err` → logs\service.out.log / service.err.log
- `nssm set KednetAgent Start SERVICE_AUTO_START`
- `nssm start KednetAgent`

### 4. Проверить

```powershell
# Логи
Get-Content C:\Users\kfigh\kednet_agent\logs\kednet_agent.log -Tail 20 -Wait

# На VPS — статус WS-подключения
curl -s -H "Authorization: Bearer $CHIEF_API_TOKEN" http://89.108.88.74:7070/api/ws/status
# → {"connected":true,"hostname":"DESKTOP-...","os":"Windows",...}
```

## Ручной запуск (без nssm)

```powershell
cd C:\Users\kfigh\kednet_agent
$env:PYTHONPATH = "C:\Users\kfigh\kednet_agent\vendor"
C:\Users\kfigh\AppData\Local\Programs\Python\Python312\python.exe -u kednet_agent.py
```

## Smoke-test (без Chief)

```powershell
python kednet_agent.py --once
# {"type": "hello", "data": {"hostname": "...", "skillsDetected": [...]}}
```

## WS-протокол

См. `chief-agent/src/ws/protocol.js`. Формат всех сообщений:

```json
{ "type": "...", "jobId": "...", "ts": 123, "data": {...} }
```

Chief → Kednet: `welcome`, `run`, `cancel`, `ping`, `scaffold`, `open`.
Kednet → Chief: `hello`, `pong`, `started`, `stdout`, `stderr`, `artifact`, `exit`, `scaffold.done`.

## Переменные окружения (для spawn'а subprocess)

При запуске skill Kednet-агент прокидывает в subprocess:

- `PYTHONIOENCODING=utf-8` — кириллица в stdout/stderr без `UnicodeDecodeError`
- `PYTHONUNBUFFERED=1` — flush после каждой строки (стриминг работает)
- `LC_ALL=C.UTF-8` — fallback локали

Если в команде `run` указано `envKeys` — Kednet-агент фильтрует окружение subprocess по whitelist (например, `["VK_ACCESS_TOKEN", "TG_BOT_TOKEN"]`). Если `envKeys` не задан — прокидывает всё окружение родителя (включая все системные переменные Windows).

## Безопасность

- Файл `kednet_agent.config.json` содержит `KEDNET_AGENT_TOKEN` — не коммитьте.
- `cwd` любой команды `run` проверяется: должен лежать внутри `skillsDir`.
- Скаффолд **не перезаписывает** существующие папки (получит `FileExistsError` → Chief отдаст 409).
- WS — без TLS (предполагается туннель/частная сеть). Если Chief за nginx с TLS — см. `nginx.conf` локацию `/chief/ws/`.

## Troubleshooting

| Симптом | Решение |
|---|---|
| `pip install websockets` ругается на TLS | `--trusted-host pypi.org --trusted-host files.pythonhosted.org` |
| Kednet-агент не коннектится | Проверить `token`, проверить firewall Windows, проверить что nginx upstream на VPS жив |
| Spawn падает с `FileNotFoundError: python.exe` | Создать `.venv\Scripts\python.exe` в агенте (`python -m venv .venv`) |
| Кириллица в stdout как `???` | Проверить, что subprocess выставлен с `PYTHONIOENCODING=utf-8` (уже выставлен Kednet-агентом) |
| nssm не запускает | `nssm set KednetAgent AppStdout C:\Users\kfigh\kednet_agent\logs\service.out.log` + проверить путь к python.exe |