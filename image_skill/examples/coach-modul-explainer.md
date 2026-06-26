# Модуль 1 explainer — WishCoach (заглушка)

**Формат:** (заполняется)
**Профиль:** coach (golden palette)
**Стиль:** watercolor (default из coach.yaml)
**Настроение:** warm (default из coach.yaml)

## Исходный запрос

```
Модуль 1: как отличить навязанное желание от истинного
```

## Параметры (планируемые)

| Поле | Значение |
|------|----------|
| format | pinterest |
| style | watercolor |
| mood | warm |
| palette | primary `#F59E0B` (golden) |

## Команда

```bash
python scripts/image.py generate pinterest "Модуль 1: как отличить навязанное желание от истинного" --profile=coach
```

## Что нужно сделать (Phase 2)

1. Заполнить реальным `prompt_text` после первого прогона.
2. Заполнить реальный `seed` и `image_size_kb`.
3. Добавить screenshot PNG.

## Связано с

- [[profile-coach]] — полный профиль (пока заглушка)
- [[wishcoach-project]] — целевой продукт
