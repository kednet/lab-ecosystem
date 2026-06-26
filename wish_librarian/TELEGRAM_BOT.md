# 🤖 Telegram-бот для WishLibrarian — Полная инструкция

> Запуск ИИ-агента «Библиотекарь желаний» в виде Telegram-бота:
> скидываешь ссылку на книгу — получаешь конспект, воркбук, советы.

---

## 📑 Содержание

1. [Быстрый старт (10 минут)](#-быстрый-старт-10-минут)
2. [Шаг 1. Создание бота в @BotFather](#-шаг-1-создание-бота-в-botfather)
3. [Шаг 2. Настройка WishLibrarian](#-шаг-2-настройка-wishlibrarian)
4. [Шаг 3. Запуск](#-шаг-3-запуск)
5. [Шаг 4. Проверка](#-шаг-4-проверка)
6. [Команды бота](#-команды-бота)
7. [Inline-кнопки](#-inline-кнопки)
8. [Деплой на сервер](#-деплой-на-сервер)
9. [Деплой через Docker](#-деплой-через-docker)
10. [Деплой через systemd (Linux)](#-деплой-через-systemd-linux)
11. [Типичные ошибки](#-типичные-ошибки)
12. [Безопасность токена](#-безопасность-токена)
13. [Что внутри бота](#-что-внутри-бота)

---

## 🚀 Быстрый старт (10 минут)

```
1. Открыть @BotFather → /newbot → получить токен
2. set TELEGRAM_BOT_TOKEN=123:ABC-DEF
3. python -m agent.cli --doctor        ← убедиться, что AI-провайдер работает
4. python -m agent.telegram_bot
5. Открыть своего бота в Telegram → /start
```

Готово. Скидывайте ссылку на книгу.

---

## 🤖 Шаг 1. Создание бота в @BotFather

### 1.1. Найти BotFather

В Telegram в строке поиска наберите **@BotFather** (синяя галочка, official
бот от Telegram). Нажмите «Start» или отправьте `/start`.

### 1.2. Создать нового бота

```
Вы:     /newbot
Bot:    Alright, a new bot. How are we going to call it?
        Please choose a name for your bot.

Вы:     WishLibrarian Bot    ← любое имя, его увидят пользователи

Bot:    Good. Now let's choose a username for your bot.
        It must end in `bot`. Like this, for example: TetrisBot.

Вы:     wish_librarian_kf_bot   ← уникальный, заканчивается на `bot`
                                  (должен быть свободен)

Bot:    Done! Congratulations on your new bot.
        You will find it at t.me/wish_librarian_kf_bot.
        Use this token to access the HTTP API:
        1234567890:ABCdefGHIjklMNOpqrsTUVwxyz-12345   ← ЭТО ВАШ ТОКЕН

        Keep your token secure and store it safely.
        ...
```

**Скопируйте токен** — это длинная строка вида `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz-12345`.

### 1.3. Настроить описание (опционально)

```
/setdescription → "Парсит книги с koob.ru, LiveLib, Литреса. Генерирует конспект, воркбук и советы."
/setabouttext   → "ИИ-агент «Библиотекарь желаний» на базе Claude/YandexGPT/GigaChat."
/setuserpic     → [отправьте картинку]
/setcommands    →
                  start - Справка
                  add - Добавить книгу
                  list - Последние книги
                  search - Поиск
                  book - Открыть конспект
                  export - Экспорт
                  doctor - Диагностика
                  cancel - Отменить обработку
```

### 1.4. Что не делать

- **Не публикуйте токен** в открытых репозиториях, чатах, скриншотах.
- **Не доверяйте токен посторонним** — он даёт полный контроль над ботом.
- Если токен утёк — `/revoke` в BotFather, получите новый.

---

## ⚙️ Шаг 2. Настройка WishLibrarian

### 2.1. Убедиться, что `aiogram` установлен

```bash
pip install aiogram>=3
```

Или переустановить всё:

```bash
pip install -r requirements.txt
```

### 2.2. Проверить AI-провайдера

Telegram-бот использует тот же `AI_PROVIDER` из `.env`, что и CLI. Сначала
убедитесь, что он работает:

```bash
python -m agent.cli --doctor
# Должно быть: 🤖 AI: claude (claude:claude-sonnet-4-5) — ✅ работает
```

Если AI-провайдер не настроен — заполните `.env` (см. [USAGE.md](./USAGE.md#-конфигурация-env)).

**Без рабочего AI-провайдера бот сможет только парсить, но не генерировать контент.**

### 2.3. Установить токен

#### Windows (cmd)

```cmd
set TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz-12345
```

#### Windows (PowerShell)

```powershell
$env:TELEGRAM_BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz-12345"
```

#### Linux / Mac

```bash
export TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz-12345
```

#### Постоянно (рекомендуется для прод)

Добавьте в `~/.bashrc` (или `~/.zshrc`, или Windows Environment Variables):

```bash
export TELEGRAM_BOT_TOKEN=...
```

Либо загружайте из `.env` через `python-dotenv` в своём лаунчере.

---

## ▶ Шаг 3. Запуск

### 3.1. Простой запуск (для теста)

```bash
python -m agent.telegram_bot
```

В консоли:

```
🤖 Telegram-бот запущен
🤖 WishLibrarian Bot is running. Press Ctrl+C to stop.
```

### 3.2. Фоновый режим (Linux/Mac)

```bash
nohup python -m agent.telegram_bot > logs/telegram.log 2>&1 &
```

### 3.3. Через tmux/screen (если SSH)

```bash
tmux new -s wishbot
python -m agent.telegram_bot
# Ctrl+B, D — отсоединиться
# tmux attach -t wishbot — вернуться
```

---

## ✅ Шаг 4. Проверка

1. Откройте в Telegram своего бота: `t.me/wish_librarian_kf_bot`
2. `/start` — должно появиться приветствие
3. `/doctor` — диагностика (AI-провайдер, зависимости, число книг)
4. `/add https://www.koob.ru/zeland/level1` — обработка книги

При успехе появится сообщение с кнопками **📝 Summary**, **✍️ Workbook**, **💡 Tips**, **📄 Всё в .txt**.

---

## ⌨ Команды бота

| Команда | Что делает | Пример |
|---------|-----------|--------|
| `/start`, `/help` | Справка | `/start` |
| `/add <URL>` | Обработать книгу | `/add https://www.koob.ru/zeland/level1` |
| `/cancel` | Отменить текущую обработку | `/cancel` |
| `/list [N]` | Последние N книг (default 10, max 50) | `/list 20` |
| `/search <запрос>` | Поиск по библиотеке | `/search привычки` |
| `/book <название>` | Прислать summary.md | `/book трансерфинг` |
| `/export <fmt> <название>` | Экспорт в txt/html/pdf/... | `/export txt трансерфинг` |
| `/doctor` | Диагностика | `/doctor` |

### Пример сессии

```
Вы:     /start
Бот:    📚 WishLibrarian Bot
        Я обрабатываю книги с koob.ru, LiveLib, Лабиринта, Литрес и др.
        ...

Вы:     /add https://www.koob.ru/zeland/level1
Бот:    ⏳ Обрабатываю:
        https://www.koob.ru/zeland/level1
        ...
Бот:    ✅ Готово!
        📖 Трансерфинг реальности
        ✍️ Зеланд Вадим
        📅 2004
        📁 Зеланд_Трансерфинг_...
        [📝 Summary] [✍️ Workbook]
        [💡 Tips]    [📄 Всё в .txt]

Вы:     /book трансерфинг
Бот:    [summary.md разбитый на части по 4000 символов]
```

### Свободный текст = URL

Если вы пришлёте боту просто ссылку (без `/add`) — бот обработает её так же:

```
Вы:     https://www.koob.ru/zeland/level1
Бот:    ⏳ Обрабатываю: ...
```

---

## 🖱 Inline-кнопки

После успешной обработки книги бот показывает 4 кнопки:

| Кнопка | Действие |
|--------|----------|
| 📝 Summary | Прислать полный конспект (разбитый на сообщения) |
| ✍️ Workbook | Прислать воркбук |
| 💡 Tips | Прислать практические советы |
| 📄 Всё в .txt | Сгенерировать .txt-файл и прислать документом |

---

## 🌐 Деплой на сервер

### Вариант A. VPS (Timeweb, Aéza, Selectel, …)

**Минимальные требования**: 1 vCPU, 1 ГБ RAM, 10 ГБ диска, Ubuntu 22.04.

```bash
# 1. Подключиться
ssh root@your-server-ip

# 2. Установить Python
apt update && apt install -y python3.12 python3.12-venv

# 3. Скопировать проект
git clone https://github.com/your/wish_librarian.git
cd wish_librarian

# 4. venv + зависимости
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 5. .env
cp .env.example .env
nano .env   # вписать ключи

# 6. Запустить под systemd (см. ниже)
```

### Вариант B. Docker

`Dockerfile` в корне проекта:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent/ ./agent/
COPY .env .
CMD ["python", "-m", "agent.telegram_bot"]
```

Сборка и запуск:

```bash
docker build -t wishlibrarian-bot .
docker run -d \
  --name wishlibrarian \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN="123456:ABC..." \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/cache:/app/cache \
  wishlibrarian-bot
```

### Вариант C. systemd (Linux, рекомендуется)

`/etc/systemd/system/wishlibrarian.service`:

```ini
[Unit]
Description=WishLibrarian Telegram Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/wish_librarian
Environment="TELEGRAM_BOT_TOKEN=123456:ABC..."
ExecStart=/opt/wish_librarian/.venv/bin/python -m agent.telegram_bot
Restart=always
RestartSec=10
StandardOutput=append:/var/log/wishlibrarian/bot.log
StandardError=append:/var/log/wishlibrarian/bot.log

[Install]
WantedBy=multi-user.target
```

```bash
# 1. Подготовить
sudo mkdir -p /opt/wish_librarian /var/log/wishlibrarian
sudo chown -R www-data:www-data /opt/wish_librarian /var/log/wishlibrarian
cd /opt/wish_librarian && git clone … .

# 2. Создать venv от www-data
sudo -u www-data python3.12 -m venv .venv
sudo -u www-data .venv/bin/pip install -r requirements.txt

# 3. Включить
sudo systemctl daemon-reload
sudo systemctl enable wishlibrarian
sudo systemctl start wishlibrarian

# 4. Проверить
sudo systemctl status wishlibrarian
sudo tail -f /var/log/wishlibrarian/bot.log
```

Управление:

```bash
sudo systemctl stop wishlibrarian     # остановить
sudo systemctl restart wishlibrarian # перезапустить
sudo journalctl -u wishlibrarian -f  # логи в реальном времени
```

### Вариант D. Бесплатно — на домашнем ПК / ноутбуке

Если у вас есть компьютер, который не выключается — `python -m agent.telegram_bot`
в tmux-сессии. Минус: при перезагрузке нужно поднимать руками.

---

## 🧯 Типичные ошибки

### `❌ TELEGRAM_BOT_TOKEN не задан`

Переменная окружения не видна процессу. Проверьте:

```bash
# Linux/Mac
echo $TELEGRAM_BOT_TOKEN

# Windows cmd
echo %TELEGRAM_BOT_TOKEN%
```

Если пусто — экспортируйте заново **в том же терминале**, где запускаете бота.

### `RuntimeError: No AI keys configured`

Бот запустился, но `AI_PROVIDER` из `.env` не имеет ключа. Решение:
1. `python -m agent.cli --doctor` — посмотреть, что не так
2. Заполнить `.env` (см. [USAGE.md](./USAGE.md#-конфигурация-env))
3. Перезапустить бот

### `Conflict: terminated by other getUpdates`

Запущено **два** экземпляра бота одновременно (например, на сервере и локально).
Telegram разрешает только **один** `getUpdates` на токен.

```bash
# Найти все процессы
ps aux | grep telegram_bot
# Убить лишние
kill <PID>
```

### Бот молчит (не отвечает на /start)

1. Проверьте, что токен правильный (`/revoke` → создать новый в BotFather).
2. Посмотрите логи — там может быть `httpx` timeout (SOCKS-прокси мешает).
3. С VPN-клиентом `httpx` падает на SOCKS4 — отключите VPN для теста.

### `httpx: SOCKS proxy error`

Добавьте в код запуска:

```python
# в самом начале agent/telegram_bot.py
import os
for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
         "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(k, None)
```

(Уже сделано в коде — но если у вас `socks5://` в `HTTPS_PROXY` через VPN,
то `trust_env=False` в `httpx.Client` отключает чтение прокси.)

### Бот обрабатывает книгу 5 минут

Это нормально — AI-генерация конспекта ~10–30 сек, плюс скачивание обложки,
отзывы, научные статьи. На медленном интернете может быть дольше.

Чтобы ускорить:
- `--ai yandex` (YandexGPT быстрее Claude)
- В `.env`: `ENABLE_SCIENTIFIC_SEARCH=false`
- Используйте `--no-ai-cache` только когда нужна свежая генерация

---

## 🔐 Безопасность токена

### Что может сделать тот, у кого есть токен?

**Абсолютно всё** от имени бота:
- Читать все сообщения боту
- Отправлять сообщения от бота
- Видеть список пользователей
- Удалять/редактировать сообщения

### Правила

1. **Никогда** не коммитьте токен в git.
2. **Никогда** не показывайте токен в скриншотах/демо.
3. **Всегда** храните токен в `.env` (в `.gitignore`) или в переменных окружения.
4. **Периодически** делайте `/revoke` и пересоздавайте токен.
5. **Ограничивайте** доступ к серверу, где крутится бот.

### `.gitignore` (обязательно)

```gitignore
.env
output/library/
cache/
logs/
```

### Если токен утёк

1. Открыть @BotFather
2. `/revoke` → выбрать бота
3. Получить новый токен
4. Обновить в `.env` / `systemd`-юните / Docker-окружении
5. Перезапустить бот

---

## 🛠 Что внутри бота

`agent/telegram_bot.py` использует **aiogram 3.28.2**. Архитектура:

```
User message
   ↓
aiogram Dispatcher
   ↓
Command filter (/add, /list, …)
   ↓
Handler (cmd_add, cmd_list, …)
   ↓
WishLibrarian.process_book(url, force=False, parse_only=False)  ← в executor
   ↓
Inline-кнопки для summary/workbook/tips
```

**Особенности**:

- **Executor**: `loop.run_in_executor(None, librarian.process_book, ...)` —
  блокирующая обработка не подвешивает event loop.
- **State**: `_chat_state[chat_id] = {processing, current_url, librarian}` —
  один librarian на чат.
- **Chunking**: `_split_message(text, 4000)` — длинные summary.md
  разбиваются на несколько сообщений (Telegram лимит — 4096).
- **Inline-кнопки**: после `/add` — кнопки `book:summary:FOLDER`, `book:workbook:FOLDER`,
  `book:tips:FOLDER`, `export:txt:FOLDER`. При нажатии присылают соответствующий
  файл.
- **Только один процесс на токен**: `getUpdates` — single-consumer. Не запускайте
  бота в двух терминалах.

**Зависимости**: только `aiogram>=3` (уже в `requirements.txt`).

---

## 📚 Дополнительно

- [USAGE.md](./USAGE.md) — общая инструкция (CLI, экспорт, поиск, doctor)
- [README.md](./README.md) — обзор проекта
- [aiogram docs](https://docs.aiogram.dev/en/v3.0.0/) — если хотите добавить свои хендлеры
- [@BotFather](https://t.me/BotFather) — управление ботом
- [Telegram Bot API](https://core.telegram.org/bots/api) — официальная документация
