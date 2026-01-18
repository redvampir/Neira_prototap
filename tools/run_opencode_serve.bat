@echo off
setlocal
chcp 65001 > nul

REM Запуск OpenCode в headless-режиме с логом.
REM Рекомендуется запускать из пути без кириллицы: C:\neira_work

set "PORT=%~1"
if "%PORT%"=="" set "PORT=39468"

set "ROOT=C:\neira_work"
set "LOG=%ROOT%\artifacts\opencode_serve_%PORT%.log"

if not exist "%ROOT%" (
  echo ❌ Не найден %ROOT% (junction). Сначала создайте C:\neira_work.
  exit /b 1
)

echo 🚀 Запуск OpenCode на http://127.0.0.1:%PORT%
echo 📝 Лог: %LOG%
echo.

cd /d "%ROOT%" || exit /b 1

REM Стартуем в фоне отдельным процессом cmd, чтобы текущий терминал не зависал
start "OpenCode" /B cmd /c "tools\opencode.cmd serve --hostname 127.0.0.1 --port %PORT% --print-logs --log-level INFO 1>> \"%LOG%\" 2>>&1"

echo ✅ Команда отправлена в фон. Подождите 1-2 секунды и откройте:
echo    http://127.0.0.1:%PORT%
echo.
exit /b 0
