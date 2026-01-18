@echo off
chcp 65001 >nul
echo ╔═══════════════════════════════════════╗
echo ║   🧠 NEIRA EXTENSION - Сборка         ║
echo ╚═══════════════════════════════════════╝
echo.

cd /d "%~dp0"

echo [1/4] Проверка Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js не установлен!
    echo    Скачайте: https://nodejs.org/
    pause
    exit /b 1
)
echo ✅ Node.js найден

echo.
echo [2/4] Установка зависимостей...
call npm install
if errorlevel 1 (
    echo ❌ Ошибка установки зависимостей
    pause
    exit /b 1
)
echo ✅ Зависимости установлены

echo.
echo [3/4] Компиляция TypeScript...
call npm run compile
if errorlevel 1 (
    echo ❌ Ошибка компиляции
    pause
    exit /b 1
)
echo ✅ Компиляция завершена

echo.
echo [4/4] Сборка .vsix...
call npx vsce package --allow-missing-repository
if errorlevel 1 (
    echo ❌ Ошибка сборки .vsix
    pause
    exit /b 1
)
echo ✅ Расширение собрано!

echo.
echo ═══════════════════════════════════════
echo Файл: neira-assistant-1.0.0.vsix
echo.
echo Установка в VS Code:
echo   code --install-extension neira-assistant-1.0.0.vsix
echo.
echo Установка в Cursor:
echo   cursor --install-extension neira-assistant-1.0.0.vsix
echo ═══════════════════════════════════════
pause
