"""
Emoji Feedback System — обучение Neira через реакции пользователя

Позволяет пользователю корректировать поведение Neira, реагируя эмодзи на её ответы.
Данные используются для:
- Улучшения Neural Pathways
- Корректировки промптов
- Статистики качества
- Автоматического обучения
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class FeedbackEntry:
    """Запись обратной связи от пользователя"""
    timestamp: str
    user_id: str
    user_query: str
    neira_response: str
    reaction_emoji: str
    quality_score: int  # 1-10
    context: Dict[str, Any]
    
    def to_dict(self) -> dict:
        return asdict(self)


class EmojiMap:
    """Маппинг эмодзи на оценки качества"""
    
    # Отличные ответы (9-10)
    EXCELLENT = {
        "💯": 10,
        "⭐": 10,
        "🌟": 10,
        "✨": 9,
        "🎯": 9,
    }
    
    # Хорошие ответы (7-8)
    GOOD = {
        "👍": 8,
        "❤️": 8,
        "🔥": 8,
        "👏": 7,
        "✅": 7,
        "👌": 7,
    }
    
    # Нормальные ответы (5-6)
    NEUTRAL = {
        "🤔": 6,
        "😐": 5,
        "🆗": 5,
    }
    
    # Плохие ответы (3-4)
    BAD = {
        "👎": 4,
        "😕": 3,
        "😞": 3,
        "🤷": 4,
    }
    
    # Очень плохие (1-2)
    TERRIBLE = {
        "❌": 2,
        "🚫": 1,
        "💩": 1,
        "😡": 2,
    }
    
    @classmethod
    def get_score(cls, emoji: str) -> Optional[int]:
        """Получить оценку для эмодзи"""
        for category in [cls.EXCELLENT, cls.GOOD, cls.NEUTRAL, cls.BAD, cls.TERRIBLE]:
            if emoji in category:
                return category[emoji]
        return None
    
    @classmethod
    def get_category(cls, emoji: str) -> str:
        """Получить категорию эмодзи"""
        if emoji in cls.EXCELLENT:
            return "excellent"
        elif emoji in cls.GOOD:
            return "good"
        elif emoji in cls.NEUTRAL:
            return "neutral"
        elif emoji in cls.BAD:
            return "bad"
        elif emoji in cls.TERRIBLE:
            return "terrible"
        return "unknown"


class EmojiFeedbackSystem:
    """Система обратной связи через эмодзи"""
    
    def __init__(self, feedback_file: str = "neira_emoji_feedback.json"):
        self.feedback_file = feedback_file
        self.feedback: List[Dict] = []
        self.stats = defaultdict(int)
        self._load()
    
    def _load(self):
        """Загрузить историю обратной связи"""
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.feedback = data.get("feedback", [])
                    self._update_stats()
            except Exception as e:
                print(f"⚠️ Ошибка загрузки feedback: {e}")
                self.feedback = []
    
    def _save(self):
        """Сохранить обратную связь"""
        try:
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "feedback": self.feedback,
                    "stats": dict(self.stats),
                    "last_updated": datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения feedback: {e}")
    
    def _update_stats(self):
        """Обновить статистику"""
        self.stats = defaultdict(int)
        for entry in self.feedback:
            emoji = entry.get("reaction_emoji", "")
            category = EmojiMap.get_category(emoji)
            self.stats[f"category_{category}"] += 1
            self.stats["total"] += 1
            self.stats["total_score"] += entry.get("quality_score", 0)
    
    def add_feedback(
        self,
        user_id: str,
        user_query: str,
        neira_response: str,
        reaction_emoji: str,
        context: Optional[Dict] = None
    ) -> Optional[FeedbackEntry]:
        """
        Добавить обратную связь
        
        Args:
            user_id: ID пользователя
            user_query: Запрос пользователя
            neira_response: Ответ Neira
            reaction_emoji: Эмодзи-реакция
            context: Дополнительный контекст (модель, стратегия и т.д.)
        
        Returns:
            FeedbackEntry или None, если эмодзи не распознан
        """
        score = EmojiMap.get_score(reaction_emoji)
        
        if score is None:
            return None
        
        entry = FeedbackEntry(
            timestamp=datetime.now().isoformat(),
            user_id=str(user_id),
            user_query=user_query[:500],  # Ограничиваем размер
            neira_response=neira_response[:1000],
            reaction_emoji=reaction_emoji,
            quality_score=score,
            context=context or {}
        )
        
        self.feedback.append(entry.to_dict())
        self._update_stats()
        self._save()
        
        return entry
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику обратной связи"""
        if self.stats["total"] == 0:
            return {
                "total": 0,
                "average_score": 0,
                "by_category": {}
            }
        
        avg_score = self.stats["total_score"] / self.stats["total"]
        
        return {
            "total": self.stats["total"],
            "average_score": round(avg_score, 2),
            "by_category": {
                "excellent": self.stats.get("category_excellent", 0),
                "good": self.stats.get("category_good", 0),
                "neutral": self.stats.get("category_neutral", 0),
                "bad": self.stats.get("category_bad", 0),
                "terrible": self.stats.get("category_terrible", 0),
            }
        }
    
    def get_recent_feedback(self, limit: int = 10) -> List[Dict]:
        """Получить последние N записей обратной связи"""
        return self.feedback[-limit:]
    
    def get_low_quality_responses(self, threshold: int = 4) -> List[Dict]:
        """Получить ответы с низкой оценкой для анализа"""
        return [
            entry for entry in self.feedback
            if entry.get("quality_score", 10) <= threshold
        ]
    
    def get_high_quality_responses(self, threshold: int = 8) -> List[Dict]:
        """Получить ответы с высокой оценкой для обучения"""
        return [
            entry for entry in self.feedback
            if entry.get("quality_score", 0) >= threshold
        ]
    
    def analyze_patterns(self) -> Dict[str, Any]:
        """Анализ паттернов для улучшения"""
        if not self.feedback:
            return {"patterns": [], "recommendations": []}
        
        # Группируем по стратегиям Cortex
        strategy_scores = defaultdict(list)
        for entry in self.feedback:
            strategy = entry.get("context", {}).get("strategy", "unknown")
            score = entry.get("quality_score", 0)
            strategy_scores[strategy].append(score)
        
        # Вычисляем средние оценки
        strategy_avg = {
            strategy: sum(scores) / len(scores)
            for strategy, scores in strategy_scores.items()
        }
        
        # Находим проблемные стратегии
        recommendations = []
        for strategy, avg_score in strategy_avg.items():
            if avg_score < 5:
                recommendations.append({
                    "issue": f"Низкая оценка стратегии {strategy}",
                    "avg_score": round(avg_score, 2),
                    "suggestion": f"Рассмотреть улучшение {strategy} или переключение на другую стратегию"
                })
        
        return {
            "strategy_scores": {k: round(v, 2) for k, v in strategy_avg.items()},
            "recommendations": recommendations
        }


if __name__ == "__main__":
    # Тестирование
    feedback_system = EmojiFeedbackSystem()
    
    # Тестовая обратная связь
    feedback_system.add_feedback(
        user_id="12345",
        user_query="Как дела?",
        neira_response="Всё отлично! Работаю и учусь 😊",
        reaction_emoji="👍",
        context={"strategy": "neural_pathway", "model": "ministral-3:3b"}
    )
    
    print("📊 Статистика:", json.dumps(feedback_system.get_stats(), indent=2, ensure_ascii=False))
    print("\n📈 Анализ:", json.dumps(feedback_system.analyze_patterns(), indent=2, ensure_ascii=False))
