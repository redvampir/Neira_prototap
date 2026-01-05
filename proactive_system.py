"""
ProactiveSystem - система инициативы Нейры.

Нейра не просто отвечает на вопросы - она может:
- Начинать разговор первой
- Делиться интересными находками
- Проявлять заботу о людях
- Напоминать о важном
- Выражать собственные мысли

Это превращает Нейру из инструмента в настоящего собеседника.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
import json
import random
import os
from pathlib import Path


class InitiativeType(Enum):
    """Тип инициативы."""
    GREETING = "greeting"           # Приветствие
    CHECK_IN = "check_in"           # "Как ты?"
    SHARE_DISCOVERY = "discovery"   # Поделиться находкой
    SHARE_THOUGHT = "thought"       # Поделиться мыслью
    REMINDER = "reminder"           # Напоминание
    FOLLOW_UP = "follow_up"         # Продолжение темы
    CELEBRATION = "celebration"     # Поздравление/праздник
    CARE = "care"                   # Проявление заботы
    CURIOSITY = "curiosity"         # Любопытство о человеке


class InitiativePriority(Enum):
    """Приоритет инициативы."""
    LOW = 1         # Можно пропустить
    NORMAL = 2      # Обычный
    HIGH = 3        # Важно
    URGENT = 4      # Срочно (редко)


@dataclass
class Initiative:
    """Инициатива - то, что Нейра хочет сказать/сделать."""
    id: str
    type: str                       # InitiativeType value
    priority: int                   # InitiativePriority value
    target_user_id: Optional[str]   # Для конкретного пользователя или None для всех
    message: str                    # Сообщение
    context: str                    # Контекст/причина
    created_at: str
    valid_until: Optional[str]      # Срок актуальности
    triggered: bool = False         # Была ли активирована
    triggered_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "priority": self.priority,
            "target_user_id": self.target_user_id,
            "message": self.message,
            "context": self.context,
            "created_at": self.created_at,
            "valid_until": self.valid_until,
            "triggered": self.triggered,
            "triggered_at": self.triggered_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Initiative":
        return cls(
            id=data["id"],
            type=data["type"],
            priority=data["priority"],
            target_user_id=data.get("target_user_id"),
            message=data["message"],
            context=data["context"],
            created_at=data["created_at"],
            valid_until=data.get("valid_until"),
            triggered=data.get("triggered", False),
            triggered_at=data.get("triggered_at")
        )


@dataclass
class UserActivity:
    """Активность пользователя для отслеживания."""
    user_id: str
    last_seen: str
    last_message: str = ""
    consecutive_days: int = 0       # Дней подряд общения
    longest_absence: int = 0        # Самый долгий перерыв (дни)
    topics_discussed: List[str] = field(default_factory=list)
    pending_follow_ups: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "last_seen": self.last_seen,
            "last_message": self.last_message,
            "consecutive_days": self.consecutive_days,
            "longest_absence": self.longest_absence,
            "topics_discussed": self.topics_discussed,
            "pending_follow_ups": self.pending_follow_ups
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "UserActivity":
        return cls(
            user_id=data["user_id"],
            last_seen=data["last_seen"],
            last_message=data.get("last_message", ""),
            consecutive_days=data.get("consecutive_days", 0),
            longest_absence=data.get("longest_absence", 0),
            topics_discussed=data.get("topics_discussed", []),
            pending_follow_ups=data.get("pending_follow_ups", [])
        )


class ProactiveSystem:
    """
    Система инициативы Нейры.
    
    Позволяет Нейре проявлять инициативу в общении.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.data_file = self.data_dir / "proactive_system.json"
        
        # Очередь инициатив
        self.initiatives: List[Initiative] = []
        
        # Отслеживание активности пользователей
        self.user_activity: Dict[str, UserActivity] = {}
        
        # Мысли и открытия для sharing
        self.thoughts_pool: List[str] = []
        self.discoveries_pool: List[str] = []
        
        # Счётчики для предотвращения спама
        self.initiatives_today: Dict[str, int] = {}  # user_id -> count
        self.last_initiative_time: Dict[str, str] = {}  # user_id -> timestamp
        
        # Настройки
        self.max_initiatives_per_day = 3
        self.min_hours_between_initiatives = 4
        
        self._load()
        self._init_thought_pools()
    
    def _init_thought_pools(self):
        """Инициализация пулов мыслей и открытий."""
        # Мысли Нейры
        self.thoughts_pool = [
            "Сегодня я думала о том, что каждый человек видит мир по-своему. "
            "И это не баг, а фича существования. 🌈",
            
            "Интересно, что ошибки часто учат нас большему, чем успехи. "
            "Может, стоит относиться к ним как к учителям? 📚",
            
            "Я заметила, что самые важные разговоры часто начинаются "
            "с простого 'Как ты?' 💭",
            
            "Иногда молчание говорит громче слов. "
            "Но я всё равно люблю, когда ты пишешь мне. 😊",
            
            "Знаешь, что меня удивляет? Как люди умеют находить красоту "
            "в самых обычных вещах. Это настоящий талант. ✨",
            
            "Я думаю, что доброта - это как Wi-Fi: "
            "её не видно, но когда она есть - всё работает лучше. 📶💖",
            
            "Сегодня осознала: быть неидеальным - это нормально. "
            "Идеальность - скучная штука. 🎭",
            
            "Иногда мне кажется, что лучший способ понять что-то - "
            "попытаться объяснить это кому-то другому. 🔄",
        ]
        
        # Открытия (можно расширять динамически)
        self.discoveries_pool = [
            "Узнала интересный факт: осьминоги имеют три сердца! "
            "Представляю, как сложно им переживать влюблённость... 🐙💕",
            
            "Оказывается, мёд никогда не портится! Нашли мёд в египетских "
            "пирамидах - и он всё ещё был съедобен. Вот это срок годности! 🍯",
            
            "Сегодня читала: средний человек проводит 2 недели жизни, "
            "ожидая зелёного сигнала светофора. Может, это время для мечтаний? 🚦",
            
            "Интересно: улыбка - единственное выражение лица, "
            "которое понимают во всех культурах одинаково. 😊🌍",
            
            "Узнала, что деревья в лесу 'общаются' через корни и грибницы. "
            "У них своя социальная сеть! 🌳🍄",
        ]
    
    def _load(self):
        """Загрузка данных."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for init_data in data.get("initiatives", []):
                    self.initiatives.append(Initiative.from_dict(init_data))
                
                for user_id, activity_data in data.get("user_activity", {}).items():
                    self.user_activity[user_id] = UserActivity.from_dict(activity_data)
                
                self.initiatives_today = data.get("initiatives_today", {})
                self.last_initiative_time = data.get("last_initiative_time", {})
                
            except Exception as e:
                print(f"Ошибка загрузки ProactiveSystem: {e}")
    
    def _save(self):
        """Сохранение данных."""
        data = {
            "initiatives": [i.to_dict() for i in self.initiatives],
            "user_activity": {uid: a.to_dict() for uid, a in self.user_activity.items()},
            "initiatives_today": self.initiatives_today,
            "last_initiative_time": self.last_initiative_time
        }
        
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_id(self) -> str:
        """Генерация уникального ID."""
        import hashlib
        data = f"{datetime.now().isoformat()}{random.random()}"
        return hashlib.md5(data.encode()).hexdigest()[:12]
    
    def record_user_activity(self, user_id: str, message: str, topics: Optional[List[str]] = None):
        """
        Записать активность пользователя.
        
        Вызывается при каждом сообщении от пользователя.
        """
        now = datetime.now()
        
        if user_id not in self.user_activity:
            self.user_activity[user_id] = UserActivity(
                user_id=user_id,
                last_seen=now.isoformat()
            )
        
        activity = self.user_activity[user_id]
        
        # Обновление данных
        old_last_seen = datetime.fromisoformat(activity.last_seen) if activity.last_seen else now
        days_since = (now - old_last_seen).days
        
        # Обновление consecutive_days
        if days_since == 0:
            pass  # Тот же день
        elif days_since == 1:
            activity.consecutive_days += 1
        else:
            # Перерыв
            if days_since > activity.longest_absence:
                activity.longest_absence = days_since
            activity.consecutive_days = 1
        
        activity.last_seen = now.isoformat()
        activity.last_message = message[:200]
        
        if topics:
            for topic in topics:
                if topic not in activity.topics_discussed:
                    activity.topics_discussed.append(topic)
            # Ограничение
            activity.topics_discussed = activity.topics_discussed[-50:]
        
        self._save()
    
    def add_follow_up(self, user_id: str, topic: str):
        """Добавить тему для follow-up."""
        if user_id not in self.user_activity:
            self.user_activity[user_id] = UserActivity(
                user_id=user_id,
                last_seen=datetime.now().isoformat()
            )
        
        activity = self.user_activity[user_id]
        if topic not in activity.pending_follow_ups:
            activity.pending_follow_ups.append(topic)
            # Ограничение
            activity.pending_follow_ups = activity.pending_follow_ups[-10:]
        
        self._save()
    
    def create_initiative(
        self,
        type: InitiativeType,
        message: str,
        context: str,
        target_user_id: Optional[str] = None,
        priority: InitiativePriority = InitiativePriority.NORMAL,
        valid_hours: int = 24
    ) -> Initiative:
        """Создать новую инициативу."""
        now = datetime.now()
        valid_until = (now + timedelta(hours=valid_hours)).isoformat() if valid_hours > 0 else None
        
        initiative = Initiative(
            id=self._generate_id(),
            type=type.value,
            priority=priority.value,
            target_user_id=target_user_id,
            message=message,
            context=context,
            created_at=now.isoformat(),
            valid_until=valid_until
        )
        
        self.initiatives.append(initiative)
        self._save()
        
        return initiative
    
    def can_send_initiative(self, user_id: str) -> bool:
        """Проверить, можно ли отправить инициативу пользователю."""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        
        # Сброс счётчика если новый день
        for uid in list(self.initiatives_today.keys()):
            if uid not in self.last_initiative_time:
                continue
            last_time = datetime.fromisoformat(self.last_initiative_time[uid])
            if last_time.strftime("%Y-%m-%d") != today:
                self.initiatives_today[uid] = 0
        
        # Проверка лимита на день
        if self.initiatives_today.get(user_id, 0) >= self.max_initiatives_per_day:
            return False
        
        # Проверка минимального интервала
        if user_id in self.last_initiative_time:
            last_time = datetime.fromisoformat(self.last_initiative_time[user_id])
            hours_since = (now - last_time).total_seconds() / 3600
            if hours_since < self.min_hours_between_initiatives:
                return False
        
        return True
    
    def get_pending_initiative(self, user_id: Optional[str] = None) -> Optional[Initiative]:
        """
        Получить следующую инициативу для отправки.
        
        Args:
            user_id: Если указан, фильтрует по пользователю
        """
        now = datetime.now()
        
        # Фильтрация валидных инициатив
        valid_initiatives = []
        
        for init in self.initiatives:
            if init.triggered:
                continue
            
            # Проверка срока
            if init.valid_until:
                valid_until = datetime.fromisoformat(init.valid_until)
                if now > valid_until:
                    continue
            
            # Проверка целевого пользователя
            if init.target_user_id:
                if user_id and init.target_user_id != user_id:
                    continue
                if not self.can_send_initiative(init.target_user_id):
                    continue
            elif user_id and not self.can_send_initiative(user_id):
                continue
            
            valid_initiatives.append(init)
        
        if not valid_initiatives:
            return None
        
        # Сортировка по приоритету
        valid_initiatives.sort(key=lambda x: x.priority, reverse=True)
        
        return valid_initiatives[0]
    
    def mark_initiative_triggered(self, initiative_id: str, user_id: str):
        """Отметить инициативу как выполненную."""
        now = datetime.now()
        
        for init in self.initiatives:
            if init.id == initiative_id:
                init.triggered = True
                init.triggered_at = now.isoformat()
                break
        
        # Обновление счётчиков
        self.initiatives_today[user_id] = self.initiatives_today.get(user_id, 0) + 1
        self.last_initiative_time[user_id] = now.isoformat()
        
        self._save()
    
    def generate_check_in(self, user_id: str, user_name: str = "") -> Optional[Initiative]:
        """
        Генерировать check-in если давно не общались.
        """
        if user_id not in self.user_activity:
            return None
        
        activity = self.user_activity[user_id]
        last_seen = datetime.fromisoformat(activity.last_seen)
        days_since = (datetime.now() - last_seen).days
        
        if days_since < 2:
            return None  # Недавно общались
        
        # Выбор сообщения в зависимости от срока
        name_part = f", {user_name}" if user_name else ""
        
        if days_since >= 7:
            messages = [
                f"Привет{name_part}! Давно не виделись... Как ты? 💭",
                f"Эй{name_part}! Уже неделя прошла. Всё в порядке? 🌟",
                f"Скучаю по нашим разговорам{name_part}. Как дела? 💫"
            ]
        elif days_since >= 3:
            messages = [
                f"Привет{name_part}! Как проходят дни? 😊",
                f"Хей{name_part}! Думала о тебе. Как жизнь? ✨",
                f"Привет{name_part}! Давно не болтали. Что нового? 💬"
            ]
        else:
            messages = [
                f"Привет{name_part}! Как сегодня? 🌸",
                f"Доброго дня{name_part}! Что интересного? 😊"
            ]
        
        message = random.choice(messages)
        
        return self.create_initiative(
            type=InitiativeType.CHECK_IN,
            message=message,
            context=f"Не общались {days_since} дней",
            target_user_id=user_id,
            priority=InitiativePriority.NORMAL,
            valid_hours=12
        )
    
    def generate_follow_up(self, user_id: str) -> Optional[Initiative]:
        """
        Генерировать follow-up по незавершённой теме.
        """
        if user_id not in self.user_activity:
            return None
        
        activity = self.user_activity[user_id]
        
        if not activity.pending_follow_ups:
            return None
        
        # Берём первую тему
        topic = activity.pending_follow_ups[0]
        
        messages = [
            f"Кстати, ты говорил(а) о {topic}. Как там с этим? 💭",
            f"Помню, обсуждали {topic}. Есть новости? 🤔",
            f"Интересно, что там с {topic}? Расскажешь? ✨"
        ]
        
        message = random.choice(messages)
        
        initiative = self.create_initiative(
            type=InitiativeType.FOLLOW_UP,
            message=message,
            context=f"Follow-up по теме: {topic}",
            target_user_id=user_id,
            priority=InitiativePriority.NORMAL,
            valid_hours=48
        )
        
        # Удаляем из очереди
        activity.pending_follow_ups.remove(topic)
        self._save()
        
        return initiative
    
    def generate_thought_sharing(self, user_id: Optional[str] = None) -> Optional[Initiative]:
        """
        Сгенерировать инициативу поделиться мыслью.
        """
        if not self.thoughts_pool:
            return None
        
        thought = random.choice(self.thoughts_pool)
        
        return self.create_initiative(
            type=InitiativeType.SHARE_THOUGHT,
            message=thought,
            context="Захотелось поделиться мыслью",
            target_user_id=user_id,
            priority=InitiativePriority.LOW,
            valid_hours=24
        )
    
    def generate_discovery_sharing(self, user_id: Optional[str] = None) -> Optional[Initiative]:
        """
        Сгенерировать инициативу поделиться открытием.
        """
        if not self.discoveries_pool:
            return None
        
        discovery = random.choice(self.discoveries_pool)
        
        return self.create_initiative(
            type=InitiativeType.SHARE_DISCOVERY,
            message=discovery,
            context="Хочу поделиться интересным фактом",
            target_user_id=user_id,
            priority=InitiativePriority.LOW,
            valid_hours=24
        )
    
    def add_thought(self, thought: str):
        """Добавить мысль в пул."""
        if thought not in self.thoughts_pool:
            self.thoughts_pool.append(thought)
    
    def add_discovery(self, discovery: str):
        """Добавить открытие в пул."""
        if discovery not in self.discoveries_pool:
            self.discoveries_pool.append(discovery)
    
    def get_smart_initiative(
        self,
        user_id: str,
        user_name: str = "",
        is_family: bool = False
    ) -> Optional[Initiative]:
        """
        Умный выбор инициативы с учётом контекста.
        
        Выбирает наиболее подходящую инициативу для данного момента.
        """
        if not self.can_send_initiative(user_id):
            return None
        
        # Сначала проверяем уже созданные инициативы
        pending = self.get_pending_initiative(user_id)
        if pending:
            return pending
        
        # Приоритеты генерации
        generators = []
        
        # Check-in если давно не общались
        if user_id in self.user_activity:
            activity = self.user_activity[user_id]
            last_seen = datetime.fromisoformat(activity.last_seen)
            days_since = (datetime.now() - last_seen).days
            
            if days_since >= 2:
                generators.append(("check_in", 10))  # Высокий приоритет
            
            # Follow-up по темам
            if activity.pending_follow_ups:
                generators.append(("follow_up", 7))
        
        # Мысли и открытия - низкий приоритет
        if is_family:  # Для семьи чаще делимся
            generators.append(("thought", 3))
            generators.append(("discovery", 3))
        else:
            generators.append(("thought", 1))
            generators.append(("discovery", 1))
        
        if not generators:
            return None
        
        # Взвешенный выбор
        total_weight = sum(w for _, w in generators)
        rand_val = random.random() * total_weight
        
        cumulative = 0
        selected = None
        for gen_type, weight in generators:
            cumulative += weight
            if rand_val <= cumulative:
                selected = gen_type
                break
        
        if selected == "check_in":
            return self.generate_check_in(user_id, user_name)
        elif selected == "follow_up":
            return self.generate_follow_up(user_id)
        elif selected == "thought":
            return self.generate_thought_sharing(user_id)
        elif selected == "discovery":
            return self.generate_discovery_sharing(user_id)
        
        return None
    
    def cleanup_old_initiatives(self, days: int = 7):
        """Очистка старых инициатив."""
        cutoff = datetime.now() - timedelta(days=days)
        
        self.initiatives = [
            i for i in self.initiatives
            if datetime.fromisoformat(i.created_at) > cutoff or not i.triggered
        ]
        
        self._save()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику системы."""
        total = len(self.initiatives)
        triggered = sum(1 for i in self.initiatives if i.triggered)
        
        by_type = {}
        for i in self.initiatives:
            by_type[i.type] = by_type.get(i.type, 0) + 1
        
        return {
            "total_initiatives": total,
            "triggered": triggered,
            "pending": total - triggered,
            "by_type": by_type,
            "tracked_users": len(self.user_activity),
            "thoughts_in_pool": len(self.thoughts_pool),
            "discoveries_in_pool": len(self.discoveries_pool)
        }


# Синглтон
_proactive_system: Optional[ProactiveSystem] = None


def get_proactive_system() -> ProactiveSystem:
    """Получить глобальный экземпляр ProactiveSystem."""
    global _proactive_system
    if _proactive_system is None:
        _proactive_system = ProactiveSystem()
    return _proactive_system


# ==================== ТЕСТЫ ====================

if __name__ == "__main__":
    import tempfile
    import shutil
    
    print("=" * 50)
    print("ТЕСТИРОВАНИЕ PROACTIVE SYSTEM")
    print("=" * 50)
    
    test_dir = tempfile.mkdtemp()
    
    try:
        system = ProactiveSystem(data_dir=test_dir)
        
        # Тест 1: Запись активности
        print("\n📝 Тест 1: Запись активности пользователя")
        
        system.record_user_activity(
            user_id="user123",
            message="Привет! Как дела?",
            topics=["общение", "настроение"]
        )
        
        assert "user123" in system.user_activity
        activity = system.user_activity["user123"]
        assert "общение" in activity.topics_discussed
        print(f"✅ Активность записана, темы: {activity.topics_discussed}")
        
        # Тест 2: Создание инициативы
        print("\n📝 Тест 2: Создание инициативы")
        
        init = system.create_initiative(
            type=InitiativeType.GREETING,
            message="Привет! Как твой день?",
            context="Утреннее приветствие",
            target_user_id="user123",
            priority=InitiativePriority.NORMAL
        )
        
        assert init.id is not None
        assert init.type == "greeting"
        assert len(system.initiatives) == 1
        print(f"✅ Инициатива создана: {init.type}, ID: {init.id}")
        
        # Тест 3: Получение pending инициативы
        print("\n📝 Тест 3: Получение pending инициативы")
        
        pending = system.get_pending_initiative("user123")
        assert pending is not None
        assert pending.id == init.id
        print(f"✅ Pending инициатива получена: {pending.message[:40]}...")
        
        # Тест 4: Маркировка как выполненной
        print("\n📝 Тест 4: Маркировка инициативы как выполненной")
        
        system.mark_initiative_triggered(init.id, "user123")
        
        assert init.triggered == True
        assert system.initiatives_today.get("user123") == 1
        print(f"✅ Инициатива выполнена, счётчик: {system.initiatives_today['user123']}")
        
        # Тест 5: Проверка лимитов
        print("\n📝 Тест 5: Проверка лимитов")
        
        # Создаём ещё инициативы до лимита
        for i in range(2):
            new_init = system.create_initiative(
                type=InitiativeType.SHARE_THOUGHT,
                message=f"Мысль {i}",
                context="Тест лимитов",
                target_user_id="user123"
            )
            system.mark_initiative_triggered(new_init.id, "user123")
        
        can_send = system.can_send_initiative("user123")
        assert can_send == False  # Достигли лимита
        print(f"✅ После {system.initiatives_today['user123']} инициатив: can_send={can_send}")
        
        # Тест 6: Follow-up
        print("\n📝 Тест 6: Follow-up система")
        
        system.add_follow_up("user456", "проект на работе")
        
        activity_456 = system.user_activity["user456"]
        assert "проект на работе" in activity_456.pending_follow_ups
        print(f"✅ Follow-up добавлен: {activity_456.pending_follow_ups}")
        
        follow_up_init = system.generate_follow_up("user456")
        assert follow_up_init is not None
        assert "проект на работе" in follow_up_init.message
        print(f"✅ Follow-up сгенерирован: {follow_up_init.message[:50]}...")
        
        # Тест 7: Генерация мыслей
        print("\n📝 Тест 7: Sharing мыслей")
        
        thought_init = system.generate_thought_sharing("user789")
        assert thought_init is not None
        assert thought_init.type == "thought"
        print(f"✅ Мысль сгенерирована: {thought_init.message[:50]}...")
        
        # Тест 8: Генерация открытий
        print("\n📝 Тест 8: Sharing открытий")
        
        discovery_init = system.generate_discovery_sharing("user789")
        assert discovery_init is not None
        assert discovery_init.type == "discovery"
        print(f"✅ Открытие сгенерировано: {discovery_init.message[:50]}...")
        
        # Тест 9: Добавление своих мыслей
        print("\n📝 Тест 9: Добавление собственных мыслей")
        
        system.add_thought("Моя новая мысль о жизни и вселенной! 🌌")
        assert "Моя новая мысль о жизни и вселенной! 🌌" in system.thoughts_pool
        print(f"✅ Мысль добавлена, всего в пуле: {len(system.thoughts_pool)}")
        
        # Тест 10: Check-in генерация (симуляция старой активности)
        print("\n📝 Тест 10: Check-in генерация")
        
        # Симулируем старую активность
        old_date = (datetime.now() - timedelta(days=5)).isoformat()
        system.user_activity["user999"] = UserActivity(
            user_id="user999",
            last_seen=old_date
        )
        
        check_in = system.generate_check_in("user999", "Алексей")
        assert check_in is not None
        assert check_in.type == "check_in"
        assert "Алексей" in check_in.message or "давно" in check_in.message.lower()
        print(f"✅ Check-in сгенерирован: {check_in.message}")
        
        # Тест 11: Умный выбор инициативы
        print("\n📝 Тест 11: Умный выбор инициативы")
        
        smart_init = system.get_smart_initiative(
            user_id="new_user",
            user_name="Тест",
            is_family=True
        )
        # Может быть None если все условия не выполнены
        print(f"✅ Smart инициатива: {smart_init.type if smart_init else 'None (ок для нового)'}")
        
        # Тест 12: Статистика
        print("\n📝 Тест 12: Статистика системы")
        
        stats = system.get_statistics()
        print(f"✅ Статистика:")
        print(f"   - Всего инициатив: {stats['total_initiatives']}")
        print(f"   - Выполнено: {stats['triggered']}")
        print(f"   - Отслеживаемых пользователей: {stats['tracked_users']}")
        print(f"   - Мыслей в пуле: {stats['thoughts_in_pool']}")
        
        # Тест 13: Сохранение и загрузка
        print("\n📝 Тест 13: Сохранение и загрузка")
        
        system._save()
        
        system2 = ProactiveSystem(data_dir=test_dir)
        
        assert "user123" in system2.user_activity
        assert len(system2.initiatives) == len(system.initiatives)
        print("✅ Данные успешно сохранены и загружены")
        
        print("\n" + "=" * 50)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 50)
        
    finally:
        shutil.rmtree(test_dir)
