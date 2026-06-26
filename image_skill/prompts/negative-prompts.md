# Negative Prompts — список по умолчанию

## Назначение

Список того, что НЕ генерировать в YandexART. Объединяется с `profile.negative_prompts`
(если у профиля есть свои).

## Дефолтный список (если в profile не задан)

- "text on image" — YandexART часто пытается нарисовать буквы, и они получаются криво
- "watermark" — никаких водяных знаков
- "low quality" — низкое качество
- "blurry" — размытость
- "distorted proportions" — искажённые пропорции лиц/тел
- "ugly" — антиэстетика
- "stock photo look" — узнаваемая стоковая фотография

## Использование

В `cmd_generate.py:build_prompt()` (fallback-ветка):
```python
if negative:
    parts.append(f"no {', no '.join(negative[:3])}")
```

## Почему не на каждой картинке

YandexART не поддерживает negative_prompt в API как отдельный параметр (только в одном сообщении).
Поэтому negative вшивается в конец промпта как "no {x}, no {y}".

## Связано с
- [[image-skill-v1-phase1-built]]
- [[yandex-art-api]]
