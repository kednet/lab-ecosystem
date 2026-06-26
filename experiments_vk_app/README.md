# Experiments VK Mini App

Мини-форма «Поделиться экспериментом» — 5 полей, 2 минуты, без регистрации.
Задеплоен как VK Mini App сообщества «ЛАБОРАТОРИЯ ЖЕЛЕНИЙ» (id=237295798), app_id=54643519.

## Что внутри

Один автономный HTML-файл (`index.html`) — никакой сборки, никаких зависимостей от lab-site / `_astro/`.
Внутри:
- 5 шагов на одном экране (стейт-машина в JS): имя → источник → что пробовали → что получилось → согласие
- VK Bridge (инициализация, getUserInfo, taptic, share sheet, track event)
- Вне ВК работает как обычная web-страница (всё в `if (window.vkBridge)`)
- Локальные шрифты `Manrope` + `DM Serif Display` (загружаются с `app.pulab.ru/fonts/...`)
- POST → `https://api.pulab.online/api/experiments` (тот же endpoint, что использует TG-бот `@PUExperimentbot` и web-форма `/my-experiment/`)

## Отличия от Detector

| | Detector | Experiments |
|---|---|---|
| Экранов | 5 (по одному на вопрос) | 1 (5 шагов внутри одной страницы) |
| Состояние | В `answers[]` в памяти | В DOM-форме, между шагами переключаем `.is-active` |
| VK Bridge | init + taptic + share | init + taptic + share + trackEvent |
| Шаринг | результат скорится на клиенте | нет скоринга, после успеха — шаринг-ссылка |
| Endpoint | — | POST `/api/experiments` |

## Деплой (3 команды)

```bash
# 1. Залить index.html на VPS в /var/www/lab-site/dist/experiments-app/
scp -i ~/.ssh/lab_vps \
  C:/Users/kfigh/experiments_vk_app/index.html \
  deploy@89.108.88.74:/var/www/lab-site/dist/experiments-app/index.html

# 2. Права (deploy-юзер, без sudo)
ssh -i ~/.ssh/lab_vps deploy@89.108.88.74 \
  "chmod 644 /var/www/lab-site/dist/experiments-app/index.html"

# 3. Проверить
curl -I https://app.pulab.ru/experiments-app/
# Ожидаем: HTTP/2 200, content-type: text/html
```

Nginx-конфиг **не меняем** — `root /var/www/lab-site/dist` уже отдаёт подкаталоги.

## Проверка (6 сценариев)

1. **Web-версия** (в браузере): `curl -I https://app.pulab.ru/experiments-app/` → 200
2. **VK-версия**: открыть `https://vk.com/app54643519` в мобильном ВК → должна открыться форма
3. **Тактильность**: на телефоне — лёгкая вибрация при нажатии «Дальше»
4. **POST работает**: заполнить 5 шагов → получить экран «Спасибо! #id»
5. **API-эхо**: на странице успеха видно `#20260619-xxxxxx` (id от сервера)
6. **Nginx-логи**: `ssh -i ~/.ssh/lab_vps root@89.108.88.74 "tail -f /var/log/nginx/access.log | grep experiments-app"` — без 4xx/5xx

## Структура

```
C:\Users\kfigh\experiments_vk_app\
  index.html          ← мини-апп (autonomous, inline CSS+JS)
  README.md           ← этот файл
  docs\
    vk-setup.md       ← инструкция «как привязать URL к app_id 54643519»
```

## Связанное

- `app_id`: **54643519** (мини-апп «Поделиться экспериментом» в сообществе pulabru)
- URL мини-аппа: `https://app.pulab.ru/experiments-app/`
- Публичная ссылка ВК: `https://vk.com/app54643519`
- API: `https://api.pulab.online/api/experiments` (общий с TG-ботом и web-формой)
- TG-бот: `@PUExperimentbot` (`C:\Users\kfigh\experiments_bot\agent\experiments_bot.py`)
- Web-форма: `https://app.pulab.online/my-experiment/`
- Сообщество: `https://vk.com/club237295798`
- Соседний мини-апп Detector: `app_id=54640127` (см. `C:\Users\kfigh\detector_vk_app\`)

## Что НЕ делается (отложено)

- Отправка результата в воркер/БД (нужен backend endpoint, для экспериментов это уже есть — `/api/experiments` принимает payload 1-в-1)
- Авторизация по VK secure_key (для production)
- Иконка приложения 512×512 (заменить в кабинете VK)
- Кнопка «Поделиться экспериментом» в меню сообщества (настраивается в кабинете сообщества)
- Telegram Mini App по тому же шаблону
