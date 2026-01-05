# ✅ Чеклист: Независимость от Ollama

## Тестирование перед коммитом

### 1. Проверка llm_providers.py

- [ ] `python -c "from llm_providers import create_default_manager; m = create_default_manager(); print(m.get_stats())"`
  - Ожидается: список доступных провайдеров
  
- [ ] Тест embeddings (Ollama):
  ```python
  from llm_providers import OllamaProvider
  p = OllamaProvider()
  e = p.get_embedding("test")
  print(len(e) if e else "Failed")
  # Ожидается: 768 (размерность nomic-embed-text)
  ```

- [ ] Тест embeddings (OpenAI, если ключ есть):
  ```python
  from llm_providers import OpenAIProvider
  p = OpenAIProvider()
  if p.available:
      e = p.get_embedding("test")
      print(len(e) if e else "Failed")
  # Ожидается: 1536 (размерность text-embedding-3-small)
  ```

### 2. Проверка memory_system.py

- [ ] Import без ошибок:
  ```python
  from memory_system import SemanticSearch
  print("OK")
  ```

- [ ] Embeddings с fallback:
  ```python
  from memory_system import SemanticSearch
  e = SemanticSearch.get_embedding("тест на русском")
  print("✓ OK" if e else "✗ Failed")
  ```

### 3. Проверка cells.py

- [ ] LLMManager используется:
  ```bash
  grep -n "LLM_MANAGER_AVAILABLE" cells.py
  # Должно быть: строки 72, 74, 359, 383
  ```

- [ ] Legacy режим существует:
  ```bash
  grep -n "_call_ollama_legacy" cells.py
  # Должно быть: метод определён
  ```

### 4. Скрипты запуска

- [ ] `start_cloud_only.bat` существует
- [ ] `start_hybrid.bat` существует
- [ ] Оба скрипта имеют кодировку UTF-8 BOM (для русских символов)

### 5. Документация

- [ ] `OLLAMA_INDEPENDENCE.md` создан (300+ строк)
- [ ] `OLLAMA_INDEPENDENCE_REPORT.md` создан
- [ ] `QUICKSTART.md` обновлён (раздел "Провайдеры")
- [ ] `README.md` обновлён (v0.8.1 changelog)

---

## Функциональное тестирование

### Сценарий A: Cloud-only (без Ollama)

**Шаги:**
1. Убедись что Ollama выключен: `tasklist | find "ollama"`
2. Создай .env с `GROQ_API_KEY=gsk_...`
3. Запусти `start_cloud_only.bat`
4. Отправь сообщение боту

**Ожидаемый результат:**
- ✅ Бот отвечает через Groq
- ✅ В логах: "Trying groq"
- ✅ Нет ошибок "Ollama offline"

### Сценарий B: Hybrid (Ollama + Cloud)

**Шаги:**
1. Запусти Ollama: `ollama serve`
2. Запусти `start_hybrid.bat`
3. Отправь сообщение
4. Останови Ollama: `taskkill /f /im ollama.exe`
5. Отправь ещё сообщение

**Ожидаемый результат:**
- ✅ Первое сообщение через Ollama
- ✅ Второе сообщение через Groq (fallback)
- ✅ Нет краша, автоматическое переключение

### Сценарий C: Embeddings fallback

**Шаги:**
1. Выключи Ollama
2. Настрой OPENAI_API_KEY в .env
3. Запусти Python:
   ```python
   from memory_system import SemanticSearch
   e = SemanticSearch.get_embedding("test")
   print("OpenAI embeddings работают!" if e else "Fail")
   ```

**Ожидаемый результат:**
- ✅ Embeddings через OpenAI
- ✅ В логах: "✓ Embedding from openai"

---

## Интеграционные тесты

### Telegram Bot

- [ ] `/providers` — показывает список провайдеров
- [ ] Бот работает без Ollama
- [ ] Бот переключается между провайдерами при сбое
- [ ] Vision функции (llava) показывают предупреждение если Ollama недоступен

### Web UI

- [ ] Работает с любым провайдером
- [ ] Статистика показывает активный провайдер
- [ ] Нет hardcoded ссылок на localhost:11434

---

## Проверка производительности

### Latency тест

```python
import time
from llm_providers import create_default_manager

manager = create_default_manager()

start = time.time()
response = manager.generate("Привет!")
end = time.time()

print(f"Provider: {response.provider.value}")
print(f"Latency: {end - start:.2f}s")
print(f"Success: {response.success}")
```

**Ожидаемые значения:**
- Ollama: 0.5-2s
- Groq: 1-3s
- OpenAI: 2-5s
- Claude: 3-6s

### Memory тест

```python
from memory_system import MemorySystem
import os

ms = MemorySystem(".")
ms.add_memory("Тест независимости от Ollama", category="fact")

# Проверка embeddings
entries = ms.search_memories("Ollama", top_k=1)
print(f"✓ Search работает: {len(entries)} результатов")
```

---

## Регрессионные тесты

### Legacy функции (должны работать)

- [ ] `cells.py` — Cell.call_llm() работает
- [ ] `memory_system.py` — MemorySystem.add_memory() работает
- [ ] `telegram_bot.py` — бот запускается
- [ ] `main.py` — консольный режим работает

### Новые функции (должны работать)

- [ ] LLMManager.generate() с preferred_provider
- [ ] LLMManager.get_embedding() с fallback
- [ ] SemanticSearch.get_embedding() через LLMManager
- [ ] start_cloud_only.bat
- [ ] start_hybrid.bat

---

## Обратная совместимость

### Конфигурация (старый формат)

Если пользователь НЕ обновил конфиг:
- [ ] Система работает в legacy режиме (только Ollama)
- [ ] Нет ошибок импорта
- [ ] Предупреждение о доступности LLMManager

### Миграция

Старые установки должны:
- [ ] Автоматически получить LLMManager при `pip install -r requirements.txt`
- [ ] Работать без изменения .env (Ollama по умолчанию)
- [ ] Показывать сообщение о новых возможностях при первом запуске

---

## Checklist для коммита

- [ ] Все файлы сохранены с UTF-8 кодировкой
- [ ] Нет debug print() в production коде
- [ ] Логи используют logger.info/warning/error
- [ ] Все TODO в коде задокументированы в OLLAMA_INDEPENDENCE.md
- [ ] Версия в README.md обновлена (v0.8.1)
- [ ] Changelog описывает изменения

---

## Git commit message

```
🌐 Add multi-provider LLM support (v0.8.1)

- Add embeddings abstraction to LLMProvider
- Implement Ollama & OpenAI embeddings
- Update MemorySystem to use LLMManager
- Add start_cloud_only.bat & start_hybrid.bat
- Create OLLAMA_INDEPENDENCE.md documentation
- Update QUICKSTART.md with provider guide

Breaking changes: None (backward compatible)
New dependencies: None (optional: openai, anthropic, groq)

Closes #OLLAMA-INDEPENDENCE
```

---

## После коммита

- [ ] Создать GitHub Release v0.8.1
- [ ] Обновить Wiki с новым разделом "Multi-Provider Setup"
- [ ] Добавить примеры в Issues/Discussions
- [ ] Протестировать на чистой установке (без Ollama)
