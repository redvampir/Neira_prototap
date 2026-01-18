"""
ExecutableOrgans v1.0 — Исполняемые органы Нейры

Органы, которые содержат реальный код и могут выполнять задачи:
- GraphicsOrgan — генерация ASCII/текстовых изображений
- MathOrgan — математические вычисления
- TextOrgan — обработка текста

Особенности:
- Версионирование (каждое улучшение = новая версия)
- Автообучение на feedback
- Sandbox тестирование перед активацией
"""

import re
import json
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path
from enum import Enum

logger = logging.getLogger("ExecutableOrgans")

MATH_EXPRESSION_PATTERN = re.compile(r"^[\d\s\+\-\*\/\^\(\)\.]+$")
MATH_DIGIT_PATTERN = re.compile(r"\d")


# ============== Enums ==============

class OrganCapability(Enum):
    """Возможности органа"""
    DRAW_SHAPES = "draw_shapes"
    DRAW_COLORS = "draw_colors"
    MATH_BASIC = "math_basic"
    MATH_ADVANCED = "math_advanced"
    TEXT_TRANSFORM = "text_transform"
    CODE_GENERATE = "code_generate"


class FeedbackType(Enum):
    """Тип обратной связи"""
    POSITIVE = "positive"      # 👍
    NEGATIVE = "negative"      # 👎
    NEUTRAL = "neutral"        # 🤷
    CORRECTION = "correction"  # Пользователь исправил


# ============== Version Control ==============

@dataclass
class OrganVersion:
    """Версия органа"""
    version: str  # "1.0.0"
    capabilities: List[str]
    code_hash: str
    created_at: datetime
    changelog: str
    is_active: bool = True
    success_rate: float = 0.0
    usage_count: int = 0


@dataclass
class OrganHistory:
    """История изменений органа"""
    versions: List[OrganVersion] = field(default_factory=list)
    
    def add_version(self, capabilities: List[str], code: str, changelog: str) -> str:
        """Добавить новую версию"""
        # Вычисляем следующую версию
        if not self.versions:
            new_version = "1.0.0"
        else:
            last = self.versions[-1].version
            major, minor, patch = map(int, last.split('.'))
            # Новые capabilities = minor bump, иначе patch
            if len(capabilities) > len(self.versions[-1].capabilities):
                new_version = f"{major}.{minor + 1}.0"
            else:
                new_version = f"{major}.{minor}.{patch + 1}"
        
        version = OrganVersion(
            version=new_version,
            capabilities=capabilities,
            code_hash=hashlib.sha256(code.encode()).hexdigest()[:12],
            created_at=datetime.now(),
            changelog=changelog,
            is_active=True
        )
        
        # Деактивируем предыдущую версию
        for v in self.versions:
            v.is_active = False
        
        self.versions.append(version)
        return new_version
    
    def rollback(self, to_version: str) -> bool:
        """Откатить к предыдущей версии"""
        for v in self.versions:
            if v.version == to_version:
                # Деактивируем все
                for vv in self.versions:
                    vv.is_active = False
                v.is_active = True
                return True
        return False
    
    def get_active(self) -> Optional[OrganVersion]:
        """Получить активную версию"""
        for v in reversed(self.versions):
            if v.is_active:
                return v
        return None


# ============== Feedback Learning ==============

@dataclass
class UsageRecord:
    """Запись использования органа"""
    input_text: str
    output: str
    feedback: Optional[FeedbackType] = None
    correction: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class FeedbackLearner:
    """Система обучения на feedback"""
    
    def __init__(self, organ_id: str):
        self.organ_id = organ_id
        self.records: List[UsageRecord] = []
        self.patterns: Dict[str, str] = {}  # input_pattern -> best_output
        self.priority_boost: float = 0.0
        
    def record_usage(self, input_text: str, output: str) -> str:
        """Записать использование, вернуть ID записи"""
        record = UsageRecord(input_text=input_text, output=output)
        self.records.append(record)
        return str(len(self.records) - 1)
    
    def add_feedback(self, record_id: str, feedback: FeedbackType, correction: Optional[str] = None):
        """Добавить feedback к записи"""
        idx = int(record_id)
        if 0 <= idx < len(self.records):
            self.records[idx].feedback = feedback
            self.records[idx].correction = correction
            
            # Обучаемся на feedback
            self._learn_from_feedback(self.records[idx])
    
    def _learn_from_feedback(self, record: UsageRecord):
        """Обучиться на feedback"""
        if record.feedback == FeedbackType.POSITIVE:
            # Запоминаем успешный паттерн
            pattern = self._extract_pattern(record.input_text)
            self.patterns[pattern] = record.output
            self.priority_boost += 0.1
            logger.info(f"✅ Орган {self.organ_id} обучился: паттерн '{pattern}'")
            
        elif record.feedback == FeedbackType.NEGATIVE:
            self.priority_boost -= 0.05
            logger.info(f"⚠️ Орган {self.organ_id} получил негативный feedback")
            
        elif record.feedback == FeedbackType.CORRECTION and record.correction:
            # Учимся на исправлении
            pattern = self._extract_pattern(record.input_text)
            self.patterns[pattern] = record.correction
            logger.info(f"📝 Орган {self.organ_id} обучился на исправлении")
    
    def _extract_pattern(self, text: str) -> str:
        """Извлечь паттерн из текста"""
        # Убираем числа, оставляем структуру
        pattern = re.sub(r'\d+', 'N', text.lower())
        # Убираем лишние пробелы
        pattern = ' '.join(pattern.split())
        return pattern
    
    def get_learned_response(self, input_text: str) -> Optional[str]:
        """Получить выученный ответ если есть"""
        pattern = self._extract_pattern(input_text)
        return self.patterns.get(pattern)
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика обучения"""
        total = len(self.records)
        positive = len([r for r in self.records if r.feedback == FeedbackType.POSITIVE])
        negative = len([r for r in self.records if r.feedback == FeedbackType.NEGATIVE])
        
        return {
            "total_uses": total,
            "positive_feedback": positive,
            "negative_feedback": negative,
            "success_rate": positive / total if total > 0 else 0,
            "learned_patterns": len(self.patterns),
            "priority_boost": self.priority_boost
        }


# ============== Base Executable Organ ==============

class ExecutableOrgan(ABC):
    """Базовый класс для исполняемого органа"""
    
    def __init__(self, organ_id: str, name: str, description: str):
        self.organ_id = organ_id
        self.name = name
        self.description = description
        self.history = OrganHistory()
        self.learner = FeedbackLearner(organ_id)
        self.capabilities: List[OrganCapability] = []
        self._last_record_id: Optional[str] = None
        
    @abstractmethod
    def execute(self, command: str, **kwargs) -> str:
        """Выполнить команду. Должен быть реализован в подклассах."""
        pass
    
    @abstractmethod
    def can_handle(self, command: str) -> float:
        """Вернуть confidence 0-1 что орган может обработать команду"""
        pass
    
    def process(self, command: str, **kwargs) -> Tuple[str, Optional[str]]:
        """
        Обработать команду с учётом обучения.
        
        Returns:
            (результат, record_id для feedback или None при ошибке)
        """
        # Проверяем выученные паттерны
        learned = self.learner.get_learned_response(command)
        if learned:
            logger.info(f"🧠 Используем выученный ответ для '{command[:30]}...'")
            # Но всё равно записываем для статистики
            record_id = self.learner.record_usage(command, learned)
            self._last_record_id = record_id
            return learned, record_id
        
        # Выполняем команду и обеспечиваем устойчивость
        try:
            result = self.execute(command, **kwargs)
        except Exception as e:
            logger.exception(f"Ошибка при выполнении органа '{self.name}': {e}")
            result = f"❌ Ошибка выполнения: {e}"

        # Записываем для обучения (вне зависимости от успеха)
        try:
            record_id = self.learner.record_usage(command, result)
            self._last_record_id = record_id
        except Exception as e:
            logger.exception(f"Не удалось записать usage для органа '{self.name}': {e}")
            record_id = None

        return result, record_id
    
    def feedback(self, feedback_type: FeedbackType, correction: Optional[str] = None):
        """Добавить feedback к последнему выполнению"""
        if self._last_record_id:
            self.learner.add_feedback(self._last_record_id, feedback_type, correction)
    
    def upgrade(self, new_capabilities: List[OrganCapability], changelog: str) -> str:
        """Улучшить орган, создать новую версию"""
        self.capabilities.extend(new_capabilities)
        cap_names = [c.value for c in self.capabilities]
        version = self.history.add_version(cap_names, str(self.capabilities), changelog)
        logger.info(f"🔧 Орган {self.name} улучшен до версии {version}")
        return version
    
    def rollback(self, to_version: str) -> bool:
        """Откатить к предыдущей версии"""
        return self.history.rollback(to_version)
    
    def get_info(self) -> Dict[str, Any]:
        """Получить информацию об органе"""
        active = self.history.get_active()
        return {
            "id": self.organ_id,
            "name": self.name,
            "description": self.description,
            "capabilities": [c.value for c in self.capabilities],
            "version": active.version if active else "1.0.0",
            "versions_count": len(self.history.versions),
            "learning_stats": self.learner.get_stats()
        }


# ============== Graphics Organ ==============

class GraphicsOrgan(ExecutableOrgan):
    """
    Орган для генерации графики (ASCII art, текстовые изображения)
    
    Возможности:
    v1.0: Чёрно-белые квадраты
    v1.1: Произвольные размеры
    v2.0: Цветные квадраты (эмодзи)
    v2.1: Круги
    v3.0: Произвольные фигуры
    """
    
    # Символы для рисования
    SYMBOLS = {
        "black": "█",
        "white": "░",
        "gray": "▓",
        "dot": "●",
        "empty": "○",
        "star": "★",
        "heart": "♥",
    }
    
    COLOR_EMOJIS = {
        "red": "🟥",
        "green": "🟩",
        "blue": "🟦",
        "yellow": "🟨",
        "orange": "🟧",
        "purple": "🟪",
        "brown": "🟫",
        "black": "⬛",
        "white": "⬜",
    }
    
    def __init__(self):
        super().__init__(
            organ_id="graphics_organ",
            name="GraphicsOrgan",
            description="Генерация ASCII-графики и текстовых изображений"
        )
        self.capabilities = [OrganCapability.DRAW_SHAPES]
        # Создаём начальную версию
        self.history.add_version(
            capabilities=["draw_shapes"],
            code="initial",
            changelog="Базовая версия: чёрно-белые квадраты"
        )
    
    def can_handle(self, command: str) -> float:
        """Проверить может ли орган обработать команду"""
        command_lower = command.lower()
        
        keywords = [
            ("рисуй", 0.9), ("нарисуй", 0.9), ("создай", 0.5),
            ("квадрат", 0.8), ("круг", 0.8), ("прямоугольник", 0.8),
            ("картинк", 0.7), ("изображен", 0.7),
            ("черно-бел", 0.6), ("цветн", 0.6),
            ("пиксел", 0.7), ("ascii", 0.9),
        ]
        
        score = 0.0
        for keyword, weight in keywords:
            if keyword in command_lower:
                score = max(score, weight)
        
        return score
    
    def execute(self, command: str, **kwargs) -> str:
        """Выполнить команду рисования"""
        command_lower = command.lower()
        
        # Определяем что рисовать
        if "квадрат" in command_lower:
            return self._draw_square(command_lower)
        elif "круг" in command_lower:
            return self._draw_circle(command_lower)
        elif "прямоугольник" in command_lower:
            return self._draw_rectangle(command_lower)
        elif "линия" in command_lower or "линию" in command_lower:
            return self._draw_line(command_lower)
        elif "сердце" in command_lower or "сердц" in command_lower:
            return self._draw_heart()
        else:
            # Дефолт — квадрат
            return self._draw_square(command_lower)
    
    def _extract_size(self, text: str, default: int = 5) -> int:
        """Извлечь размер из текста"""
        # Ищем числа
        numbers = re.findall(r'\d+', text)
        if numbers:
            size = int(numbers[0])
            return min(max(size, 1), 20)  # Ограничиваем 1-20
        return default
    
    def _extract_color(self, text: str) -> Optional[str]:
        """Извлечь цвет из текста"""
        for color in self.COLOR_EMOJIS.keys():
            if color in text or self._translate_color(text) == color:
                return color
        return None
    
    def _translate_color(self, text: str) -> Optional[str]:
        """Перевести русский цвет в английский"""
        translations = {
            "красн": "red", "зелён": "green", "зелен": "green",
            "син": "blue", "жёлт": "yellow", "желт": "yellow",
            "оранж": "orange", "фиолет": "purple", "пурпур": "purple",
            "коричнев": "brown", "чёрн": "black", "черн": "black",
            "бел": "white",
        }
        for ru, en in translations.items():
            if ru in text:
                return en
        return None
    
    def _get_symbol(self, text: str, colored: bool = False) -> str:
        """Получить символ для рисования"""
        if colored:
            color = self._extract_color(text) or self._translate_color(text)
            if color and color in self.COLOR_EMOJIS:
                return self.COLOR_EMOJIS[color]
            return self.COLOR_EMOJIS["black"]
        
        if "бел" in text:
            return self.SYMBOLS["white"]
        return self.SYMBOLS["black"]
    
    def _draw_square(self, text: str) -> str:
        """Нарисовать квадрат"""
        size = self._extract_size(text)
        colored = "цвет" in text or self._extract_color(text) is not None
        symbol = self._get_symbol(text, colored)
        
        lines = []
        for _ in range(size):
            lines.append(symbol * size)
        
        return f"Квадрат {size}x{size}:\n```\n" + "\n".join(lines) + "\n```"
    
    def _draw_circle(self, text: str) -> str:
        """Нарисовать круг (приближённо)"""
        radius = self._extract_size(text, default=3)
        colored = "цвет" in text or self._extract_color(text) is not None
        symbol = self._get_symbol(text, colored)
        empty = " " if not colored else "  "
        
        lines = []
        for y in range(-radius, radius + 1):
            line = ""
            for x in range(-radius, radius + 1):
                if x*x + y*y <= radius*radius:
                    line += symbol
                else:
                    line += empty
            lines.append(line)
        
        return f"Круг радиусом {radius}:\n```\n" + "\n".join(lines) + "\n```"
    
    def _draw_rectangle(self, text: str) -> str:
        """Нарисовать прямоугольник"""
        numbers = re.findall(r'\d+', text)
        width = int(numbers[0]) if len(numbers) > 0 else 6
        height = int(numbers[1]) if len(numbers) > 1 else 3
        width = min(max(width, 1), 20)
        height = min(max(height, 1), 10)
        
        colored = "цвет" in text or self._extract_color(text) is not None
        symbol = self._get_symbol(text, colored)
        
        lines = []
        for _ in range(height):
            lines.append(symbol * width)
        
        return f"Прямоугольник {width}x{height}:\n```\n" + "\n".join(lines) + "\n```"
    
    def _draw_line(self, text: str) -> str:
        """Нарисовать линию"""
        length = self._extract_size(text, default=10)
        colored = "цвет" in text or self._extract_color(text) is not None
        symbol = self._get_symbol(text, colored)
        
        if "вертикал" in text:
            lines = [symbol for _ in range(length)]
            return f"Вертикальная линия ({length}):\n```\n" + "\n".join(lines) + "\n```"
        else:
            return f"Горизонтальная линия ({length}):\n```\n{symbol * length}\n```"
    
    def _draw_heart(self) -> str:
        """Нарисовать сердце"""
        heart = [
            "  ♥♥   ♥♥  ",
            " ♥♥♥♥ ♥♥♥♥ ",
            "♥♥♥♥♥♥♥♥♥♥♥",
            " ♥♥♥♥♥♥♥♥♥ ",
            "  ♥♥♥♥♥♥♥  ",
            "   ♥♥♥♥♥   ",
            "    ♥♥♥    ",
            "     ♥     ",
        ]
        return "Сердце:\n```\n" + "\n".join(heart) + "\n```"
    
    def enable_colors(self):
        """Включить поддержку цветов (апгрейд)"""
        if OrganCapability.DRAW_COLORS not in self.capabilities:
            self.upgrade(
                [OrganCapability.DRAW_COLORS],
                "Добавлена поддержка цветных изображений через эмодзи"
            )


# ============== Math Organ ==============

class MathOrgan(ExecutableOrgan):
    """Орган для математических вычислений"""
    
    def __init__(self):
        super().__init__(
            organ_id="math_organ",
            name="MathOrgan",
            description="Математические вычисления и формулы"
        )
        self.capabilities = [OrganCapability.MATH_BASIC]
        self.history.add_version(
            capabilities=["math_basic"],
            code="initial",
            changelog="Базовые арифметические операции"
        )
    
    @staticmethod
    def _is_pure_math_expression(command: str) -> bool:
        """Проверить, что команда — чистое математическое выражение."""
        if not command:
            return False
        stripped = command.strip()
        if not stripped:
            return False
        if not MATH_EXPRESSION_PATTERN.fullmatch(stripped):
            return False
        return bool(MATH_DIGIT_PATTERN.search(stripped))

    def can_handle(self, command: str) -> float:
        """Проверить, может ли орган обработать команду."""
        if not self._is_pure_math_expression(command):
            return 0.0
        return 0.9

    def execute(self, command: str, **kwargs) -> str:
        """Выполнить математическую операцию"""
        if not self._is_pure_math_expression(command):
            return "Не найдено математическое выражение. Пример: 2 + 2 * 3"
        # Извлекаем числа и операции
        # Безопасное вычисление через ast
        import ast
        import operator
        
        # Поддерживаемые операторы
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }
        
        def safe_eval(node):
            # Python 3.8+: ast.Num deprecated, use ast.Constant
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            elif hasattr(ast, 'Num') and isinstance(node, ast.Num):  # Legacy support
                return node.n
            elif isinstance(node, ast.BinOp):
                return operators[type(node.op)](safe_eval(node.left), safe_eval(node.right))
            elif isinstance(node, ast.UnaryOp):
                return operators[type(node.op)](safe_eval(node.operand))
            else:
                raise ValueError(f"Неподдерживаемая операция: {type(node).__name__}")
        
        # Извлекаем выражение
        expr = re.sub(r'[^\d\+\-\*\/\^\(\)\.\s]', '', command)
        expr = expr.replace('^', '**')  # Степень
        expr = expr.strip()
        
        if not expr:
            return "Не найдено математическое выражение. Пример: 2 + 2 * 3"
        
        try:
            tree = ast.parse(expr, mode='eval')
            result = safe_eval(tree.body)
            
            # Форматируем результат
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            
            return f"📊 {expr} = **{result}**"
            
        except Exception as e:
            return f"❌ Ошибка вычисления: {e}"


# ============== Text Organ ==============

class TextOrgan(ExecutableOrgan):
    """Орган для обработки текста"""
    
    def __init__(self):
        super().__init__(
            organ_id="text_organ",
            name="TextOrgan",
            description="Трансформация и обработка текста"
        )
        self.capabilities = [OrganCapability.TEXT_TRANSFORM]
        self.history.add_version(
            capabilities=["text_transform"],
            code="initial",
            changelog="Базовые текстовые трансформации"
        )
    
    def can_handle(self, command: str) -> float:
        """Проверить может ли орган обработать команду"""
        command_lower = command.lower()
        
        keywords = [
            ("переверни", 0.9), ("разверни", 0.9),
            ("заглавн", 0.8), ("прописн", 0.8),
            ("подсчитай букв", 0.9), ("подсчитай слов", 0.9),
            ("замени", 0.7), ("удали", 0.6),
            ("зашифруй", 0.8), ("расшифруй", 0.8),
        ]
        
        score = 0.0
        for keyword, weight in keywords:
            if keyword in command_lower:
                score = max(score, weight)
        
        return score
    
    def execute(self, command: str, **kwargs) -> str:
        """Выполнить текстовую трансформацию"""
        command_lower = command.lower()
        
        # Извлекаем текст в кавычках
        quoted = re.findall(r'["\'](.+?)["\']', command)
        text = quoted[0] if quoted else command
        
        if "переверни" in command_lower or "разверни" in command_lower:
            return f"🔄 Перевёрнутый текст: **{text[::-1]}**"
        
        elif "заглавн" in command_lower or "верхн" in command_lower:
            return f"🔠 ЗАГЛАВНЫМИ: **{text.upper()}**"
        
        elif "прописн" in command_lower or "нижн" in command_lower:
            return f"🔡 строчными: **{text.lower()}**"
        
        elif "подсчитай букв" in command_lower or "сколько букв" in command_lower:
            letters = len([c for c in text if c.isalpha()])
            return f"📊 Букв в тексте: **{letters}**"
        
        elif "подсчитай слов" in command_lower or "сколько слов" in command_lower:
            words = len(text.split())
            return f"📊 Слов в тексте: **{words}**"
        
        elif "зашифруй" in command_lower:
            # Простой ROT13
            result = ""
            for c in text:
                if c.isalpha():
                    base = ord('a') if c.islower() else ord('A')
                    result += chr((ord(c) - base + 13) % 26 + base)
                else:
                    result += c
            return f"🔐 Зашифровано (ROT13): **{result}**"
        
        else:
            return f"📝 Текст: {text}\n📏 Длина: {len(text)} символов"


# ============== Organ Registry ==============

class ExecutableOrganRegistry:
    """Реестр исполняемых органов"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.organs: Dict[str, ExecutableOrgan] = {}
        self._register_builtin_organs()
        self._initialized = True
        
        logger.info(f"🧬 ExecutableOrganRegistry инициализирован: {len(self.organs)} органов")
    
    def _register_builtin_organs(self):
        """Зарегистрировать встроенные органы"""
        self.register(GraphicsOrgan())
        self.register(MathOrgan())
        self.register(TextOrgan())
    
    def register(self, organ: ExecutableOrgan):
        """Зарегистрировать орган"""
        self.organs[organ.organ_id] = organ
        logger.info(f"✅ Зарегистрирован орган: {organ.name}")
    
    def get(self, organ_id: str) -> Optional[ExecutableOrgan]:
        """Получить орган по ID"""
        return self.organs.get(organ_id)
    
    def find_best_organ(self, command: str) -> Tuple[Optional[ExecutableOrgan], float]:
        """Найти лучший орган для команды"""
        best_organ = None
        best_score = 0.0
        
        for organ in self.organs.values():
            score = organ.can_handle(command)
            # Учитываем boost от обучения
            score += organ.learner.priority_boost
            score = min(score, 1.0)  # Не больше 1
            
            if score > best_score:
                best_score = score
                best_organ = organ
        
        return best_organ, best_score
    
    def process_command(self, command: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Обработать команду подходящим органом.
        
        Returns:
            (результат, organ_id, record_id для feedback)
        """
        organ, score = self.find_best_organ(command)
        
        if organ is None or score < 0.3:
            return "Не найден подходящий орган для этой команды.", None, None
        
        result, record_id = organ.process(command)
        return result, organ.organ_id, record_id
    
    def add_feedback(self, organ_id: str, feedback_type: FeedbackType, correction: Optional[str] = None):
        """Добавить feedback к последнему выполнению органа"""
        organ = self.get(organ_id)
        if organ:
            organ.feedback(feedback_type, correction)
    
    def get_all_info(self) -> List[Dict[str, Any]]:
        """Получить информацию обо всех органах"""
        return [organ.get_info() for organ in self.organs.values()]


def get_organ_registry() -> ExecutableOrganRegistry:
    """Получить singleton реестра органов"""
    return ExecutableOrganRegistry()


# ============== Sandbox Testing ==============

class OrganSandbox:
    """Песочница для тестирования органов перед активацией"""
    
    @staticmethod
    def test_organ(organ: ExecutableOrgan, test_cases: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
        """
        Протестировать орган.
        
        Args:
            organ: Орган для тестирования
            test_cases: Список (input, expected_substring) для проверки
            
        Returns:
            Результат тестирования
        """
        results = {
            "organ_id": organ.organ_id,
            "passed": 0,
            "failed": 0,
            "errors": [],
            "outputs": []
        }
        
        # Дефолтные тесты по типу органа
        if test_cases is None:
            if isinstance(organ, GraphicsOrgan):
                test_cases = [
                    ("нарисуй квадрат 3x3", "```"),
                    ("рисуй круг радиусом 2", "```"),
                ]
            elif isinstance(organ, MathOrgan):
                test_cases = [
                    ("2 + 2", "4"),
                    ("10 * 5", "50"),
                ]
            elif isinstance(organ, TextOrgan):
                test_cases = [
                    ("переверни 'привет'", "тевирп"),
                ]
            else:
                test_cases = []
        
        for input_text, expected in test_cases:
            try:
                result, _ = organ.process(input_text)
                results["outputs"].append({"input": input_text, "output": result})
                
                if expected in result:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Ожидалось '{expected}' в ответе на '{input_text}'")
                    
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Исключение при '{input_text}': {e}")
        
        results["success"] = results["failed"] == 0
        return results


# ============== Test ==============

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("🧪 Тестирование ExecutableOrgans")
    print("=" * 60)
    
    registry = get_organ_registry()
    
    # Тест GraphicsOrgan
    print("\n📊 Тест GraphicsOrgan:")
    result, organ_id, record_id = registry.process_command("нарисуй чёрный квадрат 5x5")
    print(result)
    
    # Добавляем feedback
    if organ_id:
        registry.add_feedback(organ_id, FeedbackType.POSITIVE)
    
    # Тест цветного
    print("\n🎨 Тест цветного квадрата:")
    result, _, _ = registry.process_command("нарисуй красный квадрат 4x4")
    print(result)
    
    # Тест MathOrgan
    print("\n🔢 Тест MathOrgan:")
    result, _, _ = registry.process_command("посчитай 15 * 4 + 10")
    print(result)
    
    # Тест TextOrgan
    print("\n📝 Тест TextOrgan:")
    result, _, _ = registry.process_command("переверни 'Привет Нейра!'")
    print(result)
    
    # Статистика
    print("\n📈 Статистика органов:")
    for info in registry.get_all_info():
        print(f"  {info['name']} v{info['version']}: {info['learning_stats']['total_uses']} использований")
    
    # Sandbox тест
    print("\n🧪 Sandbox тестирование:")
    graphics = registry.get("graphics_organ")
    if graphics:
        sandbox_result = OrganSandbox.test_organ(graphics)
        print(f"  Passed: {sandbox_result['passed']}, Failed: {sandbox_result['failed']}")
        if sandbox_result['errors']:
            for err in sandbox_result['errors']:
                print(f"  ❌ {err}")
    else:
        print("  ⚠️ GraphicsOrgan не найден")
