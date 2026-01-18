"""
Predictive Coding - предсказательное кодирование.

В мозге: кора постоянно генерирует предсказания о входных сигналах.
Ошибка предсказания (prediction error) запускает обучение.

Для Нейры: предугадывание следующего вопроса пользователя,
обучение на ошибках предсказания.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import json
import math
from pathlib import Path


class PredictionType(Enum):
    """Типы предсказаний."""
    NEXT_TOPIC = "next_topic"           # Следующая тема разговора
    USER_INTENT = "user_intent"         # Намерение пользователя
    EMOTIONAL_STATE = "emotional_state" # Эмоциональное состояние
    FOLLOW_UP = "follow_up"             # Уточняющий вопрос
    RESPONSE_TYPE = "response_type"     # Тип ожидаемого ответа


@dataclass
class Prediction:
    """Предсказание системы."""
    prediction_id: str
    prediction_type: str
    predicted_value: str
    confidence: float           # Уверенность (0-1)
    context: str                # Контекст предсказания
    created_at: str
    resolved: bool = False
    actual_value: Optional[str] = None
    prediction_error: float = 0.0  # Ошибка предсказания
    
    def to_dict(self) -> Dict:
        return {
            "prediction_id": self.prediction_id,
            "prediction_type": self.prediction_type,
            "predicted_value": self.predicted_value,
            "confidence": self.confidence,
            "context": self.context,
            "created_at": self.created_at,
            "resolved": self.resolved,
            "actual_value": self.actual_value,
            "prediction_error": self.prediction_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Prediction":
        return cls(**data)


@dataclass
class PredictionPattern:
    """Паттерн для генерации предсказаний."""
    pattern_id: str
    trigger: str                # Триггер паттерна
    prediction_type: str
    likely_outcomes: Dict[str, float]  # outcome -> probability
    success_count: int = 0
    total_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "pattern_id": self.pattern_id,
            "trigger": self.trigger,
            "prediction_type": self.prediction_type,
            "likely_outcomes": self.likely_outcomes,
            "success_count": self.success_count,
            "total_count": self.total_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "PredictionPattern":
        return cls(**data)


class PredictiveCoding:
    """
    Система предсказательного кодирования.
    
    Генерирует предсказания и обучается на ошибках.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "predictive_coding.json"
        
        # История предсказаний
        self.predictions: List[Prediction] = []
        
        # Паттерны предсказаний
        self.patterns: Dict[str, PredictionPattern] = {}
        
        # Статистика
        self.total_predictions = 0
        self.successful_predictions = 0
        self.avg_prediction_error = 0.5
        
        # Конфигурация
        self.config = {
            "min_confidence_threshold": 0.3,
            "learning_rate": 0.1,
            "error_weight_decay": 0.95,
            "max_predictions_history": 500,
            "pattern_update_threshold": 5
        }
        
        self._init_default_patterns()
        self._load()
    
    def _init_default_patterns(self):
        """Инициализация стандартных паттернов."""
        default_patterns = [
            # После приветствия - вопрос о делах
            PredictionPattern(
                pattern_id="greeting_followup",
                trigger="greeting",
                prediction_type=PredictionType.FOLLOW_UP.value,
                likely_outcomes={
                    "how_are_you": 0.4,
                    "help_request": 0.3,
                    "small_talk": 0.2,
                    "direct_question": 0.1
                }
            ),
            # После технического вопроса - уточнение
            PredictionPattern(
                pattern_id="technical_clarification",
                trigger="technical_question",
                prediction_type=PredictionType.FOLLOW_UP.value,
                likely_outcomes={
                    "clarification": 0.4,
                    "example_request": 0.3,
                    "thanks": 0.2,
                    "new_question": 0.1
                }
            ),
            # Эмоциональное сообщение - поддержка
            PredictionPattern(
                pattern_id="emotional_support",
                trigger="emotional_message",
                prediction_type=PredictionType.USER_INTENT.value,
                likely_outcomes={
                    "needs_support": 0.5,
                    "venting": 0.3,
                    "advice_seeking": 0.2
                }
            ),
            # Вопрос "почему" - объяснение
            PredictionPattern(
                pattern_id="why_question",
                trigger="why_question",
                prediction_type=PredictionType.RESPONSE_TYPE.value,
                likely_outcomes={
                    "explanation": 0.6,
                    "reasoning": 0.3,
                    "example": 0.1
                }
            ),
        ]
        
        for pattern in default_patterns:
            if pattern.pattern_id not in self.patterns:
                self.patterns[pattern.pattern_id] = pattern
    
    def _load(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for p_data in data.get("predictions", []):
                    self.predictions.append(Prediction.from_dict(p_data))
                
                for pid, pdata in data.get("patterns", {}).items():
                    self.patterns[pid] = PredictionPattern.from_dict(pdata)
                
                self.total_predictions = data.get("total_predictions", 0)
                self.successful_predictions = data.get("successful_predictions", 0)
                self.avg_prediction_error = data.get("avg_prediction_error", 0.5)
                
            except Exception as e:
                print(f"Error loading predictive coding: {e}")
    
    def _save(self):
        # Ограничиваем историю
        if len(self.predictions) > self.config["max_predictions_history"]:
            self.predictions = self.predictions[-self.config["max_predictions_history"]:]
        
        data = {
            "predictions": [p.to_dict() for p in self.predictions],
            "patterns": {pid: p.to_dict() for pid, p in self.patterns.items()},
            "total_predictions": self.total_predictions,
            "successful_predictions": self.successful_predictions,
            "avg_prediction_error": self.avg_prediction_error
        }
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_id(self) -> str:
        import hashlib
        import random
        data = f"{datetime.now().isoformat()}{random.random()}"
        return hashlib.md5(data.encode()).hexdigest()[:12]
    
    def predict(
        self, 
        context: str, 
        prediction_type: PredictionType,
        trigger: Optional[str] = None
    ) -> Optional[Prediction]:
        """
        Сгенерировать предсказание на основе контекста.
        
        Args:
            context: Текущий контекст (последнее сообщение)
            prediction_type: Тип предсказания
            trigger: Триггер для поиска паттерна
            
        Returns:
            Prediction или None если уверенность слишком низкая
        """
        # Ищем подходящий паттерн
        pattern = None
        if trigger:
            for p in self.patterns.values():
                if p.trigger == trigger and p.prediction_type == prediction_type.value:
                    pattern = p
                    break
        
        if not pattern:
            # Используем дефолтный паттерн на основе типа
            pattern = self._get_default_pattern(prediction_type)
        
        if not pattern or not pattern.likely_outcomes:
            return None
        
        # Выбираем наиболее вероятный исход
        best_outcome = max(pattern.likely_outcomes.items(), key=lambda x: x[1])
        predicted_value, confidence = best_outcome
        
        # Корректируем уверенность на основе истории успехов
        if pattern.total_count > 0:
            success_rate = pattern.success_count / pattern.total_count
            confidence *= (0.5 + 0.5 * success_rate)
        
        if confidence < self.config["min_confidence_threshold"]:
            return None
        
        prediction = Prediction(
            prediction_id=self._generate_id(),
            prediction_type=prediction_type.value,
            predicted_value=predicted_value,
            confidence=confidence,
            context=context[:200],
            created_at=datetime.now().isoformat()
        )
        
        self.predictions.append(prediction)
        self.total_predictions += 1
        self._save()
        
        return prediction
    
    def _get_default_pattern(self, prediction_type: PredictionType) -> Optional[PredictionPattern]:
        """Получить дефолтный паттерн для типа предсказания."""
        for pattern in self.patterns.values():
            if pattern.prediction_type == prediction_type.value:
                return pattern
        return None
    
    def resolve_prediction(
        self, 
        prediction_id: str, 
        actual_value: str
    ) -> Dict[str, Any]:
        """
        Разрешить предсказание и обновить модель.
        
        Returns:
            Результат с ошибкой предсказания
        """
        prediction = None
        for p in self.predictions:
            if p.prediction_id == prediction_id and not p.resolved:
                prediction = p
                break
        
        if not prediction:
            return {"error": "Prediction not found or already resolved"}
        
        prediction.resolved = True
        prediction.actual_value = actual_value
        
        # Рассчитываем ошибку предсказания
        if prediction.predicted_value == actual_value:
            prediction.prediction_error = 0.0
            self.successful_predictions += 1
            success = True
        else:
            # Ошибка пропорциональна уверенности (большая уверенность + ошибка = большая penalty)
            prediction.prediction_error = prediction.confidence
            success = False
        
        # Обновляем среднюю ошибку
        self.avg_prediction_error = (
            self.avg_prediction_error * self.config["error_weight_decay"] +
            prediction.prediction_error * (1 - self.config["error_weight_decay"])
        )
        
        # Обучаемся на ошибке
        self._update_patterns(prediction, success)
        
        self._save()
        
        return {
            "prediction_id": prediction_id,
            "predicted": prediction.predicted_value,
            "actual": actual_value,
            "error": prediction.prediction_error,
            "success": success,
            "learning_applied": True
        }
    
    def _update_patterns(self, prediction: Prediction, success: bool):
        """Обновить паттерны на основе результата предсказания."""
        learning_rate = self.config["learning_rate"]
        
        for pattern in self.patterns.values():
            if pattern.prediction_type != prediction.prediction_type:
                continue
            
            pattern.total_count += 1
            
            if success:
                pattern.success_count += 1
                # Увеличиваем вероятность успешного исхода
                if prediction.predicted_value in pattern.likely_outcomes:
                    current = pattern.likely_outcomes[prediction.predicted_value]
                    pattern.likely_outcomes[prediction.predicted_value] = min(
                        0.9, current + learning_rate * (1 - current)
                    )
            else:
                # Уменьшаем вероятность неверного исхода
                if prediction.predicted_value in pattern.likely_outcomes:
                    current = pattern.likely_outcomes[prediction.predicted_value]
                    pattern.likely_outcomes[prediction.predicted_value] = max(
                        0.05, current - learning_rate * current
                    )
                
                # Добавляем/увеличиваем фактический исход
                if prediction.actual_value:
                    current = pattern.likely_outcomes.get(prediction.actual_value, 0.1)
                    pattern.likely_outcomes[prediction.actual_value] = min(
                        0.9, current + learning_rate * 0.5
                    )
            
            # Нормализуем вероятности
            total = sum(pattern.likely_outcomes.values())
            if total > 0:
                pattern.likely_outcomes = {
                    k: v/total for k, v in pattern.likely_outcomes.items()
                }
    
    def get_pending_predictions(self) -> List[Prediction]:
        """Получить нерешённые предсказания."""
        return [p for p in self.predictions if not p.resolved]
    
    def get_accuracy(self) -> float:
        """Получить точность предсказаний."""
        if self.total_predictions == 0:
            return 0.0
        return self.successful_predictions / self.total_predictions
    
    def suggest_next(self, context: str) -> Optional[str]:
        """
        Предложить следующее действие/вопрос пользователя.
        
        Для проактивного общения.
        """
        prediction = self.predict(
            context, 
            PredictionType.FOLLOW_UP
        )
        
        if prediction and prediction.confidence > 0.5:
            suggestions = {
                "clarification": "Возможно, захочешь уточнить детали?",
                "example_request": "Может понадобиться пример?",
                "thanks": "Надеюсь, это помогло!",
                "how_are_you": "Как у тебя дела?",
                "help_request": "Чем могу помочь?",
                "needs_support": "Я рядом, если хочешь поговорить.",
            }
            return suggestions.get(prediction.predicted_value)
        
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Статистика предсказательного кодирования."""
        return {
            "total_predictions": self.total_predictions,
            "successful_predictions": self.successful_predictions,
            "accuracy": self.get_accuracy(),
            "avg_prediction_error": self.avg_prediction_error,
            "pending_predictions": len(self.get_pending_predictions()),
            "patterns_count": len(self.patterns),
            "history_size": len(self.predictions)
        }


# Singleton
_predictive_coding: Optional[PredictiveCoding] = None

def get_predictive_coding() -> PredictiveCoding:
    global _predictive_coding
    if _predictive_coding is None:
        _predictive_coding = PredictiveCoding()
    return _predictive_coding
