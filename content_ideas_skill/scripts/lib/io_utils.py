"""
lib/io_utils.py — I/O утилиты.

Зачем: общие функции чтения/записи JSON и markdown для всех скриптов.
"""

import json
from pathlib import Path
from typing import Any, Dict


def read_json(path: Path) -> Dict[str, Any]:
    """Читает JSON. Если файла нет — возвращает пустой dict."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any, indent: int = 2) -> None:
    """Пишет JSON с UTF-8 и pretty-print."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=indent),
        encoding="utf-8",
    )


def read_text(path: Path) -> str:
    """Читает текст."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    """Пишет текст."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
