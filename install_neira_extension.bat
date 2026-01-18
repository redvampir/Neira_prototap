@echo off
chcp 65001 >nul
echo ╔═══════════════════════════════════════╗
echo ║   🧠 Установка Neira Extension        ║
echo ╚═══════════════════════════════════════╝
echo.

cd /d "%~dp0neira-vscode"

REM Проверяем наличие .vsix
if not exist "neira-assistant-1.0.0.vsix" (
    echo ⚠️ Расширение не собрано. Собираем...
    call build.bat
    if errorlevel 1 exit /b 1
)

echo.
echo Выберите редактор:
echo   [1] VS Code
echo   [2] Cursor
echo   [3] Оба
echo.
set /p choice="Ваш выбор (1/2/3): "

if "%choice%"=="1" (
    echo.
    echo Установка в VS Code...
    code --install-extension neira-assistant-1.0.0.vsix --force
    echo ✅ Установлено в VS Code!
)

if "%choice%"=="2" (
    echo.
    echo Установка в Cursor...
    cursor --install-extension neira-assistant-1.0.0.vsix --force
    echo ✅ Установлено в Cursor!
)

if "%choice%"=="3" (
    echo.
    echo Установка в VS Code...
    code --install-extension neira-assistant-1.0.0.vsix --force
    echo ✅ Установлено в VS Code!
    echo.
    echo Установка в Cursor...
    cursor --install-extension neira-assistant-1.0.0.vsix --force
    echo ✅ Установлено в Cursor!
)

echo.
echo ═══════════════════════════════════════
echo Готово! Теперь:
echo 1. Запустите: start_neira_extension.bat
echo 2. Откройте VS Code / Cursor
echo 3. Используйте Ctrl+Shift+N для чата
echo ═══════════════════════════════════════
pause
