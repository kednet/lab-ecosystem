# Промо книги — WishLibrarian (заглушка)

**Формат:** (заполняется)
**Профиль:** wl (blue palette)
**Стиль:** flat (default из wl.yaml)
**Настроение:** calm (default из wl.yaml)

## Исходный запрос

```
Промо новой книги "Книга желаний"
```

## Параметры (планируемые)

| Поле | Значение |
|------|----------|
| format | vk_post |
| style | flat |
| mood | calm |
| palette | primary `#3B82F6` (blue) |

## Команда

```bash
python scripts/image.py generate vk_post "Промо новой книги" --profile=wl
```

## Что нужно сделать (Phase 2)

1. Заполнить реальным `prompt_text` после первого прогона.
2. Заполнить реальный `seed` и `image_size_kb`.
3. Добавить screenshot PNG.

## Связано с

- [[profile-wl]] — полный профиль (пока заглушка)
