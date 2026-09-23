@echo off
:: Скрипт установки автозапуска Q Holsters Bot при старте Windows
:: Запускать от имени администратора

set "BOT_DIR=%~dp0"
set "TASK_NAME=QHolstersBot"
set "PYTHON_SCRIPT=%BOT_DIR%main.py"
set "VENV_PYTHON=%BOT_DIR%venv\Scripts\pythonw.exe"
set "SYSTEM_PYTHON=pythonw"

:: Проверяем наличие виртуального окружения
if exist "%VENV_PYTHON%" (
    set "PYTHON_EXE=%VENV_PYTHON%"
) else (
    set "PYTHON_EXE=%SYSTEM_PYTHON%"
)

echo ============================================
echo  Установка автозапуска Q Holsters Bot
echo ============================================

:: Удаляем старое задание если есть
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

:: Создаём задание в планировщике Windows
:: Запуск при входе любого пользователя, с задержкой 30 сек (дать сети подняться)
schtasks /create /tn "%TASK_NAME%" /tr "\"%PYTHON_EXE%\" \"%PYTHON_SCRIPT%\"" /sc ONLOGON /delay 0000:30 /ru SYSTEM /rl HIGHEST /f

if %errorlevel% == 0 (
    echo [OK] Автозапуск установлен. Бот будет стартовать вместе с Windows.
) else (
    echo [ERR] Не удалось создать задание. Попробуйте запустить от имени администратора.
)

echo.
echo Для ручного запуска используйте: run_bot.bat
echo Для удаления автозапуска:       uninstall_autostart.bat
pause
