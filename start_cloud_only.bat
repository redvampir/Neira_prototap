@echo off
chcp 65001 >nul
echo ========================================
echo 🌐 Neira CLOUD-ONLY Mode
echo ========================================
echo.
echo Режим: Только облачные провайдеры (без Ollama)
echo Провайдеры: Groq → OpenAI → Claude
echo.

REM Проверка .env файла
if not exist .env (
    echo ❌ Файл .env не найден!
    echo.
    echo Создайте .env с API ключами:
    echo GROQ_API_KEY=gsk_...
    echo OPENAI_API_KEY=sk-...
    echo ANTHROPIC_API_KEY=sk-ant-...
    echo.
    pause
    exit /b 1
)

REM Проверка API ключей
findstr /C:"GROQ_API_KEY" .env >nul
if errorlevel 1 (
    echo ⚠️ GROQ_API_KEY не найден в .env
    echo Groq - бесплатный провайдер, настоятельно рекомендуется!
    echo Получить ключ: https://console.groq.com/keys
    echo.
)

findstr /C:"OPENAI_API_KEY" .env >nul
if errorlevel 1 (
    echo ⚠️ OPENAI_API_KEY не найден в .env
    echo OpenAI нужен для качественных ответов
    echo Получить ключ: https://platform.openai.com/api-keys
    echo.
)

REM Проверка Ollama (предупреждение если запущен)
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul
if not errorlevel 1 (
    echo 💡 Ollama запущен, но не будет использоваться в cloud-only режиме
    echo Для отключения: taskkill /f /im ollama.exe
    echo.
)

echo Конфигурация:
echo - Провайдеры: groq,openai,claude
echo - Embeddings: OpenAI (или без embeddings)
echo - Vision: Отключен
echo.

REM Установка переменных окружения для cloud-only
set PROVIDER_PRIORITY=groq,openai,claude
set EMBED_PROVIDER=openai
set NEIRA_MODE=cloud

echo ✓ Режим cloud-only активирован
echo.
echo Запуск Telegram бота...
python telegram_bot.py

if errorlevel 1 (
    echo.
    echo ❌ Ошибка запуска!
    echo.
    echo Возможные причины:
    echo 1. Python не установлен
    echo 2. Не установлены зависимости: pip install -r requirements.txt
    echo 3. Неверные API ключи в .env
    echo 4. Нет доступа к интернету
    echo.
    pause
)
