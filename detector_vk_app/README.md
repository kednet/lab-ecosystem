# Detector VK Mini App

Мини-тест «Навязанное или твоё?» — 5 вопросов, 2 минуты, мгновенный результат.
Задеплоен как VK Mini App сообщества «ЛАБОРАТОРИЯ ЖЕЛЕНИЙ» (id=237295798), app_id=54640127.

## Что внутри

Один автономный HTML-файл (`index.html`) — никакой сборки, никаких зависимостей от lab-site / `_astro/`.
Внутри:
- 5 вопросов и 6 вердиктов из `coach_agent` (логика детектора)
- VK Bridge (инициализация, getUserInfo, taptic, share sheet, track event)
- Вне ВК работает как обычная web-страница (всё в `if (window.vkBridge)`)
- Локальные шрифты `Manrope` + `DM Serif Display` (загружаются с `app.pulab.ru/fonts/...`)

## Деплой (3 команды)

```bash
# 1. Залить index.html на VPS в /var/www/lab-site/dist/detector-app/
scp -i ~/.ssh/lab_vps -r \
  C:/Users/kfigh/detector_vk_app/index.html \
  deploy@89.108.88.74:/var/www/lab-site/dist/detector-app/index.html

# 2. Права (deploy-юзер, без sudo)
ssh -i ~/.ssh/lab_vps deploy@89.108.88.74 \
  "chmod 644 /var/www/lab-site/dist/detector-app/index.html"

# 3. Проверить
curl -I https://app.pulab.ru/detector-app/
# Ожидаем: HTTP/2 200, content-type: text/html
```

Nginx-конфиг **не меняем** — `root /var/www/lab-site/dist` уже отдаёт подкаталоги.

## Проверка (6 сценариев)

1. **Web-версия** (в браузере): `curl -I https://app.pulab.ru/detector-app/` → 200
2. **VK-версия**: открыть `https://vk.com/app54640127` в мобильном ВК → должен открыться наш тест
3. **Тактильность**: на телефоне — лёгкая вибрация при выборе ответа
4. **Шаринг**: `ВКонтакте` → нативный диалог ВК (внутри мини-аппа)
5. **Шаринг-текст**: `Скопировать текст` → буфер обмена с текстом результата
6. **Nginx-логи**: `ssh -i ~/.ssh/lab_vps root@89.108.88.74 "tail -f /var/log/nginx/access.log | grep detector-app"` — без 4xx/5xx

## Структура

```
C:\Users\kfigh\detector_vk_app\
  index.html          ← мини-апп (autonomous, inline CSS+JS)
  README.md           ← этот файл
  docs\
    vk-setup.md       ← инструкция «как привязать URL к app_id 54640127»
```

## Связанное

- `app_id`: 54640127 (хранится в `C:\Users\kfigh\wish_librarian\.env` → `VK_MINI_APP_ID`)
- URL мини-аппа: `https://app.pulab.ru/detector-app/`
- Публичная ссылка ВК: `https://vk.com/app54640127`
- Web-версия (full): `https://app.pulab.ru/detector/`
- Сообщество: `https://vk.com/club237295798`

## Что НЕ делается (отложено)

- Отправка результата в воркер/БД (нужен backend endpoint)
- Авторизация по VK secure_key (для production)
- Иконка приложения 512×512 (заменить в кабинете VK)
- Кнопка «Детектор» в меню сообщества
- Telegram Mini App по тому же шаблону
