# Рецепты Excel Skill

Короткие шпаргалки на каждый день.

## 0. Префикс для Windows (всегда)

```bash
export PYTHONIOENCODING=utf-8   # bash
# или
set PYTHONIOENCODING=utf-8      # cmd
```

Без этого любой `print("Привет")` в скриптах Python упадёт с `UnicodeEncodeError: cp1252`.

## 1. Посмотреть, что внутри файла

```bash
python scripts/excel_inspect.py "мой.xlsx" --head 10
```

## 2. Подставить цену по артикулу (наш кейс)

```bash
python scripts/excel_vlookup.py "мой.xlsx" \
    --src-sheet Себестоимость --src-key-col A --src-val-col B \
    --dst-sheet Списание     --dst-key-col F --dst-val-col H \
    --key-as-text
```

`--key-as-text` нужен, если артикулы строковые (`9.80.01.01179`). Без него openpyxl может прочитать «похожие» числовые ключи как `int` и маппинг сломается на ведущих нулях.

## 3. Добавить колонку «Сумма» = Кол-во × Цена

```bash
python scripts/excel_sum_column.py "мой.xlsx" \
    --sheet Списание --col1 G --col2 H \
    --out-col I --header "Сумма" --format "#,##0.00"
```

Скрипт пишет **формулу** `=G2*H2`, не число. Excel пересчитает при открытии. Чтобы «заморозить» — см. `docs/pitfalls.md` → «формулы vs значения».

## 4. Заполнить пустые цены нулём

```bash
python scripts/excel_fill_missing.py "мой.xlsx" --sheet Списание --col H --mode value:0
```

Или подтянуть сверху (повторить предыдущее значение):

```bash
python scripts/excel_fill_missing.py "мой.xlsx" --sheet Списание --col H --mode previous
```

## 5. Найти дубликаты артикулов

```bash
python scripts/excel_dedupe.py "мой.xlsx" --sheet Списание --key-col F
```

Удалить, оставив первое вхождение:

```bash
python scripts/excel_dedupe.py "мой.xlsx" --sheet Списание --key-col F --delete
```

## 6. Сколько уникальных покупателей / SKU / артикулов

```bash
python scripts/excel_count_unique.py "мой.xlsx" --sheet Заказы --col C --top 10
```

## 7. Выгрузить в CSV для отладки / передачи в Claude

```bash
python scripts/excel_to_csv.py "мой.xlsx" --sheet Списание --out списание.csv
```

Кодировка по умолчанию — `utf-8-sig` (с BOM), чтобы Excel открыл без «крякозябр».

В JSON:

```bash
python scripts/excel_to_json.py "мой.xlsx" --sheet Списание --out списание.json --pretty
```

## 8. Перезаписать исходник (осторожно!)

Любой скрипт по умолчанию создаёт `* — out.xlsx` рядом. Чтобы перезаписать:

```bash
... --in-place
```

Рекомендую сначала прогнать без `--in-place`, посмотреть результат, и только потом перезаписывать.
