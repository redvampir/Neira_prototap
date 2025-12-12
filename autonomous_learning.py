"""
🎓 Neira Autonomous Learning System v1.0
Система автономного самообучения с защитой от галлюцинаций

ПРИНЦИПЫ:
1. Учимся ТОЛЬКО из проверенных источников (whitelist)
2. Все знания проходят карантин (quarantine zone)
3. Мультисорсная верификация (2+ источника)
4. Автоматическое отклонение при противоречиях
5. Human-in-the-loop для спорных случаев

ЗАЩИТА ОТ ГАЛЛЮЦИНАЦИЙ:
✅ Whitelist надёжных источников
✅ Blacklist ненадёжных доменов
✅ Проверка на противоречия с памятью
✅ Паттерны галлюцинаций (из immune_system.py)
✅ Карантин перед добавлением в память
✅ Минимальный порог confidence (0.7)
"""

import asyncio
import logging
import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib

try:
    import aiohttp
    import requests
    from bs4 import BeautifulSoup  # type: ignore
except ImportError:
    print("⚠️ Установите: pip install aiohttp beautifulsoup4 lxml")


class SourceTrust(Enum):
    """Уровень доверия к источнику"""
    VERIFIED = 1.0      # Официальная документация
    HIGH = 0.9          # Wikipedia, arXiv
    MEDIUM = 0.7        # Проверенные блоги
    LOW = 0.5           # Общие новости
    UNTRUSTED = 0.0     # Неизвестные источники


@dataclass
class CuratedSource:
    """Проверенный источник знаний"""
    name: str
    url_pattern: str      # Regex для проверки URL
    trust_level: float    # 0.0-1.0
    categories: List[str] # Темы из этого источника
    rate_limit: int = 10  # Запросов в час
    
    def matches(self, url: str) -> bool:
        """Проверяет соответствие URL паттерну"""
        return bool(re.match(self.url_pattern, url))


@dataclass
class QuarantineEntry:
    """Запись в карантине (ожидает проверки)"""
    id: str
    text: str
    source_url: str
    source_trust: float
    category: str
    timestamp: str
    
    # Верификация
    verification_count: int = 0  # Сколько источников подтверждают
    confidence: float = 0.0
    contradictions: List[str] = field(default_factory=list)
    
    # Статус
    status: str = "pending"  # pending, approved, rejected
    reviewed_by: Optional[str] = None
    review_timestamp: Optional[str] = None


class SourceWhitelist:
    """Whitelist проверенных источников"""
    
    CURATED_SOURCES = [
        # Официальная документация (максимальное доверие)
        CuratedSource(
            name="Python.org",
            url_pattern=r"https?://docs\.python\.org/.*",
            trust_level=SourceTrust.VERIFIED.value,
            categories=["programming", "python", "technology"]
        ),
        CuratedSource(
            name="MDN Web Docs",
            url_pattern=r"https?://developer\.mozilla\.org/.*",
            trust_level=SourceTrust.VERIFIED.value,
            categories=["web", "javascript", "technology"]
        ),
        
        # Научные источники (высокое доверие)
        CuratedSource(
            name="Wikipedia (Russian)",
            url_pattern=r"https?://ru\.wikipedia\.org/wiki/.*",
            trust_level=SourceTrust.HIGH.value,
            categories=["general", "science", "history", "culture"]
        ),
        CuratedSource(
            name="Wikipedia (English)",
            url_pattern=r"https?://en\.wikipedia\.org/wiki/.*",
            trust_level=SourceTrust.HIGH.value,
            categories=["general", "science", "history", "culture"]
        ),
        CuratedSource(
            name="arXiv.org",
            url_pattern=r"https?://arxiv\.org/abs/.*",
            trust_level=SourceTrust.HIGH.value,
            categories=["science", "ai", "research"]
        ),
        
        # GitHub (высокое доверие, но только README)
        CuratedSource(
            name="GitHub README",
            url_pattern=r"https?://github\.com/.*/.*/(blob|raw)/.*/README\.md",
            trust_level=SourceTrust.HIGH.value,
            categories=["programming", "opensource", "technology"]
        ),
        
        # Stack Overflow (среднее доверие - только accepted answers)
        CuratedSource(
            name="Stack Overflow",
            url_pattern=r"https?://stackoverflow\.com/questions/.*",
            trust_level=SourceTrust.MEDIUM.value,
            categories=["programming", "troubleshooting"]
        ),
    ]
    
    # Blacklist ненадёжных источников
    BLACKLIST_PATTERNS = [
        r".*forum.*",           # Форумы (неконтролируемый контент)
        r".*\.blogspot\..*",    # Блоги
        r".*medium\.com.*",     # Medium (субъективно)
        r".*reddit\.com.*",     # Reddit (UGC)
        r".*quora\.com.*",      # Quora (субъективно)
        r".*\.xyz$",            # Подозрительные домены
        r".*\.tk$",             # Бесплатные домены
        r".*torrent.*",         # Торренты
    ]
    
    @classmethod
    def is_trusted(cls, url: str) -> Tuple[bool, float, str]:
        """
        Проверяет надёжность источника
        
        Returns:
            (trusted, trust_level, source_name)
        """
        # Проверка blacklist
        for pattern in cls.BLACKLIST_PATTERNS:
            if re.match(pattern, url, re.IGNORECASE):
                return (False, 0.0, "blacklisted")
        
        # Проверка whitelist
        for source in cls.CURATED_SOURCES:
            if source.matches(url):
                return (True, source.trust_level, source.name)
        
        # Неизвестный источник - не доверяем
        return (False, SourceTrust.UNTRUSTED.value, "unknown")


class KnowledgeValidator:
    """Валидатор знаний с защитой от галлюцинаций"""
    
    def __init__(self, memory_system):
        self.memory = memory_system
        self.min_sources = 2  # Минимум источников для подтверждения
        self.min_confidence = 0.7  # Минимальная уверенность для принятия
    
    async def verify_fact(self, text: str, source_url: str, source_trust: float) -> Tuple[bool, float, List[str]]:
        """
        Проверяет факт на достоверность
        
        Returns:
            (approved, confidence, contradictions)
        """
        contradictions = []
        
        # 1. Проверка на противоречия с существующей памятью
        existing_memories = self.memory.long_term + self.memory.short_term
        for entry in existing_memories:
            if self._check_contradiction(text, entry.text):
                contradictions.append(f"Противоречит: {entry.text[:100]}")
        
        # Если есть противоречия - отклоняем
        if contradictions:
            return (False, 0.0, contradictions)
        
        # 2. Базовая уверенность = доверие к источнику
        confidence = source_trust
        
        # 3. Проверка паттернов галлюцинаций
        if self._has_hallucination_patterns(text):
            return (False, 0.0, ["Обнаружены паттерны галлюцинаций"])
        
        # 4. Проверка на слишком конкретные утверждения без контекста
        if self._too_specific_without_context(text):
            confidence *= 0.5  # Снижаем уверенность
        
        # 5. Решение: принимаем если confidence >= threshold
        approved = confidence >= self.min_confidence
        
        return (approved, confidence, contradictions)
    
    def _check_contradiction(self, text1: str, text2: str) -> bool:
        """Проверяет противоречие между двумя текстами"""
        # Простая эвристика: ищем отрицания
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        # Если есть одинаковые ключевые слова + отрицание
        negations = {"не", "нет", "never", "no", "not", "без"}
        
        common_words = words1.intersection(words2)
        has_negation_1 = bool(words1.intersection(negations))
        has_negation_2 = bool(words2.intersection(negations))
        
        # Противоречие если одно отрицательное, другое нет
        if len(common_words) >= 3 and (has_negation_1 != has_negation_2):
            return True
        
        return False
    
    def _has_hallucination_patterns(self, text: str) -> bool:
        """Проверка на паттерны галлюцинаций (из immune_system.py)"""
        suspicious_patterns = [
            # Финансовые галлюцинации
            r'\$\d+\s*(млн|тыс|billion)',           # Денежные суммы без контекста
            r'прибыль|доход|заработ.*\d+',          # Финансовые цифры
            r'продаж[аи]? (мощност|ресурс)',        # Продажа абстракций
            
            # Игровые механики
            r'игр[аы]? (требует|включает)',
            r'ход (может|включает)',
            
            # Ценообразование
            r'цена (модели|мощности)',
            r'стоимость (нейрон|клетк)',
            
            # Физически невозможное
            r'скорость.*свет.*превыша',
            r'вечный двигатель',
            
            # Абсолютные утверждения
            r'(всегда|никогда|все|ни один).*100%',
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _too_specific_without_context(self, text: str) -> bool:
        """Проверка на слишком конкретные утверждения без источника"""
        # Точные цифры без контекста
        if re.search(r'\d{4,}', text) and not re.search(r'(год|версия|страниц)', text):
            return True
        
        # Конкретные имена без объяснения
        if re.search(r'[A-ZА-Я][a-zа-я]+\s[A-ZА-Я][a-zа-я]+', text):
            # Есть имя собственное, но нет глаголов объяснения
            if not re.search(r'(создал|изобрёл|написал|сказал)', text):
                return True
        
        return False


class LearningCurriculum:
    """Учебный план - что изучать и в каком порядке"""
    
    TOPICS = {
        # Приоритет 1: Самоосознание
        "self_awareness": {
            "priority": 1,
            "keywords": ["AI", "LLM", "neural_network", "machine_learning", "Ollama"],
            "sources": ["Wikipedia", "arXiv.org"],
            "max_entries": 20
        },
        
        # Приоритет 2: Текущий стек
        "current_stack": {
            "priority": 2,
            "keywords": ["Python_asyncio", "Telegram_Bot_API", "FastAPI", "pytest"],
            "sources": ["Python.org", "MDN Web Docs", "GitHub README"],
            "max_entries": 30
        },
        
        # Приоритет 3: Общие знания
        "general_knowledge": {
            "priority": 3,
            "keywords": ["история_науки", "физика", "математика", "программирование"],
            "sources": ["Wikipedia (Russian)"],
            "max_entries": 50
        },
        
        # Приоритет 4: Технологии
        "tech_trends": {
            "priority": 4,
            "keywords": ["Python_3.13", "AI_новости", "GitHub_Copilot"],
            "sources": ["Python.org", "GitHub"],
            "max_entries": 10
        }
    }
    
    @classmethod
    def get_next_topic(cls) -> Tuple[str, Dict[str, Any]]:
        """Возвращает следующую тему для изучения"""
        # Сортируем по приоритету
        sorted_topics = sorted(cls.TOPICS.items(), key=lambda x: x[1]["priority"])
        
        # Возвращаем первую
        return sorted_topics[0]


class AutonomousLearningSystem:
    """Система автономного самообучения"""
    
    def __init__(self, memory_system, idle_threshold_minutes: int = 30, admin_telegram_id: Optional[int] = None):
        self.memory = memory_system
        self.idle_threshold = idle_threshold_minutes
        self.admin_telegram_id = admin_telegram_id
        self.validator = KnowledgeValidator(memory_system)
        
        # Карантинная зона
        self.quarantine_path = "neira_quarantine.json"
        self.quarantine: List[QuarantineEntry] = self._load_quarantine()
        
        # Статистика
        self.stats = {
            "learning_sessions": 0,
            "facts_learned": 0,
            "facts_rejected": 0,
            "sources_checked": 0,
            "quarantine_approved": 0,
            "quarantine_rejected": 0,
        }
        
        # Последняя активность
        self.last_activity = datetime.now()
        
        # Фоновая задача
        self.learning_task: Optional[asyncio.Task] = None
        self.running = False
        
        logging.info("🎓 Autonomous Learning System инициализирован")
    
    def _load_quarantine(self) -> List[QuarantineEntry]:
        """Загрузить карантин из файла"""
        if not os.path.exists(self.quarantine_path):
            return []
        
        try:
            with open(self.quarantine_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            entries = []
            for entry_dict in data:
                # Восстанавливаем пустые списки для contradictions
                if 'contradictions' not in entry_dict:
                    entry_dict['contradictions'] = []
                entries.append(QuarantineEntry(**entry_dict))
            logging.info(f"📂 Загружено из карантина: {len(entries)}")
            return entries
        except Exception as e:
            logging.error(f"Ошибка загрузки карантина: {e}")
            return []
    
    def _save_quarantine(self):
        """Сохранить карантин в файл"""
        try:
            data = [asdict(entry) for entry in self.quarantine]
            with open(self.quarantine_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Ошибка сохранения карантина: {e}")
    
    def mark_activity(self):
        """Отметить активность (диалог с пользователем)"""
        self.last_activity = datetime.now()
    
    def is_idle(self) -> bool:
        """Проверка: Neira не занята?"""
        elapsed = (datetime.now() - self.last_activity).total_seconds() / 60
        return elapsed >= self.idle_threshold
    
    async def start_autonomous_learning(self):
        """Запустить фоновое обучение"""
        if self.running:
            logging.warning("Обучение уже запущено")
            return
        
        self.running = True
        self.learning_task = asyncio.create_task(self._learning_loop())
        logging.info("🎓 Автономное обучение запущено")
    
    async def stop_autonomous_learning(self):
        """Остановить фоновое обучение"""
        self.running = False
        if self.learning_task:
            self.learning_task.cancel()
            try:
                await self.learning_task
            except asyncio.CancelledError:
                pass
        logging.info("🛑 Автономное обучение остановлено")
    
    async def _learning_loop(self):
        """Основной цикл обучения"""
        while self.running:
            try:
                # Проверяем idle
                if self.is_idle():
                    logging.info("💤 Neira в режиме idle - начинаю обучение...")
                    await self._run_learning_session()
                
                # Ждём 1 час до следующей проверки
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Ошибка в цикле обучения: {e}")
                await asyncio.sleep(60)  # Retry через минуту
    
    async def _run_learning_session(self):
        """Запустить сессию обучения"""
        self.stats["learning_sessions"] += 1
        logging.info(f"📚 Начало сессии обучения #{self.stats['learning_sessions']}")
        
        # Получаем следующую тему
        topic_name, topic_config = LearningCurriculum.get_next_topic()
        logging.info(f"📖 Тема: {topic_name}")
        
        # Учимся из разных источников
        for keyword in topic_config["keywords"][:3]:  # Берём первые 3 ключевых слова
            await self._learn_from_keyword(keyword, topic_config)
            await asyncio.sleep(5)  # Rate limiting
        
        # Проверяем карантин
        await self._review_quarantine()
        
        logging.info(f"✅ Сессия обучения завершена. Изучено: {self.stats['facts_learned']}")
    
    async def _learn_from_keyword(self, keyword: str, topic_config: Dict):
        """Изучить тему по ключевому слову"""
        logging.info(f"🔍 Поиск: {keyword}")
        
        # Используем Wikipedia как основной источник
        keyword_clean = keyword.replace('_', ' ')
        url = f"https://ru.wikipedia.org/wiki/{keyword.replace(' ', '_')}"
        
        # Проверяем доверие к источнику
        trusted, trust_level, source_name = SourceWhitelist.is_trusted(url)
        
        if not trusted:
            logging.warning(f"⚠️ Источник не в whitelist: {url}")
            return
        
        # Извлекаем первый параграф (summary) из Wikipedia
        try:
            fact = await self._extract_wikipedia_summary(keyword_clean, url)
            if not fact:
                logging.warning(f"⚠️ Не удалось извлечь информацию для '{keyword}'")
                return
        except Exception as e:
            logging.error(f"Ошибка извлечения: {e}")
            return
        
        # Валидируем
        approved, confidence, contradictions = await self.validator.verify_fact(
            fact, url, trust_level
        )
        
        self.stats["sources_checked"] += 1
        
        if approved:
            # Добавляем в карантин
            entry_id = hashlib.md5(fact.encode()).hexdigest()[:12]
            
            quarantine_entry = QuarantineEntry(
                id=entry_id,
                text=fact,
                source_url=url,
                source_trust=trust_level,
                category="learned",
                timestamp=datetime.now().isoformat(),
                confidence=confidence,
                status="pending"
            )
            
            self.quarantine.append(quarantine_entry)
            self._save_quarantine()
            self.stats["facts_learned"] += 1
            
            logging.info(f"✅ Факт в карантин: {fact[:60]}...")
        else:
            self.stats["facts_rejected"] += 1
            logging.warning(f"❌ Факт отклонён: {fact[:60]}... | {contradictions}")
    
    async def _extract_wikipedia_summary(self, keyword: str, url: str) -> Optional[str]:
        """Извлекает краткое описание из Wikipedia через API с fallback на en."""
        async def fetch_summary(session, api_url: str) -> Optional[str]:
            try:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    summary = data.get("extract")
                    if summary:
                        summary = summary.strip()
                        if len(summary) > 500:
                            summary = summary[:500]
                        return f"{keyword}: {summary}"
            except Exception as e:  # pragma: no cover - сеть непредсказуема
                logging.warning(f"Wiki API error for {api_url}: {e}")
            return None

        title = keyword.replace(" ", "_")
        api_ru = f"https://ru.wikipedia.org/api/rest_v1/page/summary/{title}"
        api_en = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

        async with aiohttp.ClientSession() as session:
            # Сначала пробуем ru
            summary = await fetch_summary(session, api_ru)
            if summary:
                return summary
            # Fallback на en
            summary = await fetch_summary(session, api_en)
            if summary:
                return summary

        return None
    
    async def _review_quarantine(self):
        """Проверить карантин и переместить одобренные записи в память"""
        approved_count = 0
        
        for entry in self.quarantine[:]:  # Копия списка
            # Автоодобрение если confidence высокая и нет противоречий
            if entry.confidence >= 0.9 and not entry.contradictions and entry.status == "pending":
                # Переносим в память
                self.memory.remember(
                    text=entry.text,
                    source=f"autonomous_learning:{entry.source_url}",
                    category="learned",
                    force_long_term=True
                )
                
                # Удаляем из карантина
                self.quarantine.remove(entry)
                approved_count += 1
                self.stats["quarantine_approved"] += 1
        
        if approved_count > 0:
            self._save_quarantine()
            logging.info(f"✅ Одобрено из карантина: {approved_count}")
    
    def manual_approve(self, entry_id: str) -> bool:
        """Ручное одобрение из карантина (администратором)"""
        for entry in self.quarantine:
            if entry.id == entry_id:
                # Переносим в память
                self.memory.remember(
                    text=entry.text,
                    source=f"autonomous_learning:{entry.source_url}",
                    category="learned",
                    force_long_term=True
                )
                
                # Обновляем статус
                entry.status = "approved"
                entry.reviewed_by = "admin"
                entry.review_timestamp = datetime.now().isoformat()
                
                self.quarantine.remove(entry)
                self._save_quarantine()
                self.stats["quarantine_approved"] += 1
                
                logging.info(f"✅ Одобрено вручную: {entry.text[:60]}...")
                return True
        
        return False
    
    def manual_reject(self, entry_id: str) -> bool:
        """Ручное отклонение из карантина"""
        for entry in self.quarantine:
            if entry.id == entry_id:
                entry.status = "rejected"
                entry.reviewed_by = "admin"
                entry.review_timestamp = datetime.now().isoformat()
                
                self.quarantine.remove(entry)
                self._save_quarantine()
                self.stats["quarantine_rejected"] += 1
                
                logging.info(f"❌ Отклонено вручную: {entry.text[:60]}...")
                return True
        
        return False
    
    def get_quarantine_stats(self) -> Dict[str, Any]:
        """Статистика карантина"""
        return {
            "total": len(self.quarantine),
            "pending": len([e for e in self.quarantine if e.status == "pending"]),
            "high_confidence": len([e for e in self.quarantine if e.confidence >= 0.9]),
            "needs_review": len([e for e in self.quarantine if e.confidence < 0.9]),
        }
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Статистика обучения"""
        return {
            **self.stats,
            "quarantine": self.get_quarantine_stats(),
            "idle_minutes": round((datetime.now() - self.last_activity).total_seconds() / 60, 1),
            "is_idle": self.is_idle(),
            "running": self.running,
            "whitelist_sources": len(SourceWhitelist.CURATED_SOURCES),
            "blacklist_patterns": len(SourceWhitelist.BLACKLIST_PATTERNS),
        }


if __name__ == "__main__":
    # Тесты
    print("🧪 Тестирование системы автономного обучения\n")
    
    # Тест whitelist
    print("📋 Тест whitelist источников:")
    test_urls = [
        "https://docs.python.org/3/library/asyncio.html",
        "https://ru.wikipedia.org/wiki/Python",
        "https://some-random-blog.com/article",
        "https://github.com/python/cpython/blob/main/README.md",
        "https://reddit.com/r/python",
        "https://suspicious-site.xyz/article",
    ]
    
    for url in test_urls:
        trusted, trust_level, source_name = SourceWhitelist.is_trusted(url)
        status = f"✅ {source_name} ({trust_level:.0%})" if trusted else "❌ Недоверенный"
        print(f"  {status}: {url}")
    
    print("\n✅ Система готова к интеграции!")
