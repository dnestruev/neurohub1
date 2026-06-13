@echo off
chcp 65001 >nul
title NeuroHub — Web App
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║        NeuroHub — Web App            ║
echo  ║   ключи, Markdown, красивый чат       ║
echo  ╚══════════════════════════════════════╝
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    echo Скачай: https://www.python.org/downloads/
    echo При установке отметь "Add to PATH"
    pause
    exit /b 1
)

echo Устанавливаю/обновляю приложение...
python -m pip install -e . -q
if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не удалось установить зависимости.
    pause
    exit /b 1
)

echo.
echo Открываю NeuroHub в браузере...
echo Если браузер не открылся, смотри адрес ниже.
echo.
python -m neurohub.web_app

pause
