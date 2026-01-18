@echo off
REM Стартовый скрипт для Neira 0.1 Simulator (Windows)

echo ========================================
echo   Neira 0.1 Simulator
echo   Симулятор дыхания, ритма и резонанса
echo ========================================
echo.

REM Проверка Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python не найден! Установите Python 3.10+
    pause
    exit /b 1
)

echo [OK] Python найден
echo.

REM Проверка виртуального окружения
if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Создаю виртуальное окружение...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Не удалось создать виртуальное окружение
        pause
        exit /b 1
    )
)

echo [INFO] Активирую виртуальное окружение...
call venv\Scripts\activate.bat

REM Проверка зависимостей
echo [INFO] Проверяю зависимости...
pip show numpy >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Устанавливаю numpy...
    pip install numpy
)

pip show rich >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Устанавливаю rich...
    pip install rich
)

echo.
echo [OK] Все зависимости установлены
echo.
echo ========================================
echo   Запускаю симулятор...
echo ========================================
echo.

python simulation_demo.py

echo.
echo ========================================
echo   Симуляция завершена
echo ========================================
pause
