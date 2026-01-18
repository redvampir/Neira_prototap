@echo off
REM Запуск Web UI для Нейры
REM Открывает backend (FastAPI) и frontend (браузер)

echo ============================================================
echo   NEIRA Web UI Launcher v0.8.1
echo ============================================================
echo.

REM Проверяем что Ollama запущена
echo [1/4] Проверка Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Ollama не запущена! Запускаю...
    start "" ollama serve
    timeout /t 5 >nul
    
    REM Проверяем повторно
    curl -s http://localhost:11434/api/tags >nul 2>&1
    if errorlevel 1 (
        echo ❌ Не удалось запустить Ollama!
        echo    Попробуйте запустить вручную: ollama serve
        pause
        exit /b 1
    )
)
echo ✅ Ollama готова

REM Проверяем Python
echo.
echo [2/4] Проверка Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден!
    echo    Установите Python 3.10+ с python.org
    pause
    exit /b 1
)
echo ✅ Python установлен

REM Устанавливаем зависимости если нужно
echo.
echo [3/4] Проверка зависимостей backend...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo 📦 Устанавливаю зависимости...
    pip install -r backend\requirements.txt
    if errorlevel 1 (
        echo ❌ Не удалось установить зависимости!
        pause
        exit /b 1
    )
)
echo ✅ Зависимости установлены

REM Запускаем backend
echo.
echo [4/4] Запуск Backend API...
cd backend
start "Neira Backend" cmd /k "echo 🚀 Запуск Neira Backend API... & echo. & python api.py"
cd ..

REM Ждём пока backend стартует
echo.
echo ⏳ Жду запуска backend (5 сек)...
timeout /t 5 >nul

REM Проверяем что backend запустился
echo.
echo 🔍 Проверка backend API...
curl -s http://localhost:8000/ >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Backend ещё запускается... жду ещё 3 сек
    timeout /t 3 >nul
)

REM Открываем frontend в браузере
echo.
echo 🌐 Открываю Web UI в браузере...
start "" "%~dp0frontend\index.html"

echo.
echo ============================================================
echo   ✅ Neira Web UI запущен!
echo.
echo   📱 Frontend:  %~dp0frontend\index.html
echo   🔌 Backend:   http://localhost:8000
echo   📚 API Docs:  http://localhost:8000/docs
echo.
echo   💡 Советы:
echo   - Если кнопки не работают, обнови страницу (F5)
echo   - Проверь консоль браузера (F12) на ошибки
echo   - Для остановки закрой окно "Neira Backend"
echo.
echo ============================================================
echo.
echo Нажми любую клавишу для открытия API docs...
pause >nul
start "" "http://localhost:8000/docs"
