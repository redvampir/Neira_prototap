"""
Synaptic Pruning - синаптический прунинг.

В мозге: устранение слабых и неиспользуемых синапсов,
особенно активен в детстве и подростковом возрасте.
"Use it or lose it" - нейроны, которые не используются, отмирают.

Для Нейры: автоматическое удаление редко используемых знаний,
оптимизация базы знаний.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set, Any
from enum import Enum
import json
from pathlib import Path


class PruningStrategy(Enum):
    """Стратегии прунинга."""
    AGE_BASED = "age_based"          # По возрасту (старые неиспользуемые)
    USAGE_BASED = "usage_based"      # По частоте использования
    STRENGTH_BASED = "strength_based" # По силе связи
    REDUNDANCY = "redundancy"         # Удаление дубликатов
    HYBRID = "hybrid"                 # Комбинация стратегий


@dataclass 
class SynapticConnection:
    """Синаптическая связь (элемент знаний/памяти)."""
    connection_id: str
    source: str                # Источник связи
    target: str                # Цель связи
    strength: float            # Сила связи (0-1)
    usage_count: int = 0       # Количество использований
    last_used: str = ""        # Последнее использование
    created_at: str = ""
    category: str = "general"
    protected: bool = False    # Защищено от прунинга
    pruning_score: float = 0.0 # Оценка для прунинга (выше = более вероятно удаление)
    
    def to_dict(self) -> Dict:
        return {
            "connection_id": self.connection_id,
            "source": self.source,
            "target": self.target,
            "strength": self.strength,
            "usage_count": self.usage_count,
            "last_used": self.last_used,
            "created_at": self.created_at,
            "category": self.category,
            "protected": self.protected,
            "pruning_score": self.pruning_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SynapticConnection":
        return cls(**data)


@dataclass
class PruningEvent:
    """Событие прунинга."""
    event_id: str
    timestamp: str
    strategy: str
    pruned_count: int
    total_before: int
    total_after: int
    pruned_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "strategy": self.strategy,
            "pruned_count": self.pruned_count,
            "total_before": self.total_before,
            "total_after": self.total_after,
            "pruned_ids": self.pruned_ids
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "PruningEvent":
        return cls(**data)


class SynapticPruning:
    """
    Система синаптического прунинга.
    
    Автоматически удаляет слабые и неиспользуемые связи.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "synaptic_pruning.json"
        
        # Все синаптические связи
        self.connections: Dict[str, SynapticConnection] = {}
        
        # История прунинга
        self.pruning_history: List[PruningEvent] = []
        
        # Статистика
        self.total_pruned = 0
        self.last_pruning: Optional[str] = None
        
        # Конфигурация
        self.config = {
            # Пороги для прунинга
            "min_strength_threshold": 0.1,      # Минимальная сила для сохранения
            "min_usage_threshold": 2,           # Минимум использований
            "max_age_days": 90,                 # Максимальный возраст неиспользуемой связи
            "inactive_days_threshold": 30,      # Дней неактивности
            
            # Защита
            "protect_recent_days": 7,           # Защита свежих связей
            "protect_high_strength": 0.8,       # Защита сильных связей
            "protect_categories": ["core", "identity", "important"],
            
            # Лимиты
            "max_prune_per_run": 50,            # Максимум за один запуск
            "pruning_cooldown_hours": 24,       # Часов между прунингами
            "min_connections_keep": 100,        # Минимум связей сохранить
        }
        
        self._load()
    
    def _load(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for cid, cdata in data.get("connections", {}).items():
                    self.connections[cid] = SynapticConnection.from_dict(cdata)
                
                for pdata in data.get("pruning_history", []):
                    self.pruning_history.append(PruningEvent.from_dict(pdata))
                
                self.total_pruned = data.get("total_pruned", 0)
                self.last_pruning = data.get("last_pruning")
                
            except Exception as e:
                print(f"Error loading synaptic pruning: {e}")
    
    def _save(self):
        data = {
            "connections": {cid: c.to_dict() for cid, c in self.connections.items()},
            "pruning_history": [p.to_dict() for p in self.pruning_history[-100:]],
            "total_pruned": self.total_pruned,
            "last_pruning": self.last_pruning
        }
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_id(self) -> str:
        import hashlib
        import random
        data = f"{datetime.now().isoformat()}{random.random()}"
        return hashlib.md5(data.encode()).hexdigest()[:12]
    
    def add_connection(
        self,
        source: str,
        target: str,
        strength: float = 0.5,
        category: str = "general",
        protected: bool = False
    ) -> SynapticConnection:
        """Добавить синаптическую связь."""
        connection = SynapticConnection(
            connection_id=self._generate_id(),
            source=source,
            target=target,
            strength=min(1.0, max(0.0, strength)),
            usage_count=1,
            last_used=datetime.now().isoformat(),
            created_at=datetime.now().isoformat(),
            category=category,
            protected=protected
        )
        
        self.connections[connection.connection_id] = connection
        self._save()
        
        return connection
    
    def use_connection(self, connection_id: str, strength_boost: float = 0.05):
        """Отметить использование связи (усиливает её)."""
        if connection_id in self.connections:
            conn = self.connections[connection_id]
            conn.usage_count += 1
            conn.last_used = datetime.now().isoformat()
            conn.strength = min(1.0, conn.strength + strength_boost)
            conn.pruning_score = max(0.0, conn.pruning_score - 0.1)  # Снижаем риск прунинга
            self._save()
    
    def calculate_pruning_scores(self):
        """Рассчитать оценки прунинга для всех связей."""
        now = datetime.now()
        
        for conn in self.connections.values():
            if conn.protected or conn.category in self.config["protect_categories"]:
                conn.pruning_score = 0.0
                continue
            
            score = 0.0
            
            # Фактор возраста
            try:
                created = datetime.fromisoformat(conn.created_at)
                age_days = (now - created).days
                if age_days > self.config["max_age_days"]:
                    score += 0.3
            except:
                pass
            
            # Фактор неактивности
            try:
                last = datetime.fromisoformat(conn.last_used)
                inactive_days = (now - last).days
                if inactive_days > self.config["inactive_days_threshold"]:
                    score += 0.3 * (inactive_days / self.config["max_age_days"])
            except:
                pass
            
            # Фактор слабой силы
            if conn.strength < self.config["min_strength_threshold"]:
                score += 0.4
            elif conn.strength < 0.3:
                score += 0.2
            
            # Фактор низкого использования
            if conn.usage_count < self.config["min_usage_threshold"]:
                score += 0.2
            
            # Защита сильных связей
            if conn.strength > self.config["protect_high_strength"]:
                score = max(0.0, score - 0.5)
            
            # Защита недавних связей
            try:
                created = datetime.fromisoformat(conn.created_at)
                if (now - created).days < self.config["protect_recent_days"]:
                    score = 0.0
            except:
                pass
            
            conn.pruning_score = min(1.0, score)
        
        self._save()
    
    def run_pruning(
        self, 
        strategy: PruningStrategy = PruningStrategy.HYBRID,
        force: bool = False
    ) -> PruningEvent:
        """
        Запустить прунинг.
        
        Args:
            strategy: Стратегия прунинга
            force: Игнорировать cooldown
            
        Returns:
            PruningEvent с результатами
        """
        # Проверка cooldown
        if not force and self.last_pruning:
            try:
                last = datetime.fromisoformat(self.last_pruning)
                hours_passed = (datetime.now() - last).total_seconds() / 3600
                if hours_passed < self.config["pruning_cooldown_hours"]:
                    return PruningEvent(
                        event_id=self._generate_id(),
                        timestamp=datetime.now().isoformat(),
                        strategy=strategy.value,
                        pruned_count=0,
                        total_before=len(self.connections),
                        total_after=len(self.connections),
                        pruned_ids=[]
                    )
            except:
                pass
        
        # Пересчитываем оценки
        self.calculate_pruning_scores()
        
        total_before = len(self.connections)
        
        # Находим кандидатов на удаление
        candidates: List[SynapticConnection] = []
        
        for conn in self.connections.values():
            if conn.protected or conn.category in self.config["protect_categories"]:
                continue
            
            if strategy == PruningStrategy.AGE_BASED:
                if self._should_prune_by_age(conn):
                    candidates.append(conn)
            
            elif strategy == PruningStrategy.USAGE_BASED:
                if self._should_prune_by_usage(conn):
                    candidates.append(conn)
            
            elif strategy == PruningStrategy.STRENGTH_BASED:
                if self._should_prune_by_strength(conn):
                    candidates.append(conn)
            
            elif strategy == PruningStrategy.HYBRID:
                if conn.pruning_score > 0.6:  # Комбинированная оценка
                    candidates.append(conn)
        
        # Сортируем по оценке прунинга
        candidates.sort(key=lambda c: c.pruning_score, reverse=True)
        
        # Ограничиваем количество
        max_to_prune = min(
            self.config["max_prune_per_run"],
            max(0, total_before - self.config["min_connections_keep"])
        )
        candidates = candidates[:max_to_prune]
        
        # Удаляем
        pruned_ids = []
        for conn in candidates:
            pruned_ids.append(conn.connection_id)
            del self.connections[conn.connection_id]
        
        # Создаём событие
        event = PruningEvent(
            event_id=self._generate_id(),
            timestamp=datetime.now().isoformat(),
            strategy=strategy.value,
            pruned_count=len(pruned_ids),
            total_before=total_before,
            total_after=len(self.connections),
            pruned_ids=pruned_ids
        )
        
        self.pruning_history.append(event)
        self.total_pruned += len(pruned_ids)
        self.last_pruning = datetime.now().isoformat()
        
        self._save()
        
        return event
    
    def _should_prune_by_age(self, conn: SynapticConnection) -> bool:
        """Проверка по возрасту."""
        try:
            last_used = datetime.fromisoformat(conn.last_used)
            days_inactive = (datetime.now() - last_used).days
            return days_inactive > self.config["inactive_days_threshold"]
        except:
            return False
    
    def _should_prune_by_usage(self, conn: SynapticConnection) -> bool:
        """Проверка по использованию."""
        return conn.usage_count < self.config["min_usage_threshold"]
    
    def _should_prune_by_strength(self, conn: SynapticConnection) -> bool:
        """Проверка по силе."""
        return conn.strength < self.config["min_strength_threshold"]
    
    def protect_connection(self, connection_id: str, protected: bool = True):
        """Защитить/снять защиту с связи."""
        if connection_id in self.connections:
            self.connections[connection_id].protected = protected
            self._save()
    
    def get_weak_connections(self, limit: int = 20) -> List[SynapticConnection]:
        """Получить слабые связи (кандидаты на удаление)."""
        self.calculate_pruning_scores()
        connections = sorted(
            self.connections.values(), 
            key=lambda c: c.pruning_score, 
            reverse=True
        )
        return [c for c in connections if not c.protected][:limit]
    
    def get_strong_connections(self, limit: int = 20) -> List[SynapticConnection]:
        """Получить сильные связи."""
        return sorted(
            self.connections.values(),
            key=lambda c: c.strength,
            reverse=True
        )[:limit]
    
    def decay_all_connections(self, decay_rate: float = 0.01):
        """Естественное угасание всех связей."""
        for conn in self.connections.values():
            if not conn.protected and conn.category not in self.config["protect_categories"]:
                conn.strength = max(0.0, conn.strength - decay_rate)
        self._save()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Статистика системы прунинга."""
        strengths = [c.strength for c in self.connections.values()]
        
        return {
            "total_connections": len(self.connections),
            "total_pruned": self.total_pruned,
            "protected_count": sum(1 for c in self.connections.values() if c.protected),
            "avg_strength": sum(strengths) / len(strengths) if strengths else 0,
            "min_strength": min(strengths) if strengths else 0,
            "max_strength": max(strengths) if strengths else 0,
            "weak_connections": len([c for c in self.connections.values() if c.strength < 0.3]),
            "pruning_events": len(self.pruning_history),
            "last_pruning": self.last_pruning
        }


# Singleton
_synaptic_pruning: Optional[SynapticPruning] = None

def get_synaptic_pruning() -> SynapticPruning:
    global _synaptic_pruning
    if _synaptic_pruning is None:
        _synaptic_pruning = SynapticPruning()
    return _synaptic_pruning
