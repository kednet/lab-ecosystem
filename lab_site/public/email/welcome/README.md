# Email-баннеры для welcome-цепочки «История одного желания»

7 баннеров 600×250 для 7 писем цепочки (18 дней).

| Файл | Шаг | Заголовок | Подпись | URL для вставки |
|------|-----|-----------|---------|-----------------|
| `step-01.jpg` | 1/7 | Вы здесь — и это уже шаг | детектор желаний · 2 минуты | `https://app.pulab.ru/email/welcome/step-01.jpg` |
| `step-02.jpg` | 2/7 | Своё vs навязанное | один вопрос-фильтр | `https://app.pulab.ru/email/welcome/step-02.jpg` |
| `step-03.jpg` | 3/7 | Тело как компас | 3 минуты тишины | `https://app.pulab.ru/email/welcome/step-03.jpg` |
| `step-04.jpg` | 4/7 | Запишите одно желание | формула: хочу + потому что | `https://app.pulab.ru/email/welcome/step-04.jpg` |
| `step-05.jpg` | 5/7 | Услышать других | истории участниц + Telegram | `https://app.pulab.ru/email/welcome/step-05.jpg` |
| `step-06.jpg` | 6/7 | Сообщество: не одна | ВКонтакте · Telegram · клуб | `https://app.pulab.ru/email/welcome/step-06.jpg` |
| `step-07.jpg` | 7/7 | Поделитесь результатом | ваша история → в ленту | `https://app.pulab.ru/email/welcome/step-07.jpg` |

## Где брать файлы для UniSender

- На проде: по URL выше (положила в `public/email/welcome/`).
- Локально (для drag'n'drop в редактор UniSender): `C:\Users\kfigh\lab_site\public\email\welcome\step-0X.jpg`.

## Генератор (если нужно переделать)

`C:\Users\kfigh\temp\make_welcome_banners.py` — Pillow, без API, ~1 сек на 7 штук. Меняешь `LETTERS` и перезапускаешь.

## Стиль

- Палитра: тёплый розовый (#FFF1F2 → #FFE4E6) + винный акцент (#881337).
- Шрифты: Segoe UI Bold/Regular (стандарт Windows).
- Формат: JPEG 88% quality, progressive — 12-15 КБ на письмо.
- Все клиенты (Outlook, Gmail, Яндекс, Mail.ru) корректно отрисуют.
