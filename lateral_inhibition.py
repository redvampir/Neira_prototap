"""
Lateral Inhibition - laterapьное торможение.

В мозге: когда один нейрон активируется сильно, он подавляет
соседей. Это создает контраст и фокус внимания.

Для Нейры: активная тема подавляет конкурирующие,
усиливая фокус на текущем контексте.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from enum import Enum
import json
import math
from pathlib import Path


class TopicCategory(Enum):
    """Категории тем для группировки."""
    TECHNICAL = "technical"
    EMOTIONAL = "emotional"
    CREATIVE = "creative"
    FACTUAL = "factual"
    PHILOSOPHICAL = "philosophical"
    PRACTICAL = "practical"
    SOCIAL = "social"


@dataclass
class ActiveTopic:
    """Активная тема в сознании."""
    topic_id: str
    name: str
    category: str
    activation: float = 0.0       # Текущая активация (0-1)
    base_activation: float = 0.0  # Базовая активация до торможения
    inhibited_by: List[str] = field(default_factory=list)
    last_activated: str = ""
    activation_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "topic_id": self.topic_id,
            "name": self.name,
            "category": self.category,
            "activation": self.activation,
            "base_activation": self.base_activation,
            "inhibited_by": self.inhibited_by,
            "last_activated": self.last_activated,
            "activation_count": self.activation_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ActiveTopic":
        return cls(
            topic_id=data["topic_id"],
            name=data["name"],
            category=data["category"],
            activation=data.get("activation", 0.0),
            base_activation=data.get("base_activation", 0.0),
            inhibited_by=data.get("inhibited_by", []),
            last_activated=data.get("last_activated", ""),
            activation_count=data.get("activation_count", 0)
        )


class LateralInhibition:
    """
    Система латерального торможения.
    
    Управляет фокусом внимания через подавление
    конкурирующих тем и усиление активной.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "lateral_inhibition.json"
        
        # Активные темы
        self.topics: Dict[str, ActiveTopic] = {}
        
        # Матрица ингибирования (какие категории тормозят какие)
        self.inhibition_matrix = {
            "technical": {"emotional": 0.6, "creative": 0.3, "philosophical": 0.2},
            "emotional": {"technical": 0.5, "factual": 0.4},
            "creative": {"factual": 0.5, "technical": 0.3},
            "factual": {"creative": 0.4, "emotional": 0.3},
            "philosophical": {"practical": 0.4, "factual": 0.2},
            "practical": {"philosophical": 0.3, "creative": 0.2},
            "social": {"technical": 0.4}
        }
        
        # Конфигурация
        self.config = {
            "decay_rate": 0.1,           # Затухание активации за цикл
            "inhibition_strength": 0.5,  # Сила торможения
            "winner_boost": 1.5,         # Усиление победителя
            "min_activation": 0.05,      # Минимальный порог
            "max_active_topics": 5       # Макс активных тем
        }
        
        self._load()
    
    def _load(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for tid, tdata in data.get("topics", {}).items():
                    self.topics[tid] = ActiveTopic.from_dict(tdata)
            except Exception as e:
                print(f"Error loading lateral inhibition: {e}")
    
    def _save(self):
        data = {"topics": {tid: t.to_dict() for tid, t in self.topics.items()}}
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def activate_topic(
        self, 
        topic_id: str, 
        name: str, 
        category: str,
        strength: float = 1.0
    ) -> Dict[str, Any]:
        """
        Активировать тему и применить латеральное торможение.
        
        Returns:
            Словарь с результатами: активная тема, подавленные темы
        """
        now = datetime.now().isoformat()
        
        # Создаем или обновляем тему
        if topic_id not in self.topics:
            self.topics[topic_id] = ActiveTopic(
                topic_id=topic_id,
                name=name,
                category=category
            )
        
        topic = self.topics[topic_id]
        topic.base_activation = min(1.0, strength)
        topic.activation = topic.base_activation * self.config["winner_boost"]
        topic.activation = min(1.0, topic.activation)
        topic.last_activated = now
        topic.activation_count += 1
        topic.inhibited_by = []
        
        # Применяем латеральное торможение к другим темам
        inhibited = []
        for other_id, other_topic in self.topics.items():
            if other_id == topic_id:
                continue
            
            # Рассчитываем силу торможения
            inhibition = self._calculate_inhibition(topic, other_topic)
            
            if inhibition > 0:
                other_topic.activation = max(
                    self.config["min_activation"],
                    other_topic.activation - inhibition
                )
                other_topic.inhibited_by.append(topic_id)
                inhibited.append({
                    "topic_id": other_id,
                    "name": other_topic.name,
                    "inhibition": inhibition,
                    "new_activation": other_topic.activation
                })
        
        # Очищаем слабые темы
        self._cleanup_weak_topics()
        
        self._save()
        
        return {
            "active_topic": {
                "id": topic_id,
                "name": name,
                "activation": topic.activation
            },
            "inhibited_topics": inhibited,
            "total_active": len([t for t in self.topics.values() 
                               if t.activation > self.config["min_activation"]])
        }
    
    def _calculate_inhibition(self, active: ActiveTopic, target: ActiveTopic) -> float:
        """Рассчитать силу торможения между темами."""
        # Базовое торможение от силы активации
        base_inhibition = active.activation * self.config["inhibition_strength"]
        
        # Модификатор от категорий (из матрицы)
        category_mod = self.inhibition_matrix.get(
            active.category, {}
        ).get(target.category, 0.1)
        
        # Итоговое торможение
        return base_inhibition * category_mod * target.activation
    
    def _cleanup_weak_topics(self):
        """Удалить слабо активные темы."""
        threshold = self.config["min_activation"]
        to_remove = [
            tid for tid, topic in self.topics.items()
            if topic.activation < threshold
        ]
        for tid in to_remove:
            del self.topics[tid]
    
    def apply_decay(self):
        """Применить затухание ко всем темам."""
        decay = self.config["decay_rate"]
        for topic in self.topics.values():
            topic.activation = max(0, topic.activation - decay)
        self._cleanup_weak_topics()
        self._save()
    
    def get_focus(self) -> Optional[ActiveTopic]:
        """Получить текущий фокус внимания (самая активная тема)."""
        if not self.topics:
            return None
        return max(self.topics.values(), key=lambda t: t.activation)
    
    def get_active_topics(self, min_activation: float = 0.1) -> List[ActiveTopic]:
        """Получить все активные темы выше порога."""
        return sorted(
            [t for t in self.topics.values() if t.activation >= min_activation],
            key=lambda t: t.activation,
            reverse=True
        )
    
    def get_context_filter(self) -> Set[str]:
        """
        Получить фильтр контекста на основе активных тем.
        
        Используется для фильтрации нерелевантной информации.
        """
        focus = self.get_focus()
        if not focus:
            return set()
        
        # Возвращаем категории, которые НЕ тормозятся текущим фокусом
        inhibited_categories = set(
            self.inhibition_matrix.get(focus.category, {}).keys()
        )
        
        all_categories = set(c.value for c in TopicCategory)
        return all_categories - inhibited_categories
    
    def get_statistics(self) -> Dict[str, Any]:
        """Статистика системы торможения."""
        if not self.topics:
            return {"total_topics": 0}
        
        focus = self.get_focus()
        by_category = {}
        for t in self.topics.values():
            by_category[t.category] = by_category.get(t.category, 0) + 1
        
        return {
            "total_topics": len(self.topics),
            "active_topics": len(self.get_active_topics()),
            "current_focus": focus.name if focus else None,
            "focus_activation": focus.activation if focus else 0,
            "by_category": by_category,
            "avg_activation": sum(t.activation for t in self.topics.values()) / len(self.topics)
        }


# Singleton
_lateral_inhibition: Optional[LateralInhibition] = None

def get_lateral_inhibition() -> LateralInhibition:
    global _lateral_inhibition
    if _lateral_inhibition is None:
        _lateral_inhibition = LateralInhibition()
    return _lateral_inhibition
