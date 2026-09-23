@echo off
:: Удаление автозапуска Q Holsters Bot
schtasks /delete /tn "QHolstersBot" /f
echo [OK] Автозапуск удалён.
pause
