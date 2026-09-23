@echo off
:: Ручной запуск бота Q Holsters
set "BOT_DIR=%~dp0"

if exist "%BOT_DIR%venv\Scripts\python.exe" (
    "%BOT_DIR%venv\Scripts\python.exe" "%BOT_DIR%main.py"
) else (
    python "%BOT_DIR%main.py"
)
pause
