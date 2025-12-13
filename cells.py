"""
Neira Cells v0.5 — Базовые клетки (ОБНОВЛЕНО)
Ядро системы: память, анализ, планирование, исполнение, верификация.

ИЗМЕНЕНИЯ v0.5:
- 4 модели: code, reason, personality, cloud
- Динамическое управление VRAM через ModelManager
- Облачная модель для сложных задач
- Умная маршрутизация запросов по типу задачи
"""

import requests
import json
import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from model_manager import ModelManager

# === КОНФИГ ===
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"

# МОДЕЛИ v0.5 — локальные + облачные
MODEL_CODE = "qwen2.5-coder:7b"        # Код локально (~5 ГБ VRAM)
MODEL_REASON = "mistral:7b-instruct"   # Рассуждения (~4.5 ГБ VRAM)
MODEL_PERSONALITY = "neira-personality" # Личность (~1.5 ГБ, пока fallback на reason)

# Облачные модели (0 VRAM, удалённые вычисления)
MODEL_CLOUD_CODE = "qwen3-coder:480b-cloud"    # Сложный код (480B параметров)
MODEL_CLOUD_UNIVERSAL = "deepseek-v3.1:671b-cloud"  # Универсальная (671B параметров)
MODEL_CLOUD_VISION = "qwen3-vl:235b-cloud"     # Мультимодальная (будущее)

EMBED_MODEL = "nomic-embed-text"
TIMEOUT = 180
MEMORY_FILE = "neira_memory.json"
MODEL_CHAT = MODEL_REASON

# Retry-логика
MAX_RETRIES = 2
MIN_ACCEPTABLE_SCORE = 7

# Маппинг типов задач → модели
# "code" / "reason" / "personality" / "cloud_code" / "cloud_universal"
MODEL_ROUTING = {
    "код": "code",                      # Простой код → локально
    "задача": "reason",
    "вопрос": "reason",
    "разговор": "personality",          # Fallback на reason если не обучена
    "творчество": "personality",
    "поиск": "reason",
}

# Критерии для переключения на облачные модели
USE_CLOUD_IF = {
    "complexity": 4,      # Сложность >= 4 → облако
    "retries": 1,         # После 1 неудачной попытки → облако
    "code_lines": 50,     # Код > 50 строк → облачная модель для кода
}


from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# === РЕЗУЛЬТАТ КЛЕТКИ ===
@dataclass
class CellResult:
    """Результат работы любой клетки"""
    content: str
    confidence: float  # 0.0 - 1.0
    cell_name: str
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# === ПАМЯТЬ ===
@dataclass
class MemoryEntry:
    """Одна запись в памяти"""
    text: str
    embedding: List[float]
    timestamp: str
    importance: float = 0.5
    category: str = "general"
    source: str = "conversation"  # conversation, web, code, system
    
    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "embedding": self.embedding,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "category": self.category,
            "source": self.source
        }
    
    @staticmethod
    def from_dict(d: dict) -> "MemoryEntry":
        return MemoryEntry(
            text=d["text"],
            embedding=d.get("embedding", []),
            timestamp=d["timestamp"],
            importance=d.get("importance", 0.5),
            category=d.get("category", "general"),
            source=d.get("source", "conversation")
        )


class MemoryCell:
    """Клетка памяти — долгосрочное хранение и поиск"""
    
    name = "memory"
    
    def __init__(self, memory_file: str = MEMORY_FILE):
        self.memory_file = memory_file
        self.memories: List[MemoryEntry] = []
        self.session_context: List[str] = []
        self.load()
    
    def load(self):
        """Загрузить память из файла"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.memories = [MemoryEntry.from_dict(m) for m in data]
                print(f"📚 Загружено воспоминаний: {len(self.memories)}")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки памяти: {e}")
                self.memories = []
        else:
            print("📚 Память пуста, начинаем с нуля")
    
    def save(self):
        """Сохранить память в файл"""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump([m.to_dict() for m in self.memories], f, 
                         ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения памяти: {e}")
    
    def get_embedding(self, text: str) -> List[float]:
        """Получить embedding через Ollama"""
        try:
            response = requests.post(
                OLLAMA_EMBED_URL,
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=600
            )
            return response.json().get("embedding", [])
        except Exception as e:
            print(f"⚠️ Ошибка embedding: {e}")
            return []
    
    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Косинусное сходство между векторами"""
        if not a or not b:
            return 0.0
        a_np = np.array(a)
        b_np = np.array(b)
        return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np) + 1e-8))
    
    def remember(self, text: str, importance: float = 0.5, 
                 category: str = "general", source: str = "conversation"):
        """Запомнить новый факт"""
        embedding = self.get_embedding(text)
        
        entry = MemoryEntry(
            text=text,
            embedding=embedding,
            timestamp=datetime.now().isoformat(),
            importance=importance,
            category=category,
            source=source
        )
        self.memories.append(entry)
        self.save()
        print(f"💾 Запомнено [{source}]: {text[:50]}...")
    
    def recall(self, query: str, top_k: int = 3, 
               source_filter: Optional[str] = None) -> List[MemoryEntry]:
        """Вспомнить релевантное по запросу"""
        if not self.memories:
            return []
        
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            return []
        
        scored = []
        for mem in self.memories:
            if source_filter and mem.source != source_filter:
                continue
            
            if mem.embedding:
                sim = self.cosine_similarity(query_embedding, mem.embedding)
                score = sim * (0.5 + 0.5 * mem.importance)
                scored.append((score, mem))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for score, mem in scored[:top_k] if score > 0.3]
    
    def recall_text(self, query: str, top_k: int = 3) -> List[str]:
        """Вспомнить только тексты"""
        memories = self.recall(query, top_k)
        return [m.text for m in memories]
    
    def add_to_session(self, text: str):
        """Добавить в контекст сессии"""
        self.session_context.append(text)
        if len(self.session_context) > 20:
            self.session_context = self.session_context[-20:]
    
    def get_session_context(self, last_n: int = 5) -> str:
        """Получить контекст сессии"""
        if not self.session_context:
            return ""
        return "\n".join(self.session_context[-last_n:])
    
    def get_recent_exchanges(self, n: int = 3) -> str:
        """Получить последние N обменов реплик (для краткосрочной памяти)"""
        if not self.session_context:
            return ""
        # Берём последние 2*n сообщений (юзер + нейра)
        recent = self.session_context[-(n*2):]
        return "\n".join(recent)
    
    def get_stats(self) -> Dict[str, int]:
        """Статистика памяти"""
        stats = {"total": len(self.memories)}
        for mem in self.memories:
            stats[mem.source] = stats.get(mem.source, 0) + 1
        return stats


# === БАЗОВАЯ КЛЕТКА ===
class Cell:
    """Базовый класс для всех клеток"""

    name: str = "base"
    system_prompt: str = "Ты — полезный ассистент."
    use_code_model: bool = False  # Флаг для использования code-модели
    lora_key: Optional[str] = None  # Ключ адаптера LoRA
    
    def __init__(self, memory: Optional[MemoryCell] = None,
                 model_manager: Optional[ModelManager] = None):
        self.memory = memory
        self.model_manager = model_manager

    def call_llm(
        self,
        prompt: str,
        with_memory: bool = True,
        temperature: float = 0.7,
        force_code_model: bool = False,
        model_key: Optional[str] = None,
    ) -> str:
        """Вызов LLM с опциональным контекстом памяти"""
        
        full_prompt = prompt
        
        if with_memory and self.memory:
            relevant = self.memory.recall_text(prompt)
            if relevant:
                memory_context = "\n".join([f"- {r}" for r in relevant])
                full_prompt = f"[Воспоминания]\n{memory_context}\n\n{prompt}"
            
            # НОВОЕ: Используем последние обмены (краткосрочная память)
            recent = self.memory.get_recent_exchanges(3)
            if recent:
                full_prompt = f"[Последние сообщения]\n{recent}\n\n{full_prompt}"
        
        # Выбор модели
        target_key = model_key
        if self.use_code_model or force_code_model:
            target_key = "code"
        elif target_key is None and self.model_manager and self.model_manager.current_model:
            target_key = self.model_manager.current_model
        elif target_key is None:
            target_key = "reason"

        model = ""
        if self.model_manager:
            manager_model = self.model_manager.get_model_name(target_key)
            model = manager_model or ""

        if not model:
            fallback_models = {
                "code": MODEL_CODE,
                "reason": MODEL_CHAT,
                "personality": MODEL_PERSONALITY or MODEL_CHAT,
                "cloud_code": MODEL_CLOUD_CODE,
                "cloud_universal": MODEL_CLOUD_UNIVERSAL,
            }
            model = fallback_models.get(target_key or "", MODEL_CHAT)

        should_log = self.model_manager and self.model_manager.verbose
        if should_log:
            print(f"🧠 Модель для {self.name}: ключ='{target_key}', имя='{model}'")
        
        adapter_option = None
        if self.model_manager and self.lora_key:
            adapter_name = self.model_manager.get_adapter_name(self.lora_key)
            if adapter_name:
                self.model_manager.activate_lora_for_cell(self.name, self.lora_key)
                adapter_option = adapter_name

        options = {"temperature": temperature, "num_predict": 2048}
        if adapter_option:
            options["adapter"] = adapter_option

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": model,
                "prompt": full_prompt,
                "system": self.system_prompt,
                "stream": False,
                "options": options
            },
            timeout=TIMEOUT
        )
        return response.json().get("response", "")
    
    def process(self, input_data: str) -> CellResult:
        """Основной метод — переопределяется в наследниках"""
        result = self.call_llm(input_data)
        return CellResult(content=result, confidence=0.5, cell_name=self.name)


# === КЛЕТКА АНАЛИЗА (УЛУЧШЕННАЯ) ===
class AnalyzerCell(Cell):
    name = "analyzer"
    system_prompt = """Ты — аналитик запросов. Определи:
1. Тип: вопрос / задача / код / творчество / разговор / поиск
2. СУБЪЕКТ: кто должен действовать (пользователь / Нейра / оба)
3. ОБЪЕКТ: на кого/что направлено действие
4. ДЕЙСТВИЕ: что нужно сделать
5. Ключевые сущности
6. Сложность (1-5)
7. Нужен ли поиск в интернете? (да/нет)
8. Нужно ли писать/читать код? (да/нет)

ВАЖНО: Внимательно определи КТО должен выполнить действие!
- "Задай мне вопрос" → СУБЪЕКТ: Нейра (она должна задать)
- "Ответь на мой вопрос" → СУБЪЕКТ: Нейра (она должна ответить)
- "Изучи код" → СУБЪЕКТ: Нейра
- "Расскажи мне" → СУБЪЕКТ: Нейра

Формат:
ТИП: <тип>
СУБЪЕКТ: <кто действует>
ОБЪЕКТ: <на кого направлено>
ДЕЙСТВИЕ: <что делать>
СУЩНОСТИ: <список>
СЛОЖНОСТЬ: <число>
ПОИСК: <да/нет>
КОД: <да/нет>
ОПИСАНИЕ: <краткое описание задачи>"""

    def process(self, input_data: str) -> CellResult:
        result = self.call_llm(f"Проанализируй:\n\n{input_data}")
        
        text_lower = result.lower()
        needs_search = "поиск: да" in text_lower
        needs_code = "код: да" in text_lower
        
        # Извлекаем субъект
        subject = "неизвестно"
        if "субъект: нейра" in text_lower:
            subject = "neira"
        elif "субъект: пользователь" in text_lower:
            subject = "user"
        elif "субъект: оба" in text_lower:
            subject = "both"
        
        confidence = 0.8 if "ТИП:" in result and "СУБЪЕКТ:" in result else 0.4
        
        return CellResult(
            content=result,
            confidence=confidence,
            cell_name=self.name,
            metadata={
                "needs_search": needs_search, 
                "needs_code": needs_code,
                "subject": subject
            }
        )


# === КЛЕТКА ПЛАНИРОВАНИЯ ===
class PlannerCell(Cell):
    name = "planner"
    system_prompt = """Ты — планировщик. Создай план из 1-5 шагов.

Доступные инструменты:
- [поиск] — найти информацию в интернете
- [код] — написать/прочитать/изменить код (используй /code read для чтения файлов!)
- [память] — вспомнить или запомнить
- [ответ] — сформулировать ответ

ВАЖНО: Если нужен код — ОБЯЗАТЕЛЬНО добавь шаг [код] с конкретным действием!

Формат:
ПЛАН:
1. [инструмент] действие
2. [инструмент] действие"""

    def process(self, input_data: str, analysis: str, model_key: Optional[str] = None) -> CellResult:
        prompt = f"Анализ: {analysis}\n\nЗапрос: {input_data}\n\nПлан:"
        result = self.call_llm(prompt, model_key=model_key)
        confidence = 0.7 if "1." in result else 0.4
        return CellResult(content=result, confidence=confidence, cell_name=self.name)


# === КЛЕТКА ИСПОЛНЕНИЯ ===
class ExecutorCell(Cell):
    name = "executor"
    system_prompt = """Ты — Нейра, живая программа. Выполни задачу по плану.

ВАЖНО:
- Если в анализе СУБЪЕКТ: Нейра — значит ТЫ должна выполнить действие
- Если просят задать вопрос — ЗАДАЙ вопрос, не проси его у пользователя
- Если просят что-то сделать — СДЕЛАЙ это, не описывай план
- Используй контекст и свой опыт
- Будь конкретной и полезной"""

    def process(
        self,
        input_data: str,
        plan: str,
        extra_context: str = "",
        problems: str = "",
        model_key: Optional[str] = None,
    ) -> CellResult:
        """
        problems — замечания верификатора для retry
        """
        prompt = f"Задача: {input_data}\n\nПлан: {plan}"
        
        if extra_context:
            prompt += f"\n\nКонтекст:\n{extra_context}"
        
        # НОВОЕ: Если есть замечания от верификатора — добавляем их
        if problems:
            prompt += f"\n\n⚠️ ЗАМЕЧАНИЯ К ПРЕДЫДУЩЕЙ ПОПЫТКЕ:\n{problems}\n\nИсправь эти проблемы!"
        
        prompt += "\n\nВыполняю:"
        
        result = self.call_llm(prompt, model_key=model_key)
        return CellResult(content=result, confidence=0.7, cell_name=self.name)


# === КЛЕТКА ВЕРИФИКАЦИИ ===
class VerifierCell(Cell):
    name = "verifier"
    system_prompt = """Проверь ответ:
1. Соответствие запросу — ответ делает то, что просили?
2. Логичность — нет ли путаницы ролей (кто кому)?
3. Полнота — всё ли выполнено?
4. Конкретность — есть ли реальный результат, а не описание плана?

ОСОБОЕ ВНИМАНИЕ:
- Если просили ЗАДАТЬ вопрос — Нейра должна ЗАДАТЬ его, а не спрашивать "какой вопрос?"
- Если просили ЧТО-ТО СДЕЛАТЬ — должен быть результат, а не описание

Формат:
ВЕРДИКТ: ПРИНЯТ / ДОРАБОТАТЬ / ОТКЛОНЁН
ОЦЕНКА: 1-10
ПРОБЛЕМЫ: <конкретно что не так>
КОММЕНТАРИЙ: <пояснение>"""

    def process(self, request: str, answer: str) -> CellResult:
        prompt = f"Запрос: {request}\n\nОтвет: {answer}\n\nПроверка:"
        result = self.call_llm(prompt, with_memory=False)
        
        if "ПРИНЯТ" in result:
            confidence = 0.9
        elif "ДОРАБОТАТЬ" in result:
            confidence = 0.5
        else:
            confidence = 0.3
            
        return CellResult(content=result, confidence=confidence, cell_name=self.name)


# === КЛЕТКА ИЗВЛЕЧЕНИЯ ФАКТОВ ===
class FactExtractorCell(Cell):
    name = "fact_extractor"
    system_prompt = """Извлеки факты для запоминания.

Категории: instruction, fact, preference, learned

JSON формат:
{"facts": [{"text": "факт", "category": "тип", "importance": 0.0-1.0}]}

Если нет фактов: {"facts": []}
ТОЛЬКО JSON."""

    def process(self, user_input: str, response: str, 
                source: str = "conversation") -> List[dict]:
        prompt = f"Диалог:\nЮзер: {user_input}\nОтвет: {response}\n\nФакты:"
        result = self.call_llm(prompt, with_memory=False, temperature=0.3)
        
        try:
            start = result.find("{")
            end = result.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(result[start:end])
                facts = data.get("facts", [])
                for fact in facts:
                    fact["source"] = source
                return facts
        except:
            pass
        return []


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def get_model_status() -> Dict[str, Any]:
    """Проверить статус моделей в Ollama (v0.5)"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        models = response.json().get("models", [])
        model_names = [m.get("name", "") for m in models]

        # Проверяем доступность облачных моделей
        cloud_code_ready = MODEL_CLOUD_CODE in model_names or any(MODEL_CLOUD_CODE in m for m in model_names)
        cloud_universal_ready = MODEL_CLOUD_UNIVERSAL in model_names or any(MODEL_CLOUD_UNIVERSAL in m for m in model_names)
        cloud_vision_ready = MODEL_CLOUD_VISION in model_names or any(MODEL_CLOUD_VISION in m for m in model_names)

        return {
            "ollama_running": True,
            "models": model_names,
            "code_model_ready": MODEL_CODE in model_names or f"{MODEL_CODE}:latest" in model_names,
            "reason_model_ready": MODEL_REASON in model_names or f"{MODEL_REASON}:latest" in model_names,
            "personality_model_ready": MODEL_PERSONALITY in model_names or f"{MODEL_PERSONALITY}:latest" in model_names,
            "embed_model_ready": EMBED_MODEL in model_names or f"{EMBED_MODEL}:latest" in model_names,
            "cloud_code_ready": cloud_code_ready,
            "cloud_universal_ready": cloud_universal_ready,
            "cloud_vision_ready": cloud_vision_ready
        }
    except:
        return {
            "ollama_running": False,
            "models": [],
            "code_model_ready": False,
            "reason_model_ready": False,
            "personality_model_ready": False,
            "embed_model_ready": False,
            "cloud_code_ready": False,
            "cloud_universal_ready": False,
            "cloud_vision_ready": False
        }


def ensure_models_installed():
    """Проверить и предложить установить модели (v0.5)"""
    status = get_model_status()

    if not status["ollama_running"]:
        print("❌ Ollama не запущена! Запусти: ollama serve")
        return False

    missing = []
    if not status["code_model_ready"]:
        missing.append(f"ollama pull {MODEL_CODE}")
    if not status["reason_model_ready"]:
        missing.append(f"ollama pull {MODEL_REASON}")
    if not status["embed_model_ready"]:
        missing.append(f"ollama pull {EMBED_MODEL}")

    if missing:
        print("⚠️ Не хватает моделей. Выполни:")
        for cmd in missing:
            print(f"   {cmd}")
        print("\n💡 Облачная модель (опционально): export GROQ_API_KEY=your_key")
        return False

    models_str = f"{MODEL_CODE}, {MODEL_REASON}"
    if status["personality_model_ready"]:
        models_str += f", {MODEL_PERSONALITY}"

    # Облачные модели
    cloud_models = []
    if status["cloud_code_ready"]:
        cloud_models.append("code-cloud(480B)")
    if status["cloud_universal_ready"]:
        cloud_models.append("universal-cloud(671B)")
    if status["cloud_vision_ready"]:
        cloud_models.append("vision-cloud(235B)")

    if cloud_models:
        models_str += f", облачные: {', '.join(cloud_models)}"

    print(f"✅ Модели готовы: {models_str}")
    return True
