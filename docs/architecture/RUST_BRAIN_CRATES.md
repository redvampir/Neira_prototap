# Rust Brain Crates — состав и границы

> Цель: зафиксировать состав ключевых crate/модулей Rust‑ядра мозга Neira, их границы ответственности, зависимости и минимальные публичные интерфейсы.

## 1) Карта модулей (что за что отвечает)

| Crate/модуль | Короткая роль | Основной выход |
| --- | --- | --- |
| `intent` | распознавание цели/намерения | структурированный `Intent` |
| `router` | маршрутизация между путями и памятью | `RoutePlan` |
| `pathways` | управление «нейронными путями» (последовательности шагов) | `PathwayPlan` |
| `memory` | единый доступ к уровням памяти | `MemoryRecord` / `MemoryView` |
| `wisdom` | стабилизированные выводы и правила | `Wisdom` |
| `synth` | синтез ответа и объяснения | `SynthResult` |
| `learning` | обучение и обновление весов/порогов | `LearningDelta` |
| `llm_fallback` | резервный LLM‑контур | `FallbackResponse` |

## 2) Границы ответственности и зависимости

### 2.1 Границы (контракты)

- **`intent`** — только анализ входа и формирование намерения. Не читает память напрямую, получает только контекст и правила. Использует `wisdom` для корректировок интерпретации.
- **`router`** — принимает `Intent` и определяет, какие пути и подсистемы задействовать. Не принимает решения за `pathways`.
- **`pathways`** — планирует последовательность шагов (процедуру). Не исполняет низкоуровневые операции памяти и обучения напрямую.
- **`memory`** — единая абстракция чтения/записи. Не принимает решений о том, «что» помнить — только «как» хранить и извлекать.
- **`wisdom`** — хранит конденсированные правила и выводы. Не обращается к LLM и не управляет маршрутизацией.
- **`synth`** — объединяет результаты путей и памяти в финальный ответ. Не инициирует обучение.
- **`learning`** — обновляет веса/пороги/шаблоны. Не строит ответы.
- **`llm_fallback`** — резерв на случай отсутствия/неудачи локальных путей. Используется `router`/`synth` по правилу «мягкого отката».

### 2.2 Зависимости (направление стрелок)

```
intent ──▶ router ──▶ pathways ──▶ synth
   │            │          │         │
   ▼            ▼          ▼         ▼
 wisdom      memory     memory    memory
   ▲            │          │         │
   └────────────┴──────▶ learning ◀──┘
                 │
                 ▼
           llm_fallback
```

**Пояснение:**
- `intent` зависит от `wisdom` (правила интерпретации), но не от `memory`.
- `router` зависит от `intent`, `memory` (контекст/состояние) и опционально `llm_fallback`.
- `pathways` использует `memory` для данных и `learning` для обратной связи.
- `synth` зависит от `memory`, `pathways` и `llm_fallback`.
- `learning` читает из `memory`, применяет дельты и может инициировать запись «мудрости».

## 3) Минимальные публичные интерфейсы (V1)

Ниже — минимальный «скелет» публичных API, необходимый для интеграции модулей.

### 3.1 `intent`

```rust
pub struct Intent {
    pub name: String,
    pub confidence: f32,
    pub slots: std::collections::HashMap<String, String>,
}

pub struct IntentContext {
    pub language: String,
    pub user_mode: String,
}

pub fn infer_intent(text: &str, ctx: &IntentContext) -> Result<Intent, IntentError>;
```

### 3.2 `router`

```rust
pub struct RoutePlan {
    pub pathways: Vec<String>,
    pub needs_fallback: bool,
}

pub struct RouteContext {
    pub intent: Intent,
    pub memory_hint: Option<String>,
}

pub fn build_route_plan(ctx: &RouteContext) -> Result<RoutePlan, RouteError>;
```

### 3.3 `pathways`

```rust
pub struct PathwayPlan {
    pub steps: Vec<String>,
    pub expected_outputs: Vec<String>,
}

pub struct PathwayInput {
    pub route: RoutePlan,
    pub memory_snapshot: MemoryView,
}

pub fn plan_pathways(input: &PathwayInput) -> Result<PathwayPlan, PathwayError>;
```

### 3.4 `memory`

```rust
pub struct MemoryRecord {
    pub key: String,
    pub value: String,
    pub tags: Vec<String>,
}

pub struct MemoryQuery {
    pub query: String,
    pub limit: usize,
}

pub struct MemoryView {
    pub records: Vec<MemoryRecord>,
}

pub trait MemoryStore {
    fn read(&self, query: &MemoryQuery) -> Result<MemoryView, MemoryError>;
    fn write(&mut self, record: MemoryRecord) -> Result<(), MemoryError>;
}
```

### 3.5 `wisdom`

```rust
pub struct Wisdom {
    pub rules: Vec<String>,
    pub updated_at: String,
}

pub fn load_wisdom() -> Result<Wisdom, WisdomError>;
pub fn update_wisdom(delta: &LearningDelta) -> Result<(), WisdomError>;
```

### 3.6 `synth`

```rust
pub struct SynthInput {
    pub pathway_plan: PathwayPlan,
    pub memory_view: MemoryView,
}

pub struct SynthResult {
    pub text: String,
    pub confidence: f32,
}

pub fn synthesize(input: &SynthInput) -> Result<SynthResult, SynthError>;
```

### 3.7 `learning`

```rust
pub struct LearningDelta {
    pub notes: Vec<String>,
    pub score_adjustments: Vec<(String, f32)>,
}

pub struct LearningContext {
    pub intent: Intent,
    pub outcome: SynthResult,
}

pub fn learn(ctx: &LearningContext) -> Result<LearningDelta, LearningError>;
```

### 3.8 `llm_fallback`

```rust
pub struct FallbackRequest {
    pub prompt: String,
    pub max_tokens: usize,
}

pub struct FallbackResponse {
    pub text: String,
    pub tokens_used: usize,
}

pub fn request_fallback(req: &FallbackRequest) -> Result<FallbackResponse, FallbackError>;
```

## 4) Минимальный сценарий взаимодействия

1. `infer_intent` распознаёт намерение.
2. `build_route_plan` формирует маршрут.
3. `plan_pathways` строит план шагов с опорой на `memory`.
4. `synthesize` собирает ответ, при необходимости запрашивая `llm_fallback`.
5. `learn` формирует дельту обучения и обновляет `wisdom`.

---

Если в V2 появятся новые подсистемы, они добавляются только через явные границы и минимальные публичные интерфейсы, перечисленные в этом документе.
