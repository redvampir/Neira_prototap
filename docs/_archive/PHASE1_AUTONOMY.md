# Phase 1: Унификация + Инфраструктура автономности

## Обзор

Phase 1 — первая фаза плана по повышению автономности Нейры. Цель: заложить инфраструктуру для работы без постоянного доступа к LLM.

## Созданные модули

### 1. NeiraBrain (`neira_brain.py`)

SQLite база данных для хранения:
- **Pathways**: Нейронные пути (триггеры → ответы)
- **Cache**: Кэш ответов LLM
- **Organs**: Реестр органов
- **Metrics**: Метрики запросов и автономности
- **User Preferences**: Настройки пользователей

```python
from neira_brain import get_brain

brain = get_brain()

# Сохранить pathway
brain.save_pathway({
    'id': 'greeting',
    'triggers': ['привет', 'hello'],
    'response_template': '👋 Привет!',
    'tier': 'hot'
})

# Записать метрику
brain.record_metric('request', 'telegram', {'user_id': 123})

# Получить статистику автономности
stats = brain.get_metrics_summary(hours=24)
print(f"Автономность: {stats['autonomy_rate']}%")
```

### 2. UnifiedOrganSystem (`unified_organ_system.py`)

Единая система органов для всех платформ:
- Telegram Bot
- VS Code Extension
- Desktop App

Включает **InjectionProtector** — защита от:
- Code injection (eval, exec, __import__)
- Prompt injection ([команда], {инструкция})
- Path traversal
- Credential leaks

```python
from unified_organ_system import get_organ_system

organs = get_organ_system()

# Детекция подходящего органа
organ, reason = organs.detect_organ("Создай интерфейс для игры")
# → OrganDefinition(name='UI Code Cell'), "Выбран UI Code Cell (score: 0.85)"

# Регистрация нового органа
success, msg = organs.register_organ(
    name="Math Helper",
    description="Помощник по математике",
    cell_type="custom",
    triggers=["посчитай", "вычисли"],
    created_by="user123"
)
```

### 3. Local Embeddings v2.0 (`local_embeddings.py`)

Улучшенные локальные эмбеддинги:
- N-gram хэширование
- Семантические категории (code, ui, analysis, memory)
- Стоп-слова (русский + английский)
- Простой стемминг
- LRU кэширование

```python
from local_embeddings import get_local_embedding, find_similar

# Получить эмбеддинг
emb = get_local_embedding("Создай интерфейс для игры")

# Найти похожие
candidates = [("Сделай UI игры", emb1), ("Напиши код", emb2)]
similar = find_similar("Создай интерфейс", candidates, top_k=3)
```

### 4. ResponseEngine (`response_engine.py`)

Движок автономных ответов:
- **ResponseCache**: Кэш ответов LLM с семантическим поиском
- **PathwayAutoGenerator**: Автоматическое создание pathways из частых запросов
- **ResponseVariator**: Вариации ответов без LLM

```python
from response_engine import get_response_engine

engine = get_response_engine()

# Попытка автономного ответа
response, source = engine.try_respond_autonomous(
    "Привет!",
    user_context={'user_name': 'Алексей'}
)

if response:
    print(f"Автономный ответ: {response} (источник: {source})")
else:
    # Нужен LLM
    llm_response = call_llm(query)
    engine.store_llm_response(query, llm_response)
```

## Интеграция

### neira_server.py

- Инициализация модулей автономности в `__init__`
- `_try_autonomous_response()` — сначала пробуем ответить без LLM
- `_store_llm_response()` — сохраняем ответы LLM для обучения
- Endpoint `/autonomy/stats` — статистика автономности

### telegram_bot.py

- `try_autonomous_response()` — автономный ответ
- `store_llm_response_for_learning()` — сохранение для обучения
- Команда `/autonomy` — показать статистику
- Автоматическое сохранение ответов Cortex/Legacy

## Новые команды

### Telegram

```
/autonomy - Показать статистику автономности
```

### HTTP API

```
GET /autonomy/stats - Получить статистику автономности
```

## Метрики

Система отслеживает:

| Метрика | Описание |
|---------|----------|
| `request` | Входящий запрос |
| `pathway_hit` | Ответ из neural pathway |
| `cache_hit` | Ответ из кэша |
| `llm_call` | Вызов LLM |
| `autonomous_response` | Успешный автономный ответ |
| `organ_created` | Создание нового органа |

**Формула автономности:**
```
autonomy_rate = (pathway_hits + cache_hits) / total_requests × 100%
```

## Файлы проекта

```
prototype/
├── neira_brain.py           # SQLite база данных
├── neira_brain.db           # Файл БД (создаётся автоматически)
├── unified_organ_system.py  # Единая система органов
├── response_engine.py       # Движок автономных ответов
├── local_embeddings.py      # Локальные эмбеддинги v2.0
├── neira_server.py          # Обновлён с интеграцией
└── telegram_bot.py          # Обновлён с интеграцией
```

## Переменные окружения

```env
# Local Embeddings
NEIRA_LOCAL_EMBEDDINGS=true           # Включить локальные эмбеддинги
NEIRA_LOCAL_EMBED_SEMANTIC=true       # Семантические фичи
NEIRA_LOCAL_EMBED_CACHE_SIZE=1000     # Размер LRU кэша
NEIRA_LOCAL_EMBED_DIM=384             # Размерность вектора
```

## Следующие шаги (Phase 2)

1. **Улучшить neural_pathways.json** — добавить success_count tracking
2. **ResponseVariator** — больше шаблонов и вариаций
3. **Автоматическое обучение** — интеграция с emoji feedback
4. **Органы в Telegram** — исправить создание через бота

## Тестирование

```bash
# Тест NeiraBrain
python neira_brain.py

# Тест UnifiedOrganSystem
python unified_organ_system.py

# Тест ResponseEngine
python response_engine.py

# Тест Local Embeddings (требует включения)
set NEIRA_LOCAL_EMBEDDINGS=true
python local_embeddings.py
```

---

**Дата:** 2025-01-XX  
**Версия:** Phase 1.0  
**Автор:** GitHub Copilot + Создатель
