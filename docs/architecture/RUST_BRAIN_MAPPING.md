# Маппинг Python → Rust Brain

> Цель документа: связать существующие Python-компоненты Neira с целевыми Rust-модулями для планирования миграции.

## 1) Обзор текущей архитектуры (Python)

```
┌─────────────────────────────────────────────────────────────────┐
│                     neira_server.py                              │
│                    (Telegram Bot + API)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      NeiraCortex                                 │
│            (Центральный когнитивный процессор)                   │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │IntentRecognizer│  │DecisionRouter │  │NeuralPathwaySystem │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              ResponseSynthesizer                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  MemoryCell   │  │   Cell(s)     │  │  LLMClient    │
│  (память)     │  │ (обработчики) │  │  (fallback)   │
└───────────────┘  └───────────────┘  └───────────────┘
```

## 2) Таблица маппинга: Python → Rust

| Python компонент | Файл | Rust crate | Роль в Rust |
|------------------|------|------------|-------------|
| `IntentRecognizer` | neira_cortex.py | `intent` | `infer_intent()` — распознавание намерения |
| `DecisionRouter` | neira_cortex.py | `router` | `build_route_plan()` — выбор стратегии |
| `NeuralPathwaySystem` | neira_cortex.py | `pathways` | `plan_pathways()` — граф путей решений |
| `MemoryCell` | cells.py | `memory` | `MemoryStore` trait — чтение/запись |
| `ResponseSynthesizer` | neira_cortex.py | `synth` | `synthesize()` — сборка ответа |
| `Cell._fallback_response` | cells.py | `synth` | Локальный ответ без LLM |
| `LLMClient` | llm_providers.py | `llm_fallback` | `request_fallback()` — резервный LLM |
| `CellResult` | cells.py | — | Распадается на `Intent`, `SynthResult`, `LearningDelta` |
| `NeiraCortex` | neira_cortex.py | — | **Нет прямого аналога** — логика распределена по crates |

## 3) Детальный маппинг структур данных

### 3.1) CellResult → множественные типы

**Python (текущий):**
```python
@dataclass
class CellResult:
    content: str           # → SynthResult.text
    confidence: float      # → Intent.confidence / SynthResult.confidence
    cell_name: str         # → удаляется (не нужен в Rust)
    metadata: Dict[str, Any]  # → распадается на типизированные поля
```

**Rust (целевой):**
```rust
// Для распознавания намерения
pub struct Intent {
    pub name: String,
    pub confidence: f32,
    pub slots: HashMap<String, String>,
}

// Для синтеза ответа
pub struct SynthResult {
    pub text: String,
    pub confidence: f32,
}

// Для обучения
pub struct LearningDelta {
    pub notes: Vec<String>,
    pub score_adjustments: Vec<(String, f32)>,
}
```

### 3.2) MemoryEntry → MemoryRecord

**Python (текущий):**
```python
@dataclass
class MemoryEntry:
    text: str
    embedding: List[float]
    timestamp: str
    importance: float = 0.5
    category: str = "general"
    source: str = "conversation"
```

**Rust (целевой):**
```rust
pub struct MemoryRecord {
    pub key: String,           // Новое: уникальный ключ
    pub value: String,         // ← text
    pub tags: Vec<String>,     // ← category + source объединены
    // embedding → отдельный индекс/хранилище
    // timestamp → в метаданных или отдельном поле
    // importance → в tags или отдельном scoring модуле
}
```

### 3.3) ResponseStrategy → RoutePlan

**Python (текущий):**
```python
class ResponseStrategy(Enum):
    NEURAL_PATHWAY = "neural_pathway"
    TEMPLATE = "template"
    FRAGMENT_ASSEMBLY = "fragment_assembly"
    LLM_CONSULTANT = "llm_consultant"
    HYBRID = "hybrid"
    RAG = "rag"
```

**Rust (целевой):**
```rust
pub struct RoutePlan {
    pub pathways: Vec<String>,  // Какие пути активировать
    pub needs_fallback: bool,   // Нужен ли LLM
}
// Стратегии кодируются через комбинацию pathways + needs_fallback
```

## 4) Что НЕ переносится в Rust

| Компонент | Причина |
|-----------|---------|
| `Cell` (базовый класс) | Концепция переосмыслена — в Rust нет наследования в стиле Python |
| `AnalyzerCell`, `PlannerCell`, etc. | Становятся частью `pathways` или `synth` |
| `WebSearchCell` | Адаптер, подключается как внешний модуль |
| `_llm_client` static variable | В Rust — явная передача зависимостей |
| `neira_server.py` | Остаётся Python — Telegram/HTTP API поверх Rust-ядра |

## 5) Архитектурные решения при миграции

### 5.1) NeiraCortex → распределённая логика

**Было (Python):** Один монолитный класс `NeiraCortex` координирует всё.

**Станет (Rust):** Логика распределена:
```rust
// main.rs или lib.rs
pub fn process_request(input: &str) -> Result<String, BrainError> {
    // 1. Intent
    let intent = intent::infer_intent(input, &ctx)?;
    
    // 2. Router
    let route = router::build_route_plan(&RouteContext { intent, .. })?;
    
    // 3. Pathways
    let memory_view = memory::read(&query)?;
    let plan = pathways::plan_pathways(&PathwayInput { route, memory_view })?;
    
    // 4. Synth (с опциональным fallback)
    let result = synth::synthesize(&SynthInput { plan, memory_view })?;
    
    // 5. Learning (асинхронно)
    learning::learn(&LearningContext { intent, outcome: result.clone() })?;
    
    Ok(result.text)
}
```

### 5.2) Fallback цепочка

**Python (текущий):**
```python
def call_llm(self, prompt):
    if Cell._llm_available:
        return self._call_llm_client(prompt)
    if not OLLAMA_DISABLED:
        return self._call_ollama_legacy(prompt)
    return self._fallback_response(prompt)
```

**Rust (целевой):**
```rust
// В router или synth
pub fn get_response(input: &SynthInput) -> Result<SynthResult, SynthError> {
    // Попытка 1: локальные pathways
    if let Ok(result) = local_pathways(input) {
        return Ok(result);
    }
    
    // Попытка 2: шаблоны
    if let Ok(result) = template_match(input) {
        return Ok(result);
    }
    
    // Попытка 3: LLM fallback (только если разрешено)
    if input.allow_llm {
        return llm_fallback::request_fallback(&req);
    }
    
    // Degraded response
    Ok(SynthResult { text: "...".into(), confidence: 0.1 })
}
```

## 6) План миграции по файлам

| Этап | Python файлы | Rust crates | Приоритет |
|------|--------------|-------------|-----------|
| **0** | — | Форматы данных, глоссарий | ✅ Готово |
| **1** | neira_cortex.py (IntentRecognizer) | `intent` | 🔴 Высокий |
| **1** | neira_cortex.py (DecisionRouter) | `router` | 🔴 Высокий |
| **1** | cells.py (MemoryCell) | `memory` | 🔴 Высокий |
| **2** | neira_cortex.py (NeuralPathwaySystem) | `pathways` | 🟡 Средний |
| **2** | neira_cortex.py (ResponseSynthesizer) | `synth` | 🟡 Средний |
| **3** | cells.py (обучение) | `learning`, `wisdom` | 🟢 Низкий |
| **3** | llm_providers.py | `llm_fallback` | 🟢 Низкий |

## 7) Интеграция с mistral.rs

**Роль:** Локальный LLM для качественных ответов без сети.

```rust
// В llm_fallback crate
use mistralrs::{Model, TextGeneration};

pub struct MistralFallback {
    model: Model,
}

impl MistralFallback {
    pub fn new(model_path: &str) -> Result<Self, FallbackError> {
        let model = Model::load(model_path)?;
        Ok(Self { model })
    }
    
    pub fn generate(&self, prompt: &str, max_tokens: usize) -> Result<String, FallbackError> {
        self.model.generate(prompt, max_tokens)
    }
}

// Интеграция в request_fallback
pub fn request_fallback(req: &FallbackRequest) -> Result<FallbackResponse, FallbackError> {
    // Приоритет 1: mistral.rs (локальный, быстрый)
    if let Ok(resp) = MISTRAL_FALLBACK.generate(&req.prompt, req.max_tokens) {
        return Ok(FallbackResponse { text: resp, tokens_used: resp.len() });
    }
    
    // Приоритет 2: Внешний API (если есть сеть)
    external_api_fallback(req)
}
```

## 8) Тестовые сценарии для валидации маппинга

| Сценарий | Python вход | Ожидаемый Rust выход |
|----------|-------------|---------------------|
| Простой вопрос | "Привет" | Intent{name: "greeting", confidence: 0.9} |
| Запрос из памяти | "Что я спрашивал вчера?" | MemoryView с записями |
| Код | "Напиши функцию сортировки" | RoutePlan{pathways: ["code"], needs_fallback: true} |
| Офлайн | (нет сети) | SynthResult с меткой `degraded` |

---

**Следующий шаг:** Создать `neira-brain/` crate с минимальным `intent` модулем и прогнать первый тест.
