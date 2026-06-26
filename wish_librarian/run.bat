@echo off
REM Активация venv и запуск CLI с UTF-8 режимом
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
call "%~dp0.venv\Scripts\activate.bat"
cd /d "%~dp0"
python -m agent.cli %*
