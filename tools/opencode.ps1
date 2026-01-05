param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$paths = @(
    Join-Path $env:APPDATA 'npm\node_modules\opencode-ai\node_modules\opencode-windows-x64\bin\opencode.exe',
    Join-Path $env:APPDATA 'npm\node_modules\opencode-ai\node_modules\opencode-windows-x64-baseline\bin\opencode.exe'
)

$exe = $paths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $exe) {
    Write-Host '❌ opencode.exe не найден (opencode-ai не установлен или повреждён).' -ForegroundColor Red
    Write-Host '💡 Попробуйте: npm i -g opencode-ai' -ForegroundColor Yellow
    exit 1
}

& $exe @Args
exit $LASTEXITCODE
