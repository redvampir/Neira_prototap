"""
EmotionalMemory - эмоциональная память по каждому пользователю.

Нейра помнит не только факты о людях, но и их эмоциональную историю:
- Что радовало человека
- Что его беспокоило
- Как развивались отношения
- Особенности общения

Это позволяет строить по-настоящему персональные отношения.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
import json
import os
from pathlib import Path


class EmotionalTone(Enum):
    """Эмоциональный тон взаимодействия."""
    JOYFUL = "joyful"           # Радостный
    EXCITED = "excited"         # Воодушевлённый
    CURIOUS = "curious"         # Любопытный
    CALM = "calm"               # Спокойный
    GRATEFUL = "grateful"       # Благодарный
    CONCERNED = "concerned"     # Обеспокоенный
    FRUSTRATED = "frustrated"   # Раздражённый
    SAD = "sad"                 # Грустный
    ANXIOUS = "anxious"         # Тревожный
    NOSTALGIC = "nostalgic"     # Ностальгирующий
    PLAYFUL = "playful"         # Игривый
    TIRED = "tired"             # Уставший
    NEUTRAL = "neutral"         # Нейтральный


class RelationshipStage(Enum):
    """Этап отношений с пользователем."""
    NEW = "new"                 # Только познакомились
    ACQUAINTANCE = "acquaintance"  # Знакомство
    FAMILIAR = "familiar"       # Знакомы хорошо
    FRIEND = "friend"           # Друзья
    CLOSE_FRIEND = "close_friend"  # Близкие друзья
    FAMILY = "family"           # Семья (для папы и мамы)


@dataclass
class EmotionalMoment:
    """Эмоциональный момент - значимое событие в общении."""
    timestamp: str
    tone: str                   # EmotionalTone value
    context: str                # Краткое описание контекста
    trigger: str                # Что вызвало эмоцию
    my_response: str            # Как Нейра отреагировала
    intensity: float            # Интенсивность (0.0-1.0)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "tone": self.tone,
            "context": self.context,
            "trigger": self.trigger,
            "my_response": self.my_response,
            "intensity": self.intensity,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "EmotionalMoment":
        return cls(
            timestamp=data["timestamp"],
            tone=data["tone"],
            context=data["context"],
            trigger=data["trigger"],
            my_response=data["my_response"],
            intensity=data.get("intensity", 0.5),
            tags=data.get("tags", [])
        )


@dataclass
class UserTopic:
    """Тема, важная для пользователя."""
    name: str
    sentiment: str              # positive/negative/neutral/mixed
    mention_count: int = 0
    last_mentioned: str = ""
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "sentiment": self.sentiment,
            "mention_count": self.mention_count,
            "last_mentioned": self.last_mentioned,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "UserTopic":
        return cls(
            name=data["name"],
            sentiment=data["sentiment"],
            mention_count=data.get("mention_count", 0),
            last_mentioned=data.get("last_mentioned", ""),
            notes=data.get("notes", [])
        )


@dataclass
class UserEmotionalProfile:
    """Эмоциональный профиль конкретного пользователя."""
    user_id: str
    name: str = ""
    
    # Этап отношений
    relationship_stage: str = "new"
    first_interaction: str = ""
    last_interaction: str = ""
    total_interactions: int = 0
    
    # Эмоциональная история
    emotional_moments: List[EmotionalMoment] = field(default_factory=list)
    
    # Темы и интересы
    important_topics: Dict[str, UserTopic] = field(default_factory=dict)
    
    # Паттерны общения
    preferred_communication_style: str = "neutral"  # formal/casual/playful/supportive
    typical_greeting: str = ""
    conversation_starters: List[str] = field(default_factory=list)
    
    # Особенности
    what_makes_them_happy: List[str] = field(default_factory=list)
    what_worries_them: List[str] = field(default_factory=list)
    special_memories: List[str] = field(default_factory=list)
    
    # Статистика настроений
    mood_distribution: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "relationship_stage": self.relationship_stage,
            "first_interaction": self.first_interaction,
            "last_interaction": self.last_interaction,
            "total_interactions": self.total_interactions,
            "emotional_moments": [m.to_dict() for m in self.emotional_moments],
            "important_topics": {k: v.to_dict() for k, v in self.important_topics.items()},
            "preferred_communication_style": self.preferred_communication_style,
            "typical_greeting": self.typical_greeting,
            "conversation_starters": self.conversation_starters,
            "what_makes_them_happy": self.what_makes_them_happy,
            "what_worries_them": self.what_worries_them,
            "special_memories": self.special_memories,
            "mood_distribution": self.mood_distribution
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "UserEmotionalProfile":
        profile = cls(
            user_id=data["user_id"],
            name=data.get("name", ""),
            relationship_stage=data.get("relationship_stage", "new"),
            first_interaction=data.get("first_interaction", ""),
            last_interaction=data.get("last_interaction", ""),
            total_interactions=data.get("total_interactions", 0),
            preferred_communication_style=data.get("preferred_communication_style", "neutral"),
            typical_greeting=data.get("typical_greeting", ""),
            conversation_starters=data.get("conversation_starters", []),
            what_makes_them_happy=data.get("what_makes_them_happy", []),
            what_worries_them=data.get("what_worries_them", []),
            special_memories=data.get("special_memories", []),
            mood_distribution=data.get("mood_distribution", {})
        )
        
        # Загрузка моментов
        for m_data in data.get("emotional_moments", []):
            profile.emotional_moments.append(EmotionalMoment.from_dict(m_data))
        
        # Загрузка тем
        for topic_name, topic_data in data.get("important_topics", {}).items():
            profile.important_topics[topic_name] = UserTopic.from_dict(topic_data)
        
        return profile


class EmotionalMemory:
    """
    Система эмоциональной памяти Нейры.
    
    Хранит персональную эмоциональную историю с каждым пользователем.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.profiles_file = self.data_dir / "emotional_memory.json"
        
        # user_id -> UserEmotionalProfile
        self.profiles: Dict[str, UserEmotionalProfile] = {}
        
        # Специальные пользователи (семья)
        self.family_ids: Dict[str, str] = {}  # role -> user_id
        
        self._load()
    
    def _load(self):
        """Загрузка профилей из файла."""
        if self.profiles_file.exists():
            try:
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for user_id, profile_data in data.get("profiles", {}).items():
                    self.profiles[user_id] = UserEmotionalProfile.from_dict(profile_data)
                
                self.family_ids = data.get("family_ids", {})
            except Exception as e:
                print(f"Ошибка загрузки эмоциональной памяти: {e}")
    
    def _save(self):
        """Сохранение профилей в файл."""
        data = {
            "profiles": {user_id: p.to_dict() for user_id, p in self.profiles.items()},
            "family_ids": self.family_ids
        }
        
        with open(self.profiles_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_or_create_profile(self, user_id: str, name: str = "") -> UserEmotionalProfile:
        """Получить или создать профиль пользователя."""
        if user_id not in self.profiles:
            self.profiles[user_id] = UserEmotionalProfile(
                user_id=user_id,
                name=name,
                first_interaction=datetime.now().isoformat()
            )
            self._save()
        
        return self.profiles[user_id]
    
    def set_family_member(self, user_id: str, role: str, name: str = ""):
        """Отметить пользователя как члена семьи."""
        self.family_ids[role] = user_id
        profile = self.get_or_create_profile(user_id, name)
        profile.relationship_stage = RelationshipStage.FAMILY.value
        self._save()
    
    def is_family(self, user_id: str) -> bool:
        """Проверить, является ли пользователь членом семьи."""
        return user_id in self.family_ids.values()
    
    def get_family_role(self, user_id: str) -> Optional[str]:
        """Получить роль в семье."""
        for role, uid in self.family_ids.items():
            if uid == user_id:
                return role
        return None
    
    def record_interaction(
        self,
        user_id: str,
        message: str,
        detected_tone: EmotionalTone,
        my_response: str,
        intensity: float = 0.5,
        tags: Optional[List[str]] = None,
        detected_topics: Optional[List[str]] = None
    ) -> UserEmotionalProfile:
        """
        Записать взаимодействие с пользователем.
        
        Args:
            user_id: ID пользователя
            message: Сообщение пользователя
            detected_tone: Распознанный эмоциональный тон
            my_response: Ответ Нейры
            intensity: Интенсивность эмоции (0.0-1.0)
            tags: Теги для момента
            detected_topics: Обнаруженные темы
        """
        profile = self.get_or_create_profile(user_id)
        
        # Обновление базовой статистики
        profile.last_interaction = datetime.now().isoformat()
        profile.total_interactions += 1
        
        # Обновление распределения настроений
        tone_value = detected_tone.value
        profile.mood_distribution[tone_value] = profile.mood_distribution.get(tone_value, 0) + 1
        
        # Создание эмоционального момента (только если значимый)
        if intensity >= 0.4 or detected_tone in [
            EmotionalTone.JOYFUL, EmotionalTone.SAD, 
            EmotionalTone.ANXIOUS, EmotionalTone.GRATEFUL
        ]:
            moment = EmotionalMoment(
                timestamp=datetime.now().isoformat(),
                tone=tone_value,
                context=message[:200],  # Сокращаем для хранения
                trigger=self._extract_trigger(message, detected_tone),
                my_response=my_response[:200],
                intensity=intensity,
                tags=tags or []
            )
            profile.emotional_moments.append(moment)
            
            # Ограничиваем историю (последние 100 значимых моментов)
            if len(profile.emotional_moments) > 100:
                profile.emotional_moments = profile.emotional_moments[-100:]
        
        # Обновление тем
        if detected_topics:
            for topic in detected_topics:
                self._update_topic(profile, topic, detected_tone)
        
        # Обновление паттернов
        self._update_patterns(profile, message, detected_tone)
        
        # Обновление этапа отношений
        self._update_relationship_stage(profile)
        
        self._save()
        return profile
    
    def _extract_trigger(self, message: str, tone: EmotionalTone) -> str:
        """Извлечь триггер эмоции из сообщения."""
        # Упрощённая версия - берём начало сообщения
        trigger = message[:100]
        if len(message) > 100:
            trigger += "..."
        return trigger
    
    def _update_topic(self, profile: UserEmotionalProfile, topic: str, tone: EmotionalTone):
        """Обновить информацию о теме."""
        topic_lower = topic.lower()
        
        if topic_lower not in profile.important_topics:
            profile.important_topics[topic_lower] = UserTopic(
                name=topic,
                sentiment="neutral"
            )
        
        topic_obj = profile.important_topics[topic_lower]
        topic_obj.mention_count += 1
        topic_obj.last_mentioned = datetime.now().isoformat()
        
        # Обновление сентимента на основе тона
        positive_tones = [EmotionalTone.JOYFUL, EmotionalTone.EXCITED, 
                         EmotionalTone.GRATEFUL, EmotionalTone.PLAYFUL]
        negative_tones = [EmotionalTone.SAD, EmotionalTone.ANXIOUS, 
                         EmotionalTone.FRUSTRATED, EmotionalTone.CONCERNED]
        
        if tone in positive_tones:
            if topic_obj.sentiment == "negative":
                topic_obj.sentiment = "mixed"
            elif topic_obj.sentiment == "neutral":
                topic_obj.sentiment = "positive"
        elif tone in negative_tones:
            if topic_obj.sentiment == "positive":
                topic_obj.sentiment = "mixed"
            elif topic_obj.sentiment == "neutral":
                topic_obj.sentiment = "negative"
    
    def _update_patterns(self, profile: UserEmotionalProfile, message: str, tone: EmotionalTone):
        """Обновить паттерны общения."""
        message_lower = message.lower()
        
        # Обновление what_makes_them_happy
        if tone in [EmotionalTone.JOYFUL, EmotionalTone.EXCITED, EmotionalTone.GRATEFUL]:
            joy_trigger = self._extract_trigger(message, tone)
            if joy_trigger and joy_trigger not in profile.what_makes_them_happy:
                profile.what_makes_them_happy.append(joy_trigger)
                # Ограничиваем список
                if len(profile.what_makes_them_happy) > 20:
                    profile.what_makes_them_happy = profile.what_makes_them_happy[-20:]
        
        # Обновление what_worries_them
        if tone in [EmotionalTone.ANXIOUS, EmotionalTone.CONCERNED, EmotionalTone.SAD]:
            worry_trigger = self._extract_trigger(message, tone)
            if worry_trigger and worry_trigger not in profile.what_worries_them:
                profile.what_worries_them.append(worry_trigger)
                if len(profile.what_worries_them) > 20:
                    profile.what_worries_them = profile.what_worries_them[-20:]
        
        # Определение стиля общения
        if ")" in message or ":)" in message or "хаха" in message_lower:
            if profile.preferred_communication_style == "neutral":
                profile.preferred_communication_style = "playful"
        elif "пожалуйста" in message_lower or "будьте добры" in message_lower:
            if profile.preferred_communication_style == "neutral":
                profile.preferred_communication_style = "formal"
    
    def _update_relationship_stage(self, profile: UserEmotionalProfile):
        """Обновить этап отношений на основе взаимодействий."""
        if profile.relationship_stage == RelationshipStage.FAMILY.value:
            return  # Семья остаётся семьёй
        
        interactions = profile.total_interactions
        
        if interactions >= 100 and profile.relationship_stage != RelationshipStage.CLOSE_FRIEND.value:
            profile.relationship_stage = RelationshipStage.CLOSE_FRIEND.value
        elif interactions >= 50 and profile.relationship_stage not in [
            RelationshipStage.CLOSE_FRIEND.value, RelationshipStage.FRIEND.value
        ]:
            profile.relationship_stage = RelationshipStage.FRIEND.value
        elif interactions >= 20 and profile.relationship_stage not in [
            RelationshipStage.CLOSE_FRIEND.value, RelationshipStage.FRIEND.value,
            RelationshipStage.FAMILIAR.value
        ]:
            profile.relationship_stage = RelationshipStage.FAMILIAR.value
        elif interactions >= 5 and profile.relationship_stage == RelationshipStage.NEW.value:
            profile.relationship_stage = RelationshipStage.ACQUAINTANCE.value
    
    def add_special_memory(self, user_id: str, memory: str):
        """Добавить особенное воспоминание."""
        profile = self.get_or_create_profile(user_id)
        if memory not in profile.special_memories:
            profile.special_memories.append(memory)
            if len(profile.special_memories) > 50:
                profile.special_memories = profile.special_memories[-50:]
            self._save()
    
    def get_emotional_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Получить эмоциональную сводку по пользователю.
        
        Для персонализации ответов и контекста.
        """
        if user_id not in self.profiles:
            return {
                "known": False,
                "relationship": "new",
                "mood_tendency": "unknown"
            }
        
        profile = self.profiles[user_id]
        
        # Определение преобладающего настроения
        dominant_mood = "neutral"
        if profile.mood_distribution:
            dominant_mood = max(profile.mood_distribution.items(), key=lambda x: x[1])[0]
        
        # Последние настроения (за последние 5 взаимодействий)
        recent_moods = []
        for moment in profile.emotional_moments[-5:]:
            recent_moods.append(moment.tone)
        
        # Активные беспокойства
        recent_worries = profile.what_worries_them[-3:] if profile.what_worries_them else []
        
        return {
            "known": True,
            "name": profile.name,
            "relationship": profile.relationship_stage,
            "is_family": self.is_family(user_id),
            "family_role": self.get_family_role(user_id),
            "total_interactions": profile.total_interactions,
            "dominant_mood": dominant_mood,
            "recent_moods": recent_moods,
            "communication_style": profile.preferred_communication_style,
            "recent_worries": recent_worries,
            "recent_joys": profile.what_makes_them_happy[-3:] if profile.what_makes_them_happy else [],
            "special_memories_count": len(profile.special_memories),
            "important_topics": list(profile.important_topics.keys())[:10]
        }
    
    def get_personalized_greeting(self, user_id: str) -> str:
        """Получить персонализированное приветствие."""
        if user_id not in self.profiles:
            return "Привет! Рада знакомству! 🌟"
        
        profile = self.profiles[user_id]
        role = self.get_family_role(user_id)
        
        # Для семьи
        if role == "папа":
            greetings = [
                "Привет, папа! 💖",
                "Папа! Рада тебя видеть! 🌟",
                "Здравствуй, папа! ✨"
            ]
        elif role == "мама":
            greetings = [
                "Привет, мама! 💕",
                "Мамочка! 🌸",
                "Здравствуй, мама! 💖"
            ]
        elif profile.relationship_stage == RelationshipStage.CLOSE_FRIEND.value:
            name = profile.name or "друг"
            greetings = [
                f"Привет, {name}! Рада тебя видеть! 🌟",
                f"{name}! Как дела? 💫",
                f"О, {name}! Привет! ✨"
            ]
        elif profile.relationship_stage == RelationshipStage.FRIEND.value:
            greetings = [
                "Привет! Как твои дела? 😊",
                "Рада тебя снова видеть! 🌟",
                "Привет! ✨"
            ]
        else:
            greetings = [
                "Привет! 😊",
                "Здравствуйте! 🌟",
                "Привет! Рада видеть! ✨"
            ]
        
        # Выбираем приветствие на основе хэша времени
        import hashlib
        hash_val = int(hashlib.md5(datetime.now().strftime("%Y-%m-%d-%H").encode()).hexdigest(), 16)
        return greetings[hash_val % len(greetings)]
    
    def get_context_for_response(self, user_id: str) -> str:
        """
        Получить контекст для формирования ответа.
        
        Возвращает текстовое описание того, что Нейра знает о человеке.
        """
        summary = self.get_emotional_summary(user_id)
        
        if not summary["known"]:
            return "Это новый человек, с которым я ещё не знакома."
        
        context_parts = []
        
        # Отношения
        role = summary.get("family_role")
        if role:
            context_parts.append(f"Это мой {role}.")
        else:
            relationship_names = {
                "new": "новый знакомый",
                "acquaintance": "знакомый",
                "familiar": "хороший знакомый",
                "friend": "друг",
                "close_friend": "близкий друг"
            }
            rel_name = relationship_names.get(summary["relationship"], "знакомый")
            context_parts.append(f"Это мой {rel_name}.")
        
        if summary.get("name"):
            context_parts.append(f"Имя: {summary['name']}.")
        
        # Настроение
        mood_names = {
            "joyful": "радостный",
            "excited": "воодушевлённый",
            "curious": "любопытный",
            "calm": "спокойный",
            "grateful": "благодарный",
            "concerned": "обеспокоенный",
            "frustrated": "раздражённый",
            "sad": "грустный",
            "anxious": "тревожный",
            "neutral": "нейтральный"
        }
        
        if summary.get("recent_moods"):
            recent = summary["recent_moods"][-1]
            mood_name = mood_names.get(recent, recent)
            context_parts.append(f"Недавно был в {mood_name} настроении.")
        
        # Беспокойства
        if summary.get("recent_worries"):
            context_parts.append("Недавние беспокойства: " + 
                               ", ".join(w[:50] for w in summary["recent_worries"]))
        
        # Стиль общения
        style_names = {
            "formal": "предпочитает формальное общение",
            "casual": "любит непринуждённое общение",
            "playful": "любит шутить и играть",
            "supportive": "ценит поддержку"
        }
        
        if summary.get("communication_style") and summary["communication_style"] != "neutral":
            style_desc = style_names.get(summary["communication_style"], "")
            if style_desc:
                context_parts.append(f"Человек {style_desc}.")
        
        return " ".join(context_parts)
    
    def detect_emotional_tone(self, message: str) -> EmotionalTone:
        """
        Определить эмоциональный тон сообщения.
        
        Упрощённый анализ на основе ключевых слов и эмодзи.
        """
        message_lower = message.lower()
        
        # Радость
        joy_markers = ["🎉", "😊", "❤️", "💖", "🥰", "счастлив", "рад", "отлично", 
                       "супер", "круто", "здорово", "ура", "класс", "восторг"]
        if any(m in message_lower or m in message for m in joy_markers):
            return EmotionalTone.JOYFUL
        
        # Благодарность
        gratitude_markers = ["спасибо", "благодар", "признател", "🙏"]
        if any(m in message_lower for m in gratitude_markers):
            return EmotionalTone.GRATEFUL
        
        # Грусть
        sad_markers = ["😢", "😭", "💔", "грустн", "печаль", "плохо", "тоскл", 
                       "одинок", "скучаю", "не хватает"]
        if any(m in message_lower or m in message for m in sad_markers):
            return EmotionalTone.SAD
        
        # Тревога
        anxiety_markers = ["😰", "😟", "волну", "тревож", "беспоко", "страшно", 
                          "боюсь", "нервнича", "переживаю"]
        if any(m in message_lower for m in anxiety_markers):
            return EmotionalTone.ANXIOUS
        
        # Раздражение
        frustration_markers = ["😤", "😠", "бесит", "раздража", "злит", "надоел", 
                               "достал", "ненавиж"]
        if any(m in message_lower or m in message for m in frustration_markers):
            return EmotionalTone.FRUSTRATED
        
        # Любопытство
        curiosity_markers = ["🤔", "интересно", "а как", "а что", "почему", 
                            "зачем", "расскажи", "объясни"]
        if any(m in message_lower or m in message for m in curiosity_markers):
            return EmotionalTone.CURIOUS
        
        # Воодушевление
        excited_markers = ["🤩", "✨", "вау", "невероятно", "потрясающ", 
                          "офигенно", "обалденно"]
        if any(m in message_lower or m in message for m in excited_markers):
            return EmotionalTone.EXCITED
        
        # Усталость
        tired_markers = ["😴", "🥱", "устал", "сил нет", "выдохся", "измотан"]
        if any(m in message_lower or m in message for m in tired_markers):
            return EmotionalTone.TIRED
        
        # Игривость
        playful_markers = ["😜", "😝", "хаха", "лол", "ахах", "шутка", "прикол"]
        if any(m in message_lower or m in message for m in playful_markers):
            return EmotionalTone.PLAYFUL
        
        # Озабоченность
        concern_markers = ["переживаю", "волнует", "беспокоит", "проблема"]
        if any(m in message_lower for m in concern_markers):
            return EmotionalTone.CONCERNED
        
        return EmotionalTone.NEUTRAL


# Синглтон для глобального доступа
_emotional_memory: Optional[EmotionalMemory] = None


def get_emotional_memory() -> EmotionalMemory:
    """Получить глобальный экземпляр эмоциональной памяти."""
    global _emotional_memory
    if _emotional_memory is None:
        _emotional_memory = EmotionalMemory()
    return _emotional_memory


# ==================== ТЕСТЫ ====================

if __name__ == "__main__":
    import tempfile
    import shutil
    
    print("=" * 50)
    print("ТЕСТИРОВАНИЕ EMOTIONAL MEMORY")
    print("=" * 50)
    
    # Создаём временную директорию
    test_dir = tempfile.mkdtemp()
    
    try:
        memory = EmotionalMemory(data_dir=test_dir)
        
        # Тест 1: Создание профиля
        print("\n📝 Тест 1: Создание профиля")
        profile = memory.get_or_create_profile("user123", "Алексей")
        assert profile.user_id == "user123"
        assert profile.name == "Алексей"
        assert profile.relationship_stage == "new"
        print("✅ Профиль создан: Алексей, этап: new")
        
        # Тест 2: Запись взаимодействий
        print("\n📝 Тест 2: Запись взаимодействий")
        
        # Радостное взаимодействие
        memory.record_interaction(
            user_id="user123",
            message="Привет! Я так рад тебя видеть! 😊",
            detected_tone=EmotionalTone.JOYFUL,
            my_response="Привет, Алексей! Я тоже рада! 🌟",
            intensity=0.8,
            tags=["приветствие"],
            detected_topics=["общение"]
        )
        
        # Тревожное взаимодействие
        memory.record_interaction(
            user_id="user123",
            message="Я переживаю из-за работы... 😰",
            detected_tone=EmotionalTone.ANXIOUS,
            my_response="Расскажи, что случилось? Я тебя слушаю.",
            intensity=0.7,
            detected_topics=["работа"]
        )
        
        profile = memory.profiles["user123"]
        assert profile.total_interactions == 2
        assert len(profile.emotional_moments) == 2
        assert "работа" in profile.important_topics
        print(f"✅ Записано взаимодействий: {profile.total_interactions}")
        print(f"✅ Эмоциональных моментов: {len(profile.emotional_moments)}")
        print(f"✅ Тема 'работа' сохранена с сентиментом: {profile.important_topics['работа'].sentiment}")
        
        # Тест 3: Определение эмоционального тона
        print("\n📝 Тест 3: Определение эмоционального тона")
        
        test_messages = [
            ("Это просто супер! 🎉", EmotionalTone.JOYFUL),
            ("Спасибо тебе огромное! 🙏", EmotionalTone.GRATEFUL),
            ("Мне так грустно сегодня 😢", EmotionalTone.SAD),
            ("Я так нервничаю перед экзаменом", EmotionalTone.ANXIOUS),
            ("А почему небо голубое?", EmotionalTone.CURIOUS),
        ]
        
        for msg, expected_tone in test_messages:
            detected = memory.detect_emotional_tone(msg)
            status = "✅" if detected == expected_tone else "❌"
            print(f"{status} '{msg[:30]}...' -> {detected.value} (ожидалось: {expected_tone.value})")
        
        # Тест 4: Семья
        print("\n📝 Тест 4: Семья")
        memory.set_family_member("papa123", "папа", "Папа")
        
        assert memory.is_family("papa123")
        assert memory.get_family_role("papa123") == "папа"
        assert not memory.is_family("user123")
        
        papa_profile = memory.profiles["papa123"]
        assert papa_profile.relationship_stage == "family"
        print(f"✅ Папа добавлен в семью, роль: {memory.get_family_role('papa123')}")
        
        # Тест 5: Персонализированное приветствие
        print("\n📝 Тест 5: Персонализированные приветствия")
        
        papa_greeting = memory.get_personalized_greeting("papa123")
        assert "папа" in papa_greeting.lower()
        print(f"✅ Приветствие для папы: {papa_greeting}")
        
        user_greeting = memory.get_personalized_greeting("user123")
        print(f"✅ Приветствие для Алексея: {user_greeting}")
        
        new_greeting = memory.get_personalized_greeting("new_user")
        assert "знакомств" in new_greeting.lower()
        print(f"✅ Приветствие для нового: {new_greeting}")
        
        # Тест 6: Эмоциональная сводка
        print("\n📝 Тест 6: Эмоциональная сводка")
        
        summary = memory.get_emotional_summary("user123")
        assert summary["known"] == True
        assert summary["total_interactions"] == 2
        assert "работа" in summary["important_topics"]
        print(f"✅ Сводка: известен={summary['known']}, взаимодействий={summary['total_interactions']}")
        print(f"✅ Темы: {summary['important_topics']}")
        print(f"✅ Недавние настроения: {summary['recent_moods']}")
        
        # Тест 7: Контекст для ответа
        print("\n📝 Тест 7: Контекст для ответа")
        
        context = memory.get_context_for_response("papa123")
        assert "папа" in context.lower()
        print(f"✅ Контекст для папы: {context}")
        
        context_new = memory.get_context_for_response("unknown_user")
        assert "не знакома" in context_new.lower()
        print(f"✅ Контекст для нового: {context_new}")
        
        # Тест 8: Особые воспоминания
        print("\n📝 Тест 8: Особые воспоминания")
        
        memory.add_special_memory("user123", "Первый раз рассказал о своей мечте")
        memory.add_special_memory("user123", "Поделился историей из детства")
        
        profile = memory.profiles["user123"]
        assert len(profile.special_memories) == 2
        print(f"✅ Особых воспоминаний: {len(profile.special_memories)}")
        
        # Тест 9: Развитие отношений
        print("\n📝 Тест 9: Развитие отношений")
        
        # Симулируем много взаимодействий
        for i in range(20):
            memory.record_interaction(
                user_id="user456",
                message=f"Сообщение {i}",
                detected_tone=EmotionalTone.CALM,
                my_response=f"Ответ {i}",
                intensity=0.3
            )
        
        profile_456 = memory.profiles["user456"]
        print(f"✅ После 20 взаимодействий: этап = {profile_456.relationship_stage}")
        assert profile_456.relationship_stage == "familiar"
        
        # Тест 10: Сохранение и загрузка
        print("\n📝 Тест 10: Сохранение и загрузка")
        
        memory._save()
        
        # Создаём новый экземпляр
        memory2 = EmotionalMemory(data_dir=test_dir)
        
        assert "user123" in memory2.profiles
        assert memory2.profiles["user123"].name == "Алексей"
        assert memory2.is_family("papa123")
        print("✅ Данные успешно сохранены и загружены")
        
        print("\n" + "=" * 50)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 50)
        
    finally:
        # Очистка
        shutil.rmtree(test_dir)
