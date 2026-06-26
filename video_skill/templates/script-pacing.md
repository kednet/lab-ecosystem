# Формула VO-длительности — Video Creator Skill v1.0 (Phase 2 STUB)

Phase 1: ЗАГЛУШКА. Phase 2: формула расчёта длительности озвучки.

## Что это
Shot.vo_text имеет лимит **15 символов/сек** (нормальный темп речи на русском). Если превышен — shot растягивается, общая длительность растёт, не влезает в target duration.

## Формула

```
shot_duration_sec = ceil(vo_text_len / 15)
```

## Правила
- Минимальный shot: 3 сек (даже если vo_text короче)
- Максимальный shot: duration/2 (один шот не может занимать больше половины ролика)
- Каждый следующий shot начинается с `t_start = prev.t_end`
- Последний shot заканчивается ровно на `duration`

## Пример
```
duration=30, N=ceil(30/5)=6 shots
shot_1: vo_text="Стой. Эта мысль меняет всё." (29 символов) → 2 сек → min 3 сек
shot_2: vo_text="Ты замечала, что карта желаний..." (50 символов) → 4 сек
shot_3: 3 сек
...
shot_6: 30-N+1 сек
```

## Phase 2
- Реализация в `scripts/cmd_script.py:build_prompt()` — добавить инструкцию LLM
- LLM должна сразу вернуть shot с правильными `t_start`/`t_end` (см. SYSTEM_PROMPT)
- Валидация в `scripts/validate_script.py` (уже есть: `sum(t_end) ≈ duration ±2 сек`)

## Связано с
- `prompts/script-generate.md` — правила для LLM
- `scripts/validate_script.py` — проверка длительности
