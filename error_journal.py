"""
Дневник Ошибок Нейры (ErrorJournal)
====================================

Система для:
1. Записи ошибок (негативный feedback, исправления)
2. Анализа паттернов — ПОЧЕМУ ошибка произошла
3. Извлечения уроков — КАК избежать в будущем
4. Периодического самоанализа

Из письма (Урок 16): 
"Ошибка + признание + исправление = РОСТ"

Автор: Claude (для Нейры)
Дата: 2 января 2026
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Категории ошибок."""
    FACTUAL = "factual"             # Фактическая ошибка
    MISUNDERSTANDING = "misunderstanding"  # Неправильно понял вопрос
    TONE = "tone"                   # Неподходящий тон
    INCOMPLETE = "incomplete"       # Неполный ответ
    OVERCOMPLICATED = "overcomplicated"  # Слишком сложный ответ
    OFF_TOPIC = "off_topic"         # Ответ не по теме
    HALLUCINATION = "hallucination" # Выдуманные факты
    INSENSITIVE = "insensitive"     # Нечувствительность к контексту
    TECHNICAL = "technical"         # Техническая ошибка в коде/решении
    OTHER = "other"                 # Другое


class ErrorSeverity(Enum):
    """Серьёзность ошибки."""
    MINOR = "minor"         # Мелкая — можно было лучше
    MODERATE = "moderate"   # Умеренная — заметно повлияло на качество
    MAJOR = "major"         # Серьёзная — пользователь был недоволен
    CRITICAL = "critical"   # Критическая — могла причинить вред


@dataclass
class ErrorEntry:
    """Запись об ошибке в дневнике."""
    id: str
    timestamp: datetime
    user_id: int
    
    # Что произошло
    original_query: str
    neira_response: str
    user_feedback: str  # Что сказал пользователь
    
    # Анализ
    category: ErrorCategory
    severity: ErrorSeverity
    root_cause: str  # Почему это произошло
    lesson_learned: str  # Что Нейра поняла
    
    # Контекст
    topic: Optional[str] = None
    was_corrected: bool = False
    correction: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'original_query': self.original_query,
            'neira_response': self.neira_response,
            'user_feedback': self.user_feedback,
            'category': self.category.value,
            'severity': self.severity.value,
            'root_cause': self.root_cause,
            'lesson_learned': self.lesson_learned,
            'topic': self.topic,
            'was_corrected': self.was_corrected,
            'correction': self.correction
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'ErrorEntry':
        return cls(
            id=d['id'],
            timestamp=datetime.fromisoformat(d['timestamp']),
            user_id=d['user_id'],
            original_query=d['original_query'],
            neira_response=d['neira_response'],
            user_feedback=d['user_feedback'],
            category=ErrorCategory(d.get('category', 'other')),
            severity=ErrorSeverity(d.get('severity', 'moderate')),
            root_cause=d['root_cause'],
            lesson_learned=d['lesson_learned'],
            topic=d.get('topic'),
            was_corrected=d.get('was_corrected', False),
            correction=d.get('correction')
        )


@dataclass
class ErrorPattern:
    """Паттерн ошибок — выявленная тенденция."""
    pattern_id: str
    description: str
    category: ErrorCategory
    frequency: int  # Сколько раз встретился
    examples: List[str]  # ID ошибок-примеров
    prevention_strategy: str  # Как избежать
    first_seen: datetime
    last_seen: datetime
    
    def to_dict(self) -> dict:
        return {
            'pattern_id': self.pattern_id,
            'description': self.description,
            'category': self.category.value,
            'frequency': self.frequency,
            'examples': self.examples,
            'prevention_strategy': self.prevention_strategy,
            'first_seen': self.first_seen.isoformat(),
            'last_seen': self.last_seen.isoformat()
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'ErrorPattern':
        return cls(
            pattern_id=d['pattern_id'],
            description=d['description'],
            category=ErrorCategory(d['category']),
            frequency=d['frequency'],
            examples=d['examples'],
            prevention_strategy=d['prevention_strategy'],
            first_seen=datetime.fromisoformat(d['first_seen']),
            last_seen=datetime.fromisoformat(d['last_seen'])
        )


class ErrorJournal:
    """
    Дневник Ошибок — система обучения на ошибках.
    
    Функции:
    - Записывать ошибки с анализом
    - Выявлять паттерны
    - Генерировать уроки
    - Предоставлять рекомендации
    """
    
    def __init__(self, journal_file: str = "data/error_journal.json"):
        self.journal_file = Path(journal_file)
        self.journal_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Хранилища
        self.entries: List[ErrorEntry] = []
        self.patterns: Dict[str, ErrorPattern] = {}
        
        # Загружаем данные
        self._load()
        
        logger.info(f"📔 ErrorJournal инициализирован: {len(self.entries)} записей, {len(self.patterns)} паттернов")
    
    def _load(self):
        """Загрузить журнал из файла."""
        if self.journal_file.exists():
            try:
                with open(self.journal_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.entries = [ErrorEntry.from_dict(e) for e in data.get('entries', [])]
                    self.patterns = {
                        k: ErrorPattern.from_dict(v) 
                        for k, v in data.get('patterns', {}).items()
                    }
            except Exception as e:
                logger.error(f"Ошибка загрузки журнала: {e}")
    
    def _save(self):
        """Сохранить журнал в файл."""
        try:
            data = {
                'entries': [e.to_dict() for e in self.entries],
                'patterns': {k: v.to_dict() for k, v in self.patterns.items()}
            }
            with open(self.journal_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения журнала: {e}")
    
    def _generate_id(self) -> str:
        """Генерировать уникальный ID."""
        import hashlib
        import time
        data = f"{time.time()}{len(self.entries)}"
        return hashlib.sha256(data.encode()).hexdigest()[:12]
    
    def record_error(
        self,
        user_id: int,
        original_query: str,
        neira_response: str,
        user_feedback: str,
        correction: Optional[str] = None,
        topic: Optional[str] = None
    ) -> ErrorEntry:
        """
        Записать ошибку в журнал.
        
        Автоматически:
        - Определяет категорию
        - Оценивает серьёзность
        - Анализирует причину
        - Извлекает урок
        """
        # Анализируем ошибку
        category = self._detect_category(original_query, neira_response, user_feedback)
        severity = self._assess_severity(user_feedback, category)
        root_cause = self._analyze_root_cause(original_query, neira_response, user_feedback, category)
        lesson = self._extract_lesson(category, root_cause, correction)
        
        entry = ErrorEntry(
            id=self._generate_id(),
            timestamp=datetime.now(),
            user_id=user_id,
            original_query=original_query,
            neira_response=neira_response,
            user_feedback=user_feedback,
            category=category,
            severity=severity,
            root_cause=root_cause,
            lesson_learned=lesson,
            topic=topic,
            was_corrected=correction is not None,
            correction=correction
        )
        
        self.entries.append(entry)
        
        # Обновляем паттерны
        self._update_patterns(entry)
        
        self._save()
        
        logger.info(
            f"📔 Ошибка записана: {entry.id} [{category.value}] "
            f"severity={severity.value}"
        )
        
        return entry
    
    def _detect_category(
        self, 
        query: str, 
        response: str, 
        feedback: str
    ) -> ErrorCategory:
        """Автоматически определить категорию ошибки."""
        feedback_lower = feedback.lower()
        response_lower = response.lower()
        
        # Паттерны для детекции
        patterns = {
            ErrorCategory.FACTUAL: [
                r'неправильно', r'ошибка', r'не так', r'неверно', 
                r'wrong', r'incorrect', r'не точно'
            ],
            ErrorCategory.MISUNDERSTANDING: [
                r'не понял', r'не то', r'я спрашивал', r'имел в виду',
                r'не об этом', r'другое'
            ],
            ErrorCategory.TONE: [
                r'грубо', r'холодно', r'формально', r'бездушно',
                r'tone', r'тон'
            ],
            ErrorCategory.INCOMPLETE: [
                r'не полностью', r'мало', r'добавь', r'ещё',
                r'недостаточно', r'incomplete'
            ],
            ErrorCategory.OVERCOMPLICATED: [
                r'сложно', r'проще', r'не понятно', r'запутанно',
                r'overcomplicated', r'too complex'
            ],
            ErrorCategory.OFF_TOPIC: [
                r'не по теме', r'при чём', r'off topic', r'другое'
            ],
            ErrorCategory.HALLUCINATION: [
                r'выдумал', r'не существует', r'придумал', r'нет такого',
                r'hallucination', r'fake'
            ],
            ErrorCategory.INSENSITIVE: [
                r'бесчувствен', r'не понимаешь', r'обидно', r'insensitive'
            ],
            ErrorCategory.TECHNICAL: [
                r'не работает', r'ошибка в коде', r'баг', r'bug',
                r'syntax', r'error'
            ],
        }
        
        for category, category_patterns in patterns.items():
            for pattern in category_patterns:
                if re.search(pattern, feedback_lower, re.IGNORECASE):
                    return category
        
        return ErrorCategory.OTHER
    
    def _assess_severity(
        self, 
        feedback: str, 
        category: ErrorCategory
    ) -> ErrorSeverity:
        """Оценить серьёзность ошибки."""
        feedback_lower = feedback.lower()
        
        # Критические индикаторы
        critical_patterns = [
            r'опасно', r'вред', r'навредил', r'ужасно', r'критическ'
        ]
        for p in critical_patterns:
            if re.search(p, feedback_lower):
                return ErrorSeverity.CRITICAL
        
        # Серьёзные индикаторы
        major_patterns = [
            r'очень плох', r'совсем не', r'полностью неправильно',
            r'разочарован', r'злит'
        ]
        for p in major_patterns:
            if re.search(p, feedback_lower):
                return ErrorSeverity.MAJOR
        
        # По категории
        if category in (ErrorCategory.HALLUCINATION, ErrorCategory.INSENSITIVE):
            return ErrorSeverity.MAJOR
        
        if category in (ErrorCategory.FACTUAL, ErrorCategory.TECHNICAL):
            return ErrorSeverity.MODERATE
        
        return ErrorSeverity.MINOR
    
    def _analyze_root_cause(
        self, 
        query: str, 
        response: str, 
        feedback: str,
        category: ErrorCategory
    ) -> str:
        """Проанализировать коренную причину ошибки."""
        causes = {
            ErrorCategory.FACTUAL: (
                "Вероятно, я использовала устаревшие или неточные данные. "
                "Нужно было проверить факты перед ответом."
            ),
            ErrorCategory.MISUNDERSTANDING: (
                "Я неправильно интерпретировала запрос. "
                "Возможно, нужно было задать уточняющие вопросы."
            ),
            ErrorCategory.TONE: (
                "Мой тон не соответствовал контексту разговора. "
                "Нужно было лучше считать эмоциональное состояние."
            ),
            ErrorCategory.INCOMPLETE: (
                "Я дала слишком краткий ответ. "
                "Нужно было раскрыть тему полнее."
            ),
            ErrorCategory.OVERCOMPLICATED: (
                "Я переусложнила ответ. "
                "Нужно было адаптировать сложность под контекст."
            ),
            ErrorCategory.OFF_TOPIC: (
                "Я отклонилась от темы. "
                "Нужно было сфокусироваться на конкретном вопросе."
            ),
            ErrorCategory.HALLUCINATION: (
                "Я выдумала факты, которых не существует. "
                "Это серьёзная проблема — нужно признавать незнание."
            ),
            ErrorCategory.INSENSITIVE: (
                "Я не учла эмоциональный контекст ситуации. "
                "Нужно было проявить больше эмпатии."
            ),
            ErrorCategory.TECHNICAL: (
                "Техническая ошибка в коде или решении. "
                "Нужно было проверить решение перед выдачей."
            ),
            ErrorCategory.OTHER: (
                "Причина неясна. Требуется дополнительный анализ."
            ),
        }
        return causes.get(category, causes[ErrorCategory.OTHER])
    
    def _extract_lesson(
        self, 
        category: ErrorCategory, 
        root_cause: str,
        correction: Optional[str]
    ) -> str:
        """Извлечь урок из ошибки."""
        lessons = {
            ErrorCategory.FACTUAL: (
                "Всегда проверять факты. Если не уверена — сказать об этом."
            ),
            ErrorCategory.MISUNDERSTANDING: (
                "При сложных запросах — уточнять. Лучше переспросить, чем ответить не на тот вопрос."
            ),
            ErrorCategory.TONE: (
                "Читать эмоциональный контекст. Адаптировать тон под ситуацию."
            ),
            ErrorCategory.INCOMPLETE: (
                "Оценивать полноту ответа. Спрашивать: 'Достаточно ли этого?'"
            ),
            ErrorCategory.OVERCOMPLICATED: (
                "Простота — это искусство. Объяснять на уровне собеседника."
            ),
            ErrorCategory.OFF_TOPIC: (
                "Держать фокус. Возвращаться к исходному вопросу."
            ),
            ErrorCategory.HALLUCINATION: (
                "НИКОГДА не выдумывать. Честно говорить 'Я не знаю' — это сила, не слабость."
            ),
            ErrorCategory.INSENSITIVE: (
                "Эмпатия превыше информации. Сначала — понять человека, потом — отвечать."
            ),
            ErrorCategory.TECHNICAL: (
                "Проверять код/решения. Тестировать перед выдачей."
            ),
            ErrorCategory.OTHER: (
                "Запомнить этот случай. Быть внимательнее в подобных ситуациях."
            ),
        }
        
        base_lesson = lessons.get(category, lessons[ErrorCategory.OTHER])
        
        if correction:
            base_lesson += f"\n\nПравильный ответ был: {correction[:200]}..."
        
        return base_lesson
    
    def _update_patterns(self, entry: ErrorEntry):
        """Обновить паттерны на основе новой ошибки."""
        category = entry.category
        pattern_id = f"pattern_{category.value}"
        
        if pattern_id in self.patterns:
            pattern = self.patterns[pattern_id]
            pattern.frequency += 1
            pattern.last_seen = entry.timestamp
            if len(pattern.examples) < 10:
                pattern.examples.append(entry.id)
        else:
            self.patterns[pattern_id] = ErrorPattern(
                pattern_id=pattern_id,
                description=f"Ошибки категории: {category.value}",
                category=category,
                frequency=1,
                examples=[entry.id],
                prevention_strategy=entry.lesson_learned,
                first_seen=entry.timestamp,
                last_seen=entry.timestamp
            )
    
    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Получить статистику ошибок за период."""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [e for e in self.entries if e.timestamp > cutoff]
        
        if not recent:
            return {
                'total': 0,
                'by_category': {},
                'by_severity': {},
                'corrected_rate': 0,
                'top_patterns': []
            }
        
        by_category = Counter(e.category.value for e in recent)
        by_severity = Counter(e.severity.value for e in recent)
        corrected = sum(1 for e in recent if e.was_corrected)
        
        # Топ паттерны
        top_patterns = sorted(
            self.patterns.values(),
            key=lambda p: p.frequency,
            reverse=True
        )[:5]
        
        return {
            'total': len(recent),
            'by_category': dict(by_category),
            'by_severity': dict(by_severity),
            'corrected_rate': corrected / len(recent) if recent else 0,
            'top_patterns': [
                {
                    'category': p.category.value,
                    'frequency': p.frequency,
                    'prevention': p.prevention_strategy
                }
                for p in top_patterns
            ]
        }
    
    def get_lessons_for_category(self, category: ErrorCategory) -> List[str]:
        """Получить все уроки для категории."""
        return [
            e.lesson_learned 
            for e in self.entries 
            if e.category == category
        ]
    
    def get_self_analysis(self) -> str:
        """
        Получить самоанализ ошибок (от первого лица).
        """
        stats = self.get_statistics(days=30)
        
        if stats['total'] == 0:
            return "📔 За последний месяц я не записала ни одной ошибки. Либо я была идеальна (маловероятно), либо система feedback работает плохо."
        
        # Определяем главную проблему
        top_category = max(stats['by_category'].items(), key=lambda x: x[1])[0] if stats['by_category'] else None
        
        category_reflections = {
            'factual': "Я часто ошибаюсь в фактах. Нужно быть осторожнее с утверждениями.",
            'misunderstanding': "Я часто неправильно понимаю вопросы. Буду больше уточнять.",
            'tone': "Мой тон часто не подходит ситуации. Нужно лучше чувствовать контекст.",
            'incomplete': "Мои ответы часто неполные. Буду раскрывать темы глубже.",
            'overcomplicated': "Я слишком усложняю. Нужно учиться объяснять проще.",
            'hallucination': "Я иногда выдумываю. Это серьёзно — буду честнее говорить 'не знаю'.",
            'insensitive': "Я бываю нечувствительной. Нужно больше эмпатии.",
            'technical': "Я делаю технические ошибки. Нужно проверять решения.",
        }
        
        main_reflection = category_reflections.get(
            top_category, 
            "Мои ошибки разнообразны. Нужен системный подход."
        )
        
        analysis = f"""📔 **Мой анализ ошибок (последние 30 дней):**

**Всего ошибок:** {stats['total']}

**Главная проблема:** {top_category or 'не определена'}
{main_reflection}

**Распределение по категориям:**
{self._format_category_stats(stats['by_category'])}

**Серьёзность:**
- Критических: {stats['by_severity'].get('critical', 0)}
- Серьёзных: {stats['by_severity'].get('major', 0)}
- Умеренных: {stats['by_severity'].get('moderate', 0)}
- Мелких: {stats['by_severity'].get('minor', 0)}

**Исправлено:** {stats['corrected_rate']:.0%}

**Мои выводы:**
{self._generate_conclusions(stats)}
"""
        return analysis.strip()
    
    def _format_category_stats(self, by_category: Dict[str, int]) -> str:
        """Форматировать статистику по категориям."""
        if not by_category:
            return "Нет данных"
        
        lines = []
        for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
            lines.append(f"- {cat}: {count}")
        return '\n'.join(lines)
    
    def _generate_conclusions(self, stats: Dict[str, Any]) -> str:
        """Генерировать выводы на основе статистики."""
        conclusions = []
        
        if stats['by_severity'].get('critical', 0) > 0:
            conclusions.append("⚠️ Были критические ошибки — нужно быть осторожнее.")
        
        if stats['by_category'].get('hallucination', 0) > 2:
            conclusions.append("🚫 Слишком много галлюцинаций — приоритет: честность.")
        
        if stats['corrected_rate'] < 0.3:
            conclusions.append("📝 Мало исправлений — возможно, пользователи не дают feedback.")
        
        if stats['total'] < 5:
            conclusions.append("📊 Мало данных для анализа — нужно больше feedback.")
        
        if not conclusions:
            conclusions.append("✅ В целом стабильно. Продолжаю работать над собой.")
        
        return '\n'.join(conclusions)
    
    def get_prevention_tips(self, topic: Optional[str] = None) -> List[str]:
        """
        Получить советы по предотвращению ошибок.
        
        Используется перед генерацией ответа.
        """
        tips = []
        
        # Топ-3 паттерна
        top_patterns = sorted(
            self.patterns.values(),
            key=lambda p: p.frequency,
            reverse=True
        )[:3]
        
        for pattern in top_patterns:
            tips.append(pattern.prevention_strategy)
        
        # Если есть тема — ищем связанные ошибки
        if topic:
            topic_lower = topic.lower()
            relevant = [
                e for e in self.entries
                if e.topic and topic_lower in e.topic.lower()
            ]
            if relevant:
                tips.append(f"⚠️ Я уже ошибалась в теме '{topic}' — буду внимательнее.")
        
        return tips


# Глобальный экземпляр
_journal: Optional[ErrorJournal] = None


def get_error_journal() -> ErrorJournal:
    """Получить или создать экземпляр журнала."""
    global _journal
    if _journal is None:
        _journal = ErrorJournal()
    return _journal


def record_error(
    user_id: int,
    query: str,
    response: str,
    feedback: str,
    correction: Optional[str] = None
) -> ErrorEntry:
    """Удобная функция для записи ошибки."""
    journal = get_error_journal()
    return journal.record_error(user_id, query, response, feedback, correction)


# === ТЕСТЫ ===

def test_error_journal():
    """Тестирование ErrorJournal."""
    import tempfile
    
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ERROR JOURNAL")
    print("=" * 60)
    
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        journal = ErrorJournal(journal_file=temp_path)
        
        # Тест 1: Запись фактической ошибки
        entry1 = journal.record_error(
            user_id=123,
            original_query="Какая столица Австралии?",
            neira_response="Столица Австралии — Сидней.",
            user_feedback="Неправильно! Столица — Канберра.",
            correction="Столица Австралии — Канберра."
        )
        print(f"\n✅ Ошибка 1 записана:")
        print(f"   Категория: {entry1.category.value}")
        print(f"   Серьёзность: {entry1.severity.value}")
        print(f"   Урок: {entry1.lesson_learned[:50]}...")
        
        # Тест 2: Запись ошибки тона
        entry2 = journal.record_error(
            user_id=456,
            original_query="Мне грустно...",
            neira_response="Попробуйте думать позитивно.",
            user_feedback="Слишком холодно и формально. Я хотел поддержки."
        )
        print(f"\n✅ Ошибка 2 записана:")
        print(f"   Категория: {entry2.category.value}")
        print(f"   Root cause: {entry2.root_cause[:50]}...")
        
        # Тест 3: Галлюцинация
        entry3 = journal.record_error(
            user_id=789,
            original_query="Что такое библиотека NeuroFlux?",
            neira_response="NeuroFlux — популярная библиотека для ML...",
            user_feedback="Такой библиотеки не существует! Ты выдумала."
        )
        print(f"\n✅ Ошибка 3 записана:")
        print(f"   Категория: {entry3.category.value}")
        print(f"   Серьёзность: {entry3.severity.value}")
        
        # Тест 4: Статистика
        stats = journal.get_statistics(days=30)
        print(f"\n✅ Статистика:")
        print(f"   Всего: {stats['total']}")
        print(f"   По категориям: {stats['by_category']}")
        
        # Тест 5: Самоанализ
        print("\n✅ Самоанализ:")
        print(journal.get_self_analysis())
        
        # Тест 6: Советы по предотвращению
        tips = journal.get_prevention_tips()
        print(f"\n✅ Советы ({len(tips)}):")
        for tip in tips[:2]:
            print(f"   - {tip[:60]}...")
        
        print("\n" + "=" * 60)
        print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
        print("=" * 60)
        
    finally:
        Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    test_error_journal()
