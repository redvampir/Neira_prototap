param(
    [int]$Port = 39468
)

$log = "C:\\neira_work\\artifacts\\opencode_serve_${Port}.log"

Write-Host ("Проверка порта {0}..." -f $Port) -ForegroundColor Cyan
try {
    $ok = (Test-NetConnection 127.0.0.1 -Port $Port -WarningAction SilentlyContinue).TcpTestSucceeded
    Write-Host ("TCP: {0}" -f $ok) -ForegroundColor (if ($ok) { 'Green' } else { 'Red' })
} catch {
    Write-Host "TCP check failed" -ForegroundColor Red
}

if (Test-Path $log) {
    Write-Host "Лог:" -ForegroundColor Cyan
    Get-Content $log -Tail 30
} else {
    Write-Host "Лог пока не создан: $log" -ForegroundColor Yellow
}
