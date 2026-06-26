"""Кейс 2026-06-25: подтянуть цены в 'Списание Аэротерм.xlsx'.

Исходный файл: 'Списание Аэротерм.xlsx' на рабочем столе
Лист-источник: 'Себестоимость' (998 строк, артикул в A, цена в B)
Лист-приёмник: 'Списание' (43 строки, артикул в F, цена в H)

Потом добавляем колонку 'Сумма' = G * H.

Запуск:
    python examples/aero_term_vlookup.py
"""
import subprocess
import sys
from pathlib import Path

DESKTOP = Path.home() / "OneDrive" / "Desktop"
SRC = DESKTOP / "Списание Аэротерм.xlsx"

if not SRC.exists():
    print(f"❌ Файл не найден: {SRC}")
    sys.exit(2)

PY = sys.executable
SCRIPTS = Path(__file__).parent.parent / "scripts"

# 1. Подтянуть цены
print("\n=== Шаг 1: подставляем цены ===")
subprocess.run([
    PY, str(SCRIPTS / "excel_vlookup.py"), str(SRC),
    "--src-sheet", "Себестоимость", "--src-key-col", "A", "--src-val-col", "B",
    "--dst-sheet", "Списание",     "--dst-key-col", "F", "--dst-val-col", "H",
    "--key-as-text",
], check=True, env={"PYTHONIOENCODING": "utf-8", **__import__("os").environ})

# 2. Добавить колонку Сумма
OUT = DESKTOP / "Списание Аэротерм — с ценами.xlsx"
print("\n=== Шаг 2: добавляем колонку Сумма ===")
subprocess.run([
    PY, str(SCRIPTS / "excel_sum_column.py"), str(OUT),
    "--sheet", "Списание",
    "--col1", "G", "--col2", "H",
    "--out-col", "I", "--header", "Сумма",
], check=True, env={"PYTHONIOENCODING": "utf-8", **__import__("os").environ})

print("\n🎉 Готово!")
