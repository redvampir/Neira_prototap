"""
Детектор аномалий для системы памяти Neira
Блокирует технический мусор, зацикливания и галлюцинации ДО записи
"""

import re
from typing import Tuple, List
from datetime import datetime
from dataclasses import dataclass


@dataclass
class AnomalyReport:
    """Отчёт о детектированной аномалии"""
    is_anomaly: bool
    reason: str = ""
    confidence: float = 0.0
    suggestions: List[str] = None
    
    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []


class MemoryAnomalyDetector:
    """Детектор аномальных записей перед сохранением в память"""
    
    def __init__(self, window_size: int = 20):
        """
        Args:
            window_size: Размер окна для детекта зацикливаний
        """
        self.window_size = window_size
        
        # История последних записей для детекта зацикливания
        self.recent_window: List[Tuple[str, str]] = []  # (timestamp, text)
        
        # Паттерны технического мусора
        self.technical_patterns = [
            (r"import\s+\w+", "Python import statement"),
            (r"from\s+\w+\s+import", "Python from-import"),
            (r"class\s+\w+\s*[\(:]", "Class definition"),
            (r"def\s+\w+\s*\(", "Function definition"),
            (r"async\s+def", "Async function"),
            (r"await\s+\w+", "Await expression"),
            (r"нейронн(ая|ые|ых|ой)\s+сет", "Нейронная сеть"),
            (r"трансформер(а|ы|ов|ом)?", "Transformer model"),
            (r"градиентн(ый|ого|ом)\s+спуск", "Gradient descent"),
            (r"биохимическ(ий|ого|ом|ие)", "Биохимический процесс"),
            (r"нейромедиатор(ы|ов|ами)?", "Нейромедиаторы"),
            (r"синаптическ(ая|ие|их|ого)", "Синаптический"),
            (r"корт(екс|икальн)", "Кортекс/кортикальный"),
            (r"эмбеддинг(и|ов|ами)?", "Embeddings"),
            (r"токен(ы|ов|изация)?", "Токены"),
            (r"промпт(а|ы|ов|ом)?", "Промпт"),
        ]
        
        # Паттерны неуверенности (признаки галлюцинаций)
        self.uncertainty_phrases = [
            "я не знаю",
            "не уверен",
            "возможно",
            "может быть",
            "вероятно",
            "согласно моим данным",
            "в моей базе",
            "как языковая модель",
            "как ИИ",
            "не могу точно сказать",
            "сложно ответить",
        ]
        
        # Максимальная длина записи
        self.max_length = 2000
        
        # Порог схожести для детекта зацикливания
        self.similarity_threshold = 0.7
        
        # Минимум одинаковых за минуту для зацикливания
        self.loop_threshold = 3
    
    def check(self, text: str, timestamp: str = None) -> AnomalyReport:
        """
        Проверяет текст на аномалии
        
        Args:
            text: Текст для проверки
            timestamp: ISO timestamp (если None - берётся текущее время)
        
        Returns:
            AnomalyReport с результатами проверки
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        # 1. Технический код/жаргон
        tech_check = self._check_technical_jargon(text)
        if tech_check.is_anomaly:
            return tech_check
        
        # 2. Зацикливание (N одинаковых за минуту)
        loop_check = self._check_looping(text, timestamp)
        if loop_check.is_anomaly:
            return loop_check
        
        # 3. Слишком длинный текст
        length_check = self._check_length(text)
        if length_check.is_anomaly:
            return length_check
        
        # 4. Признаки неуверенности (галлюцинации)
        uncertainty_check = self._check_uncertainty(text)
        if uncertainty_check.is_anomaly:
            return uncertainty_check
        
        # Добавляем в окно после проверок
        self.recent_window.append((timestamp, text))
        if len(self.recent_window) > self.window_size:
            self.recent_window.pop(0)
        
        return AnomalyReport(is_anomaly=False, confidence=1.0)
    
    def _check_technical_jargon(self, text: str) -> AnomalyReport:
        """Проверка на технический код и жаргон"""
        for pattern, description in self.technical_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return AnomalyReport(
                    is_anomaly=True,
                    reason="technical_jargon",
                    confidence=0.9,
                    suggestions=[
                        f"Обнаружен технический паттерн: {description}",
                        f"Совпадения: {matches[:3]}",
                        "Это обсуждение кода, а не личная память"
                    ]
                )
        
        return AnomalyReport(is_anomaly=False)
    
    def _check_looping(self, text: str, timestamp: str) -> AnomalyReport:
        """Проверка на зацикливание (повторяющиеся записи за короткое время)"""
        minute_key = timestamp[:16]  # YYYY-MM-DDTHH:MM
        
        # Записи за эту же минуту
        same_minute = [
            txt for ts, txt in self.recent_window
            if ts[:16] == minute_key
        ]
        
        if len(same_minute) >= self.loop_threshold - 1:  # -1 т.к. текущую ещё не добавили
            # Проверяем схожесть с текущим текстом
            similarities = [
                self._text_similarity(text, prev_text)
                for prev_text in same_minute
            ]
            
            max_similarity = max(similarities, default=0)
            
            if max_similarity >= self.similarity_threshold:
                return AnomalyReport(
                    is_anomaly=True,
                    reason="looping",
                    confidence=max_similarity,
                    suggestions=[
                        f"Обнаружено {len(same_minute) + 1} похожих записей за минуту",
                        f"Максимальная схожесть: {max_similarity:.2%}",
                        "Возможно зацикливание в диалоге"
                    ]
                )
        
        return AnomalyReport(is_anomaly=False)
    
    def _check_length(self, text: str) -> AnomalyReport:
        """Проверка на чрезмерную длину"""
        if len(text) > self.max_length:
            return AnomalyReport(
                is_anomaly=True,
                reason="too_long",
                confidence=0.8,
                suggestions=[
                    f"Текст слишком длинный: {len(text)} символов (макс {self.max_length})",
                    "Возможно это копипаст кода или документации",
                    "Разбейте на несколько записей или суммаризируйте"
                ]
            )
        
        return AnomalyReport(is_anomaly=False)
    
    def _check_uncertainty(self, text: str) -> AnomalyReport:
        """Проверка на признаки неуверенности (галлюцинации)"""
        lower_text = text.lower()
        
        found_phrases = [
            phrase for phrase in self.uncertainty_phrases
            if phrase in lower_text
        ]
        
        # Если 3+ фраз неуверенности - подозрительно
        if len(found_phrases) >= 3:
            return AnomalyReport(
                is_anomaly=True,
                reason="uncertain_language",
                confidence=0.7,
                suggestions=[
                    f"Обнаружено {len(found_phrases)} фраз неуверенности",
                    f"Примеры: {found_phrases[:3]}",
                    "Возможна галлюцинация - факт не подтверждён"
                ]
            )
        
        return AnomalyReport(is_anomaly=False)
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Jaccard similarity между двумя текстами"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def reset(self):
        """Сброс истории (например, после перезапуска бота)"""
        self.recent_window.clear()
    
    def get_stats(self) -> dict:
        """Статистика работы детектора"""
        return {
            "window_size": len(self.recent_window),
            "max_window_size": self.window_size,
            "thresholds": {
                "similarity": self.similarity_threshold,
                "loop_count": self.loop_threshold,
                "max_length": self.max_length
            }
        }


# Пример использования
if __name__ == "__main__":
    detector = MemoryAnomalyDetector()
    
    # Тест 1: Технический код
    test1 = "А потом я написал import asyncio и запустил бота"
    report1 = detector.check(test1)
    print(f"Тест 1 (код): {report1.is_anomaly} - {report1.reason}")
    if report1.is_anomaly:
        for suggestion in report1.suggestions:
            print(f"  • {suggestion}")
    
    # Тест 2: Зацикливание
    timestamp = "2025-12-16T10:30:00"
    for i in range(4):
        test2 = "Я очень люблю гулять по парку каждый день"
        report2 = detector.check(test2, timestamp)
        if i == 3:  # На 4-й раз должен детектировать
            print(f"\nТест 2 (зацикл): {report2.is_anomaly} - {report2.reason}")
            if report2.is_anomaly:
                for suggestion in report2.suggestions:
                    print(f"  • {suggestion}")
    
    # Тест 3: Неуверенность
    test3 = "Я не знаю точно, возможно это было в парке, но не уверена, может быть в субботу"
    report3 = detector.check(test3)
    print(f"\nТест 3 (неув): {report3.is_anomaly} - {report3.reason}")
    if report3.is_anomaly:
        for suggestion in report3.suggestions:
            print(f"  • {suggestion}")
    
    # Тест 4: Нормальная запись
    test4 = "Сегодня была на концерте, очень понравилось!"
    report4 = detector.check(test4)
    print(f"\nТест 4 (норм): {report4.is_anomaly}")
