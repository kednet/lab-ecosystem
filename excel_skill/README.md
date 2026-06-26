# Excel Skill

Стандартные детерминированные операции с `.xlsx` файлами. Без LLM.

## Что внутри

- `scripts/excel_inspect.py` — структура файла (листы, колонки, заголовки, первые строки)
- `scripts/excel_vlookup.py` — подставить значение по ключу (как VLOOKUP)
- `scripts/excel_sum_column.py` — добавить колонку с формулой (=A*B или =A+B)
- `scripts/excel_fill_missing.py` — заполнить пустые ячейки (предыдущее / следующее / значение)
- `scripts/excel_dedupe.py` — найти или удалить дубликаты по ключу
- `scripts/excel_count_unique.py` — посчитать уникальные значения
- `scripts/excel_to_csv.py` — выгрузить лист в CSV (UTF-8 BOM по умолчанию)
- `scripts/excel_to_json.py` — выгрузить лист в JSON

## Установка

Только `openpyxl`:

```bash
pip install openpyxl
```

Больше ничего не нужно. Скрипты не лезут в сеть, не требуют API-ключей.

## Быстрый старт

```bash
# Посмотреть, что в файле
python scripts/excel_inspect.py "мой файл.xlsx"

# Подставить цену по артикулу (с одного листа на другой)
python scripts/excel_vlookup.py "мой файл.xlsx" \
    --src-sheet Себестоимость --src-key-col A --src-val-col B \
    --dst-sheet Списание     --dst-key-col F --dst-val-col H

# Добавить колонку "Сумма" = G * H
python scripts/excel_sum_column.py "мой файл.xlsx" \
    --sheet Списание --qty-col G --price-col H --out-col I --header "Сумма"
```

## Главные правила

1. **Всегда `PYTHONIOENCODING=utf-8`** при запуске на Windows (иначе cp1252 уронит `print` с кириллицей).
2. **Файл должен быть закрыт** в Excel — иначе `PermissionError: [Errno 13]`.
3. **Оригинал не трогаем** — по умолчанию каждый скрипт создаёт `* — out.xlsx` рядом. Флаг `--in-place` перезапишет исходник.
4. **Артикулы как текст** — если в ключевой колонке числа с ведущими нулями (`00789`), openpyxl читает их как int и нули теряются. Скрипты умеют `--key-as-text` для принудительного строкового сравнения.

Подробности — в `SKILL.md` и `docs/pitfalls.md`.
