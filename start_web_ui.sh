#!/bin/bash
# Запуск Web UI для Нейры (Linux/Mac)

echo "============================================================"
echo "  NEIRA Web UI Launcher"
echo "============================================================"
echo ""

# Проверяем Ollama
echo "[1/3] Проверка Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama не запущена! Запускаю..."
    ollama serve &
    sleep 3
fi
echo "✅ Ollama готова"

# Зависимости
echo ""
echo "[2/3] Проверка зависимостей backend..."
if ! pip show fastapi > /dev/null 2>&1; then
    echo "📦 Устанавливаю зависимости..."
    pip install -r backend/requirements.txt
fi
echo "✅ Зависимости установлены"

# Backend
echo ""
echo "[3/3] Запуск Backend API..."
cd backend
python api.py &
BACKEND_PID=$!
cd ..

sleep 3

# Открываем браузер
echo ""
echo "🌐 Открываю Web UI..."
if command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:8000/docs"
    xdg-open "frontend/index.html"
elif command -v open &> /dev/null; then
    open "http://localhost:8000/docs"
    open "frontend/index.html"
fi

echo ""
echo "============================================================"
echo "  ✅ Neira Web UI запущен!"
echo ""
echo "  Backend API: http://localhost:8000"
echo "  API Docs:    http://localhost:8000/docs"
echo "  Frontend:    frontend/index.html"
echo ""
echo "  Нажмите Ctrl+C для остановки"
echo "============================================================"

# Ждём завершения
wait $BACKEND_PID
