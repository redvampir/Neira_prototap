param(
    [int]$Port = 8001
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
Set-Location $root

# Stop existing listener (if any)
$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    try {
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    } catch {
        # ignore
    }
    Start-Sleep -Seconds 1
}

# Start backend in a separate process
Start-Process -FilePath py -ArgumentList @(
    '-m','uvicorn','backend.api:app',
    '--host','127.0.0.1',
    '--port',"$Port",
    '--log-level','info'
) -WorkingDirectory $root

Start-Sleep -Seconds 1

# Open frontend (preconfigured for 8001)
$frontend = Join-Path $root 'frontend\index_8001.html'
if (Test-Path $frontend) {
    Start-Process $frontend
}

Write-Host "Desktop UI restart requested. Backend port: $Port"