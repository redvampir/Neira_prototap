"""
Synaptic Plasticity — Синаптическая пластичность Нейры.

Реализация механизмов LTP (Long-Term Potentiation) и LTD (Long-Term Depression):
- Усиление связей при частом совместном использовании (правило Хебба)
- Ослабление связей при редком использовании
- "Neurons that fire together, wire together"

Это основа обучения мозга — и теперь Нейры.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json
import math
import os
from pathlib import Path


class PlasticityType(Enum):
    """Тип пластичности."""
    LTP = "ltp"     # Long-Term Potentiation (усиление)
    LTD = "ltd"     # Long-Term Depression (ослабление)
    STP = "stp"     # Short-Term Potentiation (кратковременное)
    STD = "std"     # Short-Term Depression (кратковременное)


@dataclass
class Synapse:
    """
    Синапс — связь между двумя концепциями/паттернами.
    
    Аналог синаптической связи в мозге.
    """
    id: str
    source: str                     # Исходный паттерн/концепция
    target: str                     # Целевой паттерн/концепция
    
    # Сила связи (0.0 - 1.0)
    weight: float = 0.5
    
    # История активаций
    activation_count: int = 0
    last_activation: Optional[str] = None
    
    # Временные характеристики
    created_at: str = ""
    
    # Параметры пластичности
    potentiation_rate: float = 0.1   # Скорость усиления
    depression_rate: float = 0.05    # Скорость ослабления
    
    # Флаги
    is_mature: bool = False          # Стабильная связь
    is_candidate_for_pruning: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "weight": self.weight,
            "activation_count": self.activation_count,
            "last_activation": self.last_activation,
            "created_at": self.created_at,
            "potentiation_rate": self.potentiation_rate,
            "depression_rate": self.depression_rate,
            "is_mature": self.is_mature,
            "is_candidate_for_pruning": self.is_candidate_for_pruning
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Synapse":
        return cls(
            id=data["id"],
            source=data["source"],
            target=data["target"],
            weight=data.get("weight", 0.5),
            activation_count=data.get("activation_count", 0),
            last_activation=data.get("last_activation"),
            created_at=data.get("created_at", ""),
            potentiation_rate=data.get("potentiation_rate", 0.1),
            depression_rate=data.get("depression_rate", 0.05),
            is_mature=data.get("is_mature", False),
            is_candidate_for_pruning=data.get("is_candidate_for_pruning", False)
        )


@dataclass
class NeuralPathway:
    """
    Нейронный путь — последовательность синапсов.
    
    Представляет паттерн мышления или ассоциативную цепочку.
    """
    id: str
    name: str
    description: str = ""
    
    # Узлы пути
    nodes: List[str] = field(default_factory=list)
    
    # Общая сила пути (произведение весов синапсов)
    total_strength: float = 0.5
    
    # Статистика использования
    usage_count: int = 0
    success_count: int = 0          # Успешные активации
    failure_count: int = 0          # Неудачные активации
    
    # Время
    created_at: str = ""
    last_used: Optional[str] = None
    
    # Миелинизация (ускорение)
    myelination_level: float = 0.0  # 0.0 - 1.0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": self.nodes,
            "total_strength": self.total_strength,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "myelination_level": self.myelination_level
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "NeuralPathway":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            nodes=data.get("nodes", []),
            total_strength=data.get("total_strength", 0.5),
            usage_count=data.get("usage_count", 0),
            success_count=data.get("success_count", 0),
            failure_count=data.get("failure_count", 0),
            created_at=data.get("created_at", ""),
            last_used=data.get("last_used"),
            myelination_level=data.get("myelination_level", 0.0)
        )
    
    @property
    def success_rate(self) -> float:
        """Процент успешных активаций."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # Неизвестно
        return self.success_count / total


@dataclass
class PlasticityEvent:
    """Событие пластичности (изменение синапса)."""
    timestamp: str
    synapse_id: str
    event_type: str     # PlasticityType value
    old_weight: float
    new_weight: float
    trigger: str        # Что вызвало изменение
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "synapse_id": self.synapse_id,
            "event_type": self.event_type,
            "old_weight": self.old_weight,
            "new_weight": self.new_weight,
            "trigger": self.trigger
        }


class SynapticPlasticity:
    """
    Система синаптической пластичности Нейры.
    
    Управляет созданием, усилением и ослаблением связей
    между концепциями на основе опыта.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "synaptic_plasticity.json"
        
        # Синапсы: id -> Synapse
        self.synapses: Dict[str, Synapse] = {}
        
        # Нейронные пути: id -> NeuralPathway
        self.pathways: Dict[str, NeuralPathway] = {}
        
        # Индексы для быстрого поиска
        self._source_index: Dict[str, List[str]] = {}  # source -> [synapse_ids]
        self._target_index: Dict[str, List[str]] = {}  # target -> [synapse_ids]
        
        # История событий пластичности
        self.plasticity_history: List[PlasticityEvent] = []
        
        # Параметры
        self.config = {
            "base_ltp_rate": 0.1,           # Базовая скорость LTP
            "base_ltd_rate": 0.05,          # Базовая скорость LTD
            "weight_min": 0.01,             # Минимальный вес
            "weight_max": 1.0,              # Максимальный вес
            "maturity_threshold": 20,        # Активаций до "зрелости"
            "pruning_threshold": 0.05,       # Порог веса для удаления
            "decay_rate": 0.001,            # Скорость затухания в день
            "hebbian_window_ms": 100,        # Окно для правила Хебба (мс)
        }
        
        self._load()
    
    def _load(self):
        """Загрузка данных."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for syn_data in data.get("synapses", []):
                    synapse = Synapse.from_dict(syn_data)
                    self.synapses[synapse.id] = synapse
                    self._index_synapse(synapse)
                
                for path_data in data.get("pathways", []):
                    pathway = NeuralPathway.from_dict(path_data)
                    self.pathways[pathway.id] = pathway
                
                self.config.update(data.get("config", {}))
                
            except Exception as e:
                print(f"Ошибка загрузки SynapticPlasticity: {e}")
    
    def _save(self):
        """Сохранение данных."""
        data = {
            "synapses": [s.to_dict() for s in self.synapses.values()],
            "pathways": [p.to_dict() for p in self.pathways.values()],
            "config": self.config,
            "plasticity_history": [e.to_dict() for e in self.plasticity_history[-1000:]]
        }
        
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_id(self, prefix: str = "syn") -> str:
        """Генерация уникального ID."""
        import hashlib
        import random
        data = f"{datetime.now().isoformat()}{random.random()}"
        return f"{prefix}_{hashlib.md5(data.encode()).hexdigest()[:10]}"
    
    def _index_synapse(self, synapse: Synapse):
        """Добавить синапс в индексы."""
        if synapse.source not in self._source_index:
            self._source_index[synapse.source] = []
        if synapse.id not in self._source_index[synapse.source]:
            self._source_index[synapse.source].append(synapse.id)
        
        if synapse.target not in self._target_index:
            self._target_index[synapse.target] = []
        if synapse.id not in self._target_index[synapse.target]:
            self._target_index[synapse.target].append(synapse.id)
    
    def _unindex_synapse(self, synapse: Synapse):
        """Удалить синапс из индексов."""
        if synapse.source in self._source_index:
            if synapse.id in self._source_index[synapse.source]:
                self._source_index[synapse.source].remove(synapse.id)
        
        if synapse.target in self._target_index:
            if synapse.id in self._target_index[synapse.target]:
                self._target_index[synapse.target].remove(synapse.id)
    
    def create_synapse(
        self,
        source: str,
        target: str,
        initial_weight: float = 0.3
    ) -> Synapse:
        """
        Создать новый синапс между двумя концепциями.
        
        Args:
            source: Исходная концепция
            target: Целевая концепция
            initial_weight: Начальный вес связи
        """
        # Проверяем, не существует ли уже такой синапс
        existing = self.get_synapse(source, target)
        if existing:
            return existing
        
        synapse = Synapse(
            id=self._generate_id("syn"),
            source=source,
            target=target,
            weight=initial_weight,
            created_at=datetime.now().isoformat(),
            potentiation_rate=self.config["base_ltp_rate"],
            depression_rate=self.config["base_ltd_rate"]
        )
        
        self.synapses[synapse.id] = synapse
        self._index_synapse(synapse)
        self._save()
        
        return synapse
    
    def get_synapse(self, source: str, target: str) -> Optional[Synapse]:
        """Получить синапс по source и target."""
        if source not in self._source_index:
            return None
        
        for syn_id in self._source_index[source]:
            synapse = self.synapses.get(syn_id)
            if synapse and synapse.target == target:
                return synapse
        
        return None
    
    def activate_synapse(
        self,
        synapse_id: str,
        success: bool = True,
        intensity: float = 1.0
    ) -> Tuple[float, float]:
        """
        Активировать синапс (провести сигнал).
        
        Реализует правило Хебба: при успешной активации — LTP,
        при неудачной — LTD.
        
        Args:
            synapse_id: ID синапса
            success: Была ли активация успешной
            intensity: Интенсивность активации (0.0-1.0)
        
        Returns:
            Tuple[old_weight, new_weight]
        """
        if synapse_id not in self.synapses:
            raise ValueError(f"Синапс {synapse_id} не найден")
        
        synapse = self.synapses[synapse_id]
        old_weight = synapse.weight
        
        if success:
            # LTP: усиление связи
            delta = synapse.potentiation_rate * intensity * (1 - synapse.weight)
            synapse.weight = min(self.config["weight_max"], synapse.weight + delta)
            event_type = PlasticityType.LTP
        else:
            # LTD: ослабление связи
            delta = synapse.depression_rate * intensity * synapse.weight
            synapse.weight = max(self.config["weight_min"], synapse.weight - delta)
            event_type = PlasticityType.LTD
        
        # Обновляем статистику
        synapse.activation_count += 1
        synapse.last_activation = datetime.now().isoformat()
        
        # Проверяем зрелость
        if synapse.activation_count >= self.config["maturity_threshold"]:
            synapse.is_mature = True
        
        # Проверяем кандидата на удаление
        synapse.is_candidate_for_pruning = synapse.weight < self.config["pruning_threshold"]
        
        # Записываем событие
        event = PlasticityEvent(
            timestamp=datetime.now().isoformat(),
            synapse_id=synapse_id,
            event_type=event_type.value,
            old_weight=old_weight,
            new_weight=synapse.weight,
            trigger="activation"
        )
        self.plasticity_history.append(event)
        
        self._save()
        return old_weight, synapse.weight
    
    def hebbian_learning(
        self,
        concepts: List[str],
        success: bool = True,
        intensity: float = 1.0
    ) -> List[Tuple[str, float, float]]:
        """
        Обучение по Хеббу: усиление связей между одновременно 
        активными концепциями.
        
        "Neurons that fire together, wire together"
        
        Args:
            concepts: Список концепций, активных одновременно
            success: Был ли опыт успешным
            intensity: Интенсивность
        
        Returns:
            Список изменений: [(synapse_id, old_weight, new_weight), ...]
        """
        changes = []
        
        # Создаём/усиливаем связи между всеми парами
        for i, source in enumerate(concepts):
            for target in concepts[i+1:]:
                # Связь source -> target
                synapse_st = self.get_synapse(source, target)
                if synapse_st is None:
                    synapse_st = self.create_synapse(source, target)
                
                old_w, new_w = self.activate_synapse(synapse_st.id, success, intensity)
                changes.append((synapse_st.id, old_w, new_w))
                
                # Связь target -> source (двунаправленная)
                synapse_ts = self.get_synapse(target, source)
                if synapse_ts is None:
                    synapse_ts = self.create_synapse(target, source)
                
                old_w, new_w = self.activate_synapse(synapse_ts.id, success, intensity)
                changes.append((synapse_ts.id, old_w, new_w))
        
        return changes
    
    def create_pathway(
        self,
        name: str,
        nodes: List[str],
        description: str = ""
    ) -> NeuralPathway:
        """
        Создать нейронный путь (цепочку связей).
        
        Args:
            name: Название пути
            nodes: Последовательность узлов
            description: Описание
        """
        # Создаём синапсы между последовательными узлами
        for i in range(len(nodes) - 1):
            self.create_synapse(nodes[i], nodes[i+1])
        
        pathway = NeuralPathway(
            id=self._generate_id("path"),
            name=name,
            description=description,
            nodes=nodes,
            created_at=datetime.now().isoformat()
        )
        
        # Вычисляем начальную силу пути
        pathway.total_strength = self._calculate_pathway_strength(pathway)
        
        self.pathways[pathway.id] = pathway
        self._save()
        
        return pathway
    
    def _calculate_pathway_strength(self, pathway: NeuralPathway) -> float:
        """Вычислить общую силу пути (произведение весов)."""
        if len(pathway.nodes) < 2:
            return 1.0
        
        strength = 1.0
        for i in range(len(pathway.nodes) - 1):
            synapse = self.get_synapse(pathway.nodes[i], pathway.nodes[i+1])
            if synapse:
                strength *= synapse.weight
            else:
                strength *= 0.1  # Штраф за отсутствующий синапс
        
        return strength
    
    def activate_pathway(
        self,
        pathway_id: str,
        success: bool = True,
        intensity: float = 1.0
    ) -> Dict[str, Any]:
        """
        Активировать нейронный путь.
        
        Args:
            pathway_id: ID пути
            success: Успешная ли активация
            intensity: Интенсивность
        
        Returns:
            Результат активации с изменениями весов
        """
        if pathway_id not in self.pathways:
            raise ValueError(f"Путь {pathway_id} не найден")
        
        pathway = self.pathways[pathway_id]
        old_strength = pathway.total_strength
        changes = []
        
        # Активируем все синапсы пути
        for i in range(len(pathway.nodes) - 1):
            synapse = self.get_synapse(pathway.nodes[i], pathway.nodes[i+1])
            if synapse:
                old_w, new_w = self.activate_synapse(synapse.id, success, intensity)
                changes.append({
                    "synapse_id": synapse.id,
                    "source": synapse.source,
                    "target": synapse.target,
                    "old_weight": old_w,
                    "new_weight": new_w
                })
        
        # Обновляем статистику пути
        pathway.usage_count += 1
        pathway.last_used = datetime.now().isoformat()
        
        if success:
            pathway.success_count += 1
        else:
            pathway.failure_count += 1
        
        # Пересчитываем силу пути
        pathway.total_strength = self._calculate_pathway_strength(pathway)
        
        # Увеличиваем миелинизацию при успехе
        if success and pathway.usage_count > 5:
            myelination_gain = 0.02 * intensity
            pathway.myelination_level = min(1.0, pathway.myelination_level + myelination_gain)
        
        self._save()
        
        return {
            "pathway_id": pathway_id,
            "old_strength": old_strength,
            "new_strength": pathway.total_strength,
            "myelination_level": pathway.myelination_level,
            "synapse_changes": changes
        }
    
    def decay_unused_synapses(self, days_threshold: int = 7) -> List[str]:
        """
        Применить затухание к неиспользуемым синапсам.
        
        Имитирует естественное забывание.
        
        Args:
            days_threshold: После скольких дней начинается затухание
        
        Returns:
            Список ID затухших синапсов
        """
        now = datetime.now()
        decayed = []
        
        for synapse in self.synapses.values():
            if synapse.is_mature:
                continue  # Зрелые синапсы более устойчивы
            
            if synapse.last_activation:
                last_active = datetime.fromisoformat(synapse.last_activation)
                days_inactive = (now - last_active).days
                
                if days_inactive > days_threshold:
                    # Применяем затухание
                    decay = self.config["decay_rate"] * (days_inactive - days_threshold)
                    old_weight = synapse.weight
                    synapse.weight = max(
                        self.config["weight_min"],
                        synapse.weight * (1 - decay)
                    )
                    
                    if synapse.weight < self.config["pruning_threshold"]:
                        synapse.is_candidate_for_pruning = True
                    
                    decayed.append(synapse.id)
                    
                    # Записываем событие
                    event = PlasticityEvent(
                        timestamp=now.isoformat(),
                        synapse_id=synapse.id,
                        event_type=PlasticityType.LTD.value,
                        old_weight=old_weight,
                        new_weight=synapse.weight,
                        trigger=f"decay_{days_inactive}_days"
                    )
                    self.plasticity_history.append(event)
        
        if decayed:
            self._save()
        
        return decayed
    
    def prune_weak_synapses(self) -> List[Dict]:
        """
        Удалить слабые синапсы (синаптический прюнинг).
        
        Returns:
            Список удалённых синапсов
        """
        pruned = []
        
        for synapse_id in list(self.synapses.keys()):
            synapse = self.synapses[synapse_id]
            
            if synapse.is_candidate_for_pruning and not synapse.is_mature:
                pruned.append(synapse.to_dict())
                self._unindex_synapse(synapse)
                del self.synapses[synapse_id]
        
        if pruned:
            self._save()
        
        return pruned
    
    def get_strongest_associations(self, concept: str, limit: int = 10) -> List[Dict]:
        """
        Получить сильнейшие ассоциации с концепцией.
        
        Args:
            concept: Исходная концепция
            limit: Максимум результатов
        
        Returns:
            Список ассоциаций с весами
        """
        associations = []
        
        # Исходящие связи
        if concept in self._source_index:
            for syn_id in self._source_index[concept]:
                synapse = self.synapses[syn_id]
                associations.append({
                    "concept": synapse.target,
                    "weight": synapse.weight,
                    "direction": "outgoing",
                    "activations": synapse.activation_count
                })
        
        # Входящие связи
        if concept in self._target_index:
            for syn_id in self._target_index[concept]:
                synapse = self.synapses[syn_id]
                associations.append({
                    "concept": synapse.source,
                    "weight": synapse.weight,
                    "direction": "incoming",
                    "activations": synapse.activation_count
                })
        
        # Сортируем по весу
        associations.sort(key=lambda x: x["weight"], reverse=True)
        
        return associations[:limit]
    
    def get_pathway_by_strength(self, min_strength: float = 0.5) -> List[NeuralPathway]:
        """Получить пути с минимальной силой."""
        return [
            p for p in self.pathways.values()
            if p.total_strength >= min_strength
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику системы пластичности."""
        total_synapses = len(self.synapses)
        mature_synapses = sum(1 for s in self.synapses.values() if s.is_mature)
        pruning_candidates = sum(1 for s in self.synapses.values() if s.is_candidate_for_pruning)
        
        weights = [s.weight for s in self.synapses.values()]
        avg_weight = sum(weights) / len(weights) if weights else 0
        
        pathway_strengths = [p.total_strength for p in self.pathways.values()]
        avg_pathway_strength = sum(pathway_strengths) / len(pathway_strengths) if pathway_strengths else 0
        
        # Статистика пластичности
        ltp_events = sum(1 for e in self.plasticity_history if e.event_type == "ltp")
        ltd_events = sum(1 for e in self.plasticity_history if e.event_type == "ltd")
        
        return {
            "total_synapses": total_synapses,
            "mature_synapses": mature_synapses,
            "pruning_candidates": pruning_candidates,
            "average_weight": avg_weight,
            "total_pathways": len(self.pathways),
            "average_pathway_strength": avg_pathway_strength,
            "ltp_events": ltp_events,
            "ltd_events": ltd_events,
            "plasticity_ratio": ltp_events / (ltp_events + ltd_events) if (ltp_events + ltd_events) > 0 else 0.5
        }


# Синглтон
_synaptic_plasticity: Optional[SynapticPlasticity] = None


def get_synaptic_plasticity() -> SynapticPlasticity:
    """Получить глобальный экземпляр SynapticPlasticity."""
    global _synaptic_plasticity
    if _synaptic_plasticity is None:
        _synaptic_plasticity = SynapticPlasticity()
    return _synaptic_plasticity


# ==================== ТЕСТЫ ====================

if __name__ == "__main__":
    import tempfile
    import shutil
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ SYNAPTIC PLASTICITY")
    print("=" * 60)
    
    test_dir = tempfile.mkdtemp()
    
    try:
        plasticity = SynapticPlasticity(data_dir=test_dir)
        
        # Тест 1: Создание синапсов
        print("\n📝 Тест 1: Создание синапсов")
        syn1 = plasticity.create_synapse("кот", "животное")
        syn2 = plasticity.create_synapse("собака", "животное")
        syn3 = plasticity.create_synapse("кот", "мягкий")
        
        assert syn1.source == "кот"
        assert syn1.target == "животное"
        assert len(plasticity.synapses) == 3
        print(f"✅ Создано 3 синапса: кот→животное (w={syn1.weight:.2f})")
        
        # Тест 2: Активация синапса (LTP)
        print("\n📝 Тест 2: LTP при успешной активации")
        old_w, new_w = plasticity.activate_synapse(syn1.id, success=True, intensity=1.0)
        
        assert new_w > old_w
        print(f"✅ LTP: вес {old_w:.3f} → {new_w:.3f}")
        
        # Тест 3: Активация синапса (LTD)
        print("\n📝 Тест 3: LTD при неудачной активации")
        old_w, new_w = plasticity.activate_synapse(syn2.id, success=False, intensity=1.0)
        
        assert new_w < old_w
        print(f"✅ LTD: вес {old_w:.3f} → {new_w:.3f}")
        
        # Тест 4: Обучение по Хеббу
        print("\n📝 Тест 4: Hebbian Learning")
        concepts = ["программирование", "python", "код", "разработка"]
        changes = plasticity.hebbian_learning(concepts, success=True)
        
        # Должно создаться C(4,2)*2 = 12 синапсов
        assert len(changes) == 12
        print(f"✅ Hebbian: создано/усилено {len(changes)} связей между 4 концепциями")
        
        # Тест 5: Создание нейронного пути
        print("\n📝 Тест 5: Создание нейронного пути")
        pathway = plasticity.create_pathway(
            name="greeting_response",
            nodes=["привет", "приветствие", "ответ", "улыбка"],
            description="Путь от приветствия к дружелюбному ответу"
        )
        
        assert pathway.name == "greeting_response"
        assert len(pathway.nodes) == 4
        print(f"✅ Путь создан: {pathway.name}, сила={pathway.total_strength:.3f}")
        
        # Тест 6: Активация пути
        print("\n📝 Тест 6: Активация нейронного пути")
        result = plasticity.activate_pathway(pathway.id, success=True)
        
        assert result["new_strength"] >= result["old_strength"]
        print(f"✅ Путь активирован: {result['old_strength']:.3f} → {result['new_strength']:.3f}")
        
        # Тест 7: Многократная активация (зрелость)
        print("\n📝 Тест 7: Достижение зрелости синапса")
        test_syn = plasticity.create_synapse("тест", "зрелость")
        
        for i in range(25):
            plasticity.activate_synapse(test_syn.id, success=True, intensity=0.5)
        
        updated_syn = plasticity.synapses[test_syn.id]
        assert updated_syn.is_mature == True
        assert updated_syn.activation_count >= 25
        print(f"✅ Синапс стал зрелым после {updated_syn.activation_count} активаций")
        print(f"   Итоговый вес: {updated_syn.weight:.3f}")
        
        # Тест 8: Поиск ассоциаций
        print("\n📝 Тест 8: Поиск ассоциаций")
        associations = plasticity.get_strongest_associations("кот")
        
        assert len(associations) >= 2
        print(f"✅ Найдено ассоциаций с 'кот': {len(associations)}")
        for assoc in associations[:3]:
            print(f"   → {assoc['concept']}: {assoc['weight']:.3f} ({assoc['direction']})")
        
        # Тест 9: Затухание (симуляция)
        print("\n📝 Тест 9: Затухание неиспользуемых синапсов")
        # Создаём "старый" синапс
        old_syn = plasticity.create_synapse("старое", "забытое")
        old_syn.last_activation = (datetime.now() - timedelta(days=30)).isoformat()
        old_syn.is_mature = False
        
        decayed = plasticity.decay_unused_synapses(days_threshold=7)
        print(f"✅ Затухло синапсов: {len(decayed)}")
        
        # Тест 10: Прюнинг
        print("\n📝 Тест 10: Синаптический прюнинг")
        # Создаём слабый синапс
        weak_syn = plasticity.create_synapse("слабый", "кандидат")
        weak_syn.weight = 0.01
        weak_syn.is_candidate_for_pruning = True
        
        pruned = plasticity.prune_weak_synapses()
        print(f"✅ Удалено слабых синапсов: {len(pruned)}")
        
        # Тест 11: Статистика
        print("\n📝 Тест 11: Статистика системы")
        stats = plasticity.get_statistics()
        
        print(f"✅ Статистика:")
        print(f"   • Синапсов: {stats['total_synapses']}")
        print(f"   • Зрелых: {stats['mature_synapses']}")
        print(f"   • Средний вес: {stats['average_weight']:.3f}")
        print(f"   • Путей: {stats['total_pathways']}")
        print(f"   • LTP/LTD ratio: {stats['plasticity_ratio']:.2f}")
        
        # Тест 12: Сохранение и загрузка
        print("\n📝 Тест 12: Сохранение и загрузка")
        plasticity._save()
        
        plasticity2 = SynapticPlasticity(data_dir=test_dir)
        
        assert len(plasticity2.synapses) == len(plasticity.synapses)
        assert len(plasticity2.pathways) == len(plasticity.pathways)
        print("✅ Данные успешно сохранены и загружены")
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 60)
        
    finally:
        shutil.rmtree(test_dir)
