# Fonts

Шрифты для `cmd_auto.py` (Phase 2: text overlay + watermark).

## Fallback chain

Скрипты `burn_text.py` и `burn_watermark.py` ищут шрифты в порядке:

1. `assets/fonts/Inter-Bold.ttf` (предпочтительный)
2. `C:\Windows\Fonts\arialbd.ttf` (Windows fallback)
3. `C:\Windows\Fonts\segoeuib.ttf` (Segoe UI Bold)
4. Pillow default (последний resort)

## Почему Inter-Bold не скачан

Корпоративный MITM режет `fonts.gstatic.com` (TLS interception не проходит валидацию отзыва сертификатов на Windows). См. [[corporate-mitm-proxy]].

## Как положить Inter-Bold вручную

1. Скачать с https://fonts.google.com/specimen/Inter (zip 350 КБ) на личном устройстве
2. Извлечь `Inter-Bold.ttf` (статическая версия, не variable)
3. Положить в эту папку
4. Удалить README (опционально)

Без Inter-Bold всё работает на `arialbd.ttf` — кириллица есть, метрики чуть шире, видно в коде как `font.family="Arial"`.
