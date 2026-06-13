@echo off
chcp 65001 >nul
title NeuroHub — AI Chat
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║         NeuroHub — AI Chat           ║
echo  ║   OpenRouter ^| OpenAI ^| Claude       ║
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

echo Устанавливаю зависимости...
python -m pip install -e . -q

echo.
echo Запускаю NeuroHub...
echo.
python -m neurohub

pause
