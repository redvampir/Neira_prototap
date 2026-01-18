#!/bin/bash
# Скрипт автоматической загрузки Nemotron с retry для Linux/Mac

MODEL_PATH="models/nemotron9b"
FILE_NAME="nvidia_NVIDIA-Nemotron-Nano-9B-v2-Q4_K_M.gguf"
MAX_RETRIES=100
RETRY_DELAY=5
EXPECTED_SIZE_GB=6.53

echo "🚀 Запуск автоматической загрузки Nemotron Nano 9B v2"
echo "📁 Путь: $MODEL_PATH"
echo "📦 Файл: $FILE_NAME"
echo "🔄 Максимум попыток: $MAX_RETRIES"
echo ""

EXPECTED_SIZE_BYTES=$((${EXPECTED_SIZE_GB%.*} * 1024 * 1024 * 1024))
attempt=0
success=0

get_file_size() {
    if [ -f "$MODEL_PATH/$FILE_NAME" ]; then
        stat -f%z "$MODEL_PATH/$FILE_NAME" 2>/dev/null || stat -c%s "$MODEL_PATH/$FILE_NAME" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

format_size_gb() {
    echo "scale=2; $1 / 1024 / 1024 / 1024" | bc
}

# Проверяем текущий статус
initial_size=$(get_file_size)
initial_gb=$(format_size_gb $initial_size)

if [ $initial_size -ge $((EXPECTED_SIZE_BYTES * 99 / 100)) ]; then
    echo "✅ Файл уже скачан полностью ($initial_gb GB)!"
    exit 0
elif [ $initial_size -gt 0 ]; then
    percent=$((initial_size * 100 / EXPECTED_SIZE_BYTES))
    echo "📊 Найден частично скачанный файл: $initial_gb GB / $EXPECTED_SIZE_GB GB ($percent%)"
    echo "🔄 Продолжаем загрузку..."
fi

while [ $success -eq 0 ] && [ $attempt -lt $MAX_RETRIES ]; do
    attempt=$((attempt + 1))
    
    current_size=$(get_file_size)
    current_gb=$(format_size_gb $current_size)
    percent=$((current_size * 100 / EXPECTED_SIZE_BYTES))
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔄 Попытка $attempt из $MAX_RETRIES"
    echo "📊 Текущий прогресс: $current_gb GB / $EXPECTED_SIZE_GB GB ($percent%)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    cd "$MODEL_PATH" || exit 1
    
    echo "📥 Скачивание через git lfs pull..."
    git lfs pull --include="$FILE_NAME"
    
    cd - > /dev/null || exit 1
    
    # Проверяем результат
    new_size=$(get_file_size)
    new_gb=$(format_size_gb $new_size)
    
    if [ $new_size -ge $((EXPECTED_SIZE_BYTES * 99 / 100)) ]; then
        echo ""
        echo "✅ ЗАГРУЗКА ЗАВЕРШЕНА!"
        echo "📦 Размер файла: $new_gb GB"
        echo ""
        echo "Следующие шаги:"
        echo "1. cd $MODEL_PATH"
        echo "2. ollama create nemotron-mini -f Modelfile"
        echo "3. ollama list"
        success=1
        break
    fi
    
    # Если размер изменился
    if [ $new_size -gt $current_size ]; then
        diff_gb=$(echo "scale=2; ($new_size - $current_size) / 1024 / 1024 / 1024" | bc)
        echo "📈 Скачано: +$diff_gb GB"
    elif [ $attempt -gt 1 ]; then
        echo "⚠️ Размер файла не изменился. Возможно, проблема с соединением."
    fi
    
    if [ $success -eq 0 ]; then
        echo "⏳ Пауза $RETRY_DELAY секунд перед следующей попыткой..."
        sleep $RETRY_DELAY
    fi
done

if [ $success -eq 0 ]; then
    echo ""
    echo "❌ Не удалось завершить загрузку после $MAX_RETRIES попыток"
    final_gb=$(format_size_gb $(get_file_size))
    echo "📊 Финальный прогресс: $final_gb GB / $EXPECTED_SIZE_GB GB"
    echo ""
    echo "💡 Попробуйте:"
    echo "1. Проверить интернет-соединение"
    echo "2. Запустить скрипт снова - он продолжит с текущего места"
    echo "3. Или скачать вручную: cd $MODEL_PATH && git lfs pull --include='$FILE_NAME'"
    exit 1
fi
