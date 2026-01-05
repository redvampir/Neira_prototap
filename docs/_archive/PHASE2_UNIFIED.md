# Phase 2: Единая Архитектура + Pathway Learning

> **Дата:** Июнь 2025  
> **Статус:** ✅ ЗАВЕРШЕНО  
> **Зависимости:** Phase 1 (PHASE1_AUTONOMY.md)

---

## 📋 Обзор

Phase 2 решает две ключевые задачи:

1. **Единая архитектура** — один сервер `neira_server.py`, все клиенты подключаются к нему
2. **Pathway Learning** — автоматическое обучение через emoji-feedback

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    neira_server.py                          │
│                   (Единый мозг Neira)                       │
│  ┌─────────────┐ ┌────────────┐ ┌───────────────┐          │
│  │ ResponseEngine│ │ NeiraBrain │ │ TierManager   │          │
│  │  (кэш+pathways)│ │ (SQLite)   │ │ (hot/warm/cold)│          │
│  └─────────────┘ └────────────┘ └───────────────┘          │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP API
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │Telegram │    │ VS Code │    │ Desktop │
    │  Bot    │    │Extension│    │   App   │
    └─────────┘    └─────────┘    └─────────┘
         │               │               │
         └───────────────┴───────────────┘
                         │
              NeiraClient (универсальный)
```

---

## 📁 Новые/Изменённые файлы

### `neira_client.py` (НОВЫЙ)

Универсальный клиент для подключения к серверу:

```python
from neira_client import get_client

# Синхронный режим
client = get_client()
response = client.chat("Привет!")

# Асинхронный режим
async def example():
    client = get_client()
    response = await client.chat_async("Привет!")
    
    # Отправка feedback
    await client.send_feedback_async(
        query="вопрос",
        response="ответ",
        feedback="positive",  # positive/negative/neutral
        score=0.9
    )
```

**Функции:**
- `ServerProcessManager` — автозапуск сервера если не работает
- `NeiraClient` — синхронные и асинхронные HTTP-методы
- `get_client()` — глобальный singleton

### `neira_server.py` (ИЗМЕНЁН)

Новый endpoint `/pathway/feedback`:

```bash
POST /pathway/feedback
{
    "query": "исходный запрос",
    "response": "ответ Neira",
    "feedback": "positive",
    "score": 0.9,
    "user_id": "123",
    "source": "telegram"
}
```

**Обработка:**
- `positive` feedback → увеличивает `success_count`, кэширует ответ, может создать pathway
- `negative` feedback → уменьшает `confidence`, удаляет плохой ответ из кэша

### `telegram_bot.py` (ИЗМЕНЁН)

Интеграция с сервером через NeiraClient:

```python
# Импорт
from neira_client import NeiraClient, get_client

# В reaction_handler (обработка emoji)
async def reaction_handler(update, context):
    # ... определение emoji и score ...
    
    # Отправка на сервер для pathway learning
    asyncio.create_task(
        send_feedback_to_server(
            query=query,
            response=response_text,
            feedback=feedback_type,  # positive/negative/neutral
            score=normalized_score,
            user_id=user_id
        )
    )
```

### `response_engine.py` (ИЗМЕНЁН)

Новые компоненты:

1. **`PathwayAutoGenerator.find_matching_pathway()`** — поиск pathway по запросу
2. **`PathwayAutoGenerator.maybe_create_pathway()`** — создание pathway из успешного ответа
3. **`PathwayTierManager`** — управление тирами (hot/warm/cold)

---

## 🎚️ Система тиров

### Уровни

| Tier | Описание | Использование |
|------|----------|---------------|
| **hot** | Проверенные, быстрые | Первый приоритет |
| **warm** | Работающие, нужно больше данных | Второй приоритет |
| **cold** | Новые, непроверенные | Последний приоритет |

### Правила продвижения

```
cold → warm:
  - success_count >= 3
  - confidence >= 0.6

warm → hot:
  - success_count >= 10
  - confidence >= 0.8
  - fail_count < success_count * 0.2

hot → warm (понижение):
  - fail_count > success_count * 0.33
  - ИЛИ confidence < 0.7

warm → cold (понижение):
  - fail_count > success_count * 0.5
  - ИЛИ confidence < 0.5
```

### Пример продвижения

```
1. Пользователь спрашивает "как создать функцию python"
2. LLM отвечает, ответ кэшируется
3. Пользователь ставит 👍 (positive feedback)
4. success_count += 1, ответ сохраняется в cache
5. После 3 успехов: cold → warm
6. После 10 успехов с low fail: warm → hot
7. Следующий похожий запрос → мгновенный ответ из hot pathway
```

---

## 🔄 Поток обратной связи

```
Пользователь → emoji 👍/👎 на ответ
       │
       ▼
Telegram reaction_handler
       │
       ├── Локально: emoji_feedback.add_feedback()
       │
       └── Сервер: POST /pathway/feedback
                        │
                        ▼
               handle_pathway_feedback()
                        │
                        ├── positive: ↑success_count, cache, maybe_create_pathway
                        │
                        └── negative: ↓confidence, remove_from_cache
                                │
                                ▼
                        TierManager.evaluate_pathway()
                                │
                                └── Возможно: tier change (cold→warm→hot)
```

---

## 📊 Мониторинг

### API endpoint

```bash
GET /autonomy/stats

{
    "autonomy_available": true,
    "cache": {
        "entries": 150,
        "memory_mb": 0.5
    },
    "tiers": {
        "hot": 5,
        "warm": 23,
        "cold": 47
    },
    "autonomy_rate_percent": 34.5,
    "metrics": {...}
}
```

### Telegram команда

```
/autonomy — показывает статистику автономности
```

---

## 🧪 Тестирование

### 1. Проверка feedback endpoint

```bash
# Положительный feedback
curl -X POST http://localhost:8765/pathway/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "query": "как написать цикл for",
    "response": "Используй for i in range(10): ...",
    "feedback": "positive",
    "score": 0.9,
    "source": "test"
  }'
```

### 2. Проверка tier promotion

```python
from response_engine import get_response_engine

engine = get_response_engine()

# Статистика тиров
stats = engine.tier_manager.get_tier_stats()
print(stats)  # {'hot': 5, 'warm': 23, 'cold': 47}

# Принудительная оценка всех pathways
result = engine.evaluate_all_pathways()
print(result)  # {'promoted': 3, 'demoted': 1, 'unchanged': 71}
```

### 3. Проверка автозапуска сервера

```python
from neira_client import get_client

# Если сервер не запущен, клиент запустит его автоматически
client = get_client()
response = client.health()
print(response)  # {'status': 'online', ...}
```

---

## ⚙️ Конфигурация

### Переменные окружения

```bash
# Автозапуск сервера (по умолчанию включен)
NEIRA_AUTO_START_SERVER=true

# Таймаут подключения к серверу (секунды)
NEIRA_SERVER_TIMEOUT=30

# Показывать отладочную инфо от Cortex
NEIRA_SHOW_CORTEX_INFO=false

# Режим Cortex: auto, always, never
NEIRA_CORTEX_MODE=auto
```

---

## 📝 Что дальше (Phase 3)

1. **Semantic Clustering** — группировка похожих pathway для объединения
2. **A/B Testing** — автоматическое тестирование разных вариантов ответов
3. **User Preference Learning** — персонализация на основе истории пользователя
4. **Multi-model Fallback** — автоматический переключение между LLM

---

## ✅ Чек-лист завершения Phase 2

- [x] `neira_client.py` — универсальный клиент
- [x] `/pathway/feedback` endpoint
- [x] Telegram → сервер (emoji feedback)
- [x] `PathwayAutoGenerator.find_matching_pathway()`
- [x] `PathwayAutoGenerator.maybe_create_pathway()`
- [x] `PathwayTierManager` (hot/warm/cold)
- [x] Документация (этот файл)

---

*Phase 2 создан для того, чтобы Neira училась на каждом взаимодействии, постепенно становясь всё более автономной.*
