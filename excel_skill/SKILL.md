---
name: excel-skill
description: Standard Excel file operations — inspect, vlookup, fill column, dedupe, convert. Use for .xlsx files when the task is deterministic (no LLM needed).
---

# Excel Skill

Детерминированная работа с `.xlsx`: инспекция, поиск и подстановка значений, формулы, фильтрация, дедупликация, выгрузка в CSV/JSON.

Не использует LLM — все операции предсказуемы и идемпотентны. Для задач вида «опиши что в файле» или «сделай выводы по таблице» — зови Claude напрямую и скармливай CSV/JSON, который делает этот скил.

## Когда звать

- Нужно узнать структуру Excel-файла (листы, колонки, заголовки, типы).
- Подставить значения с одного листа/файла на другой по ключу (VLOOKUP / INDEX-MATCH).
- Добавить колонку с формулой (сумма, произведение, вычисление).
- Заполнить пустые ячейки (по умолчанию / по соседней строке / по ключу).
- Найти или удалить дубликаты.
- Посчитать уникальные значения в колонке.
- Сконвертировать в CSV или JSON (для отладки или передачи в LLM).

## Когда НЕ звать

- Задача требует интерпретации смысла («опиши таблицу», «сделай вывод») — сначала конвертни в CSV/JSON через этот скил, потом передай Claude.
- Файл `.xls` (старый формат) — этот скил только `.xlsx` / `.xlsm`. Для `.xls` сначала пересохрани в Excel.
- VBA-макросы (`.xlsm` с кодом) — openpyxl читает структуру, но не редактирует VBA-код.
- Огромные файлы (>50 МБ, >100К строк) — лучше через `pandas` с `usecols=` / `dtype=`. См. `docs/pitfalls.md`.

## CLI

Все скрипты лежат в `scripts/`. Зовутся одинаково:

```bash
python scripts/excel_inspect.py FILE [--sheet NAME] [--head N]
python scripts/excel_vlookup.py SRC_KEY_FILE --src-sheet S1 --src-key-col A --src-val-col B \
                                --dst-file FILE  --dst-sheet S2 --dst-key-col F --dst-val-col H
python scripts/excel_sum_column.py FILE --sheet S --qty-col G --price-col H --out-col I --header "Сумма"
python scripts/excel_fill_missing.py FILE --sheet S --col H --mode previous|next|value:0
python scripts/excel_dedupe.py FILE --sheet S --key-col F [--delete]
python scripts/excel_count_unique.py FILE --sheet S --col F [--top N]
python scripts/excel_to_csv.py FILE --sheet S --out OUT.csv [--encoding utf-8-sig]
python scripts/excel_to_json.py FILE --sheet S --out OUT.json
```

Все скрипты принимают `--help`. Все умеют `--in-place` (перезаписать исходник) — по умолчанию создают `* — out.xlsx` рядом.

## Пит-фоллы

См. `docs/pitfalls.md` — там про cp1252, залоченный файл, артикулы как текст, числа с запятой vs точкой. Главное правило:

**Windows + кириллица = `PYTHONIOENCODING=utf-8 python ...`**. Без этого первый же `print` со словом «Списание» упадёт.

## Пример: кейс «Списание Аэротерм»

Запустить `examples/aero_term_vlookup.py` — копия сессии 2026-06-25, где 40 цен были подтянуты с листа «Себестоимость» по артикулу.
