param(
    [string]$ModelPath = "models\nemotron9b",
    [string]$FileName = "nvidia_NVIDIA-Nemotron-Nano-9B-v2-Q4_K_M.gguf",
    [int]$MaxRetries = 100,
    [int]$RetryDelay = 5
)

$ExpectedSizeGB = 6.53
$ExpectedSizeBytes = [long]($ExpectedSizeGB * 1GB)
$FullPath = Join-Path $ModelPath $FileName

Write-Host "Auto-download Nemotron 9B" -ForegroundColor Cyan
Write-Host "Directory: $ModelPath" -ForegroundColor Gray
Write-Host "File: $FileName" -ForegroundColor Gray
Write-Host "Expected size: $ExpectedSizeGB GB" -ForegroundColor Gray
Write-Host ""

$attempt = 0
$success = $false

while (-not $success -and $attempt -lt $MaxRetries) {
    $attempt++
    
    $currentSize = 0
    if (Test-Path $FullPath) {
        $file = Get-Item $FullPath
        $currentSize = [math]::Round($file.Length / 1GB, 2)
    }
    
    Write-Host "----------------------------------------" -ForegroundColor DarkGray
    Write-Host "Attempt $attempt of $MaxRetries" -ForegroundColor Cyan
    Write-Host "Current size: $currentSize GB / $ExpectedSizeGB GB" -ForegroundColor Cyan
    Write-Host "----------------------------------------" -ForegroundColor DarkGray
    
    try {
        Push-Location $ModelPath
        git lfs pull --include="$FileName" 2>&1 | Write-Host -ForegroundColor Gray
        Pop-Location
        
        if (Test-Path $FullPath) {
            $file = Get-Item $FullPath
            $finalSize = [math]::Round($file.Length / 1GB, 2)
            
            if ($file.Length -ge ($ExpectedSizeBytes * 0.99)) {
                Write-Host ""
                Write-Host "Download completed! Size: $finalSize GB" -ForegroundColor Green
                $success = $true
            }
            else {
                Write-Host "Download interrupted. Current: $finalSize GB" -ForegroundColor Yellow
                if ($attempt -lt $MaxRetries) {
                    Write-Host "Waiting $RetryDelay seconds..." -ForegroundColor Yellow
                    Start-Sleep -Seconds $RetryDelay
                }
            }
        }
        else {
            Write-Host "Error: file not found" -ForegroundColor Red
            if ($attempt -lt $MaxRetries) {
                Start-Sleep -Seconds $RetryDelay
            }
        }
    }
    catch {
        Pop-Location -ErrorAction SilentlyContinue
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
        if ($attempt -lt $MaxRetries) {
            Start-Sleep -Seconds $RetryDelay
        }
    }
}

if (-not $success) {
    Write-Host ""
    Write-Host "Failed after $MaxRetries attempts" -ForegroundColor Red
    exit 1
}
else {
    Write-Host ""
    Write-Host "Success! File ready: $FullPath" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  cd $ModelPath" -ForegroundColor Gray
    Write-Host "  ollama create nemotron-mini -f Modelfile" -ForegroundColor Gray
    exit 0
}
