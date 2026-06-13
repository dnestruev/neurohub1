# NeuroHub — локальное web-приложение
# Запуск: .\start.ps1 или двойной клик по start.bat

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "  NeuroHub — Web App" -ForegroundColor Cyan
Write-Host "  ключи, Markdown, красивый чат" -ForegroundColor DarkGray
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ОШИБКА] Python не найден!" -ForegroundColor Red
    Write-Host "Скачай: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "Нажми Enter"
    exit 1
}

Write-Host "Устанавливаю/обновляю приложение..." -ForegroundColor DarkGray
python -m pip install -e . -q

Write-Host ""
Write-Host "Открываю NeuroHub в браузере..." -ForegroundColor Green
Write-Host "Если браузер не открылся, смотри адрес ниже." -ForegroundColor DarkGray
Write-Host ""
python -m neurohub.web_app

Read-Host "`nНажми Enter для выхода"
