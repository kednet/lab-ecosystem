#!/usr/bin/env bash
# Активация venv и запуск CLI с UTF-8 режимом
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1
source .venv/Scripts/activate
python -m agent.cli "$@"
