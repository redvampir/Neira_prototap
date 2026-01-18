"""
Memory Consolidation System — Система консолидации памяти Нейры.

Реализует механизм "сна" для:
- Переноса краткосрочной памяти в долгосрочную
- Усиления важных воспоминаний
- Ослабления неважных
- "Переигрывания" опыта для лучшего запоминания
- Очистки рабочей памяти

Основан на нейробиологии сна: replay, consolidation, forgetting.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
import json
import random
import math
import os
from pathlib import Path


class SleepPhase(Enum):
    """Фазы сна и их функции."""
    AWAKE = "awake"                    # Бодрствование
    LIGHT_SLEEP = "light_sleep"        # Лёгкий сон (N1-N2)
    DEEP_SLEEP = "deep_sleep"          # Глубокий сон (N3) - консолидация
    REM = "rem"                        # REM - творческая обработка
    MICRO_SLEEP = "micro_sleep"        # Микро-сон (быстрая консолидация)


class MemoryType(Enum):
    """Типы памяти."""
    WORKING = "working"         # Рабочая память (текущий контекст)
    SHORT_TERM = "short_term"   # Краткосрочная (часы)
    LONG_TERM = "long_term"     # Долгосрочная (дни+)
    CONSOLIDATED = "consolidated"  # Консолидированная (важная)


@dataclass
class MemoryTrace:
    """След памяти — единица воспоминания."""
    id: str
    content: str
    memory_type: str = "short_term"
    importance: float = 0.5      # Важность (0.0 - 1.0)
    emotional_valence: float = 0.0  # Эмоциональная окраска (-1.0 до 1.0)
    activation_count: int = 1    # Сколько раз вспоминали
    creation_time: str = ""
    last_access_time: str = ""
    consolidation_score: float = 0.0  # Уровень консолидации
    replay_count: int = 0        # Сколько раз "переиграли"
    associations: List[str] = field(default_factory=list)  # ID связанных воспоминаний
    tags: List[str] = field(default_factory=list)
    source: str = ""             # conversation, learning, insight, etc.
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "emotional_valence": self.emotional_valence,
            "activation_count": self.activation_count,
            "creation_time": self.creation_time,
            "last_access_time": self.last_access_time,
            "consolidation_score": self.consolidation_score,
            "replay_count": self.replay_count,
            "associations": self.associations,
            "tags": self.tags,
            "source": self.source
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MemoryTrace":
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=data.get("memory_type", "short_term"),
            importance=data.get("importance", 0.5),
            emotional_valence=data.get("emotional_valence", 0.0),
            activation_count=data.get("activation_count", 1),
            creation_time=data.get("creation_time", ""),
            last_access_time=data.get("last_access_time", ""),
            consolidation_score=data.get("consolidation_score", 0.0),
            replay_count=data.get("replay_count", 0),
            associations=data.get("associations", []),
            tags=data.get("tags", []),
            source=data.get("source", "")
        )


@dataclass
class ConsolidationSession:
    """Сессия консолидации (один "сон")."""
    id: str
    start_time: str
    end_time: str = ""
    phase: str = "awake"
    memories_processed: int = 0
    memories_consolidated: int = 0
    memories_forgotten: int = 0
    insights_generated: int = 0
    
    def duration_minutes(self) -> float:
        """Длительность сессии в минутах."""
        if not self.end_time:
            return 0
        try:
            start = datetime.fromisoformat(self.start_time)
            end = datetime.fromisoformat(self.end_time)
            return (end - start).total_seconds() / 60
        except:
            return 0


class MemoryConsolidation:
    """
    Система консолидации памяти.
    
    Реализует механизм "сна" для организации и укрепления памяти.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "memory_consolidation.json"
        
        # Память разных типов
        self.working_memory: List[MemoryTrace] = []  # Текущий контекст
        self.short_term_memory: List[MemoryTrace] = []  # Недавние
        self.long_term_memory: List[MemoryTrace] = []  # Долгосрочные
        
        # Текущее состояние
        self.current_phase = SleepPhase.AWAKE
        self.sessions: List[ConsolidationSession] = []
        
        # Настройки
        self.config = {
            "working_memory_capacity": 7,     # Магическое число Миллера
            "short_term_decay_hours": 24,     # Время затухания краткосрочной
            "consolidation_threshold": 0.6,   # Порог для консолидации
            "importance_for_auto_consolidate": 0.8,  # Авто-консолидация важного
            "emotional_boost": 1.5,           # Усиление эмоциональных воспоминаний
            "replay_boost": 0.1,              # Усиление за каждый replay
            "forgetting_threshold": 0.2,      # Порог для забывания
            "association_bonus": 0.05         # Бонус за каждую ассоциацию
        }
        
        self._load()
    
    def _load(self):
        """Загрузка состояния."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.working_memory = [
                    MemoryTrace.from_dict(m) for m in data.get("working_memory", [])
                ]
                self.short_term_memory = [
                    MemoryTrace.from_dict(m) for m in data.get("short_term_memory", [])
                ]
                self.long_term_memory = [
                    MemoryTrace.from_dict(m) for m in data.get("long_term_memory", [])
                ]
                
            except Exception as e:
                print(f"Ошибка загрузки MemoryConsolidation: {e}")
    
    def _save(self):
        """Сохранение состояния."""
        data = {
            "working_memory": [m.to_dict() for m in self.working_memory],
            "short_term_memory": [m.to_dict() for m in self.short_term_memory],
            "long_term_memory": [m.to_dict() for m in self.long_term_memory],
            "sessions": [
                {
                    "id": s.id,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "phase": s.phase,
                    "memories_processed": s.memories_processed,
                    "memories_consolidated": s.memories_consolidated,
                    "memories_forgotten": s.memories_forgotten,
                    "insights_generated": s.insights_generated
                }
                for s in self.sessions[-100:]  # Последние 100 сессий
            ]
        }
        
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_id(self) -> str:
        """Генерация уникального ID."""
        import hashlib
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:12]
    
    # ============= Добавление воспоминаний =============
    
    def add_to_working_memory(
        self,
        content: str,
        importance: float = 0.5,
        emotional_valence: float = 0.0,
        tags: List[str] = None,
        source: str = "input"
    ) -> MemoryTrace:
        """
        Добавить в рабочую память.
        
        Рабочая память ограничена (7±2 элементов).
        При переполнении — перенос в краткосрочную.
        """
        now = datetime.now().isoformat()
        
        memory = MemoryTrace(
            id=self._generate_id(),
            content=content,
            memory_type=MemoryType.WORKING.value,
            importance=importance,
            emotional_valence=emotional_valence,
            creation_time=now,
            last_access_time=now,
            tags=tags or [],
            source=source
        )
        
        self.working_memory.append(memory)
        
        # Если превысили capacity — переносим старые в short-term
        while len(self.working_memory) > self.config["working_memory_capacity"]:
            oldest = self.working_memory.pop(0)
            oldest.memory_type = MemoryType.SHORT_TERM.value
            self.short_term_memory.append(oldest)
        
        self._save()
        return memory
    
    def add_to_short_term(
        self,
        content: str,
        importance: float = 0.5,
        emotional_valence: float = 0.0,
        tags: List[str] = None,
        source: str = "conversation"
    ) -> MemoryTrace:
        """Добавить в краткосрочную память."""
        now = datetime.now().isoformat()
        
        memory = MemoryTrace(
            id=self._generate_id(),
            content=content,
            memory_type=MemoryType.SHORT_TERM.value,
            importance=importance,
            emotional_valence=emotional_valence,
            creation_time=now,
            last_access_time=now,
            tags=tags or [],
            source=source
        )
        
        self.short_term_memory.append(memory)
        
        # Авто-консолидация очень важных воспоминаний
        if importance >= self.config["importance_for_auto_consolidate"]:
            self._consolidate_memory(memory)
        
        self._save()
        return memory
    
    def recall(self, memory_id: str) -> Optional[MemoryTrace]:
        """
        Вспомнить воспоминание по ID.
        
        Увеличивает activation_count и обновляет last_access_time.
        """
        for memory_list in [self.working_memory, self.short_term_memory, self.long_term_memory]:
            for memory in memory_list:
                if memory.id == memory_id:
                    memory.activation_count += 1
                    memory.last_access_time = datetime.now().isoformat()
                    memory.consolidation_score = min(1.0, memory.consolidation_score + 0.05)
                    self._save()
                    return memory
        return None
    
    def find_by_content(self, query: str, limit: int = 5) -> List[MemoryTrace]:
        """Поиск воспоминаний по содержимому."""
        query_lower = query.lower()
        all_memories = self.working_memory + self.short_term_memory + self.long_term_memory
        
        matches = []
        for memory in all_memories:
            if query_lower in memory.content.lower():
                matches.append(memory)
        
        # Сортируем по importance и activation_count
        matches.sort(key=lambda m: m.importance * m.activation_count, reverse=True)
        
        # Обновляем access time для найденных
        for memory in matches[:limit]:
            memory.last_access_time = datetime.now().isoformat()
        
        return matches[:limit]
    
    def create_association(self, memory_id_1: str, memory_id_2: str):
        """Создать ассоциацию между двумя воспоминаниями."""
        memory_1 = self.recall(memory_id_1)
        memory_2 = self.recall(memory_id_2)
        
        if memory_1 and memory_2:
            if memory_id_2 not in memory_1.associations:
                memory_1.associations.append(memory_id_2)
            if memory_id_1 not in memory_2.associations:
                memory_2.associations.append(memory_id_1)
            self._save()
    
    # ============= Консолидация ("сон") =============
    
    def start_consolidation(self, phase: SleepPhase = SleepPhase.DEEP_SLEEP) -> ConsolidationSession:
        """
        Начать сессию консолидации.
        
        Разные фазы имеют разные функции:
        - DEEP_SLEEP: Консолидация декларативной памяти
        - REM: Творческая обработка, инсайты
        - MICRO_SLEEP: Быстрая консолидация
        """
        self.current_phase = phase
        
        session = ConsolidationSession(
            id=self._generate_id(),
            start_time=datetime.now().isoformat(),
            phase=phase.value
        )
        self.sessions.append(session)
        
        return session
    
    def run_consolidation_cycle(self) -> Dict[str, Any]:
        """
        Запустить полный цикл консолидации.
        
        Returns:
            Результаты консолидации
        """
        session = self.start_consolidation(SleepPhase.DEEP_SLEEP)
        
        results = {
            "consolidated": [],
            "forgotten": [],
            "strengthened": [],
            "insights": []
        }
        
        # 1. Обработка краткосрочной памяти
        for memory in self.short_term_memory[:]:
            session.memories_processed += 1
            
            # Вычисляем score для консолидации
            score = self._calculate_consolidation_score(memory)
            memory.consolidation_score = score
            
            if score >= self.config["consolidation_threshold"]:
                # Консолидируем
                self._consolidate_memory(memory)
                results["consolidated"].append(memory.id)
                session.memories_consolidated += 1
            
            elif score <= self.config["forgetting_threshold"]:
                # Забываем
                self.short_term_memory.remove(memory)
                results["forgotten"].append(memory.id)
                session.memories_forgotten += 1
        
        # 2. Replay долгосрочных воспоминаний
        for memory in random.sample(
            self.long_term_memory, 
            min(5, len(self.long_term_memory))
        ):
            self._replay_memory(memory)
            results["strengthened"].append(memory.id)
        
        # 3. Поиск паттернов (инсайты) — REM фаза
        self.current_phase = SleepPhase.REM
        session.phase = "rem"
        
        insights = self._generate_insights()
        results["insights"] = insights
        session.insights_generated = len(insights)
        
        # 4. Очистка рабочей памяти
        cleared = len(self.working_memory)
        for memory in self.working_memory:
            memory.memory_type = MemoryType.SHORT_TERM.value
            self.short_term_memory.append(memory)
        self.working_memory.clear()
        
        # Завершаем сессию
        self.current_phase = SleepPhase.AWAKE
        session.end_time = datetime.now().isoformat()
        
        self._save()
        
        return results
    
    def quick_consolidation(self) -> Dict[str, Any]:
        """
        Быстрая (микро) консолидация.
        
        Консолидирует только самые важные воспоминания.
        """
        session = self.start_consolidation(SleepPhase.MICRO_SLEEP)
        
        results = {"consolidated": []}
        
        # Только топ-3 по важности из краткосрочной
        important = sorted(
            self.short_term_memory,
            key=lambda m: m.importance * (1 + abs(m.emotional_valence)),
            reverse=True
        )[:3]
        
        for memory in important:
            if memory.consolidation_score < self.config["consolidation_threshold"]:
                memory.consolidation_score += 0.2
                memory.replay_count += 1
                results["consolidated"].append(memory.id)
                session.memories_consolidated += 1
        
        session.end_time = datetime.now().isoformat()
        self.current_phase = SleepPhase.AWAKE
        
        self._save()
        return results
    
    def _calculate_consolidation_score(self, memory: MemoryTrace) -> float:
        """Вычислить score консолидации для воспоминания."""
        score = memory.importance
        
        # Эмоциональное усиление
        emotional_factor = 1 + abs(memory.emotional_valence) * (self.config["emotional_boost"] - 1)
        score *= emotional_factor
        
        # Бонус за активации
        activation_factor = min(2.0, 1 + math.log10(memory.activation_count + 1) * 0.3)
        score *= activation_factor
        
        # Бонус за ассоциации
        score += len(memory.associations) * self.config["association_bonus"]
        
        # Бонус за replays
        score += memory.replay_count * self.config["replay_boost"]
        
        # Затухание по времени
        try:
            created = datetime.fromisoformat(memory.creation_time)
            age_hours = (datetime.now() - created).total_seconds() / 3600
            decay_factor = max(0.5, 1 - age_hours / (self.config["short_term_decay_hours"] * 2))
            score *= decay_factor
        except:
            pass
        
        return min(1.0, max(0.0, score))
    
    def _consolidate_memory(self, memory: MemoryTrace):
        """Перенести воспоминание в долгосрочную память."""
        # Удаляем из short-term если есть там
        if memory in self.short_term_memory:
            self.short_term_memory.remove(memory)
        
        memory.memory_type = MemoryType.LONG_TERM.value
        memory.consolidation_score = max(0.6, memory.consolidation_score)
        
        # Избегаем дубликатов
        if not any(m.id == memory.id for m in self.long_term_memory):
            self.long_term_memory.append(memory)
    
    def _replay_memory(self, memory: MemoryTrace):
        """
        "Переиграть" воспоминание для укрепления.
        
        Как во сне — реактивация укрепляет след памяти.
        """
        memory.replay_count += 1
        memory.consolidation_score = min(1.0, memory.consolidation_score + self.config["replay_boost"])
        memory.last_access_time = datetime.now().isoformat()
    
    def _generate_insights(self) -> List[Dict[str, Any]]:
        """
        Генерация инсайтов через поиск паттернов.
        
        REM-фаза: творческие связи между воспоминаниями.
        """
        insights = []
        
        if len(self.long_term_memory) < 3:
            return insights
        
        # Группируем по тегам
        tag_groups: Dict[str, List[MemoryTrace]] = {}
        for memory in self.long_term_memory:
            for tag in memory.tags:
                if tag not in tag_groups:
                    tag_groups[tag] = []
                tag_groups[tag].append(memory)
        
        # Ищем связи между группами
        for tag, memories in tag_groups.items():
            if len(memories) >= 3:
                # Паттерн: много воспоминаний с одним тегом
                insights.append({
                    "type": "pattern",
                    "tag": tag,
                    "memory_count": len(memories),
                    "description": f"Обнаружен паттерн: '{tag}' встречается в {len(memories)} воспоминаниях"
                })
        
        # Ищем эмоциональные кластеры
        positive = [m for m in self.long_term_memory if m.emotional_valence > 0.3]
        negative = [m for m in self.long_term_memory if m.emotional_valence < -0.3]
        
        if positive and negative:
            insights.append({
                "type": "emotional_balance",
                "positive_count": len(positive),
                "negative_count": len(negative),
                "ratio": len(positive) / (len(positive) + len(negative))
            })
        
        return insights
    
    # ============= Статистика =============
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Получить статистику памяти."""
        return {
            "working_memory_count": len(self.working_memory),
            "working_memory_capacity": self.config["working_memory_capacity"],
            "short_term_count": len(self.short_term_memory),
            "long_term_count": len(self.long_term_memory),
            "total_memories": len(self.working_memory) + len(self.short_term_memory) + len(self.long_term_memory),
            "total_sessions": len(self.sessions),
            "current_phase": self.current_phase.value,
            "avg_consolidation_score": self._avg_consolidation_score()
        }
    
    def _avg_consolidation_score(self) -> float:
        """Средний score консолидации."""
        all_memories = self.short_term_memory + self.long_term_memory
        if not all_memories:
            return 0.0
        return sum(m.consolidation_score for m in all_memories) / len(all_memories)
    
    def get_status_report(self) -> str:
        """Текстовый отчёт о состоянии памяти."""
        stats = self.get_memory_stats()
        
        phase_emoji = {
            "awake": "👁️",
            "light_sleep": "😴",
            "deep_sleep": "🌙",
            "rem": "💭",
            "micro_sleep": "⚡"
        }
        
        lines = [
            "🧠 Система консолидации памяти:",
            "",
            f"📍 Фаза: {phase_emoji.get(stats['current_phase'], '•')} {stats['current_phase']}",
            "",
            "📊 Объёмы памяти:",
            f"   • Рабочая: {stats['working_memory_count']}/{stats['working_memory_capacity']}",
            f"   • Краткосрочная: {stats['short_term_count']}",
            f"   • Долгосрочная: {stats['long_term_count']}",
            "",
            f"📈 Средний score консолидации: {stats['avg_consolidation_score']:.2f}",
            f"🛏️ Сессий консолидации: {stats['total_sessions']}"
        ]
        
        return "\n".join(lines)


# Синглтон
_memory_consolidation: Optional[MemoryConsolidation] = None


def get_memory_consolidation() -> MemoryConsolidation:
    """Получить глобальный экземпляр MemoryConsolidation."""
    global _memory_consolidation
    if _memory_consolidation is None:
        _memory_consolidation = MemoryConsolidation()
    return _memory_consolidation


# ==================== ТЕСТЫ ====================

if __name__ == "__main__":
    import tempfile
    import shutil
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ MEMORY CONSOLIDATION SYSTEM")
    print("=" * 60)
    
    test_dir = tempfile.mkdtemp()
    
    try:
        system = MemoryConsolidation(data_dir=test_dir)
        
        # Тест 1: Добавление в рабочую память
        print("\n📝 Тест 1: Рабочая память")
        for i in range(10):
            system.add_to_working_memory(
                f"Элемент {i}",
                importance=0.3 + random.random() * 0.4
            )
        
        # Должно быть max 7 в рабочей, остальные в краткосрочной
        assert len(system.working_memory) == 7
        assert len(system.short_term_memory) == 3
        print(f"✅ Рабочая память: {len(system.working_memory)}/7")
        print(f"✅ Перенесено в краткосрочную: {len(system.short_term_memory)}")
        
        # Тест 2: Важные воспоминания авто-консолидируются
        print("\n📝 Тест 2: Авто-консолидация важных воспоминаний")
        important_memory = system.add_to_short_term(
            "Очень важный факт от папы",
            importance=0.9,
            tags=["важное", "папа"]
        )
        
        assert len(system.long_term_memory) == 1
        print(f"✅ Важное воспоминание авто-консолидировано")
        
        # Тест 3: Поиск по содержимому
        print("\n📝 Тест 3: Поиск по содержимому")
        system.add_to_short_term("Python — лучший язык программирования", importance=0.6, tags=["программирование"])
        system.add_to_short_term("Машинное обучение интересно", importance=0.5, tags=["ML"])
        
        found = system.find_by_content("Python")
        assert len(found) == 1
        assert "Python" in found[0].content
        print(f"✅ Найдено: '{found[0].content[:40]}...'")
        
        # Тест 4: Создание ассоциаций
        print("\n📝 Тест 4: Создание ассоциаций")
        m1 = system.add_to_short_term("Концепт A", importance=0.5)
        m2 = system.add_to_short_term("Концепт B", importance=0.5)
        
        system.create_association(m1.id, m2.id)
        
        # Перечитаем
        m1_updated = system.recall(m1.id)
        assert m2.id in m1_updated.associations
        print(f"✅ Ассоциация создана: {m1.id} <-> {m2.id}")
        
        # Тест 5: Расчёт score консолидации
        print("\n📝 Тест 5: Расчёт score консолидации")
        test_memory = MemoryTrace(
            id="test",
            content="Тестовое воспоминание",
            importance=0.7,
            emotional_valence=0.8,  # Сильно эмоциональное
            activation_count=5,     # Часто вспоминали
            creation_time=datetime.now().isoformat()
        )
        test_memory.associations = ["a", "b", "c"]  # 3 ассоциации
        
        score = system._calculate_consolidation_score(test_memory)
        assert score > 0.6  # Должен быть высоким
        print(f"✅ Score: {score:.3f} (высокий из-за эмоций и активаций)")
        
        # Тест 6: Полный цикл консолидации
        print("\n📝 Тест 6: Полный цикл консолидации")
        
        # Добавим ещё воспоминаний
        for i in range(5):
            system.add_to_short_term(
                f"Воспоминание для консолидации {i}",
                importance=0.4 + i * 0.1,
                emotional_valence=random.uniform(-0.5, 0.5)
            )
        
        before_lt = len(system.long_term_memory)
        before_st = len(system.short_term_memory)
        
        results = system.run_consolidation_cycle()
        
        print(f"   • Консолидировано: {len(results['consolidated'])}")
        print(f"   • Забыто: {len(results['forgotten'])}")
        print(f"   • Укреплено: {len(results['strengthened'])}")
        print(f"   • Инсайтов: {len(results['insights'])}")
        print(f"✅ Цикл консолидации завершён")
        
        # Тест 7: Микро-консолидация
        print("\n📝 Тест 7: Микро-консолидация")
        # Добавим важное воспоминание в краткосрочную
        system.add_to_short_term(
            "Срочная информация",
            importance=0.85,
            emotional_valence=0.7
        )
        
        quick_results = system.quick_consolidation()
        print(f"✅ Микро-консолидация: {len(quick_results['consolidated'])} воспоминаний")
        
        # Тест 8: Recall усиливает воспоминание
        print("\n📝 Тест 8: Recall усиливает воспоминание")
        if system.long_term_memory:
            test_mem = system.long_term_memory[0]
            old_score = test_mem.consolidation_score
            old_count = test_mem.activation_count
            
            system.recall(test_mem.id)
            
            assert test_mem.activation_count > old_count
            assert test_mem.consolidation_score >= old_score
            print(f"✅ Активаций: {old_count} → {test_mem.activation_count}")
        
        # Тест 9: Статистика
        print("\n📝 Тест 9: Статистика памяти")
        stats = system.get_memory_stats()
        
        assert "working_memory_count" in stats
        assert "long_term_count" in stats
        print(f"✅ Статистика:")
        print(f"   • Рабочая: {stats['working_memory_count']}")
        print(f"   • Краткосрочная: {stats['short_term_count']}")
        print(f"   • Долгосрочная: {stats['long_term_count']}")
        
        # Тест 10: Статус-отчёт
        print("\n📝 Тест 10: Статус-отчёт")
        report = system.get_status_report()
        
        assert "консолидации" in report.lower()
        print(f"✅ Отчёт:\n{report}")
        
        # Тест 11: Фазы сна
        print("\n📝 Тест 11: Фазы сна")
        assert system.current_phase == SleepPhase.AWAKE
        
        session = system.start_consolidation(SleepPhase.DEEP_SLEEP)
        assert system.current_phase == SleepPhase.DEEP_SLEEP
        
        system.current_phase = SleepPhase.AWAKE
        print(f"✅ Смена фаз работает: AWAKE → DEEP_SLEEP → AWAKE")
        
        # Тест 12: Сохранение и загрузка
        print("\n📝 Тест 12: Сохранение и загрузка")
        system._save()
        
        system2 = MemoryConsolidation(data_dir=test_dir)
        
        assert len(system2.long_term_memory) == len(system.long_term_memory)
        print(f"✅ Сохранено и загружено {len(system2.long_term_memory)} долгосрочных воспоминаний")
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 60)
        
    finally:
        shutil.rmtree(test_dir)
