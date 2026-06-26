# experiments_bot

Telegram-бот для сбора «экспериментов читателей» в чате.

**Стратегия:** community-first ([[lab-community-first-strategy-2026-06-18]]) — читатели = главные герои, форма снижает порог, бот даёт ещё один канал «на ходу».

## Сценарий (FSM, 5 шагов)

1. `/start` → приветствие + кнопка «🧪 Поделиться экспериментом»
2. **Имя/псевдоним** (опц., кнопка «Пропустить»)
3. **Книга** (inline-кнопки из `https://app.pulab.ru/api/books` или fallback)
4. **Что пробовали** (текст 30–1000)
5. **Что получилось** (текст 30–1000)
6. **Согласие на публикацию** (да/нет)
7. POST → `https://api.pulab.online/api/experiments` → ответ с ID

## Запуск локально

```bash
cd C:\Users\kfigh\experiments_bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# создать .env из .env.example и заполнить TELEGRAM_BOT_TOKEN
python -m agent.experiments_bot
```

## Деплой на VPS (194.226.97.7)

Systemd-юнит `experiments-bot.service`, путь `/opt/experiments_bot/`. SOCKS5 берётся из переменной `TELEGRAM_PROXY_URL` (тот же прокси, что у WL-ботов).

### Шаги (руками, по ssh)

```bash
# 1. SSH на VPS
ssh root@194.226.97.7

# 2. Создать пользователя и папки
useradd -r -s /bin/false deploy-exp 2>/dev/null || true
mkdir -p /opt/experiments_bot
mkdir -p /var/log/experiments_bot
chown -R deploy-exp:deploy-exp /opt/experiments_bot /var/log/experiments_bot

# 3. Скопировать код (с локалки)
# На ВАШЕЙ машине (Win):
cd C:\Users\kfigh\experiments_bot
scp -r agent requirements.txt README.md root@194.226.97.7:/opt/experiments_bot/

# 4. Создать venv на VPS
ssh root@194.226.97.7
cd /opt/experiments_bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
chown -R deploy-exp:deploy-exp /opt/experiments_bot

# 5. Создать .env (подставить токен)
cat > /opt/experiments_bot/.env <<'EOF'
TELEGRAM_BOT_TOKEN=СЮДА_ТОКЕН_ОТ_BOTFATHER
TELEGRAM_PROXY_URL=socks5://user:pass@host:port
EXPERIMENTS_API_URL=https://api.pulab.online
BOOKS_API_URL=https://app.pulab.ru
LOG_LEVEL=INFO
EOF
chown deploy-exp:deploy-exp /opt/experiments_bot/.env
chmod 600 /opt/experiments_bot/.env

# 6. Создать systemd-юнит
cat > /etc/systemd/system/experiments-bot.service <<'EOF'
[Unit]
Description=Experiments Telegram Bot (Лаборатория желаний)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=deploy-exp
WorkingDirectory=/opt/experiments_bot
Environment="PYTHONIOENCODING=utf-8"
Environment="PYTHONUTF8=1"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/experiments_bot/.venv/bin/python -m agent.experiments_bot
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=experiments-bot
MemoryMax=200M
TasksMax=32

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now experiments-bot
systemctl status experiments-bot
journalctl -u experiments-bot -f
```

### Проверка

```bash
# Должен показать "active (running)"
systemctl is-active experiments-bot

# Логи в реальном времени
journalctl -u experiments-bot -f

# Тест: написать боту /start в Telegram
```

### Откат

```bash
systemctl stop experiments-bot
systemctl disable experiments-bot
```

### Backup токенов

`.env` лежит только на VPS, права 600, владелец `deploy-exp`. Не коммитить.
