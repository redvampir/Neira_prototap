#!/usr/bin/env python3
"""
Система памяти Нейры v2.0

Разделённая архитектура памяти:
- Рабочая память (Working Memory) - текущий контекст диалога
- Краткосрочная память (Short-Term Memory) - сессия, очищается при перезапуске
- Долгосрочная память (Long-Term Memory) - постоянная, с валидацией
- Эпизодическая память (Episodic Memory) - события и взаимодействия
- Семантическая память (Semantic Memory) - факты и знания

Защита от галлюцинаций:
- Валидация перед записью в долгосрочную память
- Оценка достоверности (confidence score)
- Источник информации (source tracking)
- Периодическая консолидация памяти

ROADMAP v2.2:
- [x] Базовая архитектура памяти
- [x] Детектор галлюцинаций
- [x] Интеграция с cells.py
- [x] Семантический поиск по эмбеддингам
- [x] Decay (забывание неиспользуемых записей)
- [x] Автоматическая категоризация
- [x] Проверка противоречий
- [x] Связи между записями
- [x] Контекстный recall в промпт
- [x] Boost confidence по использованию
"""

import json
import os
import math


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default

try:
    import numpy as np  # type: ignore
    _NUMPY_AVAILABLE = True
except Exception:
    np = None  # type: ignore
    _NUMPY_AVAILABLE = False
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import hashlib
import re

# Импорт универсального LLM менеджера для embeddings
try:
    from llm_providers import LLMManager, create_default_manager
    LLM_MANAGER_AVAILABLE = True
except ImportError:
    LLM_MANAGER_AVAILABLE = False
    print("⚠️ LLMManager недоступен, используем legacy Ollama embeddings")

try:
    from local_embeddings import get_local_embedding
    LOCAL_EMBEDDINGS_AVAILABLE = True
except ImportError:
    LOCAL_EMBEDDINGS_AVAILABLE = False

OLLAMA_DISABLED = _env_bool("NEIRA_DISABLE_OLLAMA", False)

# Импорт защитных модулей v3.0
try:
    from memory_anomaly_detector import MemoryAnomalyDetector
    from memory_version_control import MemoryVersionControl
    PROTECTION_MODULES_AVAILABLE = True
except ImportError:
    PROTECTION_MODULES_AVAILABLE = False
    print("⚠️ Защитные модули памяти недоступны")

# Legacy конфиг для эмбеддингов (fallback)
OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"


class MemoryType(Enum):
    """Типы памяти"""
    WORKING = "working"          # Текущий контекст (до 10 сообщений)
    SHORT_TERM = "short_term"    # Сессия (до 100 записей)
    LONG_TERM = "long_term"      # Постоянная память
    EPISODIC = "episodic"        # События
    SEMANTIC = "semantic"        # Факты и знания


class MemoryCategory(Enum):
    """Категории воспоминаний"""
    FACT = "fact"                # Проверенный факт
    INSTRUCTION = "instruction"  # Инструкция от пользователя
    PREFERENCE = "preference"    # Предпочтение пользователя
    LEARNED = "learned"          # Изученное (требует проверки)
    PERSON = "person"            # Информация о человеке
    EVENT = "event"              # Событие
    CONVERSATION = "conversation" # Контекст разговора


class ValidationStatus(Enum):
    """Статус валидации"""
    PENDING = "pending"          # Ожидает проверки
    VALIDATED = "validated"      # Проверено и подтверждено
    REJECTED = "rejected"        # Отклонено как галлюцинация
    USER_CONFIRMED = "user_confirmed"  # Подтверждено пользователем


@dataclass
class MemoryEntry:
    """Запись в памяти"""
    id: str
    text: str
    memory_type: str
    category: str
    timestamp: str
    
    # Метаданные валидации
    confidence: float = 0.5      # 0.0-1.0, уверенность в достоверности
    validation_status: str = "pending"
    source: str = "conversation" # Откуда пришла информация
    
    # Связи
    related_ids: List[str] = field(default_factory=list)
    context_hash: str = ""       # Хэш контекста для отслеживания
    
    # Эмбеддинг (опционально)
    embedding: Optional[List[float]] = None
    
    # Статистика использования
    access_count: int = 0
    last_accessed: Optional[str] = None
    
    # v0.7: Пометка важных записей
    pinned: bool = False         # Защита от удаления
    tags: List[str] = field(default_factory=list)  # Пользовательские теги
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryEntry':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class HallucinationDetector:
    """Детектор галлюцинаций"""
    
    # Паттерны, характерные для галлюцинаций
    SUSPICIOUS_PATTERNS = [
        r'\$\d+',                           # Денежные суммы без контекста
        r'прибыль|доход|заработ',           # Финансовые галлюцинации
        r'продаж[аи]? (мощност|ресурс)',    # Продажа абстракций
        r'\d+ (секунд|минут|час)',          # Точные временные метрики без основания
        r'игр[аы]? (требует|включает)',     # Игровые механики
        r'ход (может|включает)',            # Пошаговые действия
        r'цена (модели|мощности)',          # Ценообразование галлюцинаций
        r'победитель|выигр',                # Игровая терминология
    ]
    
    # Слова-маркеры галлюцинаций (если 1+ найден - подозрительно)
    HALLUCINATION_MARKERS = [
        'кость', 'мощность', 'тариф', 'прибыль', 
        'продажа мощност', 'вычислительн'
    ]
    
    # Критические маркеры (один найден = блокировка)
    CRITICAL_MARKERS = ['кость']
    
    @classmethod
    def check(cls, text: str, context: Optional[List[str]] = None) -> Tuple[bool, float, str]:
        """
        Проверяет текст на галлюцинации
        
        Returns:
            (is_suspicious, confidence, reason)
        """
        text_lower = text.lower()
        
        # Проверка критических маркеров (одиночных)
        for marker in cls.CRITICAL_MARKERS:
            if marker in text_lower:
                return True, 0.2, f"Критический маркер галлюцинации: {marker}"
        # Проверка паттернов
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, text_lower):
                return True, 0.3, f"Подозрительный паттерн: {pattern}"
        
        # Проверка маркеров
        marker_count = sum(1 for m in cls.HALLUCINATION_MARKERS if m in text_lower)
        if marker_count >= 2:
            return True, 0.2, f"Множественные маркеры галлюцинаций: {marker_count}"
        
        # Проверка на самоссылки без контекста
        if context:
            # Если текст ссылается на несуществующие факты
            pass  # TODO: более сложная проверка контекста
        
        return False, 0.7, "OK"


class SemanticSearch:
    """Семантический поиск по памяти с использованием эмбеддингов"""
    
    # Глобальный менеджер (создается один раз)
    _llm_manager: Optional[Any] = None
    
    @classmethod
    def _get_manager(cls) -> Optional[Any]:
        """Ленивая инициализация LLM Manager"""
        if not LLM_MANAGER_AVAILABLE:
            return None
        if cls._llm_manager is None:
            cls._llm_manager = create_default_manager()
        return cls._llm_manager
    
    @staticmethod
    def get_embedding(text: str) -> Optional[List[float]]:
        """Получает эмбеддинг текста через LLM Manager (или fallback на Ollama)"""
        # Сначала пробуем через LLM Manager
        if not text or not text.strip():
            return None
        if LOCAL_EMBEDDINGS_AVAILABLE:
            try:
                local_embedding = get_local_embedding(text)
                if local_embedding:
                    return local_embedding
            except Exception as e:
                print(f"Local embedding error: {e}")
        manager = SemanticSearch._get_manager()
        if manager:
            try:
                embedding = manager.get_embedding(text)
                if embedding:
                    return embedding
            except Exception as e:
                print(f"⚠️ LLMManager embedding error: {e}, trying legacy Ollama")
        
        if OLLAMA_DISABLED:
            return None
        # Fallback на прямой вызов Ollama
        try:
            import requests
            response = requests.post(
                OLLAMA_EMBED_URL,
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("embedding", [])
        except Exception as e:
            print(f"⚠️ Legacy Ollama embedding error: {e}")
        
        return None
    
    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Косинусное сходство между векторами"""
        if not a or not b:
            return 0.0
        if _NUMPY_AVAILABLE and np is not None:
            a_np = np.array(a)
            b_np = np.array(b)
            dot = np.dot(a_np, b_np)
            norm = np.linalg.norm(a_np) * np.linalg.norm(b_np)
            return float(dot / (norm + 1e-8))

        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for x, y in zip(a, b):
            dot += float(x) * float(y)
            norm_a += float(x) * float(x)
            norm_b += float(y) * float(y)
        return float(dot / (math.sqrt(norm_a) * math.sqrt(norm_b) + 1e-8))
    
    @classmethod
    def search(cls, query: str, entries: List['MemoryEntry'], 
               top_k: int = 5, threshold: float = 0.3) -> List[Tuple['MemoryEntry', float]]:
        """
        Семантический поиск по записям памяти
        
        Returns:
            Список кортежей (запись, score) отсортированный по релевантности
        """
        query_embedding = cls.get_embedding(query)
        if not query_embedding:
            return []
        
        scored = []
        for entry in entries:
            if entry.embedding:
                score = cls.cosine_similarity(query_embedding, entry.embedding)
                if score >= threshold:
                    scored.append((entry, score))
        
        # Сортируем по score (убывание)
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]


class MemoryDecay:
    """Система забывания неиспользуемых воспоминаний"""
    
    # Настройки decay
    DECAY_RATE = 0.05           # Снижение confidence за период
    DECAY_PERIOD_DAYS = 7       # Период в днях
    MIN_CONFIDENCE = 0.1        # Минимальный confidence перед удалением
    PROTECTED_CATEGORIES = [    # Категории, защищённые от забывания
        MemoryCategory.INSTRUCTION.value,
        MemoryCategory.PERSON.value,
        MemoryCategory.FACT.value,
    ]
    
    @classmethod
    def apply_decay(cls, entries: List['MemoryEntry']) -> Tuple[List['MemoryEntry'], List['MemoryEntry']]:
        """
        Применяет decay к записям памяти
        
        Returns:
            (kept_entries, forgotten_entries)
        """
        now = datetime.now()
        kept = []
        forgotten = []
        
        for entry in entries:
            # Защищённые категории не забываем
            if entry.category in cls.PROTECTED_CATEGORIES:
                kept.append(entry)
                continue
            
            # Подтверждённые пользователем не забываем
            if entry.validation_status == ValidationStatus.USER_CONFIRMED.value:
                kept.append(entry)
                continue
            
            # Вычисляем время с последнего доступа
            last_access = entry.last_accessed or entry.timestamp
            try:
                last_dt = datetime.fromisoformat(last_access)
                days_since = (now - last_dt).days
            except:
                days_since = 0
            
            # Применяем decay
            periods = days_since // cls.DECAY_PERIOD_DAYS
            if periods > 0 and entry.access_count < 3:
                # Снижаем confidence только если редко используется
                new_confidence = entry.confidence - (cls.DECAY_RATE * periods)
                entry.confidence = max(new_confidence, 0.0)
            
            # Забываем если confidence слишком низкий
            if entry.confidence < cls.MIN_CONFIDENCE:
                forgotten.append(entry)
            else:
                kept.append(entry)
        
        return kept, forgotten


class AutoCategorizer:
    """Автоматическая категоризация записей памяти"""
    
    # Паттерны для категорий
    PATTERNS = {
        MemoryCategory.PERSON.value: [
            r'^[А-ЯA-Z][а-яa-z]+\s+(—|-)?\s*(это|является|создатель|автор|друг|знакомый)',
            r'(он|она|его|её|ему)\s+(любит|работает|живёт|нравится)',
            r'(зовут|имя)\s+[А-ЯA-Z][а-яa-z]+',
        ],
        MemoryCategory.INSTRUCTION.value: [
            r'^(не\s+)?(делай|говори|используй|отвечай|пиши|называй)',
            r'(должн[аы]?|нужно|надо|следует)\s+',
            r'(всегда|никогда)\s+(делай|говори|используй)',
        ],
        MemoryCategory.PREFERENCE.value: [
            r'(люблю|нравится|предпочита|хочу|хотел бы)',
            r'(не\s+люблю|не\s+нравится|ненавижу)',
            r'(любим|мо[йяё]\s+любим)',
        ],
        MemoryCategory.EVENT.value: [
            r'(вчера|сегодня|завтра|недавно)\s+',
            r'\d{1,2}[./]\d{1,2}[./]\d{2,4}',
            r'(произошло|случилось|было|будет)',
        ],
        MemoryCategory.FACT.value: [
            r'^[А-ЯA-Z].+\s+(—|это|является)\s+',
            r'(версия|версии)\s+\d+',
        ],
    }
    
    @classmethod
    def categorize(cls, text: str) -> str:
        """
        Определяет категорию текста
        
        Returns:
            Строка категории (MemoryCategory value)
        """
        text_lower = text.lower()
        
        for category, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return category
        
        # По умолчанию - conversation
        return MemoryCategory.CONVERSATION.value


class ContradictionDetector:
    """
    v2.2: Детектор противоречий в памяти
    
    Проверяет новую информацию на конфликты с существующей.
    """
    
    # Антонимы и противоположные понятия
    ANTONYMS = {
        'любит': ['ненавидит', 'не любит', 'терпеть не может'],
        'нравится': ['не нравится', 'раздражает', 'бесит'],
        'хочет': ['не хочет', 'отказывается'],
        'умеет': ['не умеет', 'не может'],
        'знает': ['не знает', 'не в курсе'],
        'использует': ['не использует', 'избегает'],
        'работает': ['не работает', 'сломан'],
        'да': ['нет'],
        'true': ['false'],
        'включён': ['выключен', 'отключён'],
        'активен': ['неактивен', 'отключён'],
    }
    
    # Паттерны для извлечения субъекта и предиката
    SUBJECT_PATTERNS = [
        r'^([А-ЯA-Z][а-яa-z]+)\s+(—|это|является|любит|ненавидит|хочет|умеет|знает|использует)',
        r'^(Нейра|Павел|Создатель)\s+',
    ]
    
    @classmethod
    def extract_subject(cls, text: str) -> Optional[str]:
        """Извлекает субъект из текста"""
        for pattern in cls.SUBJECT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).lower()
        return None
    
    @classmethod
    def check_contradiction(cls, new_text: str, existing_entries: List['MemoryEntry'],
                           similarity_threshold: float = 0.7) -> Tuple[bool, Optional['MemoryEntry'], str]:
        """
        Проверяет противоречит ли новый текст существующим записям
        
        Returns:
            (is_contradiction, conflicting_entry, reason)
        """
        new_lower = new_text.lower()
        new_subject = cls.extract_subject(new_text)
        
        # Ищем записи с тем же субъектом
        for entry in existing_entries:
            entry_lower = entry.text.lower()
            entry_subject = cls.extract_subject(entry.text)
            
            # Проверяем только если субъекты совпадают
            if new_subject and entry_subject and new_subject == entry_subject:
                
                # Проверка прямых противоречий через антонимы
                for word, antonyms in cls.ANTONYMS.items():
                    # Новый текст содержит слово, старый - антоним
                    if word in new_lower:
                        for ant in antonyms:
                            if ant in entry_lower:
                                return True, entry, f"Противоречие: '{word}' vs '{ant}'"
                    
                    # Или наоборот
                    if word in entry_lower:
                        for ant in antonyms:
                            if ant in new_lower:
                                return True, entry, f"Противоречие: '{word}' vs '{ant}'"
                
                # Проверка семантического сходства (похожие фразы с разным смыслом)
                # Используем эмбеддинги если оба текста про одно
                if entry.embedding:
                    new_embedding = SemanticSearch.get_embedding(new_text)
                    if new_embedding:
                        similarity = SemanticSearch.cosine_similarity(new_embedding, entry.embedding)
                        
                        # Высокое сходство но разные утверждения - возможное противоречие
                        if similarity > similarity_threshold:
                            # Проверяем отрицания
                            new_has_neg = any(neg in new_lower for neg in ['не ', 'нет', 'никогда', 'ни'])
                            old_has_neg = any(neg in entry_lower for neg in ['не ', 'нет', 'никогда', 'ни'])
                            
                            if new_has_neg != old_has_neg:
                                return True, entry, f"Похожие темы, разные утверждения (similarity={similarity:.2f})"
        
        return False, None, "OK"
    
    @classmethod
    def find_related(cls, text: str, entries: List['MemoryEntry'], 
                    top_k: int = 3) -> List['MemoryEntry']:
        """Находит связанные записи (для проверки или связывания)"""
        subject = cls.extract_subject(text)
        if not subject:
            return []
        
        related = []
        for entry in entries:
            entry_subject = cls.extract_subject(entry.text)
            if entry_subject and entry_subject == subject:
                related.append(entry)
        
        return related[:top_k]


class MemorySystem:
    """Система управления памятью Нейры"""
    
    def __init__(self, base_path: str = "."):
        self.base_path = base_path
        
        # Пути к файлам памяти
        self.paths = {
            MemoryType.LONG_TERM: os.path.join(base_path, "neira_memory.json"),
            MemoryType.SHORT_TERM: os.path.join(base_path, "neira_short_term.json"),
            MemoryType.EPISODIC: os.path.join(base_path, "neira_episodic.json"),
            MemoryType.SEMANTIC: os.path.join(base_path, "neira_semantic.json"),
        }
        
        # Память в RAM
        self.working_memory: List[MemoryEntry] = []  # Текущий контекст
        self.short_term: List[MemoryEntry] = []      # Сессия
        self.long_term: List[MemoryEntry] = []       # Постоянная
        self.episodic: List[MemoryEntry] = []        # События
        self.semantic: List[MemoryEntry] = []        # Знания
        
        # Настройки
        self.working_memory_size = 10    # Последние N сообщений
        self.short_term_size = 100       # Максимум в краткосрочной
        self.consolidation_threshold = 3  # Сколько раз нужно подтвердить для перехода в долгосрочную
        
        # 🛡️ ЗАЩИТА ОТ ПЕРЕПОЛНЕНИЯ v2.4
        self.max_long_term = 1000        # Максимум долгосрочных записей
        self.max_semantic = 500          # Максимум семантических знаний
        self.max_episodic = 300          # Максимум эпизодов
        self.min_confidence_keep = 0.3   # Минимальная уверенность для сохранения
        self.auto_cleanup_enabled = True # Автоматическая очистка
        
        # 🛡️ ЗАЩИТА v3.0: Детектор аномалий и версионирование
        if PROTECTION_MODULES_AVAILABLE:
            self.anomaly_detector = MemoryAnomalyDetector(window_size=20)
            self.version_control = MemoryVersionControl(
                snapshots_dir=os.path.join(base_path, "memory_snapshots")
            )
            print("✅ Защитные модули памяти активированы")
        else:
            self.anomaly_detector = None
            self.version_control = None
        
        # Загрузка
        self._load_all()
        
        # Применить лимиты при загрузке
        if self.auto_cleanup_enabled:
            self._apply_limits(auto_snapshot=True)
    
    def _generate_id(self, text: str) -> str:
        """Генерирует уникальный ID для записи"""
        content = f"{text}{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Вычисляет схожесть двух текстов по словам (Jaccard similarity)"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _load_all(self):
        """Загружает все типы памяти"""
        self.long_term = self._load_memory(MemoryType.LONG_TERM)
        self.short_term = self._load_memory(MemoryType.SHORT_TERM)
        self.episodic = self._load_memory(MemoryType.EPISODIC)
        self.semantic = self._load_memory(MemoryType.SEMANTIC)
    
    def _load_memory(self, memory_type: MemoryType) -> List[MemoryEntry]:
        """Загружает память из файла"""
        path = self.paths.get(memory_type)
        if not path or not os.path.exists(path):
            return []
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Конвертируем старый формат если нужно
            entries = []
            for item in data:
                if isinstance(item, dict):
                    # Добавляем недостающие поля
                    if 'id' not in item:
                        item['id'] = self._generate_id(item.get('text', ''))
                    if 'memory_type' not in item:
                        item['memory_type'] = memory_type.value
                    if 'validation_status' not in item:
                        item['validation_status'] = ValidationStatus.PENDING.value
                    if 'confidence' not in item:
                        item['confidence'] = 0.5
                    
                    entries.append(MemoryEntry.from_dict(item))
            
            return entries
        except Exception as e:
            print(f"⚠️ Ошибка загрузки {memory_type.value}: {e}")
            return []
    
    def _apply_limits(self, auto_snapshot: bool = False):
        """
        🛡️ Применяет лимиты памяти для защиты от переполнения
        Вызывается автоматически при загрузке и периодически
        
        Args:
            auto_snapshot: Создать snapshot перед очисткой (v3.0)
        """
        # v3.0: Создаём snapshot перед очисткой
        if auto_snapshot and self.version_control:
            try:
                self.version_control.create_snapshot(
                    [asdict(m) for m in self.long_term],
                    message="Auto-snapshot before cleanup"
                )
            except Exception as e:
                print(f"⚠️ Ошибка создания snapshot: {e}")
        
        initial_counts = {
            'long_term': len(self.long_term),
            'short_term': len(self.short_term),
            'semantic': len(self.semantic),
            'episodic': len(self.episodic)
        }
        
        # 1. Краткосрочная память - оставляем только последние N
        if len(self.short_term) > self.short_term_size:
            self.short_term = self.short_term[-self.short_term_size:]
        
        # 2. Долгосрочная память - топ по уверенности + свежести
        if len(self.long_term) > self.max_long_term:
            # Удаляем записи с низкой уверенностью
            self.long_term = [
                m for m in self.long_term 
                if m.confidence >= self.min_confidence_keep
            ]
            
            # Если всё ещё много - сортируем по важности и берём топ
            if len(self.long_term) > self.max_long_term:
                self.long_term = sorted(
                    self.long_term,
                    key=lambda x: (x.confidence, x.access_count, x.timestamp),
                    reverse=True
                )[:self.max_long_term]
        
        # 3. Семантическая память - только важные знания
        if len(self.semantic) > self.max_semantic:
            self.semantic = sorted(
                self.semantic,
                key=lambda x: (x.confidence, x.access_count),
                reverse=True
            )[:self.max_semantic]
        
        # 4. Эпизодическая память - последние события
        if len(self.episodic) > self.max_episodic:
            self.episodic = sorted(
                self.episodic,
                key=lambda x: x.timestamp,
                reverse=True
            )[:self.max_episodic]
        
        # Сохраняем если были изменения
        final_counts = {
            'long_term': len(self.long_term),
            'short_term': len(self.short_term),
            'semantic': len(self.semantic),
            'episodic': len(self.episodic)
        }
        
        if initial_counts != final_counts:
            removed = sum(initial_counts.values()) - sum(final_counts.values())
            # Тихо сохраняем без вывода
            self._save_memory(MemoryType.LONG_TERM, self.long_term)
            self._save_memory(MemoryType.SHORT_TERM, self.short_term)
            self._save_memory(MemoryType.SEMANTIC, self.semantic)
            self._save_memory(MemoryType.EPISODIC, self.episodic)
    
    def _save_memory(self, memory_type: MemoryType, entries: List[MemoryEntry]):
        """Сохраняет память в файл"""
        path = self.paths.get(memory_type)
        if not path:
            return
        
        try:
            data = [e.to_dict() for e in entries]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения {memory_type.value}: {e}")
    
    def remember(self, 
                 text: str, 
                 category: Optional[MemoryCategory] = None,
                 source: str = "conversation",
                 context: Optional[List[str]] = None,
                 force_long_term: bool = False,
                 auto_embed: bool = True) -> Optional[MemoryEntry]:
        """
        Запоминает информацию
        
        По умолчанию идёт в краткосрочную память.
        В долгосрочную - только после валидации или явного подтверждения.
        
        v2.1: Добавлены автокатегоризация и эмбеддинги
        v2.3: Защита от зацикливания - проверка дубликатов
        """
        # v2.3: Проверка на дубликаты (защита от зацикливания)
        text_normalized = text.strip().lower()
        
        # Проверяем последние 50 записей на точные дубликаты
        recent_memories = (self.short_term[-50:] if len(self.short_term) > 50 else self.short_term) + \
                         (self.long_term[-50:] if len(self.long_term) > 50 else self.long_term)
        
        for existing in recent_memories:
            if existing.text.strip().lower() == text_normalized:
                # Точный дубликат найден - обновляем счетчик доступа
                existing.access_count += 1
                existing.last_accessed = datetime.now().isoformat()
                print(f"⚠️ Дубликат обнаружен, пропускаем: {text[:50]}...")
                return existing  # Возвращаем существующую запись
        
        # Проверяем частоту похожих записей (защита от спама)
        similar_count = 0
        time_window = datetime.now() - timedelta(minutes=5)
        
        for existing in recent_memories:
            # Проверяем записи за последние 5 минут
            try:
                entry_time = datetime.fromisoformat(existing.timestamp)
                if entry_time > time_window:
                    # Проверяем на похожесть (>80% совпадение слов)
                    similarity = self._calculate_text_similarity(text, existing.text)
                    if similarity > 0.8:
                        similar_count += 1
            except:
                pass
        
        # Если больше 5 похожих записей за 5 минут - зацикливание
        if similar_count > 5:
            print(f"🚨 ЗАЦИКЛИВАНИЕ ОБНАРУЖЕНО! Пропускаем запись: {text[:50]}...")
            print(f"   Найдено {similar_count} похожих записей за последние 5 минут")
            return None
        
        # v3.0: Проверка аномалий ПЕРЕД записью
        if self.anomaly_detector:
            anomaly_report = self.anomaly_detector.check(text)
            if anomaly_report.is_anomaly:
                print(f"🚫 АНОМАЛИЯ ЗАБЛОКИРОВАНА: {anomaly_report.reason}")
                for suggestion in anomaly_report.suggestions:
                    print(f"   • {suggestion}")
                return None  # Блокируем запись
        
        # Проверка на галлюцинации
        is_suspicious, confidence, reason = HallucinationDetector.check(text, context)
        
        if is_suspicious:
            print(f"⚠️ Подозрение на галлюцинацию: {reason}")
            print(f"   Текст: {text[:100]}...")
            confidence = min(confidence, 0.3)
        
        # v2.2: Проверка противоречий с существующей памятью
        if not is_suspicious:
            is_contradiction, conflict, contra_reason = ContradictionDetector.check_contradiction(
                text, self.long_term + self.short_term
            )
            if is_contradiction and conflict:
                print(f"⚠️ Обнаружено противоречие: {contra_reason}")
                print(f"   Новое: {text[:60]}...")
                print(f"   Старое: {conflict.text[:60]}...")
                # Не блокируем, но снижаем confidence и помечаем
                confidence = min(confidence, 0.4)
                is_suspicious = True  # Помечаем как требующее проверки
        
        # v2.1: Автоматическая категоризация если не указана
        if category is None:
            auto_category = AutoCategorizer.categorize(text)
            category_value = auto_category
        else:
            category_value = category.value
        
        # v2.1: Получаем эмбеддинг для семантического поиска
        embedding = None
        if auto_embed:
            embedding = SemanticSearch.get_embedding(text)
        
        # v2.2: Находим связанные записи
        related = ContradictionDetector.find_related(text, self.long_term)
        related_ids = [r.id for r in related[:5]]
        
        # Создаём запись
        entry = MemoryEntry(
            id=self._generate_id(text),
            text=text,
            memory_type=MemoryType.SHORT_TERM.value,
            category=category_value,
            timestamp=datetime.now().isoformat(),
            confidence=confidence,
            validation_status=ValidationStatus.PENDING.value if is_suspicious else ValidationStatus.VALIDATED.value,
            source=source,
            context_hash=hashlib.md5(''.join(context or []).encode()).hexdigest()[:8],
            embedding=embedding,
            related_ids=related_ids  # v2.2: связи
        )
        
        # Решаем куда сохранять
        if force_long_term and not is_suspicious:
            entry.memory_type = MemoryType.LONG_TERM.value
            entry.validation_status = ValidationStatus.USER_CONFIRMED.value
            self.long_term.append(entry)
            self._save_memory(MemoryType.LONG_TERM, self.long_term)
            print(f"💾 Сохранено в долгосрочную память: {text[:50]}...")
        else:
            self.short_term.append(entry)
            # Ограничиваем размер краткосрочной памяти
            if len(self.short_term) > self.short_term_size:
                self._consolidate_short_term()
            self._save_memory(MemoryType.SHORT_TERM, self.short_term)
            print(f"📝 Сохранено в краткосрочную память: {text[:50]}...")
        
        # 🛡️ Проверяем лимиты после каждых 10 новых записей
        total_memories = len(self.long_term) + len(self.short_term) + len(self.semantic)
        if self.auto_cleanup_enabled and total_memories % 10 == 0:
            self._apply_limits()
        
        return entry
    
    def add_to_working(self, text: str, role: str = "user"):
        """Добавляет сообщение в рабочую память (контекст диалога)"""
        entry = MemoryEntry(
            id=self._generate_id(text),
            text=text,
            memory_type=MemoryType.WORKING.value,
            category=role,
            timestamp=datetime.now().isoformat(),
            confidence=1.0,  # Рабочая память всегда достоверна
            validation_status=ValidationStatus.VALIDATED.value,
            source="dialog"
        )
        
        self.working_memory.append(entry)
        
        # Ограничиваем размер
        if len(self.working_memory) > self.working_memory_size:
            self.working_memory = self.working_memory[-self.working_memory_size:]
    
    def get_context(self) -> str:
        """Возвращает контекст для промпта"""
        context_parts = []
        
        # Рабочая память (последние сообщения)
        if self.working_memory:
            context_parts.append("=== Текущий диалог ===")
            for entry in self.working_memory[-5:]:
                context_parts.append(f"[{entry.category}]: {entry.text}")
        
        # Релевантные долгосрочные воспоминания
        # TODO: поиск по семантическому сходству
        
        return "\n".join(context_parts)
    
    def get_contextual_recall(self, current_message: str, max_memories: int = 5) -> str:
        """
        v2.2: Контекстный recall — автоматически подгружает релевантные воспоминания
        
        Args:
            current_message: Текущее сообщение пользователя
            max_memories: Максимум воспоминаний для включения
            
        Returns:
            Форматированный контекст с релевантными воспоминаниями
        """
        context_parts = []
        
        # 1. Рабочая память (последние сообщения диалога)
        if self.working_memory:
            context_parts.append("=== Текущий диалог ===")
            for entry in self.working_memory[-5:]:
                context_parts.append(f"[{entry.category}]: {entry.text}")
        
        # 2. Семантический поиск по текущему сообщению
        relevant = self.semantic_search(current_message, top_k=max_memories, threshold=0.4)
        
        if relevant:
            context_parts.append("\n=== Релевантные воспоминания ===")
            for entry, score in relevant:
                # Показываем категорию и confidence
                conf_icon = "🟢" if entry.confidence > 0.7 else "🟡" if entry.confidence > 0.4 else "🔴"
                context_parts.append(f"{conf_icon} [{entry.category}] {entry.text}")
        
        # 3. Важные инструкции (всегда включаем)
        instructions = [e for e in self.long_term 
                       if e.category == MemoryCategory.INSTRUCTION.value 
                       and e.confidence > 0.5]
        
        if instructions:
            context_parts.append("\n=== Инструкции ===")
            for entry in instructions[:3]:  # Максимум 3 инструкции
                context_parts.append(f"📌 {entry.text}")
        
        return "\n".join(context_parts)
    
    def _consolidate_short_term(self):
        """Консолидация краткосрочной памяти в долгосрочную"""
        print("🔄 Консолидация памяти...")
        
        validated = []
        rejected = []
        
        for entry in self.short_term:
            # Проверяем статус валидации
            if entry.validation_status == ValidationStatus.VALIDATED.value:
                if entry.confidence >= 0.6:
                    entry.memory_type = MemoryType.LONG_TERM.value
                    validated.append(entry)
                else:
                    rejected.append(entry)
            elif entry.validation_status == ValidationStatus.USER_CONFIRMED.value:
                entry.memory_type = MemoryType.LONG_TERM.value
                validated.append(entry)
            else:
                # Подозрительные записи удаляются
                rejected.append(entry)
        
        # Переносим в долгосрочную
        self.long_term.extend(validated)
        self._save_memory(MemoryType.LONG_TERM, self.long_term)
        
        # Очищаем краткосрочную
        self.short_term = []
        self._save_memory(MemoryType.SHORT_TERM, self.short_term)
        
        print(f"✅ Консолидировано: {len(validated)} записей")
        print(f"🗑️ Отклонено: {len(rejected)} записей")
    
    def confirm_memory(self, memory_id: str) -> bool:
        """Подтверждает запись пользователем"""
        for entry in self.short_term:
            if entry.id == memory_id:
                entry.validation_status = ValidationStatus.USER_CONFIRMED.value
                entry.confidence = 1.0
                self._save_memory(MemoryType.SHORT_TERM, self.short_term)
                return True
        return False
    
    def reject_memory(self, memory_id: str) -> bool:
        """Отклоняет запись как галлюцинацию"""
        for entry in self.short_term:
            if entry.id == memory_id:
                entry.validation_status = ValidationStatus.REJECTED.value
                entry.confidence = 0.0
                self._save_memory(MemoryType.SHORT_TERM, self.short_term)
                return True
        return False
    
    def search(self, query: str, memory_types: Optional[List[MemoryType]] = None) -> List[MemoryEntry]:
        """Поиск по памяти"""
        results = []
        query_lower = query.lower()
        
        memories_to_search = []
        if not memory_types:
            memory_types = [MemoryType.LONG_TERM, MemoryType.SHORT_TERM]
        
        for mt in memory_types:
            if mt == MemoryType.LONG_TERM:
                memories_to_search.extend(self.long_term)
            elif mt == MemoryType.SHORT_TERM:
                memories_to_search.extend(self.short_term)
            elif mt == MemoryType.WORKING:
                memories_to_search.extend(self.working_memory)
        
        for entry in memories_to_search:
            if query_lower in entry.text.lower():
                results.append(entry)
        
        return results
    
    def semantic_search(self, query: str, top_k: int = 5, 
                        memory_types: Optional[List[MemoryType]] = None,
                        threshold: float = 0.3) -> List[Tuple[MemoryEntry, float]]:
        """
        v2.1: Семантический поиск по памяти
        
        Returns:
            Список кортежей (запись, релевантность) отсортированный по релевантности
        """
        memories_to_search: List[MemoryEntry] = []
        
        if not memory_types:
            memory_types = [MemoryType.LONG_TERM, MemoryType.SHORT_TERM]
        
        for mt in memory_types:
            if mt == MemoryType.LONG_TERM:
                memories_to_search.extend(self.long_term)
            elif mt == MemoryType.SHORT_TERM:
                memories_to_search.extend(self.short_term)
            elif mt == MemoryType.WORKING:
                memories_to_search.extend(self.working_memory)
        
        # Используем SemanticSearch
        results = SemanticSearch.search(query, memories_to_search, top_k, threshold)
        
        # v2.2: Обновляем access_count и boost confidence для найденных записей
        now = datetime.now().isoformat()
        for entry, score in results:
            entry.access_count += 1
            entry.last_accessed = now
            # Boost confidence за использование (макс 1.0)
            if entry.confidence < 1.0:
                entry.confidence = min(1.0, entry.confidence + 0.02)
        
        # Сохраняем обновлённую статистику
        self._save_memory(MemoryType.LONG_TERM, self.long_term)
        
        return results
    
    def recall(self, query: str, top_k: int = 5) -> List[str]:
        """
        v2.1: Вспомнить релевантные факты (упрощённый интерфейс)
        
        Returns:
            Список текстов релевантных воспоминаний
        """
        results = self.semantic_search(query, top_k)
        return [entry.text for entry, score in results]
    
    def apply_decay(self) -> Dict[str, int]:
        """
        v2.1: Применяет забывание к долгосрочной памяти
        
        Returns:
            Статистика {kept: N, forgotten: N}
        """
        kept, forgotten = MemoryDecay.apply_decay(self.long_term)
        
        if forgotten:
            self.long_term = kept
            self._save_memory(MemoryType.LONG_TERM, self.long_term)
            print(f"🧹 Забыто {len(forgotten)} неиспользуемых записей")
        
        return {"kept": len(kept), "forgotten": len(forgotten)}
    
    def get_stats(self) -> Dict:
        """Статистика памяти"""
        return {
            "working_memory": len(self.working_memory),
            "short_term": len(self.short_term),
            "long_term": len(self.long_term),
            "episodic": len(self.episodic),
            "semantic": len(self.semantic),
            "total": (len(self.working_memory) + len(self.short_term) + 
                     len(self.long_term) + len(self.episodic) + len(self.semantic)),
            "pending_validation": sum(1 for e in self.short_term 
                                     if e.validation_status == ValidationStatus.PENDING.value)
        }
    
    def clear_working_memory(self):
        """Очищает рабочую память (новая сессия)"""
        self.working_memory = []
    
    def clear_short_term(self):
        """Очищает краткосрочную память"""
        self.short_term = []
        self._save_memory(MemoryType.SHORT_TERM, self.short_term)


# Тестирование
if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТ СИСТЕМЫ ПАМЯТИ НЕЙРЫ v2.2")
    print("=" * 60)
    
    memory = MemorySystem(".")
    
    # Статистика
    stats = memory.get_stats()
    print(f"\n📊 Статистика памяти:")
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Тест детектора галлюцинаций
    print(f"\n🔍 Тест детектора галлюцинаций:")
    test_texts = [
        "Павел любит программирование",
        "Продажа мощностей даёт $500 в час",
        "Нейра - это AI-ассистент",
    ]
    for text in test_texts:
        is_sus, conf, reason = HallucinationDetector.check(text)
        status = "🚨 BLOCKED" if is_sus else "✅ OK"
        print(f"   {status} [{conf:.1f}] {text[:40]}...")
    
    # v2.1: Тест автокатегоризации
    print(f"\n🏷️ Тест автокатегоризации:")
    categorize_tests = [
        "Павел — создатель Нейры",
        "Не используй эмодзи в ответах",
        "Мне нравится Python",
        "Вчера было обновление системы",
        "Нейра версии 0.6",
    ]
    for text in categorize_tests:
        cat = AutoCategorizer.categorize(text)
        print(f"   [{cat}] {text}")
    
    # v2.2: Тест детектора противоречий
    print(f"\n⚔️ Тест детектора противоречий:")
    contradiction_tests = [
        ("Павел любит Python", "Павел ненавидит Python"),
        ("Нейра умеет программировать", "Нейра не умеет программировать"),
        ("Система работает", "Система не работает"),
    ]
    for text1, text2 in contradiction_tests:
        # Создаём фейковую запись для теста
        fake_entry = MemoryEntry(
            id="test", text=text1, memory_type="long_term",
            category="fact", timestamp="2025-01-01", confidence=0.8
        )
        is_contra, _, reason = ContradictionDetector.check_contradiction(text2, [fake_entry])
        status = "⚠️ ПРОТИВОРЕЧИЕ" if is_contra else "✅ OK"
        print(f"   {status}: '{text1}' vs '{text2}'")
    
    # v2.1: Тест семантического поиска
    print(f"\n🔎 Тест семантического поиска:")
    results = memory.semantic_search("создатель", top_k=3)
    if results:
        for entry, score in results:
            print(f"   [{score:.2f}] {entry.text[:50]}...")
    else:
        print("   (нет результатов или Ollama недоступна)")
    
    # v2.2: Тест контекстного recall
    print(f"\n📚 Тест контекстного recall:")
    context = memory.get_contextual_recall("Кто создал Нейру?")
    print(context[:500] + "..." if len(context) > 500 else context)
    
    print("\n✅ Система памяти v2.2 готова к использованию!")


# ========== РАСШИРЕНИЯ ДЛЯ TELEGRAM BOT v0.7 ==========

class MemoryManager:
    """Менеджер для расширенного управления памятью через Telegram"""
    
    def __init__(self, memory_system: MemorySystem):
        self.memory = memory_system
    
    def search_by_text(self, query: str, case_sensitive: bool = False) -> List[MemoryEntry]:
        """Поиск записей содержащих текст"""
        results = []
        all_entries = (self.memory.long_term + self.memory.short_term + 
                      self.memory.episodic + self.memory.semantic)
        
        for entry in all_entries:
            text_to_search = entry.text if case_sensitive else entry.text.lower()
            search_query = query if case_sensitive else query.lower()
            
            if search_query in text_to_search:
                results.append(entry)
        
        return results
    
    def delete_by_text(self, query: str, case_sensitive: bool = False) -> int:
        """
        Удаляет записи содержащие текст (пропускает закреплённые)
        Returns: количество удалённых записей
        """
        # Защита от пустого запроса
        if not query or not query.strip():
            return 0
        
        count = 0
        
        # Нормализуем запрос ОДИН РАЗ (вне цикла для оптимизации)
        search_query = query.strip() if case_sensitive else query.strip().lower()
        
        # Проходим по всем типам памяти
        for memory_list in [self.memory.long_term, self.memory.short_term, 
                           self.memory.episodic, self.memory.semantic]:
            original_len = len(memory_list)
            
            # Фильтруем записи: удаляем только НЕзакреплённые записи с совпадением текста
            # Оставляем: закреплённые OR без совпадения текста
            memory_list[:] = [
                entry for entry in memory_list
                if (entry.pinned or  # Защита закреплённых
                    search_query not in (entry.text if case_sensitive else entry.text.lower()))
            ]
            
            # Считаем сколько удалили из этого списка
            deleted_from_list = original_len - len(memory_list)
            count += deleted_from_list
        
        # Сохраняем изменения в файлы
        if count > 0:
            self._save_all()
        
        return count
    
    def delete_last_n(self, n: int, memory_type: Optional[str] = None) -> int:
        """
        Удаляет последние N записей (пропускает закреплённые)
        
        Args:
            n: количество записей для удаления
            memory_type: тип памяти или None для всех
        
        Returns: количество удалённых записей
        """
        count = 0
        
        if memory_type:
            # Удаляем из конкретного типа
            memory_list = self._get_memory_list(memory_type)
            if memory_list:
                # Фильтруем незакреплённые
                unpinned = [e for e in memory_list if not e.pinned]
                removed = min(n, len(unpinned))
                
                # Удаляем последние N незакреплённых
                to_remove_set = set(unpinned[-removed:])
                memory_list[:] = [e for e in memory_list if e not in to_remove_set]
                count = removed
        else:
            # Удаляем из всех типов (сортируем по времени)
            all_entries = []
            for mtype in ["long_term", "short_term", "episodic", "semantic"]:
                mlist = self._get_memory_list(mtype)
                if mlist:  # Проверка на None
                    all_entries.extend([(entry, mtype) for entry in mlist if not entry.pinned])
            
            # Сортируем по времени (новые в конце)
            all_entries.sort(key=lambda x: x[0].timestamp)
            
            # Удаляем последние N
            to_remove = all_entries[-n:] if n < len(all_entries) else all_entries
            
            for entry, mtype in to_remove:
                mlist = self._get_memory_list(mtype)
                if mlist and entry in mlist:  # Проверка на None
                    mlist.remove(entry)
                    count += 1
        
        self._save_all()
        return count
    
    def delete_by_category(self, category: str) -> int:
        """Удаляет все записи определённой категории (пропускает закреплённые)"""
        count = 0
        
        for memory_list in [self.memory.long_term, self.memory.short_term,
                           self.memory.episodic, self.memory.semantic]:
            original_len = len(memory_list)
            memory_list[:] = [
                entry for entry in memory_list
                if entry.pinned or entry.category != category  # Защита закреплённых
            ]
            count += original_len - len(memory_list)
        
        self._save_all()
        return count
    
    def delete_old_entries(self, days: int) -> int:
        """Удаляет записи старше N дней (пропускает закреплённые)"""
        count = 0
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for memory_list in [self.memory.long_term, self.memory.short_term,
                           self.memory.episodic, self.memory.semantic]:
            original_len = len(memory_list)
            
            memory_list[:] = [
                entry for entry in memory_list
                if (entry.pinned or  # Защита закреплённых
                    datetime.fromisoformat(entry.timestamp) > cutoff_date)
            ]
            
            count += original_len - len(memory_list)
        
        self._save_all()
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить детальную статистику памяти"""
        stats = {
            "total": 0,
            "by_type": {},
            "by_category": {},
            "oldest": None,
            "newest": None,
            "average_confidence": 0.0,
        }
        
        all_entries = (self.memory.long_term + self.memory.short_term +
                      self.memory.episodic + self.memory.semantic)
        
        stats["total"] = len(all_entries)
        stats["by_type"]["long_term"] = len(self.memory.long_term)
        stats["by_type"]["short_term"] = len(self.memory.short_term)
        stats["by_type"]["episodic"] = len(self.memory.episodic)
        stats["by_type"]["semantic"] = len(self.memory.semantic)
        
        # Статистика по категориям
        for entry in all_entries:
            cat = entry.category or "uncategorized"
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        
        # Временные границы
        if all_entries:
            timestamps = [datetime.fromisoformat(e.timestamp) for e in all_entries]
            stats["oldest"] = min(timestamps).isoformat()
            stats["newest"] = max(timestamps).isoformat()
            
            # Средняя уверенность
            confidences = [e.confidence for e in all_entries if e.confidence]
            stats["average_confidence"] = sum(confidences) / len(confidences) if confidences else 0.0
        
        return stats
    
    def deduplicate(self, similarity_threshold: float = 0.95) -> int:
        """
        Удаляет дубликаты (записи с очень высокой схожестью)
        Returns: количество удалённых дубликатов
        """
        count = 0
        
        for memory_list in [self.memory.long_term, self.memory.short_term,
                           self.memory.episodic, self.memory.semantic]:
            seen_texts = set()
            unique_entries = []
            
            for entry in memory_list:
                text_normalized = entry.text.strip().lower()
                
                # Проверяем точные дубликаты
                if text_normalized not in seen_texts:
                    # Проверяем схожесть с уже добавленными
                    is_duplicate = False
                    for unique in unique_entries:
                        similarity = self.memory._calculate_text_similarity(
                            entry.text, unique.text
                        )
                        if similarity >= similarity_threshold:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        unique_entries.append(entry)
                        seen_texts.add(text_normalized)
                    else:
                        count += 1
                else:
                    count += 1
            
            memory_list[:] = unique_entries
        
        self._save_all()
        return count
    
    def create_backup(self, backup_name: Optional[str] = None) -> str:
        """Создаёт бэкап всей памяти"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = backup_name or f"memory_backup_{timestamp}"
        backup_dir = os.path.join(self.memory.base_path, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_path = os.path.join(backup_dir, f"{backup_name}.json")
        
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "stats": self.get_stats(),
            "long_term": [e.to_dict() for e in self.memory.long_term],
            "short_term": [e.to_dict() for e in self.memory.short_term],
            "episodic": [e.to_dict() for e in self.memory.episodic],
            "semantic": [e.to_dict() for e in self.memory.semantic],
        }
        
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        return backup_path
    
    def _get_memory_list(self, memory_type: str) -> Optional[List[MemoryEntry]]:
        """Получить список памяти по типу"""
        mapping = {
            "long_term": self.memory.long_term,
            "short_term": self.memory.short_term,
            "episodic": self.memory.episodic,
            "semantic": self.memory.semantic,
        }
        return mapping.get(memory_type)
    
    def _save_all(self):
        """Сохранить все типы памяти"""
        self.memory._save_memory(MemoryType.LONG_TERM, self.memory.long_term)
        self.memory._save_memory(MemoryType.SHORT_TERM, self.memory.short_term)
        self.memory._save_memory(MemoryType.EPISODIC, self.memory.episodic)
        self.memory._save_memory(MemoryType.SEMANTIC, self.memory.semantic)
    
    # ========== v0.7 РАСШИРЕНИЯ ==========
    
    def filter_by_confidence(self, operator: str, threshold: float) -> List[MemoryEntry]:
        """
        Фильтр по уровню уверенности
        
        Args:
            operator: '<', '>', '<=', '>=', '=='
            threshold: порог уверенности (0.0-1.0)
        """
        results = []
        all_entries = (self.memory.long_term + self.memory.short_term +
                      self.memory.episodic + self.memory.semantic)
        
        for entry in all_entries:
            conf = entry.confidence or 0.5
            
            if operator == '<' and conf < threshold:
                results.append(entry)
            elif operator == '>' and conf > threshold:
                results.append(entry)
            elif operator == '<=' and conf <= threshold:
                results.append(entry)
            elif operator == '>=' and conf >= threshold:
                results.append(entry)
            elif operator == '==' and abs(conf - threshold) < 0.01:
                results.append(entry)
        
        return results
    
    def filter_by_source(self, source: str) -> List[MemoryEntry]:
        """Фильтр по источнику информации"""
        results = []
        all_entries = (self.memory.long_term + self.memory.short_term +
                      self.memory.episodic + self.memory.semantic)
        
        for entry in all_entries:
            if entry.source == source:
                results.append(entry)
        
        return results
    
    def filter_by_timerange(self, hours: int) -> List[MemoryEntry]:
        """Фильтр по временному диапазону (последние N часов)"""
        results = []
        cutoff = datetime.now() - timedelta(hours=hours)
        
        all_entries = (self.memory.long_term + self.memory.short_term +
                      self.memory.episodic + self.memory.semantic)
        
        for entry in all_entries:
            try:
                entry_time = datetime.fromisoformat(entry.timestamp)
                if entry_time > cutoff:
                    results.append(entry)
            except:
                pass
        
        return results
    
    def pin_entry(self, entry_id: str) -> bool:
        """Закрепить запись (защита от удаления)"""
        all_lists = [self.memory.long_term, self.memory.short_term,
                    self.memory.episodic, self.memory.semantic]
        
        for memory_list in all_lists:
            for entry in memory_list:
                if entry.id == entry_id:
                    entry.pinned = True
                    self._save_all()
                    return True
        
        return False
    
    def unpin_entry(self, entry_id: str) -> bool:
        """Открепить запись"""
        all_lists = [self.memory.long_term, self.memory.short_term,
                    self.memory.episodic, self.memory.semantic]
        
        for memory_list in all_lists:
            for entry in memory_list:
                if entry.id == entry_id:
                    entry.pinned = False
                    self._save_all()
                    return True
        
        return False
    
    def get_pinned(self) -> List[MemoryEntry]:
        """Получить все закреплённые записи"""
        results = []
        all_entries = (self.memory.long_term + self.memory.short_term +
                      self.memory.episodic + self.memory.semantic)
        
        for entry in all_entries:
            if entry.pinned:
                results.append(entry)
        
        return results
    
    def add_tag(self, entry_id: str, tag: str) -> bool:
        """Добавить тег к записи"""
        all_lists = [self.memory.long_term, self.memory.short_term,
                    self.memory.episodic, self.memory.semantic]
        
        for memory_list in all_lists:
            for entry in memory_list:
                if entry.id == entry_id:
                    if tag not in entry.tags:
                        entry.tags.append(tag)
                        self._save_all()
                    return True
        
        return False
    
    def filter_by_tag(self, tag: str) -> List[MemoryEntry]:
        """Найти записи с определённым тегом"""
        results = []
        all_entries = (self.memory.long_term + self.memory.short_term +
                      self.memory.episodic + self.memory.semantic)
        
        for entry in all_entries:
            if tag in entry.tags:
                results.append(entry)
        
        return results
    
    def export_to_text(self, category: Optional[str] = None) -> str:
        """
        Экспорт памяти в читаемый текст
        
        Args:
            category: фильтр по категории (None = все)
        """
        all_entries = (self.memory.long_term + self.memory.short_term +
                      self.memory.episodic + self.memory.semantic)
        
        if category:
            all_entries = [e for e in all_entries if e.category == category]
        
        # Сортируем по времени
        all_entries.sort(key=lambda e: e.timestamp)
        
        lines = ["# Экспорт памяти Neira", f"# Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
        
        if category:
            lines.append(f"# Категория: {category}\n")
        
        for entry in all_entries:
            timestamp = datetime.fromisoformat(entry.timestamp).strftime("%Y-%m-%d %H:%M")
            pin_mark = "📌 " if entry.pinned else ""
            tags = f" [теги: {', '.join(entry.tags)}]" if entry.tags else ""
            
            lines.append(f"## {pin_mark}[{entry.category}] {timestamp}")
            lines.append(f"{entry.text}")
            lines.append(f"_Источник: {entry.source} | Уверенность: {entry.confidence:.0%}{tags}_")
            lines.append("")
        
        return "\n".join(lines)
    
    def restore_from_backup(self, backup_name: str) -> bool:
        """
        Восстановить память из бэкапа
        
        Args:
            backup_name: имя файла бэкапа (с .json или без)
        """
        if not backup_name.endswith('.json'):
            backup_name += '.json'
        
        backup_dir = os.path.join(self.memory.base_path, "backups")
        backup_path = os.path.join(backup_dir, backup_name)
        
        if not os.path.exists(backup_path):
            return False
        
        try:
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Восстанавливаем каждый тип памяти
            self.memory.long_term = [
                MemoryEntry.from_dict(e) for e in backup_data.get('long_term', [])
            ]
            self.memory.short_term = [
                MemoryEntry.from_dict(e) for e in backup_data.get('short_term', [])
            ]
            self.memory.episodic = [
                MemoryEntry.from_dict(e) for e in backup_data.get('episodic', [])
            ]
            self.memory.semantic = [
                MemoryEntry.from_dict(e) for e in backup_data.get('semantic', [])
            ]
            
            # Сохраняем
            self._save_all()
            return True
            
        except Exception as e:
            print(f"⚠️ Ошибка восстановления: {e}")
            return False
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """Получить список доступных бэкапов"""
        backup_dir = os.path.join(self.memory.base_path, "backups")
        if not os.path.exists(backup_dir):
            return []
        
        backups = []
        for filename in os.listdir(backup_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(backup_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    backups.append({
                        'filename': filename,
                        'timestamp': data.get('timestamp', 'unknown'),
                        'total': data.get('stats', {}).get('total', 0),
                        'size': os.path.getsize(filepath),
                    })
                except:
                    pass
        
        # Сортируем по времени (новые первые)
        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        return backups
    
    def semantic_search(self, query: str, top_k: int = 10) -> List[Tuple[MemoryEntry, float]]:
        """
        Семантический поиск через эмбеддинги (если доступна Ollama)
        
        Returns: список (запись, score) отсортированный по релевантности
        """
        all_entries = (self.memory.long_term + self.memory.short_term +
                      self.memory.episodic + self.memory.semantic)
        
        # Используем встроенный семантический поиск
        return SemanticSearch.search(query, all_entries, top_k=top_k)

