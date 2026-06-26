# /video profile <list|show|validate> [name]

Просмотреть, показать или валидировать профили проектов (lab/wl/coach/experts/market).

## Команда

```bash
python scripts/video.py profile <list|show|validate> [name]
```

## Подкоманды

| Подкоманда | Аргумент | Описание |
|---|---|---|
| `list` | — | Список всех доступных профилей (slug, display_name) |
| `show` | `<name>` | Показать полный YAML-конфиг профиля |
| `validate` | `<name>` | Проверить, что у профиля заполнены все обязательные поля |

## Алгоритм

1. `list` → читает `data/profiles/*.yaml`, печатает таблицу `slug | display_name`
2. `show` → парсит `data/profiles/<name>.yaml` через `yaml.safe_load`, печатает pretty
3. `validate` → проверяет обязательные поля:
   - `name`, `display_name`, `description`
   - `defaults`: `platform`, `tone`, `goal`, `duration`
   - `branding`: `watermark`, `cta_default`, `palette`
   - `hashtags_base`: непустой список
   - `cta_profiles`: ≥1 ключ с непустым списком
   - `output.state_subdir`: непустая строка
   - Печатает список найденных проблем (если есть) и OK в конце

## Примеры

```bash
# Список всех профилей
python scripts/video.py profile list

# Подробности по lab
python scripts/video.py profile show lab

# Проверить, что lab корректно заполнен
python scripts/video.py profile validate lab

# Проверить заглушку (найти, что не заполнено)
python scripts/video.py profile validate wl
```

## Связано с

- `data/profiles/*.yaml` — каталог профилей
- `sub-skills/profile-system.md` — override-матрица
- `cmd_script.py:resolve_params()` — где используются поля профиля
