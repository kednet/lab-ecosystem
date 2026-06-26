# Шаблон сценария: TikTok

## Использование
Шаблон-каркас для `python scripts/video.py script tiktok ...`. Генерирует сценарий под TikTok (9:16, max 60 сек, energy/punchy тон).

## Метаданные платформы
- **aspect:** 9:16 (1080×1920)
- **max_duration:** 60 сек
- **safe_zones:** top=250, bottom=400, left=50, right=50 (для UI-оверлеев TikTok)
- **default_voice:** madirus (bold/energetic)
- **default_music_mood:** uplifting

## Структура каркаса

```markdown
# {title}

> **Hook (0-3 сек):** {hook}

**Платформа:** TikTok · **Тон:** {tone} · **Длительность:** {duration} сек
**Профиль:** {profile.display_name} · **Watermark:** {profile.branding.watermark}

## Структура
| # | t_start | t_end | Shot | VO text |
|---|---------|-------|------|---------|
{structure_table}

## CTA
> {cta}

**URL:** {profile.branding.cta_url}

## Caption
{caption}

## Hashtags
{hashtags_joined}
```

## Специфика TikTok
- Hook должен быть **≤3 сек** (первый шот короткий)
- Текст на экране — крупно, **в safe-zone** (не выше top=250 и не ниже bottom=400)
- Финал — punchy: вопрос или CTA
- BGM — uplifting/energetic, не ambient
- Хештеги: #tiktok + нишевые

## Валидация
См. `scripts/validate_script.py`:
- ≥3 shots
- sum(t_end) ≈ duration (±2 сек)
- ≥5 hashtags
- CTA ≤100 символов
- vo_text ≤140 символов

## Пример
`examples/lab-5-oshibok-karty-zhelaniy.md` (хотя тема больше для Reels, формат тот же)
