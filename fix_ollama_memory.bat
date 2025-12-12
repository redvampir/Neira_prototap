@echo off
echo ================================================
echo  ВОССТАНОВЛЕНИЕ OLLAMA - ОЧИСТКА VRAM
echo ================================================
echo.

echo [1/3] Останавливаю Ollama...
taskkill /f /im ollama.exe 2>nul
if %ERRORLEVEL% == 0 (
    echo ✅ Ollama остановлена
) else (
    echo ⚠️ Ollama уже не запущена
)
timeout /t 2 >nul

echo.
echo [2/3] Очищаю VRAM (ожидание 3 сек)...
timeout /t 3 >nul
echo ✅ VRAM освобождена

echo.
echo [3/3] Запускаю Ollama заново...
start /b ollama serve
timeout /t 2 >nul
echo ✅ Ollama запущена

echo.
echo ================================================
echo  ГОТОВО! Попробуй отправить сообщение Нейре
echo ================================================
pause
