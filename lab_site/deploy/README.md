# deploy/README.md

# Деплой Lab site на Reg.ru Cloud VPS

Этот документ описывает **развёртывание production** стенда `app.pulab.online` на VPS
в Москве. Целевая конфигурация: Nginx + Node.js (Hono) + SQLite вместо Cloudflare.

---

## Предусловия

| Что | Где взять |
|---|---|
| Reg.ru аккаунт с балансом ≥ 1500 ₽ | https://www.reg.ru/ |
| Домен `pulab.online` с доступом к DNS | обычно у того же регистратора |
| SSH-ключ (ed25519) | `ssh-keygen -t ed25519 -C "lab-vps"` |
| Локально: PowerShell + rsync (Git Bash / WSL / OpenSSH) | уже есть в Windows 10+ |

---

## Шаг 1. Заказать VPS (5 минут)

1. https://www.reg.ru/ → **Облако** → **Облачные серверы** → **Создать**
2. **Регион:** Москва-2 (или любой Tier III ЦОД в Москве)
3. **Конфигурация:**
   - Категория: **Производительный** (2.8 ГГц, NVMe)
   - **HP C1-M2-D20** — 1 vCPU, **2 ГБ RAM**, 20 ГБ NVMe (~1010 ₽/мес)
   - vCPU-режим: **30%** (для теста), потом повысите до 100% под нагрузкой
4. **ОС:** Ubuntu 24.04 LTS
5. **SSH-ключ:** загрузите публичный `~/.ssh/lab_vps.pub`
6. **Бэкап:** Включить (10 ₽/мес)
7. **Анти-DDoС:** уже включён бесплатно
8. **Оплата:** «Месяц» (не «Час» — иначе после теста будет дорого)

После создания Reg.ru пришлёт **IP-адрес** на почту.

---

## Шаг 2. Первичная настройка VPS (10 минут)

```bash
# Подключаемся
ssh -i ~/.ssh/lab_vps root@185.244.xx.xx

# Создаём пользователя для деплоя
adduser deploy --disabled-password --gecos ""
mkdir -p /home/deploy/.ssh
cp ~/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/authorized_keys
usermod -aG sudo deploy
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy

# Обновляемся и ставим базовое
apt update && apt upgrade -y
apt install -y nginx certbot python3-certbot-nginx ufw fail2ban \
               htop curl git rsync unzip
ufw allow OpenSSH
ufw allow "Nginx Full"
ufw --force enable

# Node.js 24 LTS
curl -fsSL https://deb.nodesource.com/setup_24.x | bash -
apt install -y nodejs
node -v    # v24.x
npm -v

# Каталоги
mkdir -p /var/www/lab-site/{dist,acme,wl-output,logs,backups}
mkdir -p /var/lib/lab-site
chown -R deploy:deploy /var/www/lab-site /var/lib/lab-site

# Тестовый выход из под root (дальше работаем от deploy)
exit
```

---

## Шаг 3. Скопировать код (1 минута, локально)

На Windows откройте Git Bash / PowerShell и запустите:

```bash
cd /c/Users/kfigh/lab_site

# 1. Сбилдить воркер (создаст worker/dist/server.js + index-cf.js)
cd worker && npm install && npm run build && cd ..

# 2. Сбилдить фронт (создаст dist/ со шрифтами)
npm run build

# 3. Скопировать ВСЁ на VPS одной командой (замените IP)
export VPS=185.244.xx.xx
rsync -avz --delete \
  -e "ssh -i $HOME/.ssh/lab_vps" \
  --exclude='node_modules' --exclude='.wrangler' --exclude='.astro' \
  --exclude='tmp' --exclude='*.log' \
  /c/Users/kfigh/lab_site/dist/  deploy@$VPS:/var/www/lab-site/dist/

rsync -avz --delete \
  -e "ssh -i $HOME/.ssh/lab_vps" \
  --exclude='.wrangler' --exclude='.wrangler-state' \
  /c/Users/kfigh/lab_site/worker/  deploy@$VPS:/home/deploy/app/worker/

rsync -avz \
  -e "ssh -i $HOME/.ssh/lab_vps" \
  /c/Users/kfigh/lab_site/deploy/  deploy@$VPS:/home/deploy/app/deploy/
```

Или используйте `deploy-vps.ps1` (см. ниже) — он делает всё это + перезапуск сервисов.

---

## Шаг 4. Настроить Nginx + TLS (5 минут, на VPS)

```bash
ssh -i ~/.ssh/lab_vps deploy@185.244.xx.xx

# Скопировать наш конфиг
sudo cp /home/deploy/app/deploy/nginx.conf /etc/nginx/sites-available/lab-site
sudo ln -sf /etc/nginx/sites-available/lab-site /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Создать каталог для ACME-challenge
sudo mkdir -p /var/www/lab-site/acme
sudo chown -R deploy:deploy /var/www/lab-site/acme

# Проверить синтаксис (ДО выпуска сертификата!)
sudo nginx -t

# Выпустить сертификат (замените на свой email)
sudo certbot --nginx \
  -d app.pulab.online -d api.pulab.online -d pulab.online -d www.pulab.online \
  --email your@email.com --agree-tos --no-eff-email

# Certbot:
#   - сам впишет ssl_certificate в /etc/letsencrypt/live/app.pulab.online/...
#   - сам поставит cron на автообновление
#   - НЕ будет перенастраивать редирект (он уже в нашем конфиге)

# Применить
sudo systemctl reload nginx
```

Проверка:
```bash
curl -sI https://app.pulab.online/
# Должно быть: HTTP/2 200, server: nginx
```

---

## Шаг 5. Запустить Node.js воркер (3 минуты, на VPS)

```bash
ssh -i ~/.ssh/lab_vps deploy@185.244.xx.xx

# 1. Создать .env
cd /home/deploy/app/worker
cp /home/deploy/app/deploy/lab-api.env.example .env
chmod 600 .env
nano .env   # заполнить JWT_SECRET (openssl rand -hex 32) и секреты

# 2. Установить prod-зависимости
npm ci --omit=dev

# 3. Зарегистрировать systemd unit
sudo cp /home/deploy/app/deploy/lab-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lab-api
sudo systemctl status lab-api

# 4. Проверить
curl -s http://127.0.0.1:8787/health
# {"status":"ok","environment":"production",...}

# 5. Проверить через Nginx
curl -s https://app.pulab.online/health
# То же самое
```

Логи:
```bash
sudo journalctl -u lab-api -f
# или
sudo journalctl -u lab-api -n 100 --no-pager
```

---

## Шаг 6. DNS — переключить домены (2 минуты, у регистратора)

В панели DNS домена `pulab.online` (или `app.pulab.online`):

```
app.pulab.online.   A   185.244.xx.xx
api.pulab.online.   A   185.244.xx.xx
pulab.online.       A   185.244.xx.xx
www.pulab.online.   A   185.244.xx.xx
```

(если `app` и `pulab` — это поддомен, то в записях `pulab.online. A` — IP основного домена)

**Ждём 5–30 минут** на распространение DNS, проверяем:
```bash
nslookup app.pulab.online
dig app.pulab.online
```

---

## Шаг 7. Smoke-тест (5 минут, без VPN!)

```bash
# 1. Главная страница
curl -sI https://app.pulab.online/ | head -3
# HTTP/2 200

# 2. Шрифты (должны отдаваться локально)
curl -sI https://app.pulab.online/fonts/manrope-400.woff2
# HTTP/2 200, content-type: font/woff2

# 3. API
curl -s https://app.pulab.online/health
# {"status":"ok"...}

# 4. Без VPN — попросите 2-3 человек открыть сайт из РФ
#    https://app.pulab.online/  → должна грузиться, шрифты работать
```

**ВАЖНО:** проверяйте доступ **именно из РФ без VPN**. Самые частые грабли —
что сайт открылся у вас через корпоративный прокси, а у пользователей в РФ —
всё ещё блокировка.

---

## Автоматический деплой (CI/CD)

После первоначальной настройки используйте `deploy-vps.ps1`:

```powershell
cd C:\Users\kfigh\lab_site
.\deploy-vps.ps1 -VpsHost 185.244.xx.xx
```

Скрипт за 1–2 минуты:
1. Соберёт Astro (`npm run build`)
2. Соберёт воркер (`npm run build` в `worker/`)
3. Скопирует `dist/`, `worker/` и `deploy/` на VPS через rsync
4. Перезапустит `lab-api` через `systemctl restart lab-api`
5. Перезагрузит Nginx (`nginx -s reload`)
6. Покажет статус health-check

---

## Мониторинг (рекомендую)

| Что | Как |
|---|---|
| Аптайм | UptimeRobot.com (бесплатно, 50 проверок) — пингует `/health` |
| Логи | `journalctl -u lab-api -f` |
| Размер SQLite | `du -sh /var/lib/lab-site/kv.db` |
| Снэпшот VPS | Раз в сутки через панель Reg.ru (включено) |
| Бэкап SQLite | По cron раз в сутки → `/var/www/lab-site/backups/kv-$(date +%F).db` |

Пример cron-задачи для бэкапа:
```bash
# /etc/cron.d/lab-site-backup
0 3 * * * deploy sqlite3 /var/lib/lab-site/kv.db ".backup '/var/www/lab-site/backups/kv-$(date +\%F).db'" && find /var/www/lab-site/backups -name "kv-*.db" -mtime +7 -delete
```

---

## Откат

Если что-то пошло не так:
1. **Cloudflare Pages не отключайте**, пока новый стек не обкатается 1-2 недели
2. Просто переключите DNS обратно (записи на Cloudflare)
3. Сайт мгновенно вернётся к работе через Cloudflare

Если нужно откатить именно код на VPS:
```bash
ssh deploy@185.244.xx.xx
sudo systemctl stop lab-api
# Поднять из бэкапа (Reg.ru) или из /var/www/lab-site/backups/
sudo systemctl start lab-api
```

---

## Чек-лист "всё работает в РФ"

- [ ] Сайт открывается без VPN
- [ ] Шрифты загружаются (F12 → Network → `manrope-400.woff2` → 200)
- [ ] Нет 404 на JS/CSS бандлы
- [ ] API `/health` отдаёт `status:ok`
- [ ] Авторизация (magic-link на email) работает
- [ ] Генерация книги (POST `/generate/jobs`) работает
- [ ] Трекер (`/tracker`) сохраняет желания
- [ ] Яндекс.Метрика срабатывает (проверьте в YM Debug)
- [ ] Нет ошибок в `journalctl -u lab-api -n 100`

Когда все галочки стоят — **отключайте Cloudflare Pages** (Workers оставьте как запасной вариант).
