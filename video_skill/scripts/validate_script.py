"""
validate_script.py — валидатор сценария Video Creator Skill v1.0.

Используется в cmd_script.py после генерации, и в подкоманде `validate`.

Проверяет:
- ≥3 shots в structure
- sum(t_end) ≈ duration (±2 сек)
- ≥5 hashtags
- CTA непустой и ≤100 символов
- title непустой и ≤70 символов
- hook непустой и ≤100 символов
- все shot.vo_text ≤140 символов

Возвращает list[str] — список ошибок (пустой = OK).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# UTF-8 fix
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def _load_json(md_path: Path) -> dict:
    """Парсит frontmatter (между ---) из .md файла. Если не JSON — пробуем достать regex."""
    text = md_path.read_text(encoding="utf-8")
    m = re.search(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL | re.MULTILINE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Fallback: ищем JSON-блок в любом месте
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    raise ValueError(f"Не найден валидный JSON в {md_path}")


def validate_script(md_path: Path | str, duration_target: int | None = None) -> list[str]:
    """Валидирует сценарий. Возвращает список ошибок (пустой = OK).

    Args:
        md_path: путь к .md файлу с frontmatter-JSON
        duration_target: если задан — проверяет sum(t_end) ≈ target (±2)
                        если None — берёт из JSON-поля duration
    """
    errors: list[str] = []
    md_path = Path(md_path)
    if not md_path.exists():
        return [f"Файл не найден: {md_path}"]

    try:
        data = _load_json(md_path)
    except Exception as e:
        return [f"Ошибка парсинга: {e}"]

    # Title
    title = data.get("title", "").strip()
    if not title:
        errors.append("title пустой")
    elif len(title) > 70:
        errors.append(f"title > 70 символов ({len(title)})")

    # Hook
    hook = data.get("hook", "").strip()
    if not hook:
        errors.append("hook пустой")
    elif len(hook) > 100:
        errors.append(f"hook > 100 символов ({len(hook)})")

    # Structure / shots
    structure = data.get("structure") or []
    if not isinstance(structure, list) or len(structure) < 3:
        errors.append(f"structure < 3 shots (получено {len(structure) if isinstance(structure, list) else 0})")

    total = 0
    prev_end = 0
    for i, shot in enumerate(structure):
        if not isinstance(shot, dict):
            errors.append(f"shot[{i}] не dict")
            continue
        vo = (shot.get("vo_text") or "").strip()
        if not vo:
            errors.append(f"shot[{i}].vo_text пустой")
        elif len(vo) > 140:
            errors.append(f"shot[{i}].vo_text > 140 символов ({len(vo)})")
        try:
            t_start = int(shot.get("t_start", 0))
            t_end = int(shot.get("t_end", 0))
        except Exception:
            errors.append(f"shot[{i}] t_start/t_end не int")
            continue
        # Длительность шота = разница между t_end и предыдущим t_end (или t_start)
        total += max(0, t_end - max(t_start, prev_end))
        prev_end = t_end

    # Duration
    target = duration_target if duration_target is not None else int(data.get("duration", 0))
    if target and abs(total - target) > 2:
        errors.append(f"sum(t_end)={total} ≠ duration={target} (разница {abs(total - target)} сек)")

    # Hashtags
    hashtags = data.get("hashtags") or []
    if not isinstance(hashtags, list) or len(hashtags) < 5:
        errors.append(f"hashtags < 5 (получено {len(hashtags) if isinstance(hashtags, list) else 0})")

    # CTA
    cta = (data.get("cta") or "").strip()
    if not cta:
        errors.append("cta пустой")
    elif len(cta) > 100:
        errors.append(f"cta > 100 символов ({len(cta)})")

    return errors


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Валидация сценария")
    p.add_argument("path", help="Путь к .md файлу сценария")
    p.add_argument("--duration", type=int, help="Ожидаемая длительность (если не в frontmatter)")
    args = p.parse_args()

    errs = validate_script(args.path, args.duration)
    if errs:
        print(f"❌ {len(errs)} ошибок:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("✅ OK: сценарий валиден")
        sys.exit(0)
