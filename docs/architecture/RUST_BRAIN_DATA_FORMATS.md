# Форматы данных для Rust Brain

> Цель документа: зафиксировать минимальные схемы данных для Pathway, Memory и Wisdom, а также правила сериализации и версионирования.

## 1) Версионирование форматов

**Почему важно:** форматы будут жить дольше кода и должны выдерживать миграции без потери смысла.

**Правила:**
- В каждой записи присутствует поле `format_version` (строка в стиле `MAJOR.MINOR.PATCH`).
- **MAJOR** увеличивается при несовместимых изменениях.
- **MINOR** — при добавлении новых необязательных полей.
- **PATCH** — при уточнениях описаний/конвенций без изменения структуры.
- Для миграций вводится отдельный слой адаптеров, но сами данные остаются самодостаточными.

**Рекомендуемое значение по умолчанию:** `1.0.0`.

## 2) Схемы

### 2.1) Pathway

**Назначение:** хранит маршрут решения (шаблон, триггеры, переменные) и статистику использования.

| Поле | Тип | Обязательное | Описание |
| --- | --- | --- | --- |
| `format_version` | string | да | Версия формата записи. |
| `id` | string | да | Уникальный идентификатор пути. |
| `triggers` | array<string> | да | Набор триггеров (слова, паттерны, intent‑метки). |
| `template` | string | да | Шаблон, определяющий структуру ответа/действия. |
| `variables` | object | да | Словарь переменных шаблона (ключ → значение). |
| `tier` | string | да | Уровень важности/стабильности (например, `core`, `adaptive`, `experimental`). |
| `usage_stats` | object | да | Метрики использования (см. пример). |

**usage_stats (рекомендуемая структура):**
- `hits`: number — количество обращений.
- `success_rate`: number — доля успешных применений (0..1).
- `last_used_at`: string — ISO 8601 timestamp.

### 2.2) Memory Item

**Назначение:** хранит пользовательскую память (запрос → ответ), пригодную для восстановления контекста.

| Поле | Тип | Обязательное | Описание |
| --- | --- | --- | --- |
| `format_version` | string | да | Версия формата записи. |
| `user_id` | string | да | Идентификатор пользователя. |
| `input` | string | да | Вход пользователя. |
| `response` | string | да | Ответ системы. |
| `timestamp` | string | да | Время события в ISO 8601. |
| `tags` | array<string> | да | Теги для поиска/агрегации. |

### 2.3) Wisdom Fact

**Назначение:** фиксирует проверенные факты/правила, пригодные для повторного использования и вывода.

| Поле | Тип | Обязательное | Описание |
| --- | --- | --- | --- |
| `format_version` | string | да | Версия формата записи. |
| `fact_id` | string | да | Уникальный идентификатор факта. |
| `category` | string | да | Категория (например, `safety`, `behavior`, `domain_knowledge`). |
| `content` | string | да | Содержимое факта/правила. |
| `confidence` | number | да | Уровень уверенности (0..1). |
| `relations` | array<object> | да | Связи с другими фактами (см. пример). |

**relations (рекомендуемая структура):**
- `fact_id`: string — связанный факт.
- `type`: string — тип связи (`supports`, `contradicts`, `extends`).
- `weight`: number — сила связи (0..1).

## 3) Примеры сериализации

### 3.1) Pathway

**JSON**
```json
{
  "format_version": "1.0.0",
  "id": "pathway.intent.support",
  "triggers": ["help", "support", "assist"],
  "template": "Ответь вежливо и кратко: {user_request}",
  "variables": {
    "user_request": "Где найти документацию?"
  },
  "tier": "core",
  "usage_stats": {
    "hits": 128,
    "success_rate": 0.94,
    "last_used_at": "2025-01-14T10:15:30Z"
  }
}
```

**YAML**
```yaml
format_version: "1.0.0"
id: pathway.intent.support
triggers:
  - help
  - support
  - assist
template: "Ответь вежливо и кратко: {user_request}"
variables:
  user_request: "Где найти документацию?"
tier: core
usage_stats:
  hits: 128
  success_rate: 0.94
  last_used_at: "2025-01-14T10:15:30Z"
```

### 3.2) Memory Item

**JSON**
```json
{
  "format_version": "1.0.0",
  "user_id": "user_42",
  "input": "Напомни, как запустить бота",
  "response": "Используй команду ./start.sh",
  "timestamp": "2025-01-14T10:17:02Z",
  "tags": ["ops", "runbook", "telegram"]
}
```

**YAML**
```yaml
format_version: "1.0.0"
user_id: user_42
input: "Напомни, как запустить бота"
response: "Используй команду ./start.sh"
timestamp: "2025-01-14T10:17:02Z"
tags:
  - ops
  - runbook
  - telegram
```

### 3.3) Wisdom Fact

**JSON**
```json
{
  "format_version": "1.0.0",
  "fact_id": "wisdom.safety.no_exec",
  "category": "safety",
  "content": "Запрещено выполнять непроверенный ввод пользователя через exec/eval.",
  "confidence": 0.99,
  "relations": [
    {
      "fact_id": "wisdom.security.input_validation",
      "type": "supports",
      "weight": 0.8
    }
  ]
}
```

**YAML**
```yaml
format_version: "1.0.0"
fact_id: wisdom.safety.no_exec
category: safety
content: "Запрещено выполнять непроверенный ввод пользователя через exec/eval."
confidence: 0.99
relations:
  - fact_id: wisdom.security.input_validation
    type: supports
    weight: 0.8
```

---

Если понадобится расширение форматов, изменения отражаются через повышение `format_version` и документируются в журнале миграций.
