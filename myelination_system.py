"""
Myelination System — Система миелинизации Нейры.

Реализует механизм "миелинизации" нейронных путей:
- Частые пути становятся быстрее (больше миелина)
- Ускорение обработки привычных паттернов
- Автоматизация часто используемых навыков
- "Мышечная память" для ИИ

Основано на нейробиологии: миелиновые оболочки ускоряют
проведение сигналов в 100+ раз.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json
import math
import os
from pathlib import Path


class PathwayType(Enum):
    """Типы нейронных путей."""
    COGNITIVE = "cognitive"        # Мыслительные операции
    RESPONSE = "response"          # Паттерны ответов
    SKILL = "skill"                # Навыки
    RECOGNITION = "recognition"    # Распознавание паттернов
    EMOTIONAL = "emotional"        # Эмоциональные реакции
    PROCEDURAL = "procedural"      # Процедурные навыки


class MyelinationStage(Enum):
    """Стадии миелинизации."""
    UNMYELINATED = "unmyelinated"  # Без миелина (новый путь)
    INITIAL = "initial"            # Начальная миелинизация
    DEVELOPING = "developing"      # Развивающаяся
    MATURE = "mature"              # Зрелая
    OPTIMIZED = "optimized"        # Оптимизированная


@dataclass
class MyelinatedPathway:
    """Миелинизированный путь."""
    id: str
    name: str
    pathway_type: str
    nodes: List[str]               # Узлы пути (концепты, действия)
    
    # Миелинизация
    myelin_level: float = 0.0      # Уровень миелинизации (0.0 - 1.0)
    stage: str = "unmyelinated"
    
    # Использование
    activation_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    
    # Скорость (обратная задержке)
    base_latency_ms: float = 100.0  # Базовая задержка в мс
    current_latency_ms: float = 100.0
    
    # Времена
    created_at: str = ""
    last_activated_at: str = ""
    
    # Метаданные
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "pathway_type": self.pathway_type,
            "nodes": self.nodes,
            "myelin_level": self.myelin_level,
            "stage": self.stage,
            "activation_count": self.activation_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "base_latency_ms": self.base_latency_ms,
            "current_latency_ms": self.current_latency_ms,
            "created_at": self.created_at,
            "last_activated_at": self.last_activated_at,
            "description": self.description,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MyelinatedPathway":
        return cls(
            id=data["id"],
            name=data["name"],
            pathway_type=data.get("pathway_type", "cognitive"),
            nodes=data.get("nodes", []),
            myelin_level=data.get("myelin_level", 0.0),
            stage=data.get("stage", "unmyelinated"),
            activation_count=data.get("activation_count", 0),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            base_latency_ms=data.get("base_latency_ms", 100.0),
            current_latency_ms=data.get("current_latency_ms", 100.0),
            created_at=data.get("created_at", ""),
            last_activated_at=data.get("last_activated_at", ""),
            description=data.get("description", ""),
            tags=data.get("tags", [])
        )
    
    def get_success_rate(self) -> float:
        """Процент успешных активаций."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    def get_speedup_factor(self) -> float:
        """Коэффициент ускорения относительно базовой скорости."""
        if self.current_latency_ms <= 0:
            return 1.0
        return self.base_latency_ms / self.current_latency_ms


@dataclass
class MyelinationEvent:
    """Событие миелинизации."""
    timestamp: str
    pathway_id: str
    event_type: str  # "activation", "growth", "decay", "stage_change"
    old_level: float
    new_level: float
    details: str = ""


class MyelinationSystem:
    """
    Система миелинизации Нейры.
    
    Управляет "миелинизацией" — ускорением часто используемых путей.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "myelination.json"
        
        # Пути
        self.pathways: Dict[str, MyelinatedPathway] = {}
        
        # История
        self.events: List[MyelinationEvent] = []
        
        # Конфигурация
        self.config = {
            # Рост миелина
            "growth_rate_base": 0.02,           # Базовый рост за активацию
            "growth_rate_success_bonus": 0.03,  # Бонус за успех
            "growth_rate_failure_penalty": 0.01,  # Штраф за ошибку
            
            # Затухание
            "decay_rate_per_day": 0.005,        # Затухание за день неиспользования
            "decay_threshold_days": 7,          # После скольких дней начинается затухание
            
            # Ускорение
            "max_speedup_factor": 10.0,         # Максимальное ускорение (10x)
            "min_latency_ms": 10.0,             # Минимальная задержка
            
            # Стадии
            "stage_thresholds": {
                "initial": 0.1,
                "developing": 0.3,
                "mature": 0.6,
                "optimized": 0.85
            }
        }
        
        self._load()
    
    def _load(self):
        """Загрузка состояния."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for pw_data in data.get("pathways", []):
                    pathway = MyelinatedPathway.from_dict(pw_data)
                    self.pathways[pathway.id] = pathway
                
            except Exception as e:
                print(f"Ошибка загрузки MyelinationSystem: {e}")
    
    def _save(self):
        """Сохранение состояния."""
        data = {
            "pathways": [p.to_dict() for p in self.pathways.values()],
            "events": [
                {
                    "timestamp": e.timestamp,
                    "pathway_id": e.pathway_id,
                    "event_type": e.event_type,
                    "old_level": e.old_level,
                    "new_level": e.new_level,
                    "details": e.details
                }
                for e in self.events[-500:]
            ]
        }
        
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_id(self) -> str:
        """Генерация уникального ID."""
        import hashlib
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:12]
    
    # ============= Создание путей =============
    
    def create_pathway(
        self,
        name: str,
        nodes: List[str],
        pathway_type: PathwayType = PathwayType.COGNITIVE,
        description: str = "",
        tags: List[str] = None
    ) -> MyelinatedPathway:
        """
        Создать новый путь.
        
        Args:
            name: Имя пути
            nodes: Узлы (концепты, действия)
            pathway_type: Тип пути
            description: Описание
            tags: Теги
        
        Returns:
            Созданный путь
        """
        pathway = MyelinatedPathway(
            id=self._generate_id(),
            name=name,
            pathway_type=pathway_type.value,
            nodes=nodes,
            created_at=datetime.now().isoformat(),
            description=description,
            tags=tags or []
        )
        
        self.pathways[pathway.id] = pathway
        self._save()
        
        return pathway
    
    def find_or_create_pathway(
        self,
        name: str,
        nodes: List[str],
        pathway_type: PathwayType = PathwayType.COGNITIVE
    ) -> MyelinatedPathway:
        """
        Найти существующий путь или создать новый.
        
        Поиск по имени или узлам.
        """
        # Поиск по имени
        for pathway in self.pathways.values():
            if pathway.name == name:
                return pathway
        
        # Поиск по узлам (если совпадают все узлы в том же порядке)
        nodes_tuple = tuple(nodes)
        for pathway in self.pathways.values():
            if tuple(pathway.nodes) == nodes_tuple:
                return pathway
        
        # Создаём новый
        return self.create_pathway(name, nodes, pathway_type)
    
    # ============= Активация и миелинизация =============
    
    def activate_pathway(
        self,
        pathway_id: str,
        success: bool = True,
        intensity: float = 1.0
    ) -> Tuple[float, float]:
        """
        Активировать путь.
        
        При активации:
        - Увеличивается myelin_level
        - Уменьшается latency
        - Обновляется статистика
        
        Args:
            pathway_id: ID пути
            success: Успешная ли активация
            intensity: Интенсивность (влияет на рост миелина)
        
        Returns:
            Tuple[old_level, new_level]
        """
        pathway = self.pathways.get(pathway_id)
        if not pathway:
            return 0.0, 0.0
        
        old_level = pathway.myelin_level
        
        # Обновляем статистику
        pathway.activation_count += 1
        if success:
            pathway.success_count += 1
        else:
            pathway.failure_count += 1
        
        pathway.last_activated_at = datetime.now().isoformat()
        
        # Рост миелина
        growth = self.config["growth_rate_base"] * intensity
        if success:
            growth += self.config["growth_rate_success_bonus"] * intensity
        else:
            growth -= self.config["growth_rate_failure_penalty"] * intensity
        
        # Бонус за success rate (высокий success rate = лучший рост)
        success_rate = pathway.get_success_rate()
        growth *= (0.5 + success_rate)  # от 0.5x до 1.5x
        
        pathway.myelin_level = max(0.0, min(1.0, pathway.myelin_level + growth))
        
        # Обновляем стадию
        self._update_stage(pathway)
        
        # Пересчитываем latency
        self._update_latency(pathway)
        
        # Записываем событие
        event = MyelinationEvent(
            timestamp=datetime.now().isoformat(),
            pathway_id=pathway_id,
            event_type="activation",
            old_level=old_level,
            new_level=pathway.myelin_level,
            details=f"success={success}, intensity={intensity:.2f}"
        )
        self.events.append(event)
        
        self._save()
        return old_level, pathway.myelin_level
    
    def _update_stage(self, pathway: MyelinatedPathway):
        """Обновить стадию миелинизации."""
        thresholds = self.config["stage_thresholds"]
        old_stage = pathway.stage
        
        if pathway.myelin_level >= thresholds["optimized"]:
            pathway.stage = MyelinationStage.OPTIMIZED.value
        elif pathway.myelin_level >= thresholds["mature"]:
            pathway.stage = MyelinationStage.MATURE.value
        elif pathway.myelin_level >= thresholds["developing"]:
            pathway.stage = MyelinationStage.DEVELOPING.value
        elif pathway.myelin_level >= thresholds["initial"]:
            pathway.stage = MyelinationStage.INITIAL.value
        else:
            pathway.stage = MyelinationStage.UNMYELINATED.value
        
        if pathway.stage != old_stage:
            event = MyelinationEvent(
                timestamp=datetime.now().isoformat(),
                pathway_id=pathway.id,
                event_type="stage_change",
                old_level=pathway.myelin_level,
                new_level=pathway.myelin_level,
                details=f"{old_stage} → {pathway.stage}"
            )
            self.events.append(event)
    
    def _update_latency(self, pathway: MyelinatedPathway):
        """Пересчитать задержку на основе уровня миелина."""
        # Формула: latency уменьшается экспоненциально с ростом миелина
        # При myelin=0: latency = base
        # При myelin=1: latency = base / max_speedup
        
        speedup = 1 + pathway.myelin_level * (self.config["max_speedup_factor"] - 1)
        pathway.current_latency_ms = max(
            self.config["min_latency_ms"],
            pathway.base_latency_ms / speedup
        )
    
    # ============= Затухание =============
    
    def decay_unused_pathways(self) -> List[Tuple[str, float, float]]:
        """
        Применить затухание к неиспользуемым путям.
        
        Returns:
            Список (pathway_id, old_level, new_level) для изменённых путей
        """
        decayed = []
        now = datetime.now()
        threshold_days = self.config["decay_threshold_days"]
        decay_rate = self.config["decay_rate_per_day"]
        
        for pathway in self.pathways.values():
            if not pathway.last_activated_at:
                continue
            
            try:
                last_active = datetime.fromisoformat(pathway.last_activated_at)
                days_inactive = (now - last_active).days
                
                if days_inactive > threshold_days and pathway.myelin_level > 0:
                    # Затухание пропорционально дням сверх порога
                    decay_days = days_inactive - threshold_days
                    decay_amount = decay_rate * decay_days
                    
                    old_level = pathway.myelin_level
                    pathway.myelin_level = max(0.0, pathway.myelin_level - decay_amount)
                    
                    # Обновляем стадию и latency
                    self._update_stage(pathway)
                    self._update_latency(pathway)
                    
                    decayed.append((pathway.id, old_level, pathway.myelin_level))
                    
                    # Записываем событие
                    event = MyelinationEvent(
                        timestamp=datetime.now().isoformat(),
                        pathway_id=pathway.id,
                        event_type="decay",
                        old_level=old_level,
                        new_level=pathway.myelin_level,
                        details=f"inactive {days_inactive} days"
                    )
                    self.events.append(event)
                    
            except:
                continue
        
        if decayed:
            self._save()
        
        return decayed
    
    # ============= Поиск и запросы =============
    
    def get_pathway(self, pathway_id: str) -> Optional[MyelinatedPathway]:
        """Получить путь по ID."""
        return self.pathways.get(pathway_id)
    
    def get_pathways_by_type(self, pathway_type: PathwayType) -> List[MyelinatedPathway]:
        """Получить все пути определённого типа."""
        return [
            p for p in self.pathways.values()
            if p.pathway_type == pathway_type.value
        ]
    
    def get_most_myelinated(self, limit: int = 5) -> List[MyelinatedPathway]:
        """Получить наиболее миелинизированные пути."""
        sorted_paths = sorted(
            self.pathways.values(),
            key=lambda p: p.myelin_level,
            reverse=True
        )
        return sorted_paths[:limit]
    
    def get_fastest_pathways(self, limit: int = 5) -> List[MyelinatedPathway]:
        """Получить самые быстрые пути."""
        sorted_paths = sorted(
            self.pathways.values(),
            key=lambda p: p.current_latency_ms
        )
        return sorted_paths[:limit]
    
    def find_pathways_containing_node(self, node: str) -> List[MyelinatedPathway]:
        """Найти пути, содержащие узел."""
        return [
            p for p in self.pathways.values()
            if node in p.nodes
        ]
    
    def get_optimized_pathways(self) -> List[MyelinatedPathway]:
        """Получить полностью оптимизированные пути."""
        return [
            p for p in self.pathways.values()
            if p.stage == MyelinationStage.OPTIMIZED.value
        ]
    
    # ============= Интеграция с другими системами =============
    
    def get_pathway_latency(self, pathway_id: str) -> float:
        """
        Получить текущую задержку пути.
        
        Используется для определения "скорости мышления".
        """
        pathway = self.pathways.get(pathway_id)
        if pathway:
            return pathway.current_latency_ms
        return 100.0  # Базовая задержка для неизвестных путей
    
    def is_automatic(self, pathway_id: str) -> bool:
        """
        Проверить, является ли путь "автоматическим".
        
        Автоматические пути не требуют сознательного усилия.
        """
        pathway = self.pathways.get(pathway_id)
        if not pathway:
            return False
        
        return pathway.stage in [
            MyelinationStage.MATURE.value,
            MyelinationStage.OPTIMIZED.value
        ]
    
    def get_skill_level(self, pathway_id: str) -> str:
        """
        Получить уровень владения навыком.
        
        Returns:
            "новичок", "изучающий", "опытный", "мастер", "эксперт"
        """
        pathway = self.pathways.get(pathway_id)
        if not pathway:
            return "новичок"
        
        stage_to_skill = {
            "unmyelinated": "новичок",
            "initial": "изучающий",
            "developing": "опытный",
            "mature": "мастер",
            "optimized": "эксперт"
        }
        
        return stage_to_skill.get(pathway.stage, "новичок")
    
    # ============= Статистика =============
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику системы."""
        if not self.pathways:
            return {
                "total_pathways": 0,
                "avg_myelin_level": 0.0,
                "stages": {},
                "types": {}
            }
        
        pathways = list(self.pathways.values())
        
        # Группировка по стадиям
        stages = {}
        for stage in MyelinationStage:
            count = sum(1 for p in pathways if p.stage == stage.value)
            stages[stage.value] = count
        
        # Группировка по типам
        types = {}
        for ptype in PathwayType:
            count = sum(1 for p in pathways if p.pathway_type == ptype.value)
            if count > 0:
                types[ptype.value] = count
        
        return {
            "total_pathways": len(pathways),
            "avg_myelin_level": sum(p.myelin_level for p in pathways) / len(pathways),
            "max_myelin_level": max(p.myelin_level for p in pathways),
            "avg_speedup": sum(p.get_speedup_factor() for p in pathways) / len(pathways),
            "total_activations": sum(p.activation_count for p in pathways),
            "stages": stages,
            "types": types
        }
    
    def get_status_report(self) -> str:
        """Получить текстовый отчёт."""
        stats = self.get_statistics()
        
        if stats["total_pathways"] == 0:
            return "🧬 Система миелинизации: нет путей"
        
        stage_emoji = {
            "unmyelinated": "⚪",
            "initial": "🔵",
            "developing": "🟢",
            "mature": "🟡",
            "optimized": "⭐"
        }
        
        lines = [
            "🧬 Система миелинизации:",
            "",
            f"📊 Всего путей: {stats['total_pathways']}",
            f"📈 Средний уровень миелина: {stats['avg_myelin_level']:.0%}",
            f"⚡ Среднее ускорение: {stats['avg_speedup']:.1f}x",
            "",
            "🎯 По стадиям:"
        ]
        
        for stage, count in stats["stages"].items():
            if count > 0:
                emoji = stage_emoji.get(stage, "•")
                lines.append(f"   {emoji} {stage}: {count}")
        
        # Топ путей
        top_paths = self.get_most_myelinated(3)
        if top_paths:
            lines.append("")
            lines.append("🏆 Топ-3 пути:")
            for i, p in enumerate(top_paths, 1):
                lines.append(f"   {i}. {p.name}: {p.myelin_level:.0%} ({p.stage})")
        
        return "\n".join(lines)


# Синглтон
_myelination_system: Optional[MyelinationSystem] = None


def get_myelination_system() -> MyelinationSystem:
    """Получить глобальный экземпляр MyelinationSystem."""
    global _myelination_system
    if _myelination_system is None:
        _myelination_system = MyelinationSystem()
    return _myelination_system


# ==================== ТЕСТЫ ====================

if __name__ == "__main__":
    import tempfile
    import shutil
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ MYELINATION SYSTEM")
    print("=" * 60)
    
    test_dir = tempfile.mkdtemp()
    
    try:
        system = MyelinationSystem(data_dir=test_dir)
        
        # Тест 1: Создание пути
        print("\n📝 Тест 1: Создание пути")
        pathway = system.create_pathway(
            name="greeting_response",
            nodes=["распознать_приветствие", "выбрать_ответ", "добавить_эмоцию", "отправить"],
            pathway_type=PathwayType.RESPONSE,
            description="Путь обработки приветствий"
        )
        
        assert pathway.id in system.pathways
        assert pathway.myelin_level == 0.0
        assert pathway.stage == "unmyelinated"
        print(f"✅ Путь создан: {pathway.name}, узлов: {len(pathway.nodes)}")
        
        # Тест 2: Активация и рост миелина
        print("\n📝 Тест 2: Активация и рост миелина")
        old_level, new_level = system.activate_pathway(pathway.id, success=True)
        
        assert new_level > old_level
        print(f"✅ Миелин: {old_level:.3f} → {new_level:.3f}")
        
        # Тест 3: Многократная активация
        print("\n📝 Тест 3: Многократная активация")
        for _ in range(30):
            system.activate_pathway(pathway.id, success=True, intensity=1.0)
        
        pathway = system.get_pathway(pathway.id)
        assert pathway.myelin_level > 0.1  # Должен перейти хотя бы в initial
        assert pathway.stage != "unmyelinated"
        print(f"✅ После 30 активаций: {pathway.myelin_level:.0%}, стадия: {pathway.stage}")
        
        # Тест 4: Ускорение (latency)
        print("\n📝 Тест 4: Ускорение пути")
        base_latency = pathway.base_latency_ms
        current_latency = pathway.current_latency_ms
        speedup = pathway.get_speedup_factor()
        
        assert current_latency < base_latency
        assert speedup > 1.0
        print(f"✅ Latency: {base_latency:.0f}ms → {current_latency:.1f}ms (ускорение {speedup:.1f}x)")
        
        # Тест 5: Стадии миелинизации
        print("\n📝 Тест 5: Достижение стадии 'optimized'")
        # Доводим до оптимизированного
        while pathway.stage != "optimized":
            system.activate_pathway(pathway.id, success=True, intensity=1.5)
            pathway = system.get_pathway(pathway.id)
        
        assert pathway.stage == "optimized"
        print(f"✅ Достигнута стадия: {pathway.stage}, миелин: {pathway.myelin_level:.0%}")
        
        # Тест 6: Влияние неудач
        print("\n📝 Тест 6: Влияние неудачных активаций")
        skill_path = system.create_pathway(
            name="complex_task",
            nodes=["анализ", "план", "исполнение"],
            pathway_type=PathwayType.SKILL
        )
        
        # Половина успехов, половина неудач
        for i in range(10):
            system.activate_pathway(skill_path.id, success=(i % 2 == 0))
        
        skill_path = system.get_pathway(skill_path.id)
        success_rate = skill_path.get_success_rate()
        
        assert 0.4 <= success_rate <= 0.6
        print(f"✅ Success rate: {success_rate:.0%}, миелин: {skill_path.myelin_level:.0%}")
        
        # Тест 7: Поиск путей
        print("\n📝 Тест 7: Поиск путей")
        system.create_pathway("recognition_faces", ["ввод", "анализ", "сопоставление"], PathwayType.RECOGNITION)
        system.create_pathway("recognition_voices", ["ввод", "анализ", "сопоставление"], PathwayType.RECOGNITION)
        
        recognition_paths = system.get_pathways_by_type(PathwayType.RECOGNITION)
        assert len(recognition_paths) == 2
        print(f"✅ Найдено путей типа RECOGNITION: {len(recognition_paths)}")
        
        # Тест 8: Поиск по узлу
        print("\n📝 Тест 8: Поиск путей по узлу")
        paths_with_analysis = system.find_pathways_containing_node("анализ")
        
        assert len(paths_with_analysis) >= 2
        print(f"✅ Путей с узлом 'анализ': {len(paths_with_analysis)}")
        
        # Тест 9: Автоматические пути
        print("\n📝 Тест 9: Проверка автоматических путей")
        # greeting_response должен быть автоматическим (optimized)
        is_auto = system.is_automatic(pathway.id)
        skill_level = system.get_skill_level(pathway.id)
        
        assert is_auto == True
        assert skill_level == "эксперт"
        print(f"✅ Путь '{pathway.name}': автоматический={is_auto}, уровень='{skill_level}'")
        
        # Тест 10: Затухание
        print("\n📝 Тест 10: Затухание неиспользуемых путей")
        decay_path = system.create_pathway("old_skill", ["шаг1", "шаг2"], PathwayType.SKILL)
        
        # Активируем несколько раз
        for _ in range(10):
            system.activate_pathway(decay_path.id, success=True)
        
        decay_path = system.get_pathway(decay_path.id)
        level_before = decay_path.myelin_level
        
        # Симулируем старую дату активации
        old_date = (datetime.now() - timedelta(days=30)).isoformat()
        decay_path.last_activated_at = old_date
        
        decayed = system.decay_unused_pathways()
        
        decay_path = system.get_pathway(decay_path.id)
        assert decay_path.myelin_level < level_before
        print(f"✅ Затухание: {level_before:.3f} → {decay_path.myelin_level:.3f}")
        
        # Тест 11: Статистика
        print("\n📝 Тест 11: Статистика системы")
        stats = system.get_statistics()
        
        assert "total_pathways" in stats
        assert stats["total_pathways"] >= 5
        print(f"✅ Статистика:")
        print(f"   • Путей: {stats['total_pathways']}")
        print(f"   • Средний миелин: {stats['avg_myelin_level']:.0%}")
        print(f"   • Среднее ускорение: {stats['avg_speedup']:.1f}x")
        
        # Тест 12: Сохранение и загрузка
        print("\n📝 Тест 12: Сохранение и загрузка")
        system._save()
        
        system2 = MyelinationSystem(data_dir=test_dir)
        
        assert len(system2.pathways) == len(system.pathways)
        print(f"✅ Сохранено и загружено {len(system2.pathways)} путей")
        
        # Тест 13: Статус-отчёт
        print("\n📝 Тест 13: Статус-отчёт")
        report = system.get_status_report()
        
        assert "миелин" in report.lower()
        print(f"✅ Отчёт:\n{report}")
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 60)
        
    finally:
        shutil.rmtree(test_dir)
