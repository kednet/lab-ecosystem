---
name: english-glossary
description: IT-глоссарий + поиск слов + CSV экспорт
---

# english-glossary — IT-глоссарий

Два набора: **main** (80 must-know фраз) и **xlsx** (244 термина из рабочего словаря kfigh). Поиск по слову, фильтр по группе, экспорт в CSV для Anki.

## Использование

```bash
# Все группы (main по умолчанию)
python scripts/english.py glossary

# xlsx набор (244 термина)
python scripts/english.py glossary --source=xlsx

# Конкретная группа
python scripts/english.py glossary --topic=meetings
python scripts/english.py glossary --source=xlsx --topic=core_dev

# Поиск одного слова (во всех наборах)
python scripts/english.py glossary --word=deploy
python scripts/english.py glossary --word=auth

# Экспорт в CSV
python scripts/english.py glossary --export=csv
python scripts/english.py glossary --source=xlsx --export=csv
python scripts/english.py glossary --topic=standup --export=csv
```

## Параметры

| Параметр | Описание |
|---|---|
| `--source` | `main` (80 фраз, default) или `xlsx` (244 термина) |
| `--topic=X` | Фильтр по группе |
| `--word=WORD` | Поиск одного слова (en или ru) |
| `--export=csv` | Экспорт в CSV для Anki |

## main (8 групп × 10 фраз = 80)

`meetings`, `code-review`, `standup`, `delivery`, `incidents`, `negotiation`, `onboarding`, `retrospectives`

## xlsx (12 групп × 244 термина)

`core_dev` (180), `data_structures` (26), `security` (9), `databases` (8), `architecture` (4), `principles` (4), `git_files` (3), `ui_frontend` (3), `web_network` (3), `testing` (2), `errors` (1), `devops_cloud` (1)

**Рекомендация:** начинать с `core_dev` (180 базовых слов) — фундамент B1.

## CSV импорт в Anki

1. `glossary --source=xlsx --export=csv` → создаёт `tmp/glossary_export/glossary_xlsx.csv`
2. Anki → File → Import → выбери CSV
3. Field mapping:
   - Field 1 = `phrase`
   - Field 2 = `translation_ru`
   - Field 3 = `example_en`
   - Field 4 = `example_ru`
   - Field 5 = `tags`
4. Note type: Basic (или создать кастомный с полями en/ru)

## Поиск слова

`--word=auth` ищет подстроку во всех EN/RU полях обоих наборов:
```
🔍 Перевод: auth
=================
Найдено совпадений: 2

### authenticate
**Перевод:** аутентификация, проверка подлинности...
**Группа:** 🔐 Безопасность (`xlsx`)

### authorize
**Перевод:** авторизация, разрешить...
**Группа:** 🔐 Безопасность (`xlsx`)
```

## Связанные команды

- [[english-lesson]] — vocab дня в уроке
- [[english-dialog]] — recap_vocab в диалогах
