@echo off
echo ==============================================================
echo Копирование шрифтов Times New Roman для локальной разработки
echo ==============================================================

REM Создаем директорию для шрифтов если её нет
if not exist "static\fonts" mkdir "static\fonts"

REM Копируем Times New Roman из Windows
echo.
echo Копирование Times New Roman...

if exist "C:\Windows\Fonts\times.ttf" (
    copy "C:\Windows\Fonts\times.ttf" "static\fonts\times.ttf" >nul 2>&1
    echo [OK] times.ttf скопирован
) else (
    echo [!] times.ttf не найден в C:\Windows\Fonts\
)

if exist "C:\Windows\Fonts\timesbd.ttf" (
    copy "C:\Windows\Fonts\timesbd.ttf" "static\fonts\timesbd.ttf" >nul 2>&1
    echo [OK] timesbd.ttf скопирован
) else (
    echo [!] timesbd.ttf не найден в C:\Windows\Fonts\
)

REM Альтернативно - Liberation Serif (если установлен)
if exist "C:\Windows\Fonts\LiberationSerif-Regular.ttf" (
    copy "C:\Windows\Fonts\LiberationSerif-Regular.ttf" "static\fonts\LiberationSerif-Regular.ttf" >nul 2>&1
    echo [OK] LiberationSerif-Regular.ttf скопирован
)

if exist "C:\Windows\Fonts\LiberationSerif-Bold.ttf" (
    copy "C:\Windows\Fonts\LiberationSerif-Bold.ttf" "static\fonts\LiberationSerif-Bold.ttf" >nul 2>&1
    echo [OK] LiberationSerif-Bold.ttf скопирован
)

echo.
echo ==============================================================
echo Готово! Шрифты скопированы в static\fonts\
echo ==============================================================
echo.
pause

