# Image Prompt — главный LLM-промпт image_skill

## Назначение

Преобразует русскоязычный/EN-запрос пользователя в подробный EN-промпт для YandexART.
Добавляет стилизацию, настроение, палитру, negative prompts. YandexART лучше понимает EN.

## Вход (плейсхолдеры str.format)

- `format_label` — человеческое название формата ("Пост ВКонтакте", "Карточка Pinterest")
- `aspect` — соотношение сторон ("1:1", "2:3", "9:16", "3:4", "2:1")
- `display_name` — название бренда ("Лаборатория желаний")
- `style`, `style_hint` — стиль и его описание
- `mood`, `mood_hint` — настроение и его описание
- `palette` — dict с цветами (primary, primary_deep, primary_soft, bg, text)
- `accent_color` — основной HEX
- `user_text` — запрос пользователя
- `negative` — список negative prompts через запятую

## Выход

Строка — финальный EN-промпт для YandexART (1-2 предложения, без JSON, без markdown).

## Промпт для LLM

```
## Задача
Пользователь хочет картинку для {format_label} (aspect {aspect}).
Бренд: {display_name}.
Стиль: {style} → {style_hint}
Настроение: {mood} → {mood_hint}
Палитра: {palette} (акцент: {accent_color})

## Запрос пользователя
{user_text}

## Правила
1. Преобразуй запрос в подробный промпт для YandexART на АНГЛИЙСКОМ (YandexART лучше понимает EN).
2. Добавь стилизацию: {style_hint}.
3. Добавь настроение: {mood_hint}.
4. Укажи палитру (упомяни rose-pink color scheme если палитра розовая, и т.д.).
5. Negative prompt — избегай: {negative}.
6. Верни ТОЛЬКО финальный промпт (1-2 предложения).

## Формат ответа
Только строка-промпт. Никакого JSON, никаких комментариев.
```

## Fallback (если LLM упал)

Ручная EN-сборка в `cmd_generate.py:build_prompt()`:

`{user_text}, {style_hint}, {mood_hint}, rose-pink color scheme, {accent_color} accents, no text, no watermark, high quality, detailed, professional composition`

(где color_name — это имя цвета вроде "rose-pink" / "blue" из таблицы в `cmd_generate.py:build_prompt`)

## Связано с
- [[image-skill-v1-phase1-built]] — главный memory
- [[yandex-art-api]] — API контракт
