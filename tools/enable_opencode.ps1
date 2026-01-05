# Быстро включить команду `opencode` в текущей сессии PowerShell.
# Используйте из пути без кириллицы: C:\neira_work
#   . .\tools\enable_opencode.ps1

$cli = Join-Path $env:LOCALAPPDATA 'OpenCode\opencode-cli.exe'

if (Test-Path $cli) {
    # Добавляем папку в PATH сессии (чтобы можно было вызвать opencode-cli.exe напрямую)
    $dir = Split-Path -Parent $cli
    if (-not ($env:Path -split ';' | Where-Object { $_ -ieq $dir })) {
        $env:Path = "$env:Path;$dir"
    }

    # Делаем удобный алиас opencode -> opencode-cli.exe
    Set-Alias -Name opencode -Value $cli -Scope Global
    Write-Host "✅ Алиас 'opencode' активирован: $cli" -ForegroundColor Green
    Write-Host "Пример: opencode serve --port 39468" -ForegroundColor Gray
    return
}

Write-Host "❌ Не найден OpenCode Desktop CLI: $cli" -ForegroundColor Red
Write-Host "Можно использовать wrapper: .\\tools\\opencode.cmd ..." -ForegroundColor Yellow
