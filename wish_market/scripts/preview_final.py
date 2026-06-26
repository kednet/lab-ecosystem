"""Скрипт для просмотра wishes_final.json в stdout (без проблем с кодировкой)."""
import json
import sys
import io
from pathlib import Path

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

d = json.load(open(Path(__file__).parent.parent / "data/library/wishes_final.json", encoding="utf-8"))

print(f"=== WISHES FINAL v0.1 ===")
print(f"Версия: {d['version']}")
print(f"Всего: {d['total_wishes']}")
print(f"Сфер: {len(d['spheres'])}")
print()

print("=== Примеры с привязкой к WL ===")
shown = 0
for w in d['wishes']:
    if w['source_book_id']:
        print(f"  [{w['sphere_id']:12}] {w['text']}")
        print(f"      → {w['source_book_id']}")
        shown += 1
        if shown >= 15: break
print()

print("=== Примеры без привязки (null) — первые 12 ===")
shown = 0
for w in d['wishes']:
    if not w['source_book_id']:
        print(f"  [{w['sphere_id']:12}] {w['text']}")
        shown += 1
        if shown >= 12: break
print()

print("=== Покрытие по сферам ===")
by_sphere = {}
for w in d['wishes']:
    by_sphere.setdefault(w['sphere_id'], {'total': 0, 'with_source': 0})
    by_sphere[w['sphere_id']]['total'] += 1
    if w['source_book_id']:
        by_sphere[w['sphere_id']]['with_source'] += 1
for sid, stats in sorted(by_sphere.items()):
    pct = stats['with_source'] * 100 // stats['total']
    print(f"  {sid:12}: {stats['total']} всего, {stats['with_source']} с WL ({pct}%)")
