"""
Neural Oscillations - нейронные осцилляции (ритмы мозга).

В мозге: разные частоты соответствуют разным состояниям:
- Delta (0.5-4 Hz): глубокий сон
- Theta (4-8 Hz): медитация, расслабление  
- Alpha (8-13 Hz): спокойное бодрствование
- Beta (13-30 Hz): активное мышление, концентрация
- Gamma (30-100 Hz): пиковая концентрация, инсайты

Для Нейры: переключение между когнитивными режимами,
синхронизация разных подсистем.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable, Any
from enum import Enum
import json
import math
import time
from pathlib import Path


class BrainWave(Enum):
    """Типы мозговых ритмов."""
    DELTA = "delta"   # Глубокий отдых, консолидация памяти
    THETA = "theta"   # Креативность, интуиция, мечтание
    ALPHA = "alpha"   # Спокойствие, готовность
    BETA = "beta"     # Активное мышление, работа
    GAMMA = "gamma"   # Пиковая концентрация, инсайты


@dataclass
class OscillationState:
    """Текущее состояние осцилляций."""
    dominant_wave: str
    wave_strengths: Dict[str, float]  # wave -> strength (0-1)
    coherence: float                   # Синхронизация (0-1)
    transition_in_progress: bool = False
    target_wave: Optional[str] = None
    state_duration_seconds: float = 0.0
    last_transition: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "dominant_wave": self.dominant_wave,
            "wave_strengths": self.wave_strengths,
            "coherence": self.coherence,
            "transition_in_progress": self.transition_in_progress,
            "target_wave": self.target_wave,
            "state_duration_seconds": self.state_duration_seconds,
            "last_transition": self.last_transition
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "OscillationState":
        return cls(**data)


@dataclass
class StateTransition:
    """Запись о переходе между состояниями."""
    from_wave: str
    to_wave: str
    trigger: str
    timestamp: str
    duration_ms: float
    
    def to_dict(self) -> Dict:
        return {
            "from_wave": self.from_wave,
            "to_wave": self.to_wave,
            "trigger": self.trigger,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms
        }


class NeuralOscillations:
    """
    Система нейронных осцилляций.
    
    Управляет когнитивными режимами и синхронизацией подсистем.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "neural_oscillations.json"
        
        # Текущее состояние
        self.state = OscillationState(
            dominant_wave=BrainWave.ALPHA.value,
            wave_strengths={w.value: 0.2 for w in BrainWave},
            coherence=0.7,
            last_transition=datetime.now().isoformat()
        )
        self.state.wave_strengths[BrainWave.ALPHA.value] = 0.6
        
        # История переходов
        self.transitions: List[StateTransition] = []
        
        # Конфигурация режимов
        self.mode_configs: Dict[str, Dict[str, Any]] = {
            BrainWave.DELTA.value: {
                "description": "Режим глубокого отдыха и консолидации",
                "processing_speed": 0.3,
                "creativity": 0.2,
                "focus": 0.1,
                "memory_consolidation": 1.0,
                "response_style": "minimal",
                "triggers": ["sleep", "maintenance", "consolidate"]
            },
            BrainWave.THETA.value: {
                "description": "Режим креативности и интуиции",
                "processing_speed": 0.5,
                "creativity": 1.0,
                "focus": 0.4,
                "memory_consolidation": 0.5,
                "response_style": "creative",
                "triggers": ["dream", "create", "imagine", "brainstorm"]
            },
            BrainWave.ALPHA.value: {
                "description": "Режим спокойной готовности",
                "processing_speed": 0.7,
                "creativity": 0.6,
                "focus": 0.6,
                "memory_consolidation": 0.3,
                "response_style": "balanced",
                "triggers": ["relax", "chat", "default"]
            },
            BrainWave.BETA.value: {
                "description": "Режим активной работы",
                "processing_speed": 1.0,
                "creativity": 0.4,
                "focus": 0.9,
                "memory_consolidation": 0.2,
                "response_style": "analytical",
                "triggers": ["work", "solve", "analyze", "help", "code"]
            },
            BrainWave.GAMMA.value: {
                "description": "Режим пиковой концентрации",
                "processing_speed": 1.0,
                "creativity": 0.8,
                "focus": 1.0,
                "memory_consolidation": 0.1,
                "response_style": "focused",
                "triggers": ["urgent", "critical", "important", "insight"]
            }
        }
        
        # Матрица переходов (от -> к: легкость перехода)
        self.transition_ease: Dict[str, Dict[str, float]] = {
            BrainWave.DELTA.value: {
                BrainWave.DELTA.value: 1.0,
                BrainWave.THETA.value: 0.8,
                BrainWave.ALPHA.value: 0.5,
                BrainWave.BETA.value: 0.2,
                BrainWave.GAMMA.value: 0.1
            },
            BrainWave.THETA.value: {
                BrainWave.DELTA.value: 0.7,
                BrainWave.THETA.value: 1.0,
                BrainWave.ALPHA.value: 0.8,
                BrainWave.BETA.value: 0.4,
                BrainWave.GAMMA.value: 0.3
            },
            BrainWave.ALPHA.value: {
                BrainWave.DELTA.value: 0.5,
                BrainWave.THETA.value: 0.7,
                BrainWave.ALPHA.value: 1.0,
                BrainWave.BETA.value: 0.8,
                BrainWave.GAMMA.value: 0.5
            },
            BrainWave.BETA.value: {
                BrainWave.DELTA.value: 0.2,
                BrainWave.THETA.value: 0.4,
                BrainWave.ALPHA.value: 0.7,
                BrainWave.BETA.value: 1.0,
                BrainWave.GAMMA.value: 0.8
            },
            BrainWave.GAMMA.value: {
                BrainWave.DELTA.value: 0.1,
                BrainWave.THETA.value: 0.3,
                BrainWave.ALPHA.value: 0.5,
                BrainWave.BETA.value: 0.8,
                BrainWave.GAMMA.value: 1.0
            }
        }
        
        # Подписчики на смену режима
        self._mode_listeners: List[Callable[[str, str], None]] = []
        
        # Время последнего обновления
        self._last_update = time.time()
        
        self._load()
    
    def _load(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if "state" in data:
                    self.state = OscillationState.from_dict(data["state"])
                
                for t_data in data.get("transitions", []):
                    self.transitions.append(StateTransition(**t_data))
                
            except Exception as e:
                print(f"Error loading neural oscillations: {e}")
    
    def _save(self):
        data = {
            "state": self.state.to_dict(),
            "transitions": [t.to_dict() for t in self.transitions[-200:]]
        }
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def detect_mode_from_context(self, context: str) -> BrainWave:
        """Определить нужный режим по контексту."""
        context_lower = context.lower()
        
        for wave in BrainWave:
            config = self.mode_configs[wave.value]
            for trigger in config.get("triggers", []):
                if trigger in context_lower:
                    return wave
        
        # Эвристики
        if any(w in context_lower for w in ["код", "программ", "функци", "ошибк", "баг"]):
            return BrainWave.BETA
        
        if any(w in context_lower for w in ["придумай", "креатив", "идея", "фантази"]):
            return BrainWave.THETA
        
        if any(w in context_lower for w in ["срочно", "важно", "критич", "быстро"]):
            return BrainWave.GAMMA
        
        if any(w in context_lower for w in ["привет", "как дела", "что нового"]):
            return BrainWave.ALPHA
        
        return BrainWave.ALPHA  # По умолчанию
    
    def transition_to(self, target: BrainWave, trigger: str = "manual") -> Dict[str, Any]:
        """
        Перейти к целевому состоянию.
        
        Returns:
            Информация о переходе
        """
        start_time = time.time()
        from_wave = self.state.dominant_wave
        to_wave = target.value
        
        if from_wave == to_wave:
            return {
                "success": True,
                "transition": False,
                "message": f"Уже в режиме {to_wave}",
                "mode": to_wave
            }
        
        # Получаем лёгкость перехода
        ease = self.transition_ease.get(from_wave, {}).get(to_wave, 0.5)
        
        # Помечаем начало перехода
        self.state.transition_in_progress = True
        self.state.target_wave = to_wave
        
        # Постепенно меняем силы волн
        for wave in BrainWave:
            if wave.value == to_wave:
                self.state.wave_strengths[wave.value] = 0.6 + 0.2 * ease
            elif wave.value == from_wave:
                self.state.wave_strengths[wave.value] = 0.3 * (1 - ease)
            else:
                self.state.wave_strengths[wave.value] = 0.1
        
        # Обновляем доминирующую волну
        self.state.dominant_wave = to_wave
        self.state.transition_in_progress = False
        self.state.target_wave = None
        self.state.coherence = 0.5 + 0.3 * ease  # Когерентность зависит от лёгкости
        self.state.state_duration_seconds = 0.0
        self.state.last_transition = datetime.now().isoformat()
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Записываем переход
        transition = StateTransition(
            from_wave=from_wave,
            to_wave=to_wave,
            trigger=trigger,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms
        )
        self.transitions.append(transition)
        
        # Уведомляем слушателей
        for listener in self._mode_listeners:
            try:
                listener(from_wave, to_wave)
            except Exception:
                pass
        
        self._save()
        
        return {
            "success": True,
            "transition": True,
            "from": from_wave,
            "to": to_wave,
            "ease": ease,
            "coherence": self.state.coherence,
            "duration_ms": duration_ms,
            "mode_config": self.mode_configs[to_wave]
        }
    
    def get_current_mode(self) -> Dict[str, Any]:
        """Получить текущий режим и его параметры."""
        self._update_duration()
        
        mode = self.state.dominant_wave
        config = self.mode_configs.get(mode, {})
        
        return {
            "mode": mode,
            "description": config.get("description", ""),
            "wave_strengths": self.state.wave_strengths,
            "coherence": self.state.coherence,
            "duration_seconds": self.state.state_duration_seconds,
            "processing_speed": config.get("processing_speed", 0.7),
            "creativity": config.get("creativity", 0.5),
            "focus": config.get("focus", 0.5),
            "response_style": config.get("response_style", "balanced")
        }
    
    def _update_duration(self):
        """Обновить время в текущем состоянии."""
        current = time.time()
        delta = current - self._last_update
        self.state.state_duration_seconds += delta
        self._last_update = current
    
    def get_modifiers(self) -> Dict[str, float]:
        """
        Получить модификаторы для обработки запросов.
        
        Возвращает коэффициенты для разных аспектов.
        """
        mode = self.state.dominant_wave
        config = self.mode_configs.get(mode, {})
        
        return {
            "processing_speed": config.get("processing_speed", 0.7),
            "creativity": config.get("creativity", 0.5),
            "focus": config.get("focus", 0.5),
            "memory_consolidation": config.get("memory_consolidation", 0.3),
            "coherence": self.state.coherence
        }
    
    def add_mode_listener(self, callback: Callable[[str, str], None]):
        """Добавить слушателя смены режима."""
        self._mode_listeners.append(callback)
    
    def auto_adjust(self, context: str) -> Optional[Dict[str, Any]]:
        """
        Автоматически подстроить режим под контекст.
        
        Returns:
            Информация о переходе или None если не требуется
        """
        suggested_mode = self.detect_mode_from_context(context)
        
        if suggested_mode.value != self.state.dominant_wave:
            return self.transition_to(suggested_mode, trigger=f"auto:{context[:30]}")
        
        return None
    
    def stabilize(self, amount: float = 0.1):
        """Стабилизировать текущее состояние (повысить когерентность)."""
        self.state.coherence = min(1.0, self.state.coherence + amount)
        
        # Усилить доминирующую волну
        dominant = self.state.dominant_wave
        self.state.wave_strengths[dominant] = min(
            0.9, 
            self.state.wave_strengths[dominant] + amount
        )
        
        # Ослабить остальные
        for wave in BrainWave:
            if wave.value != dominant:
                self.state.wave_strengths[wave.value] = max(
                    0.05,
                    self.state.wave_strengths[wave.value] - amount * 0.3
                )
        
        self._save()
    
    def destabilize(self, amount: float = 0.1):
        """Дестабилизировать состояние (подготовка к переходу)."""
        self.state.coherence = max(0.2, self.state.coherence - amount)
        self._save()
    
    def natural_drift(self):
        """
        Естественный дрейф к Alpha (состояние покоя).
        
        Вызывать периодически при отсутствии активности.
        """
        if self.state.dominant_wave == BrainWave.ALPHA.value:
            self.stabilize(0.05)
            return
        
        # Дрейф к альфа через промежуточные состояния
        current = self.state.dominant_wave
        
        # Высокочастотные -> Beta -> Alpha
        if current == BrainWave.GAMMA.value:
            self.destabilize(0.1)
            if self.state.coherence < 0.4:
                self.transition_to(BrainWave.BETA, "natural_drift")
        
        elif current == BrainWave.BETA.value:
            self.destabilize(0.05)
            if self.state.coherence < 0.4:
                self.transition_to(BrainWave.ALPHA, "natural_drift")
        
        # Низкочастотные -> Theta -> Alpha
        elif current == BrainWave.DELTA.value:
            self.destabilize(0.05)
            if self.state.coherence < 0.4:
                self.transition_to(BrainWave.THETA, "natural_drift")
        
        elif current == BrainWave.THETA.value:
            self.destabilize(0.03)
            if self.state.coherence < 0.4:
                self.transition_to(BrainWave.ALPHA, "natural_drift")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Статистика осцилляций."""
        self._update_duration()
        
        # Подсчёт переходов по типам
        transition_counts: Dict[str, int] = {}
        for t in self.transitions:
            key = f"{t.from_wave}->{t.to_wave}"
            transition_counts[key] = transition_counts.get(key, 0) + 1
        
        return {
            "current_mode": self.state.dominant_wave,
            "coherence": self.state.coherence,
            "state_duration_seconds": self.state.state_duration_seconds,
            "wave_strengths": self.state.wave_strengths,
            "total_transitions": len(self.transitions),
            "transition_counts": transition_counts,
            "last_transition": self.state.last_transition
        }


# Singleton
_neural_oscillations: Optional[NeuralOscillations] = None

def get_neural_oscillations() -> NeuralOscillations:
    global _neural_oscillations
    if _neural_oscillations is None:
        _neural_oscillations = NeuralOscillations()
    return _neural_oscillations
