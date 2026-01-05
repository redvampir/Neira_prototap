# 🌐 Neira Multi-Provider LLM System

## 🎯 Теперь Neira независима от Ollama!

Вместо зависимости от одного провайдера, Neira автоматически переключается между:
- **Ollama** (локально, бесплатно, приватно)
- **Groq** (облако, бесплатно, ОЧЕНЬ быстро)
- **OpenAI** (GPT-3.5/4, качество, недорого)
- **Claude** (Anthropic, лучшее качество, дороже)
- **Gemini** (Google, бесплатно с лимитами)

## ⚡ Быстрый старт

### 1. Получи бесплатные API ключи

#### Groq (РЕКОМЕНДУЕТСЯ - быстро и бесплатно!)
```
1. Зайди: https://console.groq.com/keys
2. Создай аккаунт (GitHub/Google)
3. Скопируй API key: gsk_...
```

#### OpenAI (если нужен GPT-4)
```
1. Зайди: https://platform.openai.com/api-keys
2. Добавь карту ($5 минимум)
3. Создай ключ: sk-...
```

#### Claude (лучшее качество)
```
1. Зайди: https://console.anthropic.com/settings/keys
2. Добавь карту ($5 минимум)
3. Создай ключ: sk-ant-...
```

### 2. Настрой .env файл

```bash
# Скопируй пример
cp .env.example .env

# Открой и вставь свои ключи
notepad .env
```

Пример `.env`:
```env
# Бесплатно и быстро!
GROQ_API_KEY=gsk_ваш_ключ

# Опционально (платно)
OPENAI_API_KEY=sk-ваш_ключ
ANTHROPIC_API_KEY=sk-ant-ваш_ключ

# Режим работы: free / balanced / quality
NEIRA_MODE=balanced

# Приоритет провайдеров (первый пробуется первым)
LLM_PROVIDER_PRIORITY=ollama,groq,openai
```

### 3. Запусти Neira

```bash
python telegram_bot.py
```

**Теперь если Ollama недоступна, Neira автоматически переключится на Groq!**

## 🎨 Режимы работы

### FREE (только бесплатные)
```env
NEIRA_MODE=free
```
- Ollama (локально)
- Groq (бесплатно в облаке)
- **Стоимость: $0**

### BALANCED (баланс цены и качества)
```env
NEIRA_MODE=balanced
```
- Ollama → Groq → GPT-3.5-turbo
- **Стоимость: ~$0.002/1000 токенов**

### QUALITY (максимум качества)
```env
NEIRA_MODE=quality
```
- Claude Sonnet → GPT-4 → Groq → Ollama
- **Стоимость: ~$0.03/1000 токенов**

## 🔄 Как работает автоматический fallback

```
Пользователь: "Привет!"
    ↓
1. Пробуем Ollama (qwen2.5:0.5b)
   ❌ Ошибка: "memory layout cannot be allocated"
    ↓
2. Пробуем Groq (llama-3.1-8b-instant)
   ✅ Успех! Ответ за 0.5 секунды
    ↓
Ответ пользователю
```

## 📊 Сравнение провайдеров

| Провайдер | Скорость | Качество | Стоимость | Приватность |
|-----------|----------|----------|-----------|-------------|
| **Ollama** | 🐌 Медленно | ⭐⭐⭐ | 🆓 Бесплатно | 🔒 100% |
| **Groq** | ⚡⚡⚡ ОЧЕНЬ быстро | ⭐⭐⭐⭐ | 🆓 Бесплатно | ⚠️ В облаке |
| **OpenAI** | ⚡⚡ Быстро | ⭐⭐⭐⭐⭐ | 💰 Дешево | ⚠️ В облаке |
| **Claude** | ⚡⚡ Быстро | ⭐⭐⭐⭐⭐⭐ | 💰💰 Средне | ⚠️ В облаке |
| **Gemini** | ⚡⚡ Быстро | ⭐⭐⭐⭐ | 🆓 Лимиты | ⚠️ В облаке |

## 🛠️ Продвинутая настройка

### Разные модели для разных задач

```env
# Для кода
LLM_CODE_MODEL_OLLAMA=qwen2.5-coder:7b
LLM_CODE_MODEL_CLOUD=gpt-4

# Для рассуждений
LLM_REASON_MODEL_OLLAMA=qwen2.5:0.5b
LLM_REASON_MODEL_CLOUD=claude-3-haiku-20240307

# Для личности
LLM_PERSONALITY_MODEL_CLOUD=claude-3-5-sonnet-20241022
```

### Кастомный приоритет провайдеров

```env
# Только Groq и Claude (без Ollama)
LLM_PROVIDER_PRIORITY=groq,claude

# Сначала качество, потом скорость
LLM_PROVIDER_PRIORITY=claude,openai,groq,ollama
```

### Условия переключения на облако

```env
# Использовать облако если Ollama недоступна
USE_CLOUD_IF_OLLAMA_FAILS=true

# Использовать облако если сложность задачи > 4
USE_CLOUD_IF_COMPLEXITY=4

# Использовать облако после 2 неудачных попыток
USE_CLOUD_IF_RETRIES=2
```

## 💡 Примеры использования

### Минимальная конфигурация (только Groq)

```env
GROQ_API_KEY=gsk_твой_ключ
NEIRA_MODE=free
LLM_PROVIDER_PRIORITY=groq,ollama
```

### Максимальная надёжность (все провайдеры)

```env
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

NEIRA_MODE=balanced
LLM_PROVIDER_PRIORITY=ollama,groq,openai,claude
```

### Только облако (без локальных моделей)

```env
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...

NEIRA_MODE=quality
LLM_PROVIDER_PRIORITY=groq,openai
```

## 📈 Проверка конфигурации

```bash
python neira_config.py
```

Вывод:
```
==================================================
🧠 NEIRA CONFIGURATION
==================================================

📋 Режим: BALANCED

🔑 API Keys:
  ✓ Groq
  ✓ OpenAI
  ✗ Claude (Anthropic)
  ✗ Gemini

🎯 Приоритет провайдеров: ollama → groq → openai

🤖 Модели:
  code: qwen2.5-coder:7b
  reason: qwen2.5:0.5b
  personality: gpt-3.5-turbo

⚙️ Настройки:
  Ollama timeout: 180s
  Cloud timeout: 60s
  Max retries: 2
  Min score: 7/10
==================================================
```

## 🐛 Решение проблем

### Neira не отвечает

**Проверь логи:**
```
INFO:root:Trying ollama (qwen2.5:0.5b)...
WARNING:root:✗ Failed with ollama: memory layout cannot be allocated
INFO:root:Trying groq (llama-3.1-8b-instant)...
INFO:root:✓ Success with groq
```

**Если все провайдеры fail:**
1. Проверь API ключи в `.env`
2. Проверь интернет-соединение
3. Проверь лимиты API ключей

### Groq API ошибка

```
HTTP 429: Rate limit exceeded
```

**Решение:** Добавь `OPENAI_API_KEY` как fallback

### Слишком дорого

**Настрой лимиты в коде:**
```python
# В llm_providers.py
class LLMManager:
    def __init__(self, max_cost_per_request=0.01):
        self.max_cost = max_cost_per_request
```

## 📚 API Reference

### Создание менеджера

```python
from llm_providers import LLMManager, create_default_manager

# Дефолтный (все провайдеры)
manager = create_default_manager()

# Только быстрые
from llm_providers import create_fast_manager
manager = create_fast_manager()

# Только качественные
from llm_providers import create_quality_manager
manager = create_quality_manager()

# Кастомный
from llm_providers import OllamaProvider, GroqProvider
manager = LLMManager([
    GroqProvider(model="llama-3.1-70b-versatile"),
    OllamaProvider(model="qwen2.5:0.5b")
])
```

### Генерация ответа

```python
response = manager.generate(
    prompt="Привет!",
    system_prompt="Ты - Нейра",
    temperature=0.7,
    preferred_provider=ProviderType.GROQ  # Опционально
)

if response.success:
    print(response.content)
    print(f"Provider: {response.provider.value}")
    print(f"Cost: ${response.cost:.4f}")
else:
    print(f"Error: {response.error}")
```

## 🎓 Дальнейшее чтение

- [Groq Documentation](https://console.groq.com/docs)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
- [Claude API Reference](https://docs.anthropic.com/en/api)
- [Gemini API](https://ai.google.dev/gemini-api/docs)

## ✅ Чеклист миграции

- [ ] Получил Groq API key (бесплатно!)
- [ ] Создал `.env` файл
- [ ] Указал `GROQ_API_KEY` в `.env`
- [ ] Запустил `python neira_config.py` для проверки
- [ ] Перезапустил Telegram бота
- [ ] Отправил тестовое сообщение
- [ ] Neira ответила (проверь в логах какой провайдер использован)

**Готово! Теперь Neira работает даже без Ollama 🎉**
