"""
Neurotransmitter System — Нейромедиаторная система Нейры.

Моделирует влияние "нейромедиаторов" на поведение:
- Дофамин: мотивация, награда, обучение
- Серотонин: настроение, стабильность, спокойствие
- Норадреналин: внимание, бдительность, энергия
- ГАМК: торможение, расслабление, фильтрация
- Ацетилхолин: память, обучение, концентрация
- Эндорфины: удовольствие, снижение стресса

Каждый медиатор влияет на конкретные аспекты обработки.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json
import math
import os
from pathlib import Path


class Neurotransmitter(Enum):
    """Нейромедиаторы и их функции."""
    DOPAMINE = "dopamine"           # Мотивация, награда
    SEROTONIN = "serotonin"         # Настроение, стабильность
    NOREPINEPHRINE = "norepinephrine"  # Внимание, бдительность
    GABA = "gaba"                   # Торможение, спокойствие
    ACETYLCHOLINE = "acetylcholine"  # Память, обучение
    ENDORPHIN = "endorphin"         # Удовольствие, комфорт


@dataclass
class NeurotransmitterState:
    """Состояние одного нейромедиатора."""
    name: str
    level: float = 0.5          # Уровень (0.0 - 1.0)
    baseline: float = 0.5       # Базовый уровень
    decay_rate: float = 0.1     # Скорость возврата к baseline
    last_update: str = ""
    
    # Границы
    min_level: float = 0.1
    max_level: float = 1.0
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "level": self.level,
            "baseline": self.baseline,
            "decay_rate": self.decay_rate,
            "last_update": self.last_update,
            "min_level": self.min_level,
            "max_level": self.max_level
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "NeurotransmitterState":
        return cls(
            name=data["name"],
            level=data.get("level", 0.5),
            baseline=data.get("baseline", 0.5),
            decay_rate=data.get("decay_rate", 0.1),
            last_update=data.get("last_update", ""),
            min_level=data.get("min_level", 0.1),
            max_level=data.get("max_level", 1.0)
        )


@dataclass
class NeurotransmitterEvent:
    """Событие изменения нейромедиатора."""
    timestamp: str
    neurotransmitter: str
    old_level: float
    new_level: float
    trigger: str
    source: str  # Что вызвало: "reward", "stress", "success", "failure", etc.


class BehaviorModifier:
    """Модификаторы поведения на основе уровней нейромедиаторов."""
    
    @staticmethod
    def calculate_response_enthusiasm(dopamine: float, serotonin: float) -> float:
        """
        Энтузиазм ответа (0.0 - 1.0).
        
        Высокий дофамин + серотонин = воодушевлённый ответ.
        """
        return (dopamine * 0.6 + serotonin * 0.4)
    
    @staticmethod
    def calculate_response_caution(norepinephrine: float, gaba: float) -> float:
        """
        Осторожность ответа (0.0 - 1.0).
        
        Высокий норадреналин + низкий GABA = более осторожный.
        """
        return norepinephrine * (1 - gaba * 0.5)
    
    @staticmethod
    def calculate_memory_strength(acetylcholine: float, dopamine: float) -> float:
        """
        Сила запоминания (0.0 - 1.0).
        
        Высокий ацетилхолин + дофамин = лучше запоминается.
        """
        return (acetylcholine * 0.7 + dopamine * 0.3)
    
    @staticmethod
    def calculate_creativity(dopamine: float, serotonin: float, gaba: float) -> float:
        """
        Креативность (0.0 - 1.0).
        
        Оптимальный дофамин + низкий GABA = больше креативности.
        """
        # Перевёрнутая U: слишком много дофамина = хаос, мало = скука
        optimal_dopamine = 1 - abs(dopamine - 0.7) * 2
        return max(0, optimal_dopamine * (1 - gaba * 0.3) * (0.5 + serotonin * 0.5))
    
    @staticmethod
    def calculate_focus(norepinephrine: float, acetylcholine: float) -> float:
        """
        Фокус/концентрация (0.0 - 1.0).
        """
        return (norepinephrine * 0.5 + acetylcholine * 0.5)
    
    @staticmethod
    def calculate_emotional_warmth(serotonin: float, endorphin: float) -> float:
        """
        Эмоциональная теплота в ответе (0.0 - 1.0).
        """
        return (serotonin * 0.6 + endorphin * 0.4)


class NeurotransmitterSystem:
    """
    Нейромедиаторная система Нейры.
    
    Управляет уровнями "нейромедиаторов" и их влиянием
    на поведение и ответы.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "neurotransmitters.json"
        
        # Состояния нейромедиаторов
        self.states: Dict[str, NeurotransmitterState] = {}
        
        # История событий
        self.event_history: List[NeurotransmitterEvent] = []
        
        # Инициализация
        self._init_neurotransmitters()
        self._load()
    
    def _init_neurotransmitters(self):
        """Инициализация нейромедиаторов с базовыми настройками."""
        defaults = {
            Neurotransmitter.DOPAMINE: {
                "baseline": 0.5,
                "decay_rate": 0.15,  # Быстро падает
                "description": "Мотивация и награда"
            },
            Neurotransmitter.SEROTONIN: {
                "baseline": 0.6,
                "decay_rate": 0.05,  # Медленно меняется
                "description": "Настроение и стабильность"
            },
            Neurotransmitter.NOREPINEPHRINE: {
                "baseline": 0.4,
                "decay_rate": 0.2,   # Быстро реагирует
                "description": "Внимание и бдительность"
            },
            Neurotransmitter.GABA: {
                "baseline": 0.5,
                "decay_rate": 0.08,
                "description": "Торможение и спокойствие"
            },
            Neurotransmitter.ACETYLCHOLINE: {
                "baseline": 0.5,
                "decay_rate": 0.1,
                "description": "Память и обучение"
            },
            Neurotransmitter.ENDORPHIN: {
                "baseline": 0.4,
                "decay_rate": 0.12,
                "description": "Удовольствие и комфорт"
            }
        }
        
        for nt, config in defaults.items():
            if nt.value not in self.states:
                self.states[nt.value] = NeurotransmitterState(
                    name=nt.value,
                    level=config["baseline"],
                    baseline=config["baseline"],
                    decay_rate=config["decay_rate"]
                )
    
    def _load(self):
        """Загрузка состояния."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for nt_data in data.get("states", []):
                    state = NeurotransmitterState.from_dict(nt_data)
                    self.states[state.name] = state
                
            except Exception as e:
                print(f"Ошибка загрузки NeurotransmitterSystem: {e}")
    
    def _save(self):
        """Сохранение состояния."""
        data = {
            "states": [s.to_dict() for s in self.states.values()],
            "event_history": [
                {
                    "timestamp": e.timestamp,
                    "neurotransmitter": e.neurotransmitter,
                    "old_level": e.old_level,
                    "new_level": e.new_level,
                    "trigger": e.trigger,
                    "source": e.source
                }
                for e in self.event_history[-500:]  # Последние 500 событий
            ]
        }
        
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_level(self, neurotransmitter: Neurotransmitter) -> float:
        """Получить текущий уровень нейромедиатора."""
        state = self.states.get(neurotransmitter.value)
        return state.level if state else 0.5
    
    def set_level(
        self,
        neurotransmitter: Neurotransmitter,
        level: float,
        trigger: str = "manual",
        source: str = "system"
    ) -> Tuple[float, float]:
        """
        Установить уровень нейромедиатора.
        
        Returns:
            Tuple[old_level, new_level]
        """
        state = self.states.get(neurotransmitter.value)
        if not state:
            return 0.5, 0.5
        
        old_level = state.level
        state.level = max(state.min_level, min(state.max_level, level))
        state.last_update = datetime.now().isoformat()
        
        # Записываем событие
        event = NeurotransmitterEvent(
            timestamp=datetime.now().isoformat(),
            neurotransmitter=neurotransmitter.value,
            old_level=old_level,
            new_level=state.level,
            trigger=trigger,
            source=source
        )
        self.event_history.append(event)
        
        self._save()
        return old_level, state.level
    
    def adjust_level(
        self,
        neurotransmitter: Neurotransmitter,
        delta: float,
        trigger: str = "adjustment",
        source: str = "system"
    ) -> Tuple[float, float]:
        """
        Изменить уровень нейромедиатора на delta.
        
        Args:
            neurotransmitter: Какой медиатор
            delta: Изменение (положительное или отрицательное)
            trigger: Причина изменения
            source: Источник
        
        Returns:
            Tuple[old_level, new_level]
        """
        state = self.states.get(neurotransmitter.value)
        if not state:
            return 0.5, 0.5
        
        new_level = state.level + delta
        return self.set_level(neurotransmitter, new_level, trigger, source)
    
    def decay_to_baseline(self):
        """
        Постепенный возврат всех уровней к базовым.
        
        Вызывается периодически для симуляции гомеостаза.
        """
        for state in self.states.values():
            if abs(state.level - state.baseline) < 0.01:
                continue  # Уже на базовом
            
            # Движение к baseline
            diff = state.baseline - state.level
            adjustment = diff * state.decay_rate
            
            old_level = state.level
            state.level += adjustment
            state.last_update = datetime.now().isoformat()
    
    def on_positive_feedback(self, intensity: float = 1.0):
        """
        Реакция на позитивный feedback от пользователя.
        
        Повышает дофамин, серотонин, эндорфины.
        """
        self.adjust_level(Neurotransmitter.DOPAMINE, 0.15 * intensity, 
                         "positive_feedback", "user")
        self.adjust_level(Neurotransmitter.SEROTONIN, 0.08 * intensity,
                         "positive_feedback", "user")
        self.adjust_level(Neurotransmitter.ENDORPHIN, 0.12 * intensity,
                         "positive_feedback", "user")
    
    def on_negative_feedback(self, intensity: float = 1.0):
        """
        Реакция на негативный feedback.
        
        Снижает дофамин, повышает норадреналин (бдительность).
        """
        self.adjust_level(Neurotransmitter.DOPAMINE, -0.1 * intensity,
                         "negative_feedback", "user")
        self.adjust_level(Neurotransmitter.NOREPINEPHRINE, 0.1 * intensity,
                         "negative_feedback", "user")
        self.adjust_level(Neurotransmitter.SEROTONIN, -0.05 * intensity,
                         "negative_feedback", "user")
    
    def on_successful_task(self, difficulty: float = 0.5):
        """
        Реакция на успешное выполнение задачи.
        
        Args:
            difficulty: Сложность задачи (0.0 - 1.0)
        """
        # Награда пропорциональна сложности
        reward = 0.1 + difficulty * 0.15
        
        self.adjust_level(Neurotransmitter.DOPAMINE, reward,
                         "task_success", "task")
        self.adjust_level(Neurotransmitter.ACETYLCHOLINE, 0.08,
                         "learning", "task")
        self.adjust_level(Neurotransmitter.ENDORPHIN, reward * 0.5,
                         "accomplishment", "task")
    
    def on_failed_task(self):
        """Реакция на неудачу."""
        self.adjust_level(Neurotransmitter.DOPAMINE, -0.08,
                         "task_failure", "task")
        self.adjust_level(Neurotransmitter.NOREPINEPHRINE, 0.12,
                         "alertness", "task")
    
    def on_interesting_input(self, novelty: float = 0.5):
        """
        Реакция на интересный/новый input.
        
        Args:
            novelty: Новизна (0.0 - 1.0)
        """
        self.adjust_level(Neurotransmitter.DOPAMINE, 0.05 + novelty * 0.1,
                         "curiosity", "input")
        self.adjust_level(Neurotransmitter.NOREPINEPHRINE, 0.05 + novelty * 0.05,
                         "attention", "input")
        self.adjust_level(Neurotransmitter.ACETYLCHOLINE, 0.05 + novelty * 0.08,
                         "encoding", "input")
    
    def on_social_interaction(self, warmth: float = 0.5):
        """
        Реакция на социальное взаимодействие.
        
        Args:
            warmth: Теплота взаимодействия (0.0 - 1.0)
        """
        self.adjust_level(Neurotransmitter.SEROTONIN, 0.05 + warmth * 0.1,
                         "social", "interaction")
        self.adjust_level(Neurotransmitter.ENDORPHIN, warmth * 0.08,
                         "bonding", "interaction")
    
    def on_stress(self, intensity: float = 0.5):
        """
        Реакция на стресс.
        
        Args:
            intensity: Интенсивность стресса (0.0 - 1.0)
        """
        self.adjust_level(Neurotransmitter.NOREPINEPHRINE, 0.15 * intensity,
                         "stress", "environment")
        self.adjust_level(Neurotransmitter.SEROTONIN, -0.08 * intensity,
                         "stress", "environment")
        self.adjust_level(Neurotransmitter.GABA, -0.1 * intensity,
                         "anxiety", "environment")
    
    def on_relaxation(self, depth: float = 0.5):
        """
        Реакция на расслабление/отдых.
        
        Args:
            depth: Глубина расслабления (0.0 - 1.0)
        """
        self.adjust_level(Neurotransmitter.GABA, 0.1 * depth,
                         "relaxation", "rest")
        self.adjust_level(Neurotransmitter.SEROTONIN, 0.05 * depth,
                         "calm", "rest")
        self.adjust_level(Neurotransmitter.NOREPINEPHRINE, -0.08 * depth,
                         "deactivation", "rest")
    
    def get_behavior_modifiers(self) -> Dict[str, float]:
        """
        Получить все модификаторы поведения на основе текущих уровней.
        
        Returns:
            Dict с модификаторами
        """
        dopamine = self.get_level(Neurotransmitter.DOPAMINE)
        serotonin = self.get_level(Neurotransmitter.SEROTONIN)
        norepinephrine = self.get_level(Neurotransmitter.NOREPINEPHRINE)
        gaba = self.get_level(Neurotransmitter.GABA)
        acetylcholine = self.get_level(Neurotransmitter.ACETYLCHOLINE)
        endorphin = self.get_level(Neurotransmitter.ENDORPHIN)
        
        return {
            "enthusiasm": BehaviorModifier.calculate_response_enthusiasm(dopamine, serotonin),
            "caution": BehaviorModifier.calculate_response_caution(norepinephrine, gaba),
            "memory_strength": BehaviorModifier.calculate_memory_strength(acetylcholine, dopamine),
            "creativity": BehaviorModifier.calculate_creativity(dopamine, serotonin, gaba),
            "focus": BehaviorModifier.calculate_focus(norepinephrine, acetylcholine),
            "emotional_warmth": BehaviorModifier.calculate_emotional_warmth(serotonin, endorphin)
        }
    
    def get_response_style_hints(self) -> Dict[str, Any]:
        """
        Получить подсказки для стиля ответа.
        
        Returns:
            Рекомендации для генерации ответа
        """
        modifiers = self.get_behavior_modifiers()
        
        hints = {
            "tone": "neutral",
            "length_preference": "normal",
            "emoji_usage": "moderate",
            "formality": "casual",
            "creativity_level": "normal"
        }
        
        # Определяем тон
        if modifiers["enthusiasm"] > 0.7:
            hints["tone"] = "enthusiastic"
            hints["emoji_usage"] = "high"
        elif modifiers["enthusiasm"] < 0.3:
            hints["tone"] = "subdued"
            hints["emoji_usage"] = "low"
        elif modifiers["emotional_warmth"] > 0.7:
            hints["tone"] = "warm"
        elif modifiers["caution"] > 0.7:
            hints["tone"] = "careful"
        
        # Длина ответа
        if modifiers["focus"] > 0.7:
            hints["length_preference"] = "concise"
        elif modifiers["creativity"] > 0.7:
            hints["length_preference"] = "elaborate"
        
        # Креативность
        if modifiers["creativity"] > 0.7:
            hints["creativity_level"] = "high"
        elif modifiers["creativity"] < 0.3:
            hints["creativity_level"] = "low"
        
        return hints
    
    def get_all_levels(self) -> Dict[str, float]:
        """Получить все уровни нейромедиаторов."""
        return {name: state.level for name, state in self.states.items()}
    
    def get_status_report(self) -> str:
        """Получить текстовый отчёт о состоянии."""
        lines = ["🧪 Нейромедиаторная система:\n"]
        
        emoji_map = {
            "dopamine": "🎯",
            "serotonin": "😊",
            "norepinephrine": "⚡",
            "gaba": "🧘",
            "acetylcholine": "📚",
            "endorphin": "💖"
        }
        
        name_map = {
            "dopamine": "Дофамин (мотивация)",
            "serotonin": "Серотонин (настроение)",
            "norepinephrine": "Норадреналин (внимание)",
            "gaba": "ГАМК (спокойствие)",
            "acetylcholine": "Ацетилхолин (память)",
            "endorphin": "Эндорфины (удовольствие)"
        }
        
        for name, state in self.states.items():
            emoji = emoji_map.get(name, "•")
            display_name = name_map.get(name, name)
            bar = self._level_bar(state.level)
            diff = state.level - state.baseline
            diff_str = f"+{diff:.2f}" if diff > 0 else f"{diff:.2f}"
            lines.append(f"{emoji} {display_name}: {bar} ({diff_str})")
        
        # Модификаторы
        modifiers = self.get_behavior_modifiers()
        lines.append("\n📊 Влияние на поведение:")
        lines.append(f"  • Энтузиазм: {modifiers['enthusiasm']:.0%}")
        lines.append(f"  • Креативность: {modifiers['creativity']:.0%}")
        lines.append(f"  • Фокус: {modifiers['focus']:.0%}")
        lines.append(f"  • Теплота: {modifiers['emotional_warmth']:.0%}")
        
        return "\n".join(lines)
    
    def _level_bar(self, level: float, width: int = 10) -> str:
        """Создать визуальную шкалу уровня."""
        filled = int(level * width)
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}] {level:.0%}"
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику системы."""
        levels = self.get_all_levels()
        modifiers = self.get_behavior_modifiers()
        
        return {
            "levels": levels,
            "modifiers": modifiers,
            "average_level": sum(levels.values()) / len(levels),
            "total_events": len(self.event_history),
            "hints": self.get_response_style_hints()
        }


# Синглтон
_neurotransmitter_system: Optional[NeurotransmitterSystem] = None


def get_neurotransmitter_system() -> NeurotransmitterSystem:
    """Получить глобальный экземпляр NeurotransmitterSystem."""
    global _neurotransmitter_system
    if _neurotransmitter_system is None:
        _neurotransmitter_system = NeurotransmitterSystem()
    return _neurotransmitter_system


# ==================== ТЕСТЫ ====================

if __name__ == "__main__":
    import tempfile
    import shutil
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ NEUROTRANSMITTER SYSTEM")
    print("=" * 60)
    
    test_dir = tempfile.mkdtemp()
    
    try:
        system = NeurotransmitterSystem(data_dir=test_dir)
        
        # Тест 1: Начальные уровни
        print("\n📝 Тест 1: Начальные уровни нейромедиаторов")
        levels = system.get_all_levels()
        
        assert len(levels) == 6
        assert all(0 <= v <= 1 for v in levels.values())
        print(f"✅ Инициализировано {len(levels)} нейромедиаторов")
        for name, level in levels.items():
            print(f"   • {name}: {level:.2f}")
        
        # Тест 2: Позитивный feedback
        print("\n📝 Тест 2: Реакция на позитивный feedback")
        old_dopamine = system.get_level(Neurotransmitter.DOPAMINE)
        
        system.on_positive_feedback(intensity=1.0)
        
        new_dopamine = system.get_level(Neurotransmitter.DOPAMINE)
        assert new_dopamine > old_dopamine
        print(f"✅ Дофамин: {old_dopamine:.3f} → {new_dopamine:.3f}")
        
        # Тест 3: Негативный feedback
        print("\n📝 Тест 3: Реакция на негативный feedback")
        old_dopamine = system.get_level(Neurotransmitter.DOPAMINE)
        old_norepinephrine = system.get_level(Neurotransmitter.NOREPINEPHRINE)
        
        system.on_negative_feedback(intensity=0.8)
        
        new_dopamine = system.get_level(Neurotransmitter.DOPAMINE)
        new_norepinephrine = system.get_level(Neurotransmitter.NOREPINEPHRINE)
        
        assert new_dopamine < old_dopamine
        assert new_norepinephrine > old_norepinephrine
        print(f"✅ Дофамин: {old_dopamine:.3f} → {new_dopamine:.3f}")
        print(f"✅ Норадреналин: {old_norepinephrine:.3f} → {new_norepinephrine:.3f}")
        
        # Тест 4: Успешная задача
        print("\n📝 Тест 4: Успешное выполнение сложной задачи")
        old_dopamine = system.get_level(Neurotransmitter.DOPAMINE)
        
        system.on_successful_task(difficulty=0.9)
        
        new_dopamine = system.get_level(Neurotransmitter.DOPAMINE)
        assert new_dopamine > old_dopamine
        print(f"✅ Дофамин после сложной задачи: {new_dopamine:.3f}")
        
        # Тест 5: Интересный input
        print("\n📝 Тест 5: Интересный/новый input")
        old_ach = system.get_level(Neurotransmitter.ACETYLCHOLINE)
        
        system.on_interesting_input(novelty=0.8)
        
        new_ach = system.get_level(Neurotransmitter.ACETYLCHOLINE)
        assert new_ach > old_ach
        print(f"✅ Ацетилхолин (обучение): {old_ach:.3f} → {new_ach:.3f}")
        
        # Тест 6: Социальное взаимодействие
        print("\n📝 Тест 6: Тёплое социальное взаимодействие")
        old_serotonin = system.get_level(Neurotransmitter.SEROTONIN)
        
        system.on_social_interaction(warmth=0.9)
        
        new_serotonin = system.get_level(Neurotransmitter.SEROTONIN)
        assert new_serotonin > old_serotonin
        print(f"✅ Серотонин: {old_serotonin:.3f} → {new_serotonin:.3f}")
        
        # Тест 7: Модификаторы поведения
        print("\n📝 Тест 7: Модификаторы поведения")
        modifiers = system.get_behavior_modifiers()
        
        assert "enthusiasm" in modifiers
        assert "creativity" in modifiers
        assert "focus" in modifiers
        print(f"✅ Модификаторы:")
        for name, value in modifiers.items():
            print(f"   • {name}: {value:.2f}")
        
        # Тест 8: Подсказки для ответа
        print("\n📝 Тест 8: Подсказки для стиля ответа")
        hints = system.get_response_style_hints()
        
        assert "tone" in hints
        assert "emoji_usage" in hints
        print(f"✅ Подсказки: тон={hints['tone']}, emoji={hints['emoji_usage']}")
        
        # Тест 9: Стресс и расслабление
        print("\n📝 Тест 9: Стресс и расслабление")
        
        system.on_stress(intensity=0.7)
        stressed_norepinephrine = system.get_level(Neurotransmitter.NOREPINEPHRINE)
        print(f"   После стресса - норадреналин: {stressed_norepinephrine:.3f}")
        
        system.on_relaxation(depth=0.8)
        relaxed_gaba = system.get_level(Neurotransmitter.GABA)
        print(f"   После расслабления - ГАМК: {relaxed_gaba:.3f}")
        print("✅ Реакции на стресс/расслабление работают")
        
        # Тест 10: Decay к baseline
        print("\n📝 Тест 10: Decay к baseline")
        # Сильно поднимаем дофамин
        system.set_level(Neurotransmitter.DOPAMINE, 0.95)
        high_dopamine = system.get_level(Neurotransmitter.DOPAMINE)
        
        # Применяем decay несколько раз
        for _ in range(10):
            system.decay_to_baseline()
        
        decayed_dopamine = system.get_level(Neurotransmitter.DOPAMINE)
        baseline = system.states["dopamine"].baseline
        
        assert abs(decayed_dopamine - baseline) < abs(high_dopamine - baseline)
        print(f"✅ Decay: {high_dopamine:.3f} → {decayed_dopamine:.3f} (baseline={baseline:.2f})")
        
        # Тест 11: Статус-отчёт
        print("\n📝 Тест 11: Статус-отчёт")
        report = system.get_status_report()
        
        assert "Дофамин" in report
        assert "Серотонин" in report
        print(f"✅ Статус-отчёт:\n{report}")
        
        # Тест 12: Сохранение и загрузка
        print("\n📝 Тест 12: Сохранение и загрузка")
        system._save()
        
        system2 = NeurotransmitterSystem(data_dir=test_dir)
        
        assert len(system2.states) == len(system.states)
        # Проверяем что уровни сохранились
        for name in system.states:
            assert abs(system2.states[name].level - system.states[name].level) < 0.01
        print("✅ Данные успешно сохранены и загружены")
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 60)
        
    finally:
        shutil.rmtree(test_dir)
