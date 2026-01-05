# 🌐 Независимость от Ollama

## Статус (14.12.2024)

✅ **ГОТОВО**: Нейра поддерживает множественные LLM провайдеры  
⚠️ **ЧАСТИЧНО**: Embeddings и Vision модели требуют Ollama  
📝 **TODO**: Расширить LLMManager для embeddings

---

## Текущая архитектура

### Универсальные компоненты (LLM Manager)

| Модуль | Статус | Провайдеры |
|--------|--------|-----------|
| `cells.py` | ✅ Универсальный | Ollama, OpenAI, Claude, Groq |
| `llm_providers.py` | ✅ Готов | Все основные API |
| `neira_config.py` | ✅ Конфигурация | Priority: ollama→groq→openai→claude |

### Зависимые от Ollama

| Модуль | Функция | Требует Ollama |
|--------|---------|---------------|
| `memory_system.py` | Embeddings (`nomic-embed-text`) | ✅ Да |
| `telegram_bot.py` | Vision (`llava:7b`) | ✅ Да |
| `model_manager.py` | Управление VRAM локальных моделей | ✅ Да |

---

## Режимы работы

### 1️⃣ **FREE** — Только бесплатные провайдеры
```python
PROVIDER_PRIORITY = "ollama,groq"  # Groq fallback если Ollama недоступен
```

**Требования:**
- Ollama (опционально, для embeddings/vision)
- Groq API key (`GROQ_API_KEY` в `.env`)

**Модели:**
- `ollama`: `qwen2.5:0.5b` (локально)
- `groq`: `llama-3.3-70b-versatile` (облако)

---

### 2️⃣ **BALANCED** — Микс бесплатных + дешёвые платные
```python
PROVIDER_PRIORITY = "ollama,groq,openai"
```

**Требования:**
- `GROQ_API_KEY`
- `OPENAI_API_KEY`

**Модели:**
- `ollama`: `qwen2.5:3b`
- `groq`: `llama-3.3-70b-versatile`
- `openai`: `gpt-3.5-turbo`

---

### 3️⃣ **QUALITY** — Максимальное качество
```python
PROVIDER_PRIORITY = "claude,openai,groq,ollama"
```

**Требования:**
- `ANTHROPIC_API_KEY` (Claude)
- `OPENAI_API_KEY`

**Модели:**
- `claude`: `claude-3-5-sonnet-20241022`
- `openai`: `gpt-4o`
- `groq`: fallback
- `ollama`: fallback

---

## Запуск **БЕЗ** Ollama

### Вариант А: Только облачные провайдеры

```bash
# 1. Отключи Ollama
taskkill /f /im ollama.exe

# 2. Настрой API ключи
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...

# 3. Режим "quality" (без ollama в priority)
PROVIDER_PRIORITY=claude,openai,groq
```

⚠️ **Ограничения без Ollama:**
- ❌ Vision модели (llava) недоступны
- ❌ Embeddings требуют OpenAI API или альтернативу
- ❌ ModelManager не работает (управление VRAM локальных моделей)

### Вариант Б: OpenAI Embeddings вместо Ollama

**TODO** (требует доработки `memory_system.py`):

```python
# Вместо
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

# Использовать
OPENAI_EMBED_MODEL = "text-embedding-3-small"  # $0.00002 / 1K tokens
```

Стоимость: ~$0.02 за 1000 запросов (очень дешёво).

---

## Roadmap: Полная независимость

### Этап 1: Embeddings abstraction ⏳
- [ ] Добавить `LLMProvider.get_embedding(text: str) -> List[float]`
- [ ] Реализовать в `OpenAIProvider` (text-embedding-3-small)
- [ ] Обновить `MemorySystem` для использования абстракции
- [ ] Fallback: если embeddings недоступны → используем простой TF-IDF

### Этап 2: Vision abstraction ⏳
- [ ] Добавить `LLMProvider.analyze_image(image_base64, prompt) -> str`
- [ ] Реализовать в `OpenAIProvider` (gpt-4o-vision)
- [ ] Реализовать в `ClaudeProvider` (claude-3-5-sonnet vision)
- [ ] Обновить `telegram_bot.py` для использования абстракции

### Этап 3: Документация ⏳
- [ ] Обновить QUICKSTART.md (примеры без Ollama)
- [ ] Обновить SETUP.md (API keys configuration)
- [ ] Создать FAQ "Как запустить без Ollama?"

---

## Примеры конфигурации

### Cloud-only (без локальных моделей)
```env
# .env
PROVIDER_PRIORITY=groq,openai
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...

# Embeddings через OpenAI
EMBED_PROVIDER=openai
OPENAI_EMBED_MODEL=text-embedding-3-small
```

### Hybrid (локальный Ollama + облачный fallback)
```env
PROVIDER_PRIORITY=ollama,groq,openai
GROQ_API_KEY=gsk_...

# Ollama для embeddings/vision
OLLAMA_URL=http://localhost:11434
```

### Groq-only (самый дешёвый)
```env
PROVIDER_PRIORITY=groq
GROQ_API_KEY=gsk_...

# Embeddings отключены (используем простой поиск)
EMBED_PROVIDER=none
```

---

## Текущие ограничения

| Функция | Ollama-only | Альтернатива |
|---------|-------------|--------------|
| **Text generation** | ❌ Универсально | OpenAI, Claude, Groq |
| **Embeddings** | ✅ `nomic-embed-text` | TODO: OpenAI embeddings |
| **Vision** | ✅ `llava:7b` | TODO: OpenAI/Claude vision |
| **VRAM management** | ✅ ModelManager | Не требуется для облачных |

---

## Команды диагностики

### Проверить доступные провайдеры
```python
from llm_providers import create_default_manager

manager = create_default_manager()
print(manager.available_providers)
# Ожидаемый вывод: ['ollama', 'groq', 'openai']
```

### Тест без Ollama
```python
# 1. Убедись что Ollama выключен
# 2. Запусти
from llm_providers import LLMManager, GroqProvider, OpenAIProvider

manager = LLMManager(providers=[
    GroqProvider(),
    OpenAIProvider()
])

response = manager.generate("Привет!")
print(response.content)  # Должен работать через Groq или OpenAI
```

---

## Вопросы и ответы

**Q: Можно ли полностью отказаться от Ollama?**  
A: Технически да (для text generation), но embeddings и vision пока требуют его. Работаем над абстракцией.

**Q: Какой самый дешёвый способ запуска?**  
A: Groq (бесплатный лимит 14400 req/day) + отключить embeddings.

**Q: Нужен ли GPU без Ollama?**  
A: Нет. Облачные провайдеры (OpenAI/Claude/Groq) работают на их серверах.

**Q: Какой провайдер лучший для русского языка?**  
A: `claude-3-5-sonnet` > `gpt-4o` > `qwen2.5` (Ollama) > `groq llama-3.3`

---

## Контрибьюция

Хочешь помочь с независимостью от Ollama?

1. **Embeddings provider** — реализуй OpenAI embeddings в `llm_providers.py`
2. **Vision provider** — добавь gpt-4o-vision support
3. **Тестирование** — проверь работу без Ollama в разных режимах

Пиши в Issues: `[OLLAMA-INDEPENDENCE]`
