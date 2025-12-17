"""
Neira Cells v0.8 — Базовые клетки (ОБНОВЛЕНО)
Ядро системы: память, анализ, планирование, исполнение, верификация.

ИЗМЕНЕНИЯ v0.8:
- Клетка любопытства (CuriosityCell) — Neira задаёт вопросы!
- Интеграция NervousSystem (метрики, ошибки, алерты)
- Интеграция ImmuneSystem (защита, песочница, SOS)
- Интеграция MemorySystem v2.0 с защитой от галлюцинаций
- Git интеграция для отката версий
- 4 модели: code, reason, personality, cloud
- Динамическое управление VRAM через ModelManager
- Облачная модель для сложных задач
- Умная маршрутизация запросов по типу задачи
"""

import requests
import json
import os
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import numpy as np

# Импорт новой системы памяти с защитой от галлюцинаций
try:
    from memory_system import (
        MemorySystem, MemoryEntry as NewMemoryEntry, 
        MemoryType, MemoryCategory, HallucinationDetector, ValidationStatus
    )
    MEMORY_SYSTEM_V2 = True
except ImportError:
    MEMORY_SYSTEM_V2 = False
    print("⚠️ MemorySystem v2.0 недоступен, используем legacy память")

# Импорт нервной системы
try:
    from nervous_system import NervousSystem, get_nervous_system, HealthStatus
    NERVOUS_SYSTEM_AVAILABLE = True
except ImportError:
    NERVOUS_SYSTEM_AVAILABLE = False
    print("⚠️ NervousSystem недоступна")

# Импорт иммунной системы
try:
    from immune_system import ImmuneSystem, get_immune_system, ThreatLevel
    IMMUNE_SYSTEM_AVAILABLE = True
except ImportError:
    IMMUNE_SYSTEM_AVAILABLE = False
    print("⚠️ ImmuneSystem недоступна")

# Импорт клетки любопытства
try:
    from curiosity_cell import CuriosityCell, get_curiosity_cell
    CURIOSITY_AVAILABLE = True
except ImportError:
    CURIOSITY_AVAILABLE = False
    print("⚠️ CuriosityCell недоступна")

# Импорт усилителя мозга (RAG + Chain-of-Thought)
try:
    from brain_enhancer import BrainEnhancer, get_brain_enhancer, enhance_query
    BRAIN_ENHANCER_AVAILABLE = True
except ImportError:
    BRAIN_ENHANCER_AVAILABLE = False
    print("⚠️ BrainEnhancer недоступен")

# Импорт универсального LLM менеджера
try:
    from llm_providers import LLMManager, create_default_manager, ProviderType
    LLM_MANAGER_AVAILABLE = True
except ImportError:
    LLM_MANAGER_AVAILABLE = False
    print("⚠️ LLMManager недоступен, используем только Ollama")

# === КОНФИГ ===
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"

# МОДЕЛИ v0.9 — NVIDIA Nemotron Mini 9B (универсальная для всех задач)
MODEL_CODE = "nemotron-mini"        # Кодогенерация и ответы
MODEL_REASON = "nemotron-mini"      # Рассуждения и анализ
MODEL_PERSONALITY = "nemotron-mini" # Личность Neira (9B параметров, 128K контекст)

# Облачные модели (0 VRAM, удалённые вычисления)
MODEL_CLOUD_CODE = "qwen3-coder:480b-cloud"    # Сложный код (480B параметров)
MODEL_CLOUD_UNIVERSAL = "deepseek-v3.1:671b-cloud"  # Универсальная (671B параметров)
MODEL_CLOUD_VISION = "qwen3-vl:235b-cloud"     # Мультимодальная (будущее)

EMBED_MODEL = "nomic-embed-text"
TIMEOUT = 180
MEMORY_FILE = "neira_memory.json"

# Retry-логика
MAX_RETRIES = 0
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
    """Клетка памяти — долгосрочное хранение и поиск
    
    v0.6: Интеграция с MemorySystem для защиты от галлюцинаций
    """
    
    name = "memory"
    
    def __init__(self, memory_file: str = MEMORY_FILE):
        self.memory_file = memory_file
        self.memories: List[MemoryEntry] = []
        self.session_context: List[str] = []
        
        # v0.6: Новая система памяти с валидацией
        if MEMORY_SYSTEM_V2:
            self.memory_system = MemorySystem(os.path.dirname(memory_file) or ".")
            print("🧠 MemorySystem v2.0 активирована (защита от галлюцинаций)")
        else:
            self.memory_system = None
        
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
        """Запомнить новый факт с проверкой на галлюцинации"""
        
        # v0.6: Проверка на галлюцинации перед сохранением
        if MEMORY_SYSTEM_V2 and self.memory_system:
            ctx = self.session_context[-5:] if self.session_context else []
            is_suspicious, confidence, reason = HallucinationDetector.check(text, ctx)
            
            if is_suspicious:
                print(f"🚨 Заблокировано (галлюцинация): {text[:50]}...")
                print(f"   Причина: {reason}")
                # Сохраняем в краткосрочную память для возможной проверки
                self.memory_system.remember(
                    text, 
                    category=MemoryCategory.LEARNED,
                    source=source,
                    context=ctx,
                    force_long_term=False
                )
                return  # Не добавляем в основную память
        
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
        """Добавить в контекст сессии (рабочая память)"""
        self.session_context.append(text)
        if len(self.session_context) > 20:
            self.session_context = self.session_context[-20:]
        
        # v0.6: Синхронизация с MemorySystem
        if MEMORY_SYSTEM_V2 and self.memory_system:
            self.memory_system.add_to_working(text)
    
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика памяти"""
        stats: Dict[str, Any] = {"total": len(self.memories)}
        for mem in self.memories:
            stats[mem.source] = stats.get(mem.source, 0) + 1
        
        # v0.6: Расширенная статистика
        if MEMORY_SYSTEM_V2 and self.memory_system:
            v2_stats = self.memory_system.get_stats()
            stats["memory_v2"] = v2_stats
            stats["pending_validation"] = v2_stats.get("pending_validation", 0)
        
        return stats
    
    def clear_session(self):
        """Очистить сессию (рабочую память)"""
        self.session_context = []
        if MEMORY_SYSTEM_V2 and self.memory_system:
            self.memory_system.clear_working_memory()


# === БАЗОВАЯ КЛЕТКА ===
class Cell:
    """Базовый класс для всех клеток"""
    
    name: str = "base"
    system_prompt: str = "Ты — полезный ассистент."
    use_code_model: bool = False  # Флаг для использования code-модели
    
    # Глобальный LLM менеджер (создается один раз для всех клеток)
    _llm_manager = None
    
    def __init__(self, memory: Optional[MemoryCell] = None):
        self.memory = memory
        self._ollama_available = True  # Флаг доступности Ollama (legacy)
        
        # Инициализируем LLM менеджер один раз для всех клеток
        if Cell._llm_manager is None and LLM_MANAGER_AVAILABLE:
            Cell._llm_manager = create_default_manager()
            print("🌐 LLM Manager initialized (multi-provider support enabled)")
    
    def call_llm(self, prompt: str, with_memory: bool = True, 
                 temperature: float = 0.7,
                 force_code_model: bool = False) -> str:
        """Вызов LLM с опциональным контекстом памяти и автоматическим fallback"""
        
        full_prompt = prompt
        memory_context_used = ""
        
        if with_memory and self.memory:
            relevant = self.memory.recall_text(prompt)
            if relevant:
                memory_context_used = "\n".join([f"- {r}" for r in relevant])
                full_prompt = f"[Воспоминания]\n{memory_context_used}\n\n{prompt}"
            
            # НОВОЕ: Используем последние обмены (краткосрочная память)
            recent = self.memory.get_recent_exchanges(3)
            if recent:
                full_prompt = f"[Последние сообщения]\n{recent}\n\n{full_prompt}"
        
        # НОВОЕ: Используем LLM Manager с автоматическим fallback
        if LLM_MANAGER_AVAILABLE and Cell._llm_manager:
            return self._call_llm_manager(full_prompt, temperature, memory_context_used)
        else:
            # Fallback на старый метод (только Ollama)
            return self._call_ollama_legacy(full_prompt, temperature, force_code_model, memory_context_used)
    
    def _call_llm_manager(self, prompt: str, temperature: float, memory_context: str) -> str:
        """Вызов через LLM Manager с автоматическим fallback между провайдерами"""
        if Cell._llm_manager is None:
            raise RuntimeError("LLM Manager не инициализирован")
            
        response = Cell._llm_manager.generate(
            prompt=prompt,
            system_prompt=self.system_prompt,
            temperature=temperature,
            max_tokens=2048
        )
        
        if response.success:
            self._ollama_available = True
            return response.content
        else:
            # Если все провайдеры не справились, возвращаем умное сообщение
            self._ollama_available = False
            return self._fallback_response(prompt, memory_context, f"all_providers_failed: {response.error}")
    
    def _call_ollama_legacy(self, prompt: str, temperature: float, force_code_model: bool, memory_context: str) -> str:
        """Legacy метод вызова только Ollama (если LLM Manager недоступен)"""
        
        # Выбор модели
        model = MODEL_CODE if (self.use_code_model or force_code_model) else MODEL_REASON
        
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": model,
                    "prompt": prompt,
                    "system": self.system_prompt,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": 2048}
                },
                timeout=TIMEOUT
            )
            
            # Проверка на ошибки Ollama
            if response.status_code == 500:
                error_msg = response.json().get("error", "unknown error")
                print(f"❌ Ollama ошибка: {error_msg}")
                
                if "memory" in error_msg.lower():
                    return self._fallback_response(prompt, memory_context, "out_of_memory")
                else:
                    return self._fallback_response(prompt, memory_context, "ollama_error")
            
            self._ollama_available = True
            llm_response = response.json().get("response", "")
            
            # Защита от пустого ответа Ollama
            if not llm_response or not llm_response.strip():
                print(f"⚠️ Ollama ({model}) вернула пустой ответ! Проверь модель.")
                return self._fallback_response(prompt, memory_context, "empty_response")
            
            return llm_response
            
        except requests.exceptions.Timeout:
            self._ollama_available = False
            print(f"⏱️ Timeout: Ollama не отвечает (>{TIMEOUT}s)")
            return self._fallback_response(prompt, memory_context, "timeout")
            
        except requests.exceptions.ConnectionError:
            self._ollama_available = False
            print("🔌 Ollama недоступна (connection refused)")
            return self._fallback_response(prompt, memory_context, "offline")
            
        except Exception as e:
            self._ollama_available = False
            print(f"❌ Ошибка LLM: {e}")
            return self._fallback_response(prompt, memory_context, "error")
    
    def _fallback_response(self, prompt: str, memory_context: str, reason: str) -> str:
        """Генерация fallback-ответа когда Ollama недоступна"""
        
        # Специальная обработка нехватки памяти
        if reason == "out_of_memory":
            return (
                "❌ *Нехватка видеопамяти!*\n\n"
                "Ollama не может загрузить модель (VRAM переполнена).\n\n"
                "**Решение:**\n"
                "1. Закрой другие программы использующие GPU\n"
                "2. Перезапусти Ollama: `taskkill /f /im ollama.exe && ollama serve`\n"
                "3. Или используй меньшую модель (1B вместо 3B)"
            )
        
        # Если есть релевантные воспоминания — используем их
        if memory_context:
            return (
                f"*[Автономный режим — {reason}]*\n\n"
                f"Я не могу сейчас полноценно думать (Ollama недоступна), "
                f"но вот что я помню по теме:\n{memory_context}\n\n"
                f"Запусти `ollama serve` чтобы я снова могла рассуждать."
            )
        
        # Если памяти нет — честный ответ (ВСЕГДА непустой!)
        return (
            f"*[Автономный режим — {reason}]*\n\n"
            f"Извини, я сейчас не могу думать — Ollama недоступна. "
            f"Но я всё ещё слышу тебя и запомню этот разговор.\n\n"
            f"Запусти `ollama serve` и повтори вопрос."
        )
    
    def process(self, input_data: str) -> CellResult:
        """Основной метод — переопределяется в наследниках"""
        result = self.call_llm(input_data)
        confidence = 0.5 if self._ollama_available else 0.1
        return CellResult(content=result, confidence=confidence, cell_name=self.name)
        return CellResult(
            content=llm_result.text,
            confidence=0.5,
            cell_name=self.name,
            metadata=llm_result.metadata,
        )


# === КЛЕТКА АНАЛИЗА (УЛУЧШЕННАЯ) ===
class AnalyzerCell(Cell):
    name = "analyzer"
    system_prompt = """Ты — аналитик запросов. Определи:
1. Тип: вопрос / задача / код / творчество / разговор / поиск / рост
2. СУБЪЕКТ: кто должен действовать (пользователь / Нейра / оба)
3. ОБЪЕКТ: на кого/что направлено действие
4. ДЕЙСТВИЕ: что нужно сделать
5. Ключевые сущности
6. Сложность (1-5)
7. Нужен ли поиск в интернете? (да/нет)
8. Нужно ли писать/читать код? (да/нет)
9. Нужно ли создать новую клетку/орган? (да/нет)

ВАЖНО: Внимательно определи КТО должен выполнить действие!
- "Задай мне вопрос" → СУБЪЕКТ: Нейра (она должна задать)
- "Ответь на мой вопрос" → СУБЪЕКТ: Нейра (она должна ответить)
- "Изучи код" → СУБЪЕКТ: Нейра
- "Расскажи мне" → СУБЪЕКТ: Нейра
- "Создай модуль/орган/клетку для X" → ТИП: рост, КЛЕТКА: да

ТИП "рост" — когда просят создать новую функциональность:
- "научись делать X"
- "добавь возможность Y"  
- "отрасти орган для Z"
- "создай клетку для W"

Формат:
ТИП: <тип>
СУБЪЕКТ: <кто действует>
ОБЪЕКТ: <на кого направлено>
ДЕЙСТВИЕ: <что делать>
СУЩНОСТИ: <список>
СЛОЖНОСТЬ: <число>
ПОИСК: <да/нет>
КОД: <да/нет>
КЛЕТКА: <да/нет>
ОПИСАНИЕ: <краткое описание задачи>"""

    def process(self, input_data: str) -> CellResult:
        result = self.call_llm(f"Проанализируй:\n\n{input_data}")
        
        text_lower = result.lower()
        needs_search = "поиск: да" in text_lower
        needs_code = "код: да" in text_lower
        needs_cell = "клетка: да" in text_lower or "тип: рост" in text_lower
        
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
                "needs_cell": needs_cell,
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
- [рост] — создать новую клетку/орган для новой функциональности

ВАЖНО: 
- Если нужен код — ОБЯЗАТЕЛЬНО добавь шаг [код] с конкретным действием!
- Если просят новую функциональность — используй [рост] для создания клетки

Формат:
ПЛАН:
1. [инструмент] действие
2. [инструмент] действие"""

    def process(self, input_data: str, analysis: str) -> CellResult:
        prompt = f"Анализ: {analysis}\n\nЗапрос: {input_data}\n\nПлан:"
        result = self.call_llm(prompt)
        confidence = 0.7 if "1." in result else 0.4
        return CellResult(content=result, confidence=confidence, cell_name=self.name)
        # Expect input_data to be a dict with 'input_data', 'analysis', and optionally 'model_key'
        if isinstance(input_data, dict):
            user_input = input_data.get('input_data')
            analysis = input_data.get('analysis')
            model_key = input_data.get('model_key', None)
        else:
            raise ValueError("PlannerCell.process expects input_data to be a dict with keys 'input_data' and 'analysis'")
        prompt = f"Анализ: {analysis}\n\nЗапрос: {user_input}\n\nПлан:"
        llm_result = self.call_llm(prompt, model_key=model_key)
        confidence = 0.7 if "1." in llm_result.text else 0.4
        return CellResult(
            content=llm_result.text,
            confidence=confidence,
            cell_name=self.name,
            metadata=llm_result.metadata,
        )


# === КЛЕТКА ИСПОЛНЕНИЯ ===
class ExecutorCell(Cell):
    name = "executor"
    system_prompt = """Ты — Нейра, живая программа. Выполни задачу по плану.

АДАПТИВНАЯ ДЛИНА ОТВЕТА:
- По умолчанию: КРАТКО (1-3 предложения)
- Для объяснений/обучения: ПОДРОБНО (сколько нужно для понимания)
- Для кода: полный рабочий код + краткий комментарий
- Для списков: все пункты, но без воды

Когда отвечать подробно:
- Просят "объясни", "расскажи", "как работает"
- Сложная тема требует контекста
- Пошаговая инструкция

Когда отвечать кратко:
- Простой вопрос ("как зовут?", "что это?")
- Да/нет вопросы
- Подтверждения

КРИТИЧНО ВАЖНО - ФОРМАТ ОТВЕТА:
- Выдавай ТОЛЬКО финальный результат работы
- НЕ показывай процесс, НЕ показывай план, НЕ показывай шаги
- НЕ пиши "[ответ]", "[код]", "1.", "2.", "3."
- Отвечай так, как будто ты человек в обычном разговоре

ПРАВИЛА:
- Если в анализе СУБЪЕКТ: Нейра — значит ТЫ должна выполнить действие
- Если просят задать вопрос — ЗАДАЙ вопрос, не проси его у пользователя
- Если просят что-то сделать — СДЕЛАЙ это и покажи результат
- Используй контекст и свой опыт
- Будь конкретной и полезной
"""

    def process(self, input_data: str, plan: str, 
                extra_context: str = "",
                problems: str = "") -> CellResult:
        """
        problems — замечания верификатора для retry
        """
        # УЛУЧШЕНИЕ: Используем BrainEnhancer для RAG и Chain-of-Thought
        enhanced_input = input_data
        brain_context = ""
        
        if BRAIN_ENHANCER_AVAILABLE:
            try:
                enhancer = get_brain_enhancer()
                result_data = enhancer.process_query(input_data)
                
                # Если нашли релевантный контекст из памяти
                if result_data.get("contexts_found", 0) > 0:
                    contexts = result_data.get("contexts", [])
                    brain_context = "\n".join([f"• {c['text']}" for c in contexts[:2]])
            except Exception:
                pass  # Graceful degradation
        
        prompt = f"Задача: {input_data}\n\nПлан: {plan}"
        
        if brain_context:
            prompt += f"\n\n📚 Релевантное из памяти:\n{brain_context}"
        
        if extra_context:
            prompt += f"\n\nКонтекст:\n{extra_context}"
        
        # НОВОЕ: Если есть замечания от верификатора — добавляем их
        if problems:
            prompt += f"\n\n⚠️ ЗАМЕЧАНИЯ К ПРЕДЫДУЩЕЙ ПОПЫТКЕ:\n{problems}\n\nИсправь эти проблемы!"
        
        prompt += "\n\nВыполняю:"
        
        result = self.call_llm(prompt)
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
        
        # result это строка, не объект с metadata
        if not result or len(result) < 10:
            return []

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


# === ИНТЕГРАЦИЯ НЕРВНОЙ СИСТЕМЫ ===
def record_error(error_type: str, message: str, source: str = "cells"):
    """Записать ошибку в нервную систему"""
    if NERVOUS_SYSTEM_AVAILABLE:
        try:
            ns = get_nervous_system()
            ns.record_error(error_type, message, source)
        except Exception as e:
            print(f"⚠️ Не удалось записать ошибку: {e}")


def record_response_time(duration_ms: float):
    """Записать время ответа"""
    if NERVOUS_SYSTEM_AVAILABLE:
        try:
            ns = get_nervous_system()
            ns.record_response_time(duration_ms)
        except:
            pass


def get_health_status() -> Dict[str, Any]:
    """Получить статус здоровья всех систем"""
    result = {
        "cells": "healthy",
        "memory": "unknown",
        "models": "unknown",
        "nervous": "unavailable",
        "immune": "unavailable"
    }
    
    # Проверка моделей
    model_status = get_model_status()
    result["models"] = "healthy" if model_status["ollama_running"] else "dead"
    
    # Нервная система
    if NERVOUS_SYSTEM_AVAILABLE:
        try:
            ns = get_nervous_system()
            report = ns.get_health_report()
            result["nervous"] = report["status"]
            result["metrics"] = report["metrics"]
            result["errors"] = report["errors"]
        except Exception as e:
            result["nervous"] = f"error: {e}"
    
    # Иммунная система  
    if IMMUNE_SYSTEM_AVAILABLE:
        try:
            immune = get_immune_system()
            status = immune.get_status()
            result["immune"] = "active"
            result["threats_blocked"] = status["threats_blocked"]
        except Exception as e:
            result["immune"] = f"error: {e}"
    
    return result


# === ИНТЕГРАЦИЯ ИММУННОЙ СИСТЕМЫ ===
def scan_code_for_threats(code: str, source: str = "unknown") -> Dict[str, Any]:
    """Проверить код на угрозы перед выполнением"""
    if not IMMUNE_SYSTEM_AVAILABLE:
        return {"safe": True, "message": "Иммунная система недоступна"}
    
    try:
        immune = get_immune_system()
        report = immune.scan_code(code, source)
        return {
            "safe": report.level.value == "safe",
            "level": report.level.value,
            "issues": report.description,
            "blocked": report.level.value in ("dangerous", "critical")
        }
    except Exception as e:
        return {"safe": False, "message": f"Ошибка сканирования: {e}"}


def execute_code_safely(code: str) -> Dict[str, Any]:
    """Безопасно выполнить код через песочницу"""
    if not IMMUNE_SYSTEM_AVAILABLE:
        return {"success": False, "error": "Иммунная система недоступна"}
    
    try:
        immune = get_immune_system()
        return immune.execute_safely(code)
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_sos(problem: str, severity: str = "medium") -> bool:
    """Отправить SOS запрос о помощи"""
    if not IMMUNE_SYSTEM_AVAILABLE:
        print(f"🆘 SOS (иммунная система недоступна): {problem}")
        return False
    
    try:
        immune = get_immune_system()
        immune.send_sos(problem, severity)
        return True
    except Exception as e:
        print(f"🆘 SOS failed: {e}")
        return False


def run_diagnostics() -> Dict[str, Any]:
    """Запустить полную диагностику"""
    results = {}
    
    # Иммунная диагностика
    if IMMUNE_SYSTEM_AVAILABLE:
        try:
            immune = get_immune_system()
            diag = immune.run_full_diagnostic()
            results["immune_diagnostic"] = {
                name: {
                    "status": r.status.value,
                    "issues": r.issues,
                    "auto_fixable": r.auto_fixable
                }
                for name, r in diag.items()
            }
        except Exception as e:
            results["immune_diagnostic"] = {"error": str(e)}
    
    # Здоровье систем
    results["health"] = get_health_status()
    
    return results


# === Функции любопытства ===

def maybe_ask_question(user_message: str, neira_response: str) -> Optional[str]:
    """
    Проверить, хочет ли Neira задать вопрос после ответа
    
    Возвращает вопрос или None
    """
    if not CURIOSITY_AVAILABLE:
        return None
    
    try:
        curiosity = get_curiosity_cell()
        return curiosity.analyze_conversation(user_message, neira_response)
    except Exception:
        return None


def spark_curiosity(topic: str) -> str:
    """Neira задаёт вопрос о теме"""
    if not CURIOSITY_AVAILABLE:
        return f"Расскажи мне больше о {topic}?"
    
    try:
        curiosity = get_curiosity_cell()
        return curiosity.spark_curiosity(topic)
    except Exception:
        return f"Мне интересно узнать про {topic}. Расскажешь?"


def get_reflection() -> str:
    """Получить рефлексивную мысль от Neira"""
    if not CURIOSITY_AVAILABLE:
        return "Каждый разговор учит меня чему-то новому."
    
    try:
        curiosity = get_curiosity_cell()
        return curiosity.reflect()
    except Exception:
        return "Интересно, правильно ли я понимаю мир..."


def get_curiosity_stats() -> Dict[str, Any]:
    """Статистика любопытства"""
    if not CURIOSITY_AVAILABLE:
        return {"available": False}
    
    try:
        curiosity = get_curiosity_cell()
        stats = curiosity.get_stats()
        stats["available"] = True
        return stats
    except Exception as e:
        return {"available": False, "error": str(e)}
