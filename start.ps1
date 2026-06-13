# NeuroHub — запуск двойным кликом на start.bat
# Или в PowerShell: .\start.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "  NeuroHub — AI Chat" -ForegroundColor Cyan
Write-Host "  OpenRouter | OpenAI | Claude | Gemini" -ForegroundColor DarkGray
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ОШИБКА] Python не найден!" -ForegroundColor Red
    Write-Host "Скачай: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "Нажми Enter"
    exit 1
}

Write-Host "Устанавливаю зависимости..." -ForegroundColor DarkGray
python -m pip install -e . -q

Write-Host ""
Write-Host "Запускаю NeuroHub..." -ForegroundColor Green
Write-Host ""
python -m neurohub

Read-Host "`nНажми Enter для выхода"
