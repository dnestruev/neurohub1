@echo off
chcp 65001 >nul
title NeuroHub — Desktop App
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║       NeuroHub — Desktop App         ║
echo  ║   настоящее окно, ключи, Markdown     ║
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
echo Запускаю NeuroHub Desktop...
echo.
python -m neurohub.desktop_app

pause
