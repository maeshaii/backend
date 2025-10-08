@echo off
echo Checking current migrations...
dir apps\shared\migrations\*.py

echo.
echo Checking Django migration status...
python manage.py showmigrations shared

echo.
echo If migrations are not applied, run:
echo python manage.py migrate shared
pause
