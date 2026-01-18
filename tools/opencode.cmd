@echo off
setlocal

REM Wrapper to run OpenCode CLI even if it's not in PATH.
REM Works best when you access this repo via C:\neira_work (junction without Cyrillic).

REM 1) OpenCode Desktop CLI (обычно самый надёжный на Windows)
REM В некоторых окружениях переменные могут содержать мусор/пробелы — поэтому находим бинарь через where.
set "OPEX="
for /f "delims=" %%P in ('where /r C:\Users opencode-cli.exe 2^>nul') do (
  for %%I in ("%%P") do set "OPEX=%%~fI"
  goto :found_desktop
)
:found_desktop

if defined OPEX if exist "%OPEX%" goto :run

REM Если не нашли desktop CLI — попробуем npm-варианты ниже

REM 2) Fallback: npm opencode-ai (иногда бинарь может быть несовместим/повреждён)
if not exist "%OPEX%" set "OPEX=%APPDATA%\npm\node_modules\opencode-ai\node_modules\opencode-windows-x64\bin\opencode.exe"
if not exist "%OPEX%" set "OPEX=%APPDATA%\npm\node_modules\opencode-ai\node_modules\opencode-windows-x64-baseline\bin\opencode.exe"

if not exist "%OPEX%" (
  echo ❌ opencode.exe не найден.
  echo    Проверено:
  echo      %LOCALAPPDATA%\OpenCode\opencode-cli.exe
  echo      %APPDATA%\npm\node_modules\opencode-ai\node_modules\opencode-windows-x64\bin\opencode.exe
  echo      %APPDATA%\npm\node_modules\opencode-ai\node_modules\opencode-windows-x64-baseline\bin\opencode.exe
  echo.
  echo 💡 Попробуйте переустановить:
  echo    OpenCode Desktop Installer (если используете Desktop)
  echo    или npm i -g opencode-ai
  exit /b 1
)

:run
"%OPEX%" %*
