# Рассвет желания — Pinterest (2:3, watercolor, warm)

**Формат:** Карточка Pinterest (2:3, target 1000×1500)
**Профиль:** lab
**Стиль:** watercolor
**Настроение:** warm

## Исходный запрос

```
Рассвет над книгой желаний
```

## Финальный EN-промпт

```
A magical sunrise over an open book with pages catching golden hour light, 
soft watercolor illustration, warm tones, sunset colors, golden hour, 
gentle and dreamy mood, rose-pink and warm orange color scheme, 
#E11D48 accents, no text, no watermark, high quality, detailed
```

## Параметры

| Поле | Значение |
|------|----------|
| format | pinterest |
| width_ratio | 4 |
| height_ratio | 6 |
| aspect | 2:3 |
| target_size | [1000, 1500] |
| style | watercolor |
| mood | warm (override из CLI) |
| Размер PNG | 256×384 (~20-50 КБ в Phase 1) |

## Команда

```bash
# С override mood
python scripts/image.py generate pinterest "Рассвет над книгой желаний" --mood=warm --profile=lab

# С дефолтным mood
python scripts/image.py generate pinterest "Рассвет над книгой желаний" --profile=lab
```

## Связано с

- [[template-pinterest]] — формат pinterest
- [[lab-5-oshibok]] — другой пример lab (vk_post)
