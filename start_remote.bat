@echo off
REM Запуск Neira с удалённым доступом через ngrok
REM Требуется: установленный ngrok (https://ngrok.com/download)

echo ============================================================
echo   NEIRA Remote Access via ngrok
echo ============================================================
echo.

REM Проверяем ngrok
where ngrok >nul 2>&1
if errorlevel 1 (
    echo ❌ ngrok не найден!
    echo.
    echo Установка:
    echo   1. Скачай: https://ngrok.com/download
    echo   2. Распакуй ngrok.exe в C:\Windows или добавь в PATH
    echo   3. Зарегистрируйся на ngrok.com и выполни:
    echo      ngrok config add-authtoken YOUR_TOKEN
    echo.
    pause
    exit /b 1
)

REM Проверяем Ollama
echo [1/4] Проверка Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Ollama не запущена! Запускаю...
    start "" ollama serve
    timeout /t 3 >nul
)
echo ✅ Ollama готова

REM Запускаем backend
echo.
echo [2/4] Запуск Backend API...
cd backend
start "Neira Backend" cmd /k python api.py
cd ..
timeout /t 3 >nul
echo ✅ Backend запущен на http://localhost:8000

REM Запускаем ngrok
echo.
echo [3/4] Запуск ngrok туннеля...
start "ngrok" cmd /k ngrok http 8000
timeout /t 5 >nul

REM Получаем URL
echo.
echo [4/4] Получение публичного URL...
echo.

REM ngrok API для получения URL
curl -s http://localhost:4040/api/tunnels > ngrok_tunnels.json 2>nul
if exist ngrok_tunnels.json (
    echo ============================================================
    echo   ✅ NEIRA ДОСТУПНА УДАЛЁННО!
    echo.
    echo   Открой http://localhost:4040 чтобы увидеть публичный URL
    echo   Или посмотри в окне ngrok
    echo.
    echo   Пример URL: https://xxxx-xx-xx-xx-xx.ngrok-free.app
    echo.
    echo   API:        https://YOUR_URL/api/chat
    echo   WebSocket:  wss://YOUR_URL/ws/chat
    echo   Docs:       https://YOUR_URL/docs
    echo ============================================================
    del ngrok_tunnels.json
) else (
    echo ⚠️ Не удалось получить URL автоматически
    echo    Посмотри в окне ngrok или на http://localhost:4040
)

echo.
echo Нажми любую клавишу для выхода (туннели останутся работать)
pause >nul
