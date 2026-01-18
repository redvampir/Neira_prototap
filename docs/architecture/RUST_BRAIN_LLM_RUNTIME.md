# Интеграция LLM Runtime для Rust Brain

> Цель документа: зафиксировать выбор LLM runtime, рекомендуемые модели и архитектуру интеграции.

## 1) Выбранный Runtime: mistral.rs

**Репозиторий:** [EricLBuehler/mistral.rs](https://github.com/EricLBuehler/mistral.rs)

**Почему mistral.rs:**
- ✅ Нативный Rust (без Python bindings)
- ✅ CUDA поддержка (RTX 3060 Ti)
- ✅ Поддержка множества архитектур (Mistral, Llama, Qwen, Phi)
- ✅ Quantization (AWQ, GPTQ, GGUF)
- ✅ Активно развивается

**Альтернативы (отвергнуты):**
| Runtime | Причина отказа |
|---------|---------------|
| llama.cpp | C++, требует FFI bindings |
| candle | Низкоуровневый, нужно много кода |
| llm (Rust) | Менее активный, меньше моделей |

## 2) Рекомендуемые модели

### 2.1) Основная модель: Mistral 7B Instruct v0.3

**Характеристики:**
- Размер: 7B параметров
- VRAM: ~6GB (Q4), ~4GB (Q3)
- Контекст: 8K токенов (расширяемо до 32K)
- Языки: English, Русский (хорошо)
- Формат: GGUF (оптимально для inference)

**Загрузка:**
```bash
# Через huggingface-cli
huggingface-cli download TheBloke/Mistral-7B-Instruct-v0.3-GGUF \
  mistral-7b-instruct-v0.3.Q4_K_M.gguf \
  --local-dir ./models/
```

**Почему Mistral 7B:**
- Оптимальный баланс качества и скорости для 8GB VRAM
- Хорошо понимает русский язык
- Отличная instruction-following способность
- Поддерживается mistral.rs из коробки

### 2.2) Альтернатива: Qwen2.5-7B-Instruct

**Характеристики:**
- Размер: 7B параметров
- VRAM: ~6GB (Q4)
- Контекст: 32K токенов (нативно!)
- Языки: English, Русский, Китайский
- Кодирование: отличное

**Когда выбрать Qwen:**
- Нужен длинный контекст (>8K)
- Много работы с кодом
- Нужна мультиязычность

### 2.3) Резервная модель: Phi-3-mini-4k

**Характеристики:**
- Размер: 3.8B параметров
- VRAM: ~3GB (Q4)
- Контекст: 4K токенов
- Скорость: очень быстрая

**Когда выбрать Phi-3:**
- Быстрые простые запросы
- Ограниченная VRAM
- Degraded mode

## 3) Архитектура интеграции

```
┌─────────────────────────────────────────────────────────────────┐
│                        Rust Brain Core                           │
│                                                                  │
│  intent → router → pathways → memory → synth                    │
│                                    │                             │
│                                    ▼                             │
│                         ┌─────────────────┐                     │
│                         │  llm_fallback   │                     │
│                         └────────┬────────┘                     │
└──────────────────────────────────┼──────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
             ┌──────────┐  ┌──────────┐  ┌──────────┐
             │mistral.rs│  │ External │  │ Degraded │
             │ (local)  │  │   API    │  │  Mode    │
             └──────────┘  └──────────┘  └──────────┘
                  │
                  ▼
         ┌───────────────┐
         │ Mistral 7B    │
         │ (Q4_K_M.gguf) │
         └───────────────┘
```

## 4) Конфигурация

### 4.1) Файл конфигурации: `brain_config.toml`

```toml
[llm]
# Основная модель
primary_model = "mistral-7b-instruct-v0.3"
primary_path = "./models/mistral-7b-instruct-v0.3.Q4_K_M.gguf"
primary_context = 8192

# Резервная модель (для быстрых/простых запросов)
fallback_model = "phi-3-mini"
fallback_path = "./models/phi-3-mini-4k.Q4_K_M.gguf"
fallback_context = 4096

# Настройки генерации
default_temperature = 0.7
default_max_tokens = 1024
default_top_p = 0.9

# CUDA настройки
cuda_enabled = true
gpu_layers = 35  # Сколько слоёв на GPU (для 8GB VRAM)

[fallback_rules]
# Правила переключения на LLM
max_local_attempts = 2
local_timeout_ms = 180
allow_external_api = false  # Офлайн по умолчанию
```

### 4.2) Rust интерфейс

```rust
// llm_fallback/src/lib.rs

use mistralrs::{MistralRs, MistralRsBuilder, TextModelBuilder};

pub struct LLMFallbackConfig {
    pub model_path: String,
    pub context_size: usize,
    pub gpu_layers: usize,
    pub temperature: f32,
}

pub struct LLMFallback {
    model: MistralRs,
    config: LLMFallbackConfig,
}

impl LLMFallback {
    pub fn new(config: LLMFallbackConfig) -> Result<Self, FallbackError> {
        let model = MistralRsBuilder::new()
            .with_gguf(&config.model_path)?
            .with_gpu_layers(config.gpu_layers)
            .build()?;
        
        Ok(Self { model, config })
    }
    
    pub async fn generate(&self, req: &FallbackRequest) -> Result<FallbackResponse, FallbackError> {
        let response = self.model
            .send_chat_completion_request(
                ChatCompletionRequest {
                    messages: vec![
                        ChatMessage::system(&req.system_prompt),
                        ChatMessage::user(&req.prompt),
                    ],
                    max_tokens: Some(req.max_tokens),
                    temperature: Some(self.config.temperature),
                    ..Default::default()
                }
            )
            .await?;
        
        Ok(FallbackResponse {
            text: response.choices[0].message.content.clone(),
            tokens_used: response.usage.total_tokens,
            model_used: self.config.model_path.clone(),
        })
    }
}
```

## 5) Метрики производительности (ожидаемые)

| Модель | VRAM | Tokens/sec | Latency (p95) |
|--------|------|------------|---------------|
| Mistral 7B Q4 | ~6GB | 30-40 | 200-400ms |
| Qwen2.5 7B Q4 | ~6GB | 25-35 | 250-500ms |
| Phi-3 mini Q4 | ~3GB | 50-70 | 100-200ms |

**Целевые показатели для Neira:**
- Простые запросы (без LLM): ≤180ms
- Запросы с LLM fallback: ≤500ms
- Сложные генерации: ≤2000ms

## 6) План внедрения

### Этап 1: Тестирование mistral.rs (текущий)
- [x] Сборка mistral.rs с CUDA
- [ ] Загрузка Mistral 7B модели
- [ ] Тест inference через CLI
- [ ] Бенчмарк latency

### Этап 2: Интеграция в Rust Brain
- [ ] Создать `llm_fallback` crate
- [ ] Реализовать `LLMFallback` struct
- [ ] Добавить в `synth` как опциональный fallback
- [ ] Тесты офлайн-режима

### Этап 3: Оптимизация
- [ ] Профилирование VRAM usage
- [ ] Настройка gpu_layers
- [ ] KV-cache оптимизация
- [ ] Batch inference (если нужно)

## 7) Рекомендация для Neira

**Финальный выбор: Mistral 7B Instruct v0.3 (Q4_K_M)**

**Причины:**
1. Оптимален для 8GB VRAM RTX 3060 Ti
2. Отличное понимание русского языка
3. Хороший instruction-following
4. Нативная поддержка в mistral.rs
5. Достаточно быстрый для интерактивного использования

**Конфигурация для старта:**
```toml
[llm]
primary_model = "mistral-7b-instruct-v0.3"
primary_path = "./models/mistral-7b-instruct-v0.3.Q4_K_M.gguf"
gpu_layers = 33  # ~6GB VRAM, остаток для KV cache
default_temperature = 0.7
default_max_tokens = 1024
```

---

**Следующий шаг:** Загрузить модель и протестировать inference.
