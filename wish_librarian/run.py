"""
Удобный засказчик для Windows (не требует ручной активации venv).

Использование:
    python run.py --url "https://..."
    python run.py --test
    python run.py --help
"""
import os
import sys
from pathlib import Path

# Включаем UTF-8 режим в stdout на Windows
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

# Если запустили не из venv, перезапускаемся внутри venv
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    import subprocess
    rc = subprocess.call([str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    sys.exit(rc)

# Уже внутри venv — выполняем CLI
sys.path.insert(0, str(ROOT))
from agent.cli import main

if __name__ == "__main__":
    main()
