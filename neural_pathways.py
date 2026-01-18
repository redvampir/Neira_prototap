"""
Neural Pathways v1.0 — Система заученных рефлексов Neira
Быстрые детерминированные ответы без LLM с tier-оптимизацией

Архитектура:
- HOT tier (начало): частые запросы, множество пользователей (87% попаданий)
- WARM tier: популярные, но реже (10% попаданий)
- COOL tier: нишевые запросы (2% попаданий)
- COLD tier (конец): индивидуальные, уникальные (1% попаданий)

Автоматическая миграция между tiers по частоте использования.
"""

import json
import os
import re
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import random


class PathwayTier(Enum):
    """Уровни приоритета pathways"""
    HOT = "hot"      # Частые, множество пользователей
    WARM = "warm"    # Популярные
    COOL = "cool"    # Нишевые
    COLD = "cold"    # Индивидуальные
    ARCHIVED = "archived"  # Неиспользуемые 30+ дней


@dataclass
class PathwayMatch:
    """Результат совпадения pathway"""
    pathway_id: str
    confidence: float
    matched_trigger: str
    tier: PathwayTier
    latency_ms: float


@dataclass
class NeuralPathway:
    """Заученный паттерн ответа"""
    id: str
    triggers: List[str]  # Ключевые фразы для активации
    response_template: str  # Шаблон ответа
    category: str = "general"  # greeting, question, task, code, chat
    
    # Метрики
    success_count: int = 0  # Сколько раз успешно использован
    failure_count: int = 0  # Сколько раз не подошел
    unique_users: set = field(default_factory=set)  # Кто использовал
    last_used: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    # Tier system
    tier: PathwayTier = PathwayTier.COLD  # Начинаем с COLD
    position: int = 0  # Позиция в списке (0 = начало)
    
    # Конфигурация
    confidence_threshold: float = 0.2  # Минимальная уверенность для активации (LOW для чувствительных тем!)
    llm_fallback: bool = False  # Нужен ли LLM fallback
    variables: Dict[str, Any] = field(default_factory=dict)  # Переменные для шаблона
    
    # Флаги
    require_exact_match: bool = False  # Требуется точное совпадение
    case_sensitive: bool = False
    user_specific: bool = False  # Pathway для конкретного пользователя
    user_id: Optional[str] = None
    
    def matches(self, user_input: str, user_id: Optional[str] = None) -> Optional[float]:
        """
        Проверить совпадение с входом пользователя
        
        Returns:
            Confidence score (0-1) или None если не совпадает
        """
        # Проверка user-specific pathway
        if self.user_specific and user_id != self.user_id:
            return None
        
        input_normalized = user_input if self.case_sensitive else user_input.lower()
        
        # Точное совпадение
        if self.require_exact_match:
            for trigger in self.triggers:
                trigger_normalized = trigger if self.case_sensitive else trigger.lower()
                if input_normalized == trigger_normalized:
                    return 1.0
            return None
        
        # Нечеткое совпадение (содержит триггер)
        best_confidence = 0.0
        for trigger in self.triggers:
            trigger_normalized = trigger if self.case_sensitive else trigger.lower()
            
            if trigger_normalized in input_normalized:
                # Чем ближе к полному совпадению, тем выше confidence
                trigger_len = len(trigger_normalized)
                input_len = len(input_normalized)
                confidence = min(1.0, trigger_len / input_len * 1.2)
                best_confidence = max(best_confidence, confidence)
        
        return best_confidence if best_confidence >= self.confidence_threshold else None
    
    def execute(self, user_input: str, user_id: Optional[str] = None) -> str:
        """
        Выполнить pathway - сгенерировать ответ
        
        Returns:
            Готовый ответ
        """
        # Подставляем переменные в шаблон
        response = self.response_template
        
        # Простые переменные
        for key, value in self.variables.items():
            if isinstance(value, list):
                # Рандомный выбор из списка
                response = response.replace(f"{{{key}}}", random.choice(value))
            elif isinstance(value, str) and value.startswith("function:"):
                # Вызов функции (пока заглушка)
                response = response.replace(f"{{{key}}}", f"[{value}]")
            else:
                response = response.replace(f"{{{key}}}", str(value))
        
        return response
    
    def record_usage(self, user_id: str, success: bool = True):
        """Записать факт использования pathway"""
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        self.unique_users.add(user_id)
        self.last_used = datetime.now()
    
    def calculate_tier(self) -> PathwayTier:
        """
        Вычислить оптимальный tier на основе метрик
        
        Правила:
        - HOT: >100 использований, >10 пользователей
        - WARM: 20-100 использований OR >5 пользователей
        - COOL: 5-20 использований
        - COLD: <5 использований
        - ARCHIVED: не использовался 30+ дней
        """
        # Проверка на архивацию
        if self.last_used:
            days_unused = (datetime.now() - self.last_used).days
            if days_unused > 30:
                return PathwayTier.ARCHIVED
        
        # Tier по метрикам
        users_count = len(self.unique_users)
        
        if self.success_count >= 100 and users_count >= 10:
            return PathwayTier.HOT
        elif self.success_count >= 20 or users_count >= 5:
            return PathwayTier.WARM
        elif self.success_count >= 5:
            return PathwayTier.COOL
        else:
            return PathwayTier.COLD
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация для JSON"""
        data = asdict(self)
        # Преобразуем set в list
        data['unique_users'] = list(self.unique_users)
        # Преобразуем enum
        data['tier'] = self.tier.value
        # Преобразуем datetime
        data['created_at'] = self.created_at.isoformat()
        data['last_used'] = self.last_used.isoformat() if self.last_used else None
        return data
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'NeuralPathway':
        """Десериализация из JSON"""
        # Восстанавливаем set
        data['unique_users'] = set(data.get('unique_users', []))
        # Восстанавливаем enum
        data['tier'] = PathwayTier(data.get('tier', 'cold'))
        # Восстанавливаем datetime
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('last_used'):
            data['last_used'] = datetime.fromisoformat(data['last_used'])
        return NeuralPathway(**data)


class NeuralPathwaySystem:
    """
    Система управления Neural Pathways с tier-оптимизацией
    
    Основные функции:
    - Быстрый поиск pathways (O(1) для HOT tier)
    - Автоматическая реорганизация по частоте
    - Миграция между tiers
    - Персистентность
    """
    
    def __init__(self, storage_file: str = "neural_pathways.json"):
        self.storage_file = storage_file
        self.pathways: List[NeuralPathway] = []
        
        # Счетчики для оптимизации
        self.total_lookups = 0
        self.hot_hits = 0
        self.warm_hits = 0
        self.cool_hits = 0
        self.cold_hits = 0
        self.misses = 0
        
        self.load()
    
    def add(self, pathway: NeuralPathway, tier: Optional[PathwayTier] = None):
        """
        Добавить новый pathway
        
        Args:
            pathway: Pathway для добавления
            tier: Принудительный tier (если None, вычисляется автоматически)
        """
        if tier:
            pathway.tier = tier
        else:
            pathway.tier = pathway.calculate_tier()
        
        # Добавляем в соответствующую позицию
        self.pathways.append(pathway)
        self._reorganize_by_tier()
    
    def match(self, user_input: str, user_id: Optional[str] = None) -> Optional[PathwayMatch]:
        """
        Найти подходящий pathway (оптимизированный поиск)
        
        Поиск начинается с HOT tier (начало списка) для максимальной скорости.
        
        Returns:
            PathwayMatch если найдено совпадение, иначе None
        """
        import time
        start_time = time.perf_counter()
        
        self.total_lookups += 1
        
        # Проходим pathways в порядке приоритета (HOT → WARM → COOL → COLD)
        for pathway in self.pathways:
            # Пропускаем архивные
            if pathway.tier == PathwayTier.ARCHIVED:
                continue
            
            confidence = pathway.matches(user_input, user_id)
            
            if confidence is not None:
                latency_ms = (time.perf_counter() - start_time) * 1000
                
                # Обновляем статистику по tier
                if pathway.tier == PathwayTier.HOT:
                    self.hot_hits += 1
                elif pathway.tier == PathwayTier.WARM:
                    self.warm_hits += 1
                elif pathway.tier == PathwayTier.COOL:
                    self.cool_hits += 1
                else:
                    self.cold_hits += 1
                
                return PathwayMatch(
                    pathway_id=pathway.id,
                    confidence=confidence,
                    matched_trigger=user_input,
                    tier=pathway.tier,
                    latency_ms=latency_ms
                )
        
        self.misses += 1
        return None
    
    def execute(self, match: PathwayMatch, user_input: str, user_id: str) -> str:
        """
        Выполнить matched pathway
        
        Args:
            match: Результат поиска
            user_input: Оригинальный ввод пользователя
            user_id: ID пользователя
            
        Returns:
            Сгенерированный ответ
        """
        pathway = self.get_by_id(match.pathway_id)
        if not pathway:
            raise ValueError(f"Pathway {match.pathway_id} not found")
        
        # Генерируем ответ
        response = pathway.execute(user_input, user_id)
        
        # Записываем использование
        pathway.record_usage(user_id, success=True)
        
        # Периодически проверяем нужна ли миграция tier
        if pathway.success_count % 10 == 0:
            self._check_tier_migration(pathway)
        
        return response
    
    def get_by_id(self, pathway_id: str) -> Optional[NeuralPathway]:
        """Найти pathway по ID"""
        for pathway in self.pathways:
            if pathway.id == pathway_id:
                return pathway
        return None
    
    def _check_tier_migration(self, pathway: NeuralPathway):
        """Проверить нужна ли миграция pathway в другой tier"""
        new_tier = pathway.calculate_tier()
        
        if new_tier != pathway.tier:
            old_tier = pathway.tier
            pathway.tier = new_tier
            self._reorganize_by_tier()
            print(f"🔄 Pathway '{pathway.id}' мигрировал: {old_tier.value} → {new_tier.value}")
    
    def _reorganize_by_tier(self):
        """
        Реорганизовать pathways по tier-приоритету
        
        Порядок: HOT → WARM → COOL → COLD → ARCHIVED
        Внутри tier сортируем по success_count (убывание)
        """
        tier_order = {
            PathwayTier.HOT: 0,
            PathwayTier.WARM: 1,
            PathwayTier.COOL: 2,
            PathwayTier.COLD: 3,
            PathwayTier.ARCHIVED: 4
        }
        
        self.pathways.sort(
            key=lambda p: (tier_order[p.tier], -p.success_count)
        )
        
        # Обновляем позиции
        for i, pathway in enumerate(self.pathways):
            pathway.position = i
    
    def reorganize_all(self):
        """
        Полная реорганизация всех pathways
        
        Вызывается каждые 100 диалогов или по запросу
        """
        # Пересчитываем tier для всех
        for pathway in self.pathways:
            pathway.tier = pathway.calculate_tier()
        
        # Реорганизуем
        self._reorganize_by_tier()
        
        print(f"🔄 Реорганизация завершена: {self.tier_stats()}")
    
    def tier_stats(self) -> Dict[str, Any]:
        """Статистика по tiers"""
        stats = {
            "total": len(self.pathways),
            "by_tier": {},
            "coverage": {}
        }
        
        for tier in PathwayTier:
            count = sum(1 for p in self.pathways if p.tier == tier)
            stats["by_tier"][tier.value] = count
        
        # Покрытие запросов (приблизительно)
        total_lookups = max(1, self.total_lookups)
        stats["coverage"] = {
            "hot": f"{(self.hot_hits / total_lookups * 100):.1f}%",
            "warm": f"{(self.warm_hits / total_lookups * 100):.1f}%",
            "cool": f"{(self.cool_hits / total_lookups * 100):.1f}%",
            "cold": f"{(self.cold_hits / total_lookups * 100):.1f}%",
            "miss": f"{(self.misses / total_lookups * 100):.1f}%"
        }
        
        return stats
    
    def save(self):
        """Сохранить pathways в файл"""
        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "pathways": [p.to_dict() for p in self.pathways],
            "stats": {
                "total_lookups": self.total_lookups,
                "hot_hits": self.hot_hits,
                "warm_hits": self.warm_hits,
                "cool_hits": self.cool_hits,
                "cold_hits": self.cold_hits,
                "misses": self.misses
            }
        }
        
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load(self):
        """Загрузить pathways из файла"""
        if not os.path.exists(self.storage_file):
            print("ℹ️ Neural Pathways файл не найден, начинаем с пустой базы")
            self._create_default_pathways()
            return
        
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.pathways = [
                NeuralPathway.from_dict(p) for p in data.get("pathways", [])
            ]
            
            # Восстанавливаем статистику
            stats = data.get("stats", {})
            self.total_lookups = stats.get("total_lookups", 0)
            self.hot_hits = stats.get("hot_hits", 0)
            self.warm_hits = stats.get("warm_hits", 0)
            self.cool_hits = stats.get("cool_hits", 0)
            self.cold_hits = stats.get("cold_hits", 0)
            self.misses = stats.get("misses", 0)
            
            print(f"✅ Загружено {len(self.pathways)} neural pathways")
            
        except Exception as e:
            print(f"⚠️ Ошибка загрузки pathways: {e}")
            self._create_default_pathways()
    
    def _create_default_pathways(self):
        """Создать базовые pathways для начала"""
        defaults = [
            NeuralPathway(
                id="greeting",
                triggers=["привет", "здравствуй", "хай", "hi", "hello"],
                response_template="{greeting_emoji} {greeting_phrase}!",
                category="greeting",
                tier=PathwayTier.HOT,
                variables={
                    "greeting_emoji": ["👋", "🌟", "✨", "😊"],
                    "greeting_phrase": ["Привет", "Здравствуй", "Рада тебя видеть", "Приветствую"]
                }
            ),
            NeuralPathway(
                id="gratitude",
                triggers=["спасибо", "благодарю", "thanks", "thx"],
                response_template="{thanks_emoji} {thanks_phrase}!",
                category="social",
                tier=PathwayTier.HOT,
                variables={
                    "thanks_emoji": ["😊", "🌟", "💫"],
                    "thanks_phrase": ["Пожалуйста", "Рада помочь", "Всегда пожалуйста", "Обращайся"]
                }
            ),
            NeuralPathway(
                id="self_introduction",
                triggers=["кто ты", "что ты", "представься"],
                response_template="Я - Neira 🧠, живая программа с собственным интеллектом. Я учусь, запоминаю и развиваюсь!",
                category="self_info",
                tier=PathwayTier.WARM
            ),
            NeuralPathway(
                id="how_are_you",
                triggers=["как дела", "как ты", "что делаешь"],
                response_template="✨ Отлично! Работаю, учусь и общаюсь. А у тебя как?",
                category="chat",
                tier=PathwayTier.WARM
            )
        ]
        
        for pathway in defaults:
            self.add(pathway)
        
        self.save()
        print(f"✅ Создано {len(defaults)} базовых pathways")


# === Convenience функции ===

def create_pathway_system(storage_file: str = "neural_pathways.json") -> NeuralPathwaySystem:
    """Создать систему pathways"""
    return NeuralPathwaySystem(storage_file)


# === Тестирование ===
if __name__ == "__main__":
    print("=" * 60)
    print("🧠 Neural Pathways System Test")
    print("=" * 60)
    
    # Создаем систему
    system = create_pathway_system("test_pathways.json")
    
    # Тестовые запросы
    test_inputs = [
        ("привет", "user1"),
        ("здравствуй", "user2"),
        ("спасибо", "user1"),
        ("кто ты", "user3"),
        ("как дела", "user1"),
        ("привет", "user4"),  # Повтор - должен быть HOT
        ("что-то новое", "user1"),  # Miss
    ]
    
    print("\n📝 Тестовые запросы:\n")
    
    for user_input, user_id in test_inputs:
        match = system.match(user_input, user_id)
        
        if match:
            response = system.execute(match, user_input, user_id)
            print(f"✓ '{user_input}' → {match.tier.value} tier ({match.latency_ms:.1f}ms)")
            print(f"  Ответ: {response}")
        else:
            print(f"✗ '{user_input}' → не найдено pathway")
        print()
    
    # Статистика
    print("=" * 60)
    print("📊 Статистика:")
    print("=" * 60)
    stats = system.tier_stats()
    print(f"\nВсего pathways: {stats['total']}")
    print(f"\nПо tiers:")
    for tier, count in stats['by_tier'].items():
        print(f"  {tier}: {count}")
    print(f"\nПокрытие запросов:")
    for tier, coverage in stats['coverage'].items():
        print(f"  {tier}: {coverage}")
    
    # Сохранение
    system.save()
    print(f"\n💾 Сохранено в {system.storage_file}")
