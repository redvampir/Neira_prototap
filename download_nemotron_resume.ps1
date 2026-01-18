param(
    [string]$ModelPath = "models\nemotron9b",
    [string]$FileName = "nvidia_NVIDIA-Nemotron-Nano-9B-v2-Q4_K_M.gguf",
    [int]$MaxRetries = 100,
    [int]$RetryDelay = 5
)

$ExpectedSizeGB = 6.53
$ExpectedSizeBytes = [long]($ExpectedSizeGB * 1GB)
$FullPath = Join-Path $ModelPath $FileName

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Автоматическая загрузка Nemotron 9B  " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Директория: $ModelPath" -ForegroundColor Gray
Write-Host "Файл: $FileName" -ForegroundColor Gray
Write-Host "Ожидаемый размер: $ExpectedSizeGB GB" -ForegroundColor Gray
Write-Host "Макс. попыток: $MaxRetries" -ForegroundColor Gray
Write-Host ""

function Get-FileSizeGB {
    param([string]$Path)
    
    if (Test-Path $Path) {
        $file = Get-Item $Path
        return [math]::Round($file.Length / 1GB, 2)
    }
    return 0
}

function Get-ProgressPercent {
    param([string]$Path)
    
    if (Test-Path $Path) {
        $file = Get-Item $Path
        $percent = [math]::Round(($file.Length / $ExpectedSizeBytes) * 100, 1)
        return $percent
    }
    return 0
}

function Test-DownloadComplete {
    param([string]$Path)
    
    if (Test-Path $Path) {
        $file = Get-Item $Path
        return ($file.Length -ge ($ExpectedSizeBytes * 0.99))
    }
    return $false
}

$attempt = 0
$success = $false

while (-not $success -and $attempt -lt $MaxRetries) {
    $attempt++
    
    $currentSize = Get-FileSizeGB -Path $FullPath
    $currentPercent = Get-ProgressPercent -Path $FullPath
    
    Write-Host ""
    Write-Host "----------------------------------------" -ForegroundColor DarkGray
    Write-Host "Попытка $attempt из $MaxRetries" -ForegroundColor Cyan
    Write-Host "Текущий прогресс: $currentSize GB / $ExpectedSizeGB GB ($currentPercent%)" -ForegroundColor Cyan
    Write-Host "----------------------------------------" -ForegroundColor DarkGray
    
    try {
        Push-Location $ModelPath
        
        Write-Host "Скачивание через git lfs pull..." -ForegroundColor Yellow
        
        git lfs pull --include="$FileName" 2>&1 | ForEach-Object {
            Write-Host $_ -ForegroundColor Gray
        }
        
        Pop-Location
        
        if (Test-DownloadComplete -Path $FullPath) {
            $finalSize = Get-FileSizeGB -Path $FullPath
            $finalPercent = Get-ProgressPercent -Path $FullPath
            
            Write-Host ""
            Write-Host "Загрузка завершена успешно!" -ForegroundColor Green
            Write-Host "Финальный размер: $finalSize GB ($finalPercent%)" -ForegroundColor Green
            $success = $true
        }
        else {
            $currentSize = Get-FileSizeGB -Path $FullPath
            $currentPercent = Get-ProgressPercent -Path $FullPath
            
            if ($currentPercent -gt 0) {
                Write-Host "Загрузка прервана на $currentPercent%" -ForegroundColor Yellow
                Write-Host "Скачано: $currentSize GB / $ExpectedSizeGB GB" -ForegroundColor Yellow
            }
            else {
                Write-Host "Ошибка загрузки (файл не найден или пуст)" -ForegroundColor Red
            }
            
            if ($attempt -lt $MaxRetries) {
                Write-Host "Пауза $RetryDelay секунд перед следующей попыткой..." -ForegroundColor Yellow
                Start-Sleep -Seconds $RetryDelay
            }
        }
    }
    catch {
        Pop-Location -ErrorAction SilentlyContinue
        Write-Host "Ошибка: $($_.Exception.Message)" -ForegroundColor Red
        
        if ($attempt -lt $MaxRetries) {
            Write-Host "Пауза $RetryDelay секунд перед следующей попыткой..." -ForegroundColor Yellow
            Start-Sleep -Seconds $RetryDelay
        }
    }
}

if (-not $success) {
    $finalSize = Get-FileSizeGB -Path $FullPath
    $finalPercent = Get-ProgressPercent -Path $FullPath
    
    Write-Host ""
    Write-Host "Не удалось завершить загрузку после $MaxRetries попыток" -ForegroundColor Red
    Write-Host "Финальный прогресс: $finalSize GB / $ExpectedSizeGB GB ($finalPercent%)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Попробуйте:" -ForegroundColor Cyan
    Write-Host "   1. Проверить интернет-соединение" -ForegroundColor Gray
    Write-Host "   2. Запустить скрипт снова - он продолжит с текущего места" -ForegroundColor Gray
    Write-Host "   3. Или скачать вручную:" -ForegroundColor Gray
    Write-Host "      cd $ModelPath" -ForegroundColor DarkGray
    Write-Host "      git lfs pull --include='$FileName'" -ForegroundColor DarkGray
    Write-Host ""
    exit 1
}
else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Загрузка завершена успешно!          " -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Файл готов: $FullPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "Следующие шаги:" -ForegroundColor Cyan
    Write-Host "   1. Импортировать в Ollama:" -ForegroundColor Gray
    Write-Host "      cd $ModelPath" -ForegroundColor DarkGray
    Write-Host "      ollama create nemotron-mini -f Modelfile" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   2. Проверить:" -ForegroundColor Gray
    Write-Host "      ollama list" -ForegroundColor DarkGray
    Write-Host "      ollama run nemotron-mini ""Привет!""" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   3. Перезапустить бота:" -ForegroundColor Gray
    Write-Host "      python telegram_bot.py" -ForegroundColor DarkGray
    Write-Host ""
    exit 0
}
