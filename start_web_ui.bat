@echo off
REM Запуск Web UI для Нейры
REM Открывает backend (FastAPI) и frontend (браузер)

echo ============================================================
echo   NEIRA Web UI Launcher
echo ============================================================
echo.

REM Проверяем что Ollama запущена
echo [1/3] Проверка Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Ollama не запущена! Запускаю...
    start "" ollama serve
    timeout /t 3 >nul
)
echo ✅ Ollama готова

REM Устанавливаем зависимости если нужно
echo.
echo [2/3] Проверка зависимостей backend...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo 📦 Устанавливаю зависимости...
    pip install -r backend\requirements.txt
)
echo ✅ Зависимости установлены

REM Запускаем backend
echo.
echo [3/3] Запуск Backend API...
cd backend
start "Neira Backend" cmd /k python api.py
cd ..

REM Ждём пока backend стартует
echo.
echo ⏳ Жду запуска backend...
timeout /t 3 >nul

REM Открываем frontend в браузере
echo.
echo 🌐 Открываю Web UI в браузере...
start "" "http://localhost:8000/docs"
start "" "%~dp0frontend\index.html"

echo.
echo ============================================================
echo   ✅ Neira Web UI запущен!
echo.
echo   Backend API: http://localhost:8000
echo   API Docs:    http://localhost:8000/docs
echo   Frontend:    frontend\index.html
echo.
echo   Для остановки закройте окно "Neira Backend"
echo ============================================================
pause
