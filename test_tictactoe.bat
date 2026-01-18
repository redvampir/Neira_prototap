@echo off
REM Тест TicTacToe через curl (без Python импортов)

echo Тест: Создание TicTacToe UI через WebSocket
echo.

REM Проверяем что backend работает
curl -s http://localhost:8001/ > nul
if errorlevel 1 (
    echo ❌ Backend не запущен на :8001
    echo Запустите: python -m backend.api
    exit /b 1
)

echo ✅ Backend доступен
echo.
echo 📤 Отправляю WebSocket запрос...
echo.

REM Используем PowerShell для WebSocket запроса
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$uri = 'ws://localhost:8001/ws/chat'; ^
$ws = New-Object System.Net.WebSockets.ClientWebSocket; ^
$cts = New-Object System.Threading.CancellationTokenSource; ^
$task = $ws.ConnectAsync($uri, $cts.Token); ^
$task.Wait(); ^
if ($ws.State -eq 'Open') { ^
    $msg = '{\"message\":\"Создай интерфейс для игры в крестики-нолики 3x3\",\"context\":{}}'; ^
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($msg); ^
    $segment = [System.ArraySegment[byte]]::new($bytes); ^
    $sendTask = $ws.SendAsync($segment, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cts.Token); ^
    $sendTask.Wait(); ^
    Write-Host '✅ Запрос отправлен'; ^
    $buffer = New-Object byte[] 8192; ^
    $segment = [System.ArraySegment[byte]]::new($buffer); ^
    while ($ws.State -eq 'Open') { ^
        $recvTask = $ws.ReceiveAsync($segment, $cts.Token); ^
        $recvTask.Wait(); ^
        $result = $recvTask.Result; ^
        if ($result.MessageType -eq 'Text') { ^
            $text = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count); ^
            $data = $text | ConvertFrom-Json; ^
            Write-Host \"📥 Получено: $($data.type)\"; ^
            if ($data.type -eq 'artifact') { ^
                $artifact = $data.metadata.artifact; ^
                Write-Host \"✅ Артефакт: $($artifact.id)\"; ^
                Write-Host \"   Template: $($artifact.template_used)\"; ^
                break; ^
            } ^
            if ($data.type -eq 'done') { break; } ^
        } ^
        if ($result.EndOfMessage) { break; } ^
    } ^
    $ws.CloseAsync([System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure, 'Done', $cts.Token).Wait(); ^
}"

echo.
echo ✅ Тест завершён
