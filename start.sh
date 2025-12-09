#!/bin/bash

# Neira v0.6.1 - Скрипт запуска
# Автоматически проверяет зависимости и запускает систему

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Логотип
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           NEIRA v0.6.1 — AI ассистент с эволюцией           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Функция проверки
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
        return 0
    else
        echo -e "${RED}❌ $1${NC}"
        return 1
    fi
}

# 1. Проверка Python
echo -e "${YELLOW}🔍 Проверка Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    check "Python $PYTHON_VERSION установлен"
else
    echo -e "${RED}❌ Python 3 не найден!${NC}"
    echo "Установите Python 3.10 или выше: https://www.python.org/downloads/"
    exit 1
fi

# 2. Проверка зависимостей Python
echo -e "${YELLOW}🔍 Проверка Python зависимостей...${NC}"
if python3 -c "import requests" 2>/dev/null; then
    check "requests установлен"
else
    echo -e "${YELLOW}⚠️  requests не установлен${NC}"
    echo -e "${BLUE}📦 Устанавливаю requests...${NC}"
    pip install requests
    check "requests установлен"
fi

# 3. Проверка Ollama
echo -e "${YELLOW}🔍 Проверка Ollama...${NC}"
if command -v ollama &> /dev/null; then
    check "Ollama установлен"
else
    echo -e "${RED}❌ Ollama не найден!${NC}"
    echo "Установите Ollama:"
    echo "  Linux/macOS: curl -fsSL https://ollama.com/install.sh | sh"
    echo "  Windows: https://ollama.com/download"
    exit 1
fi

# 4. Проверка запущен ли Ollama
echo -e "${YELLOW}🔍 Проверка Ollama сервера...${NC}"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    check "Ollama сервер запущен"
else
    echo -e "${YELLOW}⚠️  Ollama сервер не запущен${NC}"
    echo -e "${BLUE}🚀 Запускаю Ollama в фоновом режиме...${NC}"

    # Запуск Ollama в фоне
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!

    # Ждём пока запустится
    echo -n "Ожидание запуска Ollama"
    for i in {1..10}; do
        sleep 1
        echo -n "."
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo ""
            check "Ollama сервер запущен (PID: $OLLAMA_PID)"
            break
        fi
    done

    # Проверка что запустился
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "\n${RED}❌ Не удалось запустить Ollama${NC}"
        echo "Попробуйте запустить вручную в отдельном терминале: ollama serve"
        exit 1
    fi
fi

# 5. Проверка моделей
echo -e "${YELLOW}🔍 Проверка моделей...${NC}"

MODELS_OK=true

# Проверка qwen2.5-coder:7b
if ollama list | grep -q "qwen2.5-coder:7b"; then
    check "qwen2.5-coder:7b загружена"
else
    echo -e "${YELLOW}⚠️  qwen2.5-coder:7b не найдена${NC}"
    echo -e "${BLUE}📥 Скачиваю qwen2.5-coder:7b (~5 GB)...${NC}"
    ollama pull qwen2.5-coder:7b
    check "qwen2.5-coder:7b загружена"
fi

# Проверка mistral:7b-instruct
if ollama list | grep -q "mistral:7b-instruct"; then
    check "mistral:7b-instruct загружена"
else
    echo -e "${YELLOW}⚠️  mistral:7b-instruct не найдена${NC}"
    echo -e "${BLUE}📥 Скачиваю mistral:7b-instruct (~4.5 GB)...${NC}"
    ollama pull mistral:7b-instruct
    check "mistral:7b-instruct загружена"
fi

# 6. Создание необходимых директорий
echo -e "${YELLOW}🔍 Проверка структуры проекта...${NC}"
mkdir -p backups/code_evolution
mkdir -p generated
check "Директории созданы"

# 7. Запуск Neira
echo ""
echo -e "${GREEN}✨ Все проверки пройдены!${NC}"
echo -e "${BLUE}🚀 Запускаю Neira...${NC}"
echo ""

# Переход в директорию скрипта
cd "$(dirname "$0")"

# Запуск
python3 main.py

# Cleanup при выходе
echo ""
echo -e "${YELLOW}👋 Neira завершена${NC}"
