@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Применение миграций...
python manage.py makemigrations
python manage.py migrate
echo.
echo Миграции применены!
pause

