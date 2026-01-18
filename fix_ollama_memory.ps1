# Восстановление Ollama - очистка VRAM
Write-Host "================================================" -ForegroundColor Cyan
Write-Host " ВОССТАНОВЛЕНИЕ OLLAMA - ОЧИСТКА VRAM" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Останавливаем Ollama
Write-Host "[1/3] Останавливаю Ollama..." -ForegroundColor Yellow
Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
Write-Host "✅ Ollama остановлена" -ForegroundColor Green

# Ждём освобождения VRAM
Write-Host ""
Write-Host "[2/3] Очищаю VRAM (ожидание 5 сек)..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
Write-Host "✅ VRAM освобождена" -ForegroundColor Green

# Запускаем Ollama
Write-Host ""
Write-Host "[3/3] Запускаю Ollama заново..." -ForegroundColor Yellow
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
Start-Sleep -Seconds 3
Write-Host "✅ Ollama запущена" -ForegroundColor Green

# Проверяем доступность
Write-Host ""
Write-Host "[ТЕСТ] Проверяю доступность..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 5
    Write-Host "✅ Ollama отвечает! Доступно моделей: $($response.models.Count)" -ForegroundColor Green
}
catch {
    Write-Host "⚠️ Ollama ещё не готова, подожди 10 секунд" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host " ГОТОВО! Попробуй отправить сообщение Нейре" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
