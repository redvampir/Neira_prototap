# Запуск Ollama + Neira Telegram Bot без дублей
# Использование: ./start_ollama_and_telegram_bot.ps1

$ErrorActionPreference = 'Stop'

function Stop-TelegramBotIfRunning {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'telegram_bot\.py' }

    foreach ($p in $procs) {
        Write-Host "🛑 Останавливаю telegram_bot.py (PID=$($p.ProcessId))" -ForegroundColor Yellow
        try { Stop-Process -Id $p.ProcessId -Force } catch { }
    }
}

function Start-OllamaIfNeeded {
    $ok = (Test-NetConnection -ComputerName 127.0.0.1 -Port 11434).TcpTestSucceeded
    if ($ok) {
        Write-Host "✅ Ollama уже запущен (127.0.0.1:11434)" -ForegroundColor Green
        return
    }

    Write-Host "🚀 Запускаю Ollama serve..." -ForegroundColor Cyan
    Start-Process -FilePath ollama -ArgumentList 'serve'

    Start-Sleep -Seconds 2
    $ok2 = (Test-NetConnection -ComputerName 127.0.0.1 -Port 11434).TcpTestSucceeded
    if (-not $ok2) {
        throw "Ollama не поднялся на 127.0.0.1:11434"
    }
    Write-Host "✅ Ollama поднялся (127.0.0.1:11434)" -ForegroundColor Green
}

function Start-TelegramBot {
    Write-Host "🤖 Запускаю Neira Telegram Bot..." -ForegroundColor Cyan
    Start-Process -FilePath python -ArgumentList 'telegram_bot.py'
    Start-Sleep -Seconds 1

    $bot = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'telegram_bot\.py' } |
        Select-Object -First 1

    if ($null -eq $bot) {
        throw "Не удалось запустить telegram_bot.py"
    }

    Write-Host "✅ Бот запущен (PID=$($bot.ProcessId))" -ForegroundColor Green
}

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
try {
    Stop-TelegramBotIfRunning
    Start-OllamaIfNeeded
    Start-TelegramBot
} finally {
    Pop-Location
}
