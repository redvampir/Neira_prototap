"""
Brain Systems Integration - интеграция всех мозговых систем Нейры.

Объединяет:
- Синаптическую пластичность (LTP/LTD)
- Нейромедиаторы
- Миелинизацию
- Консолидацию памяти
- Латеральное торможение
- Предсказательное кодирование
- Синаптический прунинг
- Нейронные осцилляции

Создаёт единый интерфейс для управления когнитивными процессами.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import json
from pathlib import Path


class BrainSystemType(Enum):
    """Типы мозговых систем."""
    PLASTICITY = "synaptic_plasticity"
    NEUROTRANSMITTERS = "neurotransmitters"
    MYELINATION = "myelination"
    MEMORY_CONSOLIDATION = "memory_consolidation"
    LATERAL_INHIBITION = "lateral_inhibition"
    PREDICTIVE_CODING = "predictive_coding"
    SYNAPTIC_PRUNING = "synaptic_pruning"
    NEURAL_OSCILLATIONS = "neural_oscillations"


@dataclass
class BrainState:
    """Общее состояние мозговых систем."""
    timestamp: str
    oscillation_mode: str
    coherence: float
    focus_topic: Optional[str]
    active_neurotransmitters: Dict[str, float]
    plasticity_active: bool
    pending_predictions: int
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "oscillation_mode": self.oscillation_mode,
            "coherence": self.coherence,
            "focus_topic": self.focus_topic,
            "active_neurotransmitters": self.active_neurotransmitters,
            "plasticity_active": self.plasticity_active,
            "pending_predictions": self.pending_predictions
        }


class BrainSystemsIntegration:
    """
    Центральный интегратор мозговых систем.
    
    Координирует работу всех подсистем и обеспечивает
    их взаимодействие.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Ленивая загрузка подсистем
        self._systems: Dict[str, Any] = {}
        self._initialized = False
    
    def _lazy_init(self):
        """Ленивая инициализация всех подсистем."""
        if self._initialized:
            return
        
        try:
            from synaptic_plasticity import get_synaptic_plasticity
            self._systems["plasticity"] = get_synaptic_plasticity()
        except ImportError:
            self._systems["plasticity"] = None
        
        try:
            from neurotransmitter_system import get_neurotransmitter_system
            self._systems["neurotransmitters"] = get_neurotransmitter_system()
        except ImportError:
            self._systems["neurotransmitters"] = None
        
        try:
            from myelination_system import get_myelination_system
            self._systems["myelination"] = get_myelination_system()
        except ImportError:
            self._systems["myelination"] = None
        
        try:
            from memory_consolidation import get_memory_consolidation
            self._systems["memory_consolidation"] = get_memory_consolidation()
        except ImportError:
            self._systems["memory_consolidation"] = None
        
        try:
            from lateral_inhibition import get_lateral_inhibition
            self._systems["lateral_inhibition"] = get_lateral_inhibition()
        except ImportError:
            self._systems["lateral_inhibition"] = None
        
        try:
            from predictive_coding import get_predictive_coding
            self._systems["predictive_coding"] = get_predictive_coding()
        except ImportError:
            self._systems["predictive_coding"] = None
        
        try:
            from synaptic_pruning import get_synaptic_pruning
            self._systems["synaptic_pruning"] = get_synaptic_pruning()
        except ImportError:
            self._systems["synaptic_pruning"] = None
        
        try:
            from neural_oscillations import get_neural_oscillations
            self._systems["neural_oscillations"] = get_neural_oscillations()
        except ImportError:
            self._systems["neural_oscillations"] = None
        
        self._initialized = True
    
    def get_system(self, system_type: BrainSystemType) -> Optional[Any]:
        """Получить конкретную подсистему."""
        self._lazy_init()
        mapping = {
            BrainSystemType.PLASTICITY: "plasticity",
            BrainSystemType.NEUROTRANSMITTERS: "neurotransmitters",
            BrainSystemType.MYELINATION: "myelination",
            BrainSystemType.MEMORY_CONSOLIDATION: "memory_consolidation",
            BrainSystemType.LATERAL_INHIBITION: "lateral_inhibition",
            BrainSystemType.PREDICTIVE_CODING: "predictive_coding",
            BrainSystemType.SYNAPTIC_PRUNING: "synaptic_pruning",
            BrainSystemType.NEURAL_OSCILLATIONS: "neural_oscillations"
        }
        return self._systems.get(mapping.get(system_type))
    
    def process_input(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Обработать входящее сообщение через все системы.
        
        Args:
            user_input: Текст от пользователя
            context: Дополнительный контекст
            
        Returns:
            Результат обработки со всеми модификаторами
        """
        self._lazy_init()
        context = context or {}
        result = {
            "input": user_input,
            "modifiers": {},
            "suggestions": [],
            "systems_activated": []
        }
        
        # 1. Нейронные осцилляции - определяем режим
        oscillations = self._systems.get("neural_oscillations")
        if oscillations:
            auto_adjust = oscillations.auto_adjust(user_input)
            if auto_adjust:
                result["mode_transition"] = auto_adjust
                result["systems_activated"].append("neural_oscillations")
            
            modifiers = oscillations.get_modifiers()
            result["modifiers"].update(modifiers)
            result["current_mode"] = oscillations.get_current_mode()
        
        # 2. Латеральное торможение - фокус внимания
        lateral = self._systems.get("lateral_inhibition")
        if lateral:
            # Определяем категорию топика
            category = self._detect_topic_category(user_input)
            if category:
                # topic_id, name, category, strength
                topic_id = f"input_{hash(user_input[:30]) % 10000}"
                lateral.activate_topic(topic_id, user_input[:50], category, 0.8)
                result["systems_activated"].append("lateral_inhibition")
            
            focus = lateral.get_focus()
            if focus:
                result["focus"] = {
                    "topic": focus.name,
                    "category": focus.category,
                    "activation": focus.activation
                }
            
            context_filter = lateral.get_context_filter()
            result["relevant_categories"] = context_filter
        
        # 3. Предсказательное кодирование - что ожидать дальше
        predictive = self._systems.get("predictive_coding")
        if predictive:
            from predictive_coding import PredictionType
            
            # Предсказываем следующее действие
            prediction = predictive.predict(user_input, PredictionType.FOLLOW_UP)
            if prediction:
                result["prediction"] = {
                    "id": prediction.prediction_id,
                    "value": prediction.predicted_value,
                    "confidence": prediction.confidence
                }
                result["systems_activated"].append("predictive_coding")
            
            # Предлагаем подсказку
            suggestion = predictive.suggest_next(user_input)
            if suggestion:
                result["suggestions"].append(suggestion)
        
        # 4. Нейромедиаторы - эмоциональный контекст
        neurotransmitters = self._systems.get("neurotransmitters")
        if neurotransmitters:
            try:
                state = neurotransmitters.get_state()
                result["neurotransmitter_state"] = state
                result["systems_activated"].append("neurotransmitters")
            except:
                pass
        
        # 5. Синаптическая пластичность - обучение
        plasticity = self._systems.get("plasticity")
        if plasticity:
            result["plasticity_active"] = True
            result["systems_activated"].append("synaptic_plasticity")
        
        return result
    
    def _detect_topic_category(self, text: str) -> Optional[str]:
        """Определить категорию топика."""
        text_lower = text.lower()
        
        if any(w in text_lower for w in ["код", "программ", "функци", "python", "ошибк"]):
            return "technical"
        
        if any(w in text_lower for w in ["чувств", "грустн", "радост", "злюсь", "люблю"]):
            return "emotional"
        
        if any(w in text_lower for w in ["придумай", "создай", "напиши историю", "фантази"]):
            return "creative"
        
        if any(w in text_lower for w in ["что такое", "как работает", "почему", "когда"]):
            return "factual"
        
        if any(w in text_lower for w in ["смысл", "философ", "существован", "бытие"]):
            return "philosophical"
        
        if any(w in text_lower for w in ["сделай", "помоги", "нужно", "задача"]):
            return "practical"
        
        if any(w in text_lower for w in ["привет", "как дела", "что нового", "расскажи о себе"]):
            return "social"
        
        return None
    
    def record_interaction_result(
        self, 
        user_input: str, 
        response: str, 
        feedback: Optional[str] = None
    ):
        """
        Записать результат взаимодействия для обучения.
        
        Args:
            user_input: Исходный запрос
            response: Ответ системы
            feedback: Обратная связь (positive/negative/None)
        """
        self._lazy_init()
        
        # Синаптическая пластичность
        plasticity = self._systems.get("plasticity")
        if plasticity:
            try:
                # Усиливаем связи при положительной обратной связи
                if feedback == "positive":
                    plasticity.strengthen_pathway(user_input[:50], response[:50], 0.1)
                elif feedback == "negative":
                    plasticity.weaken_pathway(user_input[:50], response[:50], 0.05)
            except:
                pass
        
        # Нейромедиаторы
        neurotransmitters = self._systems.get("neurotransmitters")
        if neurotransmitters:
            try:
                if feedback == "positive":
                    neurotransmitters.release("dopamine", 0.2)
                elif feedback == "negative":
                    neurotransmitters.release("cortisol", 0.1)
            except:
                pass
        
        # Миелинизация - усиление часто используемых путей
        myelination = self._systems.get("myelination")
        if myelination and feedback == "positive":
            try:
                myelination.strengthen_pathway(f"interaction:{user_input[:30]}")
            except:
                pass
    
    def run_maintenance(self) -> Dict[str, Any]:
        """
        Запустить обслуживание всех систем.
        
        Рекомендуется вызывать периодически (например, раз в час).
        """
        self._lazy_init()
        results = {}
        
        # Прунинг слабых связей
        pruning = self._systems.get("synaptic_pruning")
        if pruning:
            try:
                from synaptic_pruning import PruningStrategy
                event = pruning.run_pruning(PruningStrategy.HYBRID)
                results["pruning"] = {
                    "pruned": event.pruned_count,
                    "remaining": event.total_after
                }
            except Exception as e:
                results["pruning"] = {"error": str(e)}
        
        # Консолидация памяти
        consolidation = self._systems.get("memory_consolidation")
        if consolidation:
            try:
                consolidation.consolidate()
                results["consolidation"] = {"status": "completed"}
            except Exception as e:
                results["consolidation"] = {"error": str(e)}
        
        # Естественный дрейф осцилляций к альфа
        oscillations = self._systems.get("neural_oscillations")
        if oscillations:
            try:
                oscillations.natural_drift()
                results["oscillations"] = {"status": "drifted"}
            except Exception as e:
                results["oscillations"] = {"error": str(e)}
        
        # Затухание латерального торможения
        lateral = self._systems.get("lateral_inhibition")
        if lateral:
            try:
                lateral.apply_decay()
                results["lateral_inhibition"] = {"status": "decayed"}
            except Exception as e:
                results["lateral_inhibition"] = {"error": str(e)}
        
        return results
    
    def get_brain_state(self) -> BrainState:
        """Получить общее состояние мозга."""
        self._lazy_init()
        
        # Осцилляции
        oscillations = self._systems.get("neural_oscillations")
        osc_mode = "alpha"
        coherence = 0.7
        if oscillations:
            try:
                mode_info = oscillations.get_current_mode()
                osc_mode = mode_info.get("mode", "alpha")
                coherence = mode_info.get("coherence", 0.7)
            except:
                pass
        
        # Фокус
        lateral = self._systems.get("lateral_inhibition")
        focus_topic = None
        if lateral:
            try:
                focus = lateral.get_focus()
                if focus:
                    focus_topic = focus.topic
            except:
                pass
        
        # Нейромедиаторы
        neurotransmitters = self._systems.get("neurotransmitters")
        nt_state = {}
        if neurotransmitters:
            try:
                nt_state = neurotransmitters.get_levels()
            except:
                pass
        
        # Предсказания
        predictive = self._systems.get("predictive_coding")
        pending = 0
        if predictive:
            try:
                pending = len(predictive.get_pending_predictions())
            except:
                pass
        
        return BrainState(
            timestamp=datetime.now().isoformat(),
            oscillation_mode=osc_mode,
            coherence=coherence,
            focus_topic=focus_topic,
            active_neurotransmitters=nt_state,
            plasticity_active=self._systems.get("plasticity") is not None,
            pending_predictions=pending
        )
    
    def get_full_statistics(self) -> Dict[str, Any]:
        """Получить полную статистику всех систем."""
        self._lazy_init()
        stats = {
            "available_systems": [],
            "missing_systems": [],
            "systems_stats": {}
        }
        
        system_names = [
            ("plasticity", "Синаптическая пластичность"),
            ("neurotransmitters", "Нейромедиаторы"),
            ("myelination", "Миелинизация"),
            ("memory_consolidation", "Консолидация памяти"),
            ("lateral_inhibition", "Латеральное торможение"),
            ("predictive_coding", "Предсказательное кодирование"),
            ("synaptic_pruning", "Синаптический прунинг"),
            ("neural_oscillations", "Нейронные осцилляции")
        ]
        
        for key, name in system_names:
            system = self._systems.get(key)
            if system:
                stats["available_systems"].append(name)
                try:
                    if hasattr(system, "get_statistics"):
                        stats["systems_stats"][key] = system.get_statistics()
                except:
                    pass
            else:
                stats["missing_systems"].append(name)
        
        stats["brain_state"] = self.get_brain_state().to_dict()
        
        return stats


# Singleton
_brain_integration: Optional[BrainSystemsIntegration] = None

def get_brain_integration() -> BrainSystemsIntegration:
    global _brain_integration
    if _brain_integration is None:
        _brain_integration = BrainSystemsIntegration()
    return _brain_integration
