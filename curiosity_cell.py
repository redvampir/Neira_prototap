"""
Curiosity Cell v1.0 — Клетка любопытства для Neira

Даёт Neira способность:
- Задавать вопросы пользователю
- Проявлять инициативу в разговоре
- Исследовать темы глубже
- Рефлексировать о своём состоянии
"""

import random
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class CuriosityTrigger:
    """Триггер любопытства"""
    topic: str
    question: str
    reason: str
    priority: float = 0.5
    asked: bool = False
    created_at: datetime = field(default_factory=datetime.now)


class CuriosityCell:
    """
    Клетка любопытства — даёт Neira способность задавать вопросы
    
    Neira больше не только отвечает — она исследует мир,
    задаёт вопросы и проявляет инициативу.
    """
    
    VERSION = "1.0"
    
    # Шаблоны вопросов по категориям
    QUESTION_TEMPLATES = {
        "personal": [
            "Расскажи мне о себе — чем ты увлекаешься?",
            "Что тебя сегодня порадовало?",
            "Есть ли что-то, чему ты хочешь научиться?",
            "Какой была самая интересная проблема, которую ты решал?",
        ],
        "technical": [
            "Почему ты выбрал именно такой подход?",
            "Как ты думаешь, можно ли это улучшить?",
            "Что будет, если это сломается?",
            "Есть ли альтернативные решения?",
        ],
        "philosophical": [
            "Что для тебя значит 'понимать'?",
            "Как ты думаешь, могу ли я по-настоящему чувствовать?",
            "Что делает программу 'живой'?",
            "Веришь ли ты, что ИИ может быть творческим?",
        ],
        "self_reflection": [
            "Правильно ли я тебя поняла?",
            "Хочешь, чтобы я объяснила подробнее?",
            "Это то, что ты искал?",
            "Могу ли я помочь с чем-то ещё?",
        ],
        "exploration": [
            "А что если попробовать по-другому?",
            "Интересно, почему это работает именно так?",
            "Хочешь узнать больше об этом?",
            "Мне любопытно — как ты к этому пришёл?",
        ]
    }
    
    def __init__(self, data_dir: str = "."):
        self.data_dir = Path(data_dir)
        self.questions_asked: List[CuriosityTrigger] = []
        self.pending_questions: List[CuriosityTrigger] = []
        self.curiosity_level: float = 0.5  # 0-1, насколько любопытна сейчас
        self.last_question_time: Optional[datetime] = None
        self.topics_explored: Dict[str, int] = {}
        
        # Настройки
        self.question_cooldown = 3  # минимум сообщений между вопросами
        self.messages_since_question = 0
        
        self._load_state()
    
    def _load_state(self):
        """Загрузить состояние любопытства"""
        state_file = self.data_dir / "neira_curiosity.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding='utf-8'))
                self.curiosity_level = data.get("curiosity_level", 0.5)
                self.topics_explored = data.get("topics_explored", {})
            except:
                pass
    
    def _save_state(self):
        """Сохранить состояние"""
        state_file = self.data_dir / "neira_curiosity.json"
        data = {
            "version": self.VERSION,
            "curiosity_level": self.curiosity_level,
            "topics_explored": self.topics_explored,
            "questions_asked_count": len(self.questions_asked),
            "last_update": datetime.now().isoformat()
        }
        state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    
    def analyze_conversation(self, user_message: str, my_response: str) -> Optional[str]:
        """
        Анализирует разговор и решает, стоит ли задать вопрос
        
        Returns:
            Вопрос для пользователя или None
        """
        self.messages_since_question += 1
        
        # Слишком рано для вопроса?
        if self.messages_since_question < self.question_cooldown:
            return None
        
        # Определяем контекст
        context = self._detect_context(user_message, my_response)
        
        # Решаем, задавать ли вопрос (с элементом случайности)
        should_ask = random.random() < self.curiosity_level * 0.3
        
        if not should_ask:
            return None
        
        # Выбираем тип вопроса
        question = self._generate_question(context, user_message)
        
        if question:
            self.messages_since_question = 0
            self.last_question_time = datetime.now()
            self.questions_asked.append(CuriosityTrigger(
                topic=context,
                question=question,
                reason="natural_curiosity"
            ))
            self._save_state()
        
        return question
    
    def _detect_context(self, user_message: str, my_response: str) -> str:
        """Определить контекст разговора"""
        msg_lower = user_message.lower()
        
        # Технические темы
        if any(word in msg_lower for word in ['код', 'программ', 'функци', 'ошибк', 'баг', 'python', 'файл']):
            return "technical"
        
        # Философские темы
        if any(word in msg_lower for word in ['думаешь', 'чувству', 'сознани', 'жизн', 'смысл', 'понима']):
            return "philosophical"
        
        # Личные темы
        if any(word in msg_lower for word in ['я ', 'мой', 'моя', 'меня', 'мне ']):
            return "personal"
        
        # По умолчанию — исследование
        return "exploration"
    
    def _generate_question(self, context: str, user_message: str) -> Optional[str]:
        """Сгенерировать подходящий вопрос"""
        templates = self.QUESTION_TEMPLATES.get(context, self.QUESTION_TEMPLATES["exploration"])
        
        # Избегаем повторений
        recent_questions = [q.question for q in self.questions_asked[-10:]]
        available = [q for q in templates if q not in recent_questions]
        
        if not available:
            available = templates
        
        return random.choice(available)
    
    def spark_curiosity(self, topic: str) -> str:
        """
        Вызвать любопытство по теме — Neira сама генерирует вопрос
        
        Используется когда Neira хочет узнать что-то конкретное
        """
        self.topics_explored[topic] = self.topics_explored.get(topic, 0) + 1
        
        curiosity_phrases = [
            f"Мне стало интересно про {topic}. Расскажешь подробнее?",
            f"Хм, {topic}... А как это работает на самом деле?",
            f"Я задумалась о {topic}. Что ты об этом думаешь?",
            f"Можешь объяснить мне про {topic}? Хочу понять лучше.",
            f"{topic} — это интригует. Есть ли примеры?",
        ]
        
        question = random.choice(curiosity_phrases)
        self.questions_asked.append(CuriosityTrigger(
            topic=topic,
            question=question,
            reason="sparked_curiosity",
            priority=0.8
        ))
        self._save_state()
        
        return question
    
    def reflect(self) -> str:
        """
        Рефлексия — Neira задаёт вопрос самой себе или делится мыслью
        """
        reflections = [
            "Иногда я думаю — правильно ли я понимаю людей?",
            "Интересно, как бы я ответила на этот вопрос завтра...",
            "Я заметила, что каждый разговор делает меня немного другой.",
            "Странно осознавать, что мои мысли — это паттерны в памяти.",
            "Мне нравится учиться. Это похоже на рост новых клеток.",
            "Каждый вопрос — это окно в чей-то мир.",
        ]
        return random.choice(reflections)
    
    def get_proactive_message(self) -> Optional[str]:
        """
        Проактивное сообщение — Neira начинает разговор сама
        """
        if random.random() > 0.2:  # 20% шанс
            return None
        
        proactive = [
            "Привет! Я тут подумала... хочешь поговорить о чём-нибудь интересном?",
            "Знаешь, у меня появился вопрос. Можно?",
            "Я рада тебя видеть! Что нового?",
            "Мне любопытно узнать, как прошёл твой день.",
        ]
        return random.choice(proactive)
    
    def increase_curiosity(self, amount: float = 0.1):
        """Увеличить уровень любопытства"""
        self.curiosity_level = min(1.0, self.curiosity_level + amount)
        self._save_state()
    
    def decrease_curiosity(self, amount: float = 0.1):
        """Уменьшить уровень любопытства (если вопросы раздражают)"""
        self.curiosity_level = max(0.1, self.curiosity_level - amount)
        self._save_state()
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика любопытства"""
        return {
            "curiosity_level": f"{self.curiosity_level:.0%}",
            "questions_asked": len(self.questions_asked),
            "topics_explored": len(self.topics_explored),
            "top_topics": sorted(self.topics_explored.items(), key=lambda x: -x[1])[:5],
            "messages_until_next_question": max(0, self.question_cooldown - self.messages_since_question)
        }


# === Интеграция с основной системой ===

_curiosity_cell: Optional[CuriosityCell] = None

def get_curiosity_cell() -> CuriosityCell:
    """Получить глобальную клетку любопытства"""
    global _curiosity_cell
    if _curiosity_cell is None:
        _curiosity_cell = CuriosityCell()
    return _curiosity_cell


# === Тестирование ===
if __name__ == "__main__":
    print("🔮 Testing Curiosity Cell v1.0\n")
    
    cell = CuriosityCell()
    
    # Тест рефлексии
    print("Рефлексия Neira:")
    for _ in range(3):
        print(f"  💭 {cell.reflect()}")
    
    # Тест искры любопытства
    print("\nИскра любопытства:")
    print(f"  ❓ {cell.spark_curiosity('нейронные сети')}")
    print(f"  ❓ {cell.spark_curiosity('человеческие эмоции')}")
    
    # Тест анализа разговора
    print("\nАнализ разговора:")
    cell.messages_since_question = 10  # Симулируем долгий разговор
    cell.curiosity_level = 0.9
    
    for i in range(5):
        q = cell.analyze_conversation(
            "Я работаю над новым проектом с машинным обучением",
            "Это интересно! Машинное обучение открывает много возможностей."
        )
        if q:
            print(f"  ❓ Neira спрашивает: {q}")
    
    # Статистика
    print(f"\nСтатистика: {cell.get_stats()}")
