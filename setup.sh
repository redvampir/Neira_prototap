#!/bin/bash

# Neira v0.6.1 - Скрипт первоначальной настройки
# Устанавливает все зависимости и настраивает окружение

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        NEIRA v0.6.1 — Скрипт первоначальной настройки       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Переход в директорию скрипта
cd "$(dirname "$0")"

# 1. Проверка Python
echo -e "${YELLOW}📋 Шаг 1: Проверка Python${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✅ $PYTHON_VERSION установлен${NC}"
else
    echo -e "${RED}❌ Python 3 не найден!${NC}"
    echo "Установите Python 3.10+:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "  macOS: brew install python3"
    echo "  Windows: https://www.python.org/downloads/"
    exit 1
fi

# 2. Виртуальное окружение (опционально)
echo ""
echo -e "${YELLOW}📋 Шаг 2: Виртуальное окружение (опционально)${NC}"
read -p "Создать виртуальное окружение? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ ! -d "venv" ]; then
        echo -e "${BLUE}📦 Создаю виртуальное окружение...${NC}"
        python3 -m venv venv
        echo -e "${GREEN}✅ Виртуальное окружение создано${NC}"
    else
        echo -e "${GREEN}✅ Виртуальное окружение уже существует${NC}"
    fi

    # Активация
    echo -e "${BLUE}📦 Активация окружения...${NC}"
    source venv/bin/activate
    echo -e "${GREEN}✅ Окружение активировано${NC}"
fi

# 3. Установка Python зависимостей
echo ""
echo -e "${YELLOW}📋 Шаг 3: Установка Python зависимостей${NC}"
echo -e "${BLUE}📦 Устанавливаю requests...${NC}"
pip install requests
echo -e "${GREEN}✅ Python зависимости установлены${NC}"

# 4. Проверка Ollama
echo ""
echo -e "${YELLOW}📋 Шаг 4: Проверка Ollama${NC}"
if command -v ollama &> /dev/null; then
    OLLAMA_VERSION=$(ollama --version 2>&1 | head -n1)
    echo -e "${GREEN}✅ Ollama установлен: $OLLAMA_VERSION${NC}"
else
    echo -e "${RED}❌ Ollama не найден!${NC}"
    echo ""
    echo "Установите Ollama:"
    echo ""
    echo -e "${BLUE}Linux/macOS:${NC}"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    echo -e "${BLUE}Windows:${NC}"
    echo "  Скачайте с https://ollama.com/download"
    echo ""
    read -p "Установить Ollama сейчас? (Linux/macOS only) (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        curl -fsSL https://ollama.com/install.sh | sh
        echo -e "${GREEN}✅ Ollama установлен${NC}"
    else
        echo -e "${YELLOW}⚠️  Установите Ollama вручную и запустите скрипт снова${NC}"
        exit 1
    fi
fi

# 5. Запуск Ollama
echo ""
echo -e "${YELLOW}📋 Шаг 5: Запуск Ollama сервера${NC}"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama уже запущен${NC}"
else
    echo -e "${BLUE}🚀 Запускаю Ollama...${NC}"
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 2
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama запущен${NC}"
    else
        echo -e "${YELLOW}⚠️  Запустите Ollama вручную: ollama serve${NC}"
    fi
fi

# 6. Скачивание моделей
echo ""
echo -e "${YELLOW}📋 Шаг 6: Скачивание моделей${NC}"
echo -e "${BLUE}Это может занять 10-20 минут в зависимости от скорости интернета${NC}"
echo -e "${BLUE}Общий размер: ~10 GB${NC}"
echo ""

# Модель для кода
if ollama list | grep -q "qwen2.5-coder:7b"; then
    echo -e "${GREEN}✅ qwen2.5-coder:7b уже загружена${NC}"
else
    echo -e "${BLUE}📥 Скачиваю qwen2.5-coder:7b (~5 GB)...${NC}"
    ollama pull qwen2.5-coder:7b
    echo -e "${GREEN}✅ qwen2.5-coder:7b загружена${NC}"
fi

# Модель для рассуждений
if ollama list | grep -q "mistral:7b-instruct"; then
    echo -e "${GREEN}✅ mistral:7b-instruct уже загружена${NC}"
else
    echo -e "${BLUE}📥 Скачиваю mistral:7b-instruct (~4.5 GB)...${NC}"
    ollama pull mistral:7b-instruct
    echo -e "${GREEN}✅ mistral:7b-instruct загружена${NC}"
fi

# 7. Создание структуры проекта
echo ""
echo -e "${YELLOW}📋 Шаг 7: Создание структуры проекта${NC}"
mkdir -p backups/code_evolution
mkdir -p generated
mkdir -p training_data
echo -e "${GREEN}✅ Директории созданы${NC}"

# 8. Права на исполнение скриптов
echo ""
echo -e "${YELLOW}📋 Шаг 8: Настройка прав${NC}"
chmod +x start.sh stop.sh setup.sh
echo -e "${GREEN}✅ Права на исполнение установлены${NC}"

# Завершение
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                  ✨ НАСТРОЙКА ЗАВЕРШЕНА! ✨                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📚 Что дальше:${NC}"
echo ""
echo -e "  ${GREEN}1.${NC} Запустите Neira:"
echo -e "     ${YELLOW}./start.sh${NC}"
echo ""
echo -e "  ${GREEN}2.${NC} Или вручную:"
echo -e "     ${YELLOW}python3 main.py${NC}"
echo ""
echo -e "  ${GREEN}3.${NC} Для остановки:"
echo -e "     ${YELLOW}./stop.sh${NC}"
echo ""
echo -e "${BLUE}📖 Документация:${NC}"
echo -e "  - SETUP.md    — подробная инструкция"
echo -e "  - EVOLUTION.md — система эволюции"
echo -e "  - README.md   — общая информация"
echo ""
echo -e "${GREEN}Удачной работы! 🚀${NC}"
