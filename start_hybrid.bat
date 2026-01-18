@echo off
chcp 65001 >nul
echo ========================================
echo 🔄 Neira HYBRID Mode
echo ========================================
echo.
echo Режим: Ollama (локально) + Cloud (fallback)
echo Провайдеры: Ollama → Groq → OpenAI
echo.

REM Проверка Ollama
echo [1/3] Проверка Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if errorlevel 1 (
    echo ⚠️ Ollama не запущен
    echo Попытка автозапуска...
    start /B ollama serve
    timeout /t 3 /nobreak >nul
    
    tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
    if errorlevel 1 (
        echo ❌ Не удалось запустить Ollama
        echo.
        echo Продолжение БЕЗ Ollama (только облачные провайдеры)
        set PROVIDER_PRIORITY=groq,openai,claude
    ) else (
        echo ✓ Ollama запущен
        set PROVIDER_PRIORITY=ollama,groq,openai
    )
) else (
    echo ✓ Ollama уже запущен
    set PROVIDER_PRIORITY=ollama,groq,openai
)

REM Проверка .env
echo.
echo [2/3] Проверка API ключей...
if not exist .env (
    echo ⚠️ Файл .env не найден
    echo Создайте .env для облачных провайдеров
    echo.
) else (
    findstr /C:"GROQ_API_KEY" .env >nul
    if not errorlevel 1 (
        echo ✓ GROQ_API_KEY настроен
    ) else (
        echo ⚠️ GROQ_API_KEY не найден (рекомендуется для fallback)
    )
    
    findstr /C:"OPENAI_API_KEY" .env >nul
    if not errorlevel 1 (
        echo ✓ OPENAI_API_KEY настроен
    ) else (
        echo ⚠️ OPENAI_API_KEY не найден
    )
)

echo.
echo [3/3] Конфигурация:
echo - Режим: HYBRID (локально + облако)
echo - Провайдеры: %PROVIDER_PRIORITY%
echo - Embeddings: Ollama fallback → OpenAI
echo - Vision: Ollama llava (если доступен)
echo.

echo Запуск Telegram бота...
python telegram_bot.py

if errorlevel 1 (
    echo.
    echo ❌ Ошибка запуска!
    pause
)
