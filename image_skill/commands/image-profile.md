# /image profile

Управление профилями (5 штук: lab/wl/coach/experts/market).

## Команды

```bash
# Список всех профилей
python scripts/image.py profile list

# Показать содержимое конкретного профиля
python scripts/image.py profile show lab

# Валидировать профиль (проверить обязательные поля)
python scripts/image.py profile validate lab
```

## Что такое профиль

YAML-файл в `data/profiles/<name>.yaml` с настройками бренда:
- `defaults.{format, style, mood, seed}` — параметры по умолчанию
- `branding.palette` — 5 цветов (primary, primary_deep, primary_soft, bg, text)
- `branding.accent_color` — основной HEX
- `branding.watermark` — текст для watermark (Phase 2)
- `prompt_styles` — словарь "стиль → подсказка для LLM"
- `prompt_moods` — словарь "настроение → подсказка для LLM"
- `hashtags_base` — список хештегов (Phase 3 автопубликация)
- `negative_prompts` — список того, что НЕ генерировать
- `output.{state_subdir, filename_template}` — пути сохранения

## Доступные профили

| Профиль | display_name | Палитра | Статус |
|---------|--------------|---------|--------|
| `lab` | Лаборатория желаний | rose-pink (`#E11D48`) | ✅ полный |
| `wl` | WishLibrarian | blue (`#3B82F6`) | ⏳ заглушка |
| `coach` | WishCoach | golden (`#F59E0B`) | ⏳ заглушка |
| `experts` | Expert & Reviews Hub | violet (`#7C3AED`) | ⏳ заглушка |
| `market` | Wish Market | emerald (`#10B981`) | ⏳ заглушка |

## Пример: показать lab

```bash
$ python scripts/image.py profile show lab
{
  "name": "lab",
  "display_name": "Лаборатория желаний",
  "defaults": {
    "format": "vk_post",
    "style": "watercolor",
    "mood": "soft",
    ...
  },
  "branding": {
    "palette": {
      "primary": "#E11D48",
      ...
    }
  },
  ...
}
```

## Валидация

`profile validate lab` проверяет:
- Обязательные поля: `name`, `display_name`, `description`
- `defaults.format` есть и есть в `data/formats.yaml`
- `defaults.style` есть в `prompt_styles`
- `defaults.mood` есть в `prompt_moods`
- `branding.palette` содержит все 5 цветов
- `branding.accent_color` — валидный HEX
- `output.state_subdir` совпадает с `name`
- `negative_prompts` — list of strings

## Связано с

- [[SKILL]]
- [[sub-skill-profile-system]] — override-матрица
- [[data-profiles-lab-yaml]] — пример полного профиля
