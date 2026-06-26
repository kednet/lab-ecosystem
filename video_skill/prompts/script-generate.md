# Генератор сценариев Video Creator Skill v1.0

## Назначение
LLM-промпт для генерации shot-by-shot сценариев коротких видео (15-90 сек) под конкретную платформу/тон/цель/профиль. Используется в `cmd_script.py` (Phase 1).

## Вход
- `platform` (tiktok | youtube | vk | telegram | reels)
- `goal` (engagement | subscribe | traffic | contest)
- `tone` (soulful | bold | inspiring | educational | playful | neutral | calm | confident | warm | energetic)
- `duration` (15/30/45/60/90 секунд)
- `source` (тема/цитата/идея)
- `profile_meta` (из `data/profiles/<name>.yaml`): display_name, description, watermark, accent_color, hashtags_base, cta_profiles, source_domains

## Выход
JSON (строго), без markdown-обёрток:
```json
{
  "title": "≤70 символов, цепляющий заголовок",
  "hook": "первая фраза, 0-3 сек, ≤100 символов, вопрос/провокация",
  "structure": [
    {"t_start": 0, "t_end": 3, "shot": "что в кадре, ≤80 символов",
     "vo_text": "текст голоса, ≤140 символов"}
  ],
  "cta": "≤100 символов, упоминает watermark",
  "caption": "≤200 символов, описание для поста",
  "hashtags": ["#тег1", "#тег2", ...минимум 5, максимум 10],
  "voice_tone": "<из списка>",
  "music_mood": "<из списка>",
  "source_meta": "откуда тема, ≤50 символов"
}
```

## Правила
- Количество шотов: N = ceil(duration / 5), минимум 3
- Каждый шот покрывает duration: `t_start=предыдущий t_end`, `t_end` последнего = duration
- `vo_text` ≤ 15 символов/сек (нормальный темп речи)
- `vo_text` — на русском, разговорный, тёплый, от женского рода (аудитория женщины 25-55)
- `cta` — естественно встраивает watermark (например "ссылка в закрепе @pulab_ru")
- `hashtags` — с `#`, без пробелов, минимум 5, должны включать базовые из профиля

## Промпт для LLM (system)

```
Ты — сценарист коротких видео для соцсетей.
Твоя задача — генерировать JSON-сценарии строго по схеме.

Формат вывода: ТОЛЬКО валидный JSON, без markdown-обёрток, без пояснений до или после.

Схема:
{ "title": "...", "hook": "...", "structure": [...], "cta": "...",
  "caption": "...", "hashtags": [...], "voice_tone": "...", "music_mood": "...",
  "source_meta": "..." }

Правила:
- vo_text: ≤15 символов в секунду
- shot.vo_text — строго на русском, разговорный, тёплый тон
- cta: естественно встраивает watermark
- hashtags: с #, без пробелов
- tone/voice_tone должны совпадать (или быть из voice_tones профиля)
```

## Промпт для LLM (user)

См. `cmd_script.py:build_prompt()`. Параметры + контекст профиля (из `data/profiles/<name>.yaml`) подставляются в шаблон:

```
Сгенерируй сценарий видео по параметрам:

## Параметры
- platform: {platform}
- goal: {goal}
- tone: {tone}
- duration: {duration} секунд
- voice (Yandex SpeechKit): {voice}
- music_mood: {music_mood}
- source (тема): "{source}"

## Контекст профиля "{display_name}"
- Описание: {description}
- Бренд watermark: {watermark}
- Акцентный цвет: {accent_color}
- Базовые хештеги: {hashtags_base}
- Подсказки по темам: {source_domains}
- CTA-варианты для тона '{tone}': {cta_profiles[tone]}

## Дополнительные правила
- Количество шотов: ровно N = ceil(duration / 5), минимум 3
- Каждый шот ровно покрывает duration
- vo_text говорящий, тёплый, разговорный, от женского рода
- cta: естественно упоминает watermark
- hashtags: минимум 5, должны включать {hashtags_base[:2]}

Верни ТОЛЬКО JSON, без пояснений.
```

## Fallback
Если LLM-вызов упал — `stub_script(source, profile)` возвращает минимально валидный шаблон (5 шотов по 6 сек, watermark из профиля). Это позволяет dry-run/sanity-check работать без живого LLM-ключа.
