# Скрипт автоматической загрузки Nemotron с retry при обрыве
# Использует git lfs pull с автоматическим возобновлением

param(
    [string]$ModelPath = "models\nemotron9b",
    [string]$FileName = "nvidia_NVIDIA-Nemotron-Nano-9B-v2-Q4_K_M.gguf",
    [int]$MaxRetries = 100,
    [int]$RetryDelay = 5
)

$ErrorActionPreference = "Continue"

Write-Host "🚀 Запуск автоматической загрузки Nemotron Nano 9B v2" -ForegroundColor Cyan
Write-Host "📁 Путь: $ModelPath" -ForegroundColor Gray
Write-Host "📦 Файл: $FileName" -ForegroundColor Gray
Write-Host "🔄 Максимум попыток: $MaxRetries" -ForegroundColor Gray
Write-Host ""

$ExpectedSizeGB = 6.53
$ExpectedSizeBytes = [math]::Round($ExpectedSizeGB * 1GB)
$attempt = 0
$success = $false

function Get-FileProgress {
    param([string]$Path)
    
    if (Test-Path $Path) {
        $file = Get-Item $Path
        $currentGB = [math]::Round($file.Length / 1GB, 2)
        $percent = [math]::Round(($file.Length / $ExpectedSizeBytes) * 100, 1)
        return @{
            SizeGB = $currentGB
            Percent = $percent
            Complete = ($file.Length -ge ($ExpectedSizeBytes * 0.99))
        }
    }
    return @{
        SizeGB = 0
        Percent = 0
        Complete = $false
    }
}

# Проверяем текущий статус
$filePath = Join-Path $ModelPath $FileName
$initialProgress = Get-FileProgress -Path $filePath

if ($initialProgress.Complete) {
    Write-Host "✅ Файл уже скачан полностью ($($initialProgress.SizeGB) GB)!" -ForegroundColor Green
    exit 0
} elseif ($initialProgress.SizeGB -gt 0) {
    Write-Host "📊 Найден частично скачанный файл: $($initialProgress.SizeGB) GB / $ExpectedSizeGB GB ($($initialProgress.Percent)%)" -ForegroundColor Yellow
    Write-Host "🔄 Продолжаем загрузку..." -ForegroundColor Yellow
}

while (-not $success -and $attempt -lt $MaxRetries) {
    $attempt++
    
    $progress = Get-FileProgress -Path $filePath
    
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host "🔄 Попытка $attempt из $MaxRetries" -ForegroundColor Cyan
    Write-Host "📊 Текущий прогресс: $($progress.SizeGB) GB / $ExpectedSizeGB GB ($($progress.Percent)%)" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    
    try {
        # Переходим в директорию модели
        Push-Location $ModelPath
        
        # Запускаем git lfs pull с таймаутом
        Write-Host "📥 Скачивание через git lfs pull..." -ForegroundColor Yellow
        
        $process = Start-Process -FilePath "git" `
            -ArgumentList "lfs", "pull", "--include=$FileName" `
            -NoNewWindow `
            -PassThru `
            -Wait
        
        Pop-Location
        
        # Проверяем результат
        $newProgress = Get-FileProgress -Path $filePath
        
        if ($newProgress.Complete) {
            Write-Host ""
            Write-Host "✅ ЗАГРУЗКА ЗАВЕРШЕНА!" -ForegroundColor Green
            Write-Host "📦 Размер файла: $($newProgress.SizeGB) GB" -ForegroundColor Green
            Write-Host ""
            Write-Host "Следующие шаги:" -ForegroundColor Cyan
            Write-Host "1. cd $ModelPath" -ForegroundColor Gray
            Write-Host "2. ollama create nemotron-mini -f Modelfile" -ForegroundColor Gray
            Write-Host "3. ollama list" -ForegroundColor Gray
            $success = $true
            break
        }
        
        # Если размер не изменился - возможно ошибка
        if ($newProgress.SizeGB -eq $progress.SizeGB -and $attempt -gt 1) {
            Write-Host "⚠️ Размер файла не изменился. Возможно, проблема с соединением." -ForegroundColor Yellow
        } else {
            Write-Host "📈 Скачано: +$([math]::Round($newProgress.SizeGB - $progress.SizeGB, 2)) GB" -ForegroundColor Green
        }
        
    } catch {
        Write-Host "❌ Ошибка при загрузке: $_" -ForegroundColor Red
    }
    
    if (-not $success) {
        Write-Host "⏳ Пауза $RetryDelay секунд перед следующей попыткой..." -ForegroundColor Yellow
        Start-Sleep -Seconds $RetryDelay
    }
}

if (-not $success) {
    Write-Host ""
    Write-Host "❌ Не удалось завершить загрузку после $MaxRetries попыток" -ForegroundColor Red
    Write-Host "📊 Финальный прогресс: $($progress.SizeGB) GB / $ExpectedSizeGB GB ($($progress.Percent)%)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "💡 Попробуйте:" -ForegroundColor Cyan
    Write-Host "1. Проверить интернет-соединение" -ForegroundColor Gray
    Write-Host "2. Запустить скрипт снова - он продолжит с текущего места" -ForegroundColor Gray
    Write-Host "3. Или скачать вручную:" -ForegroundColor Gray
    Write-Host "   cd $ModelPath" -ForegroundColor DarkGray
    Write-Host "   git lfs pull --include='$FileName'" -ForegroundColor DarkGray
    exit 1
}
