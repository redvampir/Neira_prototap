"""
Cell Router — Система маршрутизации запросов к специализированным клеткам

Решает проблему: LLM не знает о существовании клеток (UICodeCell, CodeCell, etc)
Решение: Добавляем context layer который объясняет LLM доступные инструменты
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import re


@dataclass
class CellCapability:
    """Описание возможностей клетки для LLM"""
    name: str
    description: str
    triggers: List[str]  # Ключевые слова для активации
    examples: List[str]  # Примеры запросов
    priority: int = 1  # Приоритет при конфликте (выше = важнее)


class CellRouter:
    """
    Маршрутизатор запросов к специализированным клеткам
    
    Архитектура:
    User Request → Intent Detection → Cell Selection → Execution → Response
    
    Преимущества:
    - LLM получает контекст о доступных инструментах
    - Специализированные клетки вызываются явно
    - Нет дублирования логики в разных местах
    """
    
    def __init__(self):
        self.cells: Dict[str, CellCapability] = {}
        self._register_default_cells()
    
    def _register_default_cells(self):
        """Регистрируем встроенные клетки"""
        
        # UICodeCell — генерация интерактивных UI
        self.register_cell(CellCapability(
            name="ui_code_cell",
            description="Создание интерактивных UI компонентов (игры, формы, дашборды)",
            triggers=[
                "создай интерфейс", "сделай ui", "сгенерируй страницу",
                "нарисуй", "web приложение", "html страница",
                "крестики", "нолики", "игра", "калькулятор", "форма",
                "дашборд", "виджет", "кнопка", "меню"
            ],
            examples=[
                "Создай интерфейс для крестиков-ноликов",
                "Сделай калькулятор с красивым UI",
                "Сгенерируй дашборд для статистики"
            ],
            priority=10  # Высокий приоритет для UI запросов
        ))
        
        # CodeCell — генерация кода (не UI)
        self.register_cell(CellCapability(
            name="code_cell",
            description="Написание Python кода, скриптов, функций",
            triggers=[
                "напиши код", "функция", "скрипт", "алгоритм",
                "реализуй", "программа", "python", "def ", "class "
            ],
            examples=[
                "Напиши функцию для сортировки",
                "Создай скрипт для обработки JSON"
            ],
            priority=5
        ))
        
        # AnalysisCell — анализ данных/файлов
        self.register_cell(CellCapability(
            name="analysis_cell",
            description="Анализ данных, файлов, кода",
            triggers=[
                "проанализируй", "что в файле", "статистика",
                "какие проблемы", "оцени", "review"
            ],
            examples=[
                "Проанализируй этот код",
                "Какие проблемы в архитектуре?"
            ],
            priority=3
        ))
        
    def register_cell(self, capability: CellCapability):
        """Регистрация новой клетки"""
        self.cells[capability.name] = capability
    
    def detect_intent(self, user_input: str) -> Optional[str]:
        """
        Определяет какая клетка должна обработать запрос
        
        Returns:
            Имя клетки или None для обычного ответа
        """
        user_lower = user_input.lower()
        
        # Находим все подходящие клетки
        matches: List[tuple] = []  # (cell_name, priority, match_count)
        
        for cell_name, capability in self.cells.items():
            match_count = sum(
                1 for trigger in capability.triggers 
                if trigger in user_lower
            )
            
            if match_count > 0:
                matches.append((cell_name, capability.priority, match_count))
        
        if not matches:
            return None
        
        # Сортируем: сначала по приоритету, потом по количеству совпадений
        matches.sort(key=lambda x: (x[1], x[2]), reverse=True)
        
        return matches[0][0]
    
    def get_system_prompt_extension(self) -> str:
        """
        Генерирует дополнение к system prompt которое объясняет LLM о клетках
        
        Это ключевой метод: он делает клетки "видимыми" для модели
        """
        prompt_parts = [
            "## 🧬 Доступные специализированные клетки",
            "",
            "У тебя есть доступ к специализированным модулям (клеткам) для конкретных задач:",
            ""
        ]
        
        for cell_name, capability in self.cells.items():
            prompt_parts.extend([
                f"### {capability.name}",
                f"**Назначение:** {capability.description}",
                f"**Активация:** {', '.join(capability.triggers[:5])}...",
                f"**Примеры:**"
            ])
            
            for example in capability.examples:
                prompt_parts.append(f"  - \"{example}\"")
            
            prompt_parts.append("")
        
        prompt_parts.extend([
            "## 📋 Правила использования",
            "",
            "1. **Если запрос подходит под клетку** — укажи это в ответе:",
            "   `[CELL:ui_code_cell] <твоё пояснение>`",
            "",
            "2. **Для обычных вопросов** — отвечай как обычно",
            "",
            "3. **Приоритет UI:** Если видишь слова 'создай интерфейс', 'ui', 'игра' → используй ui_code_cell",
            ""
        ])
        
        return "\n".join(prompt_parts)
    
    def extract_cell_directive(self, response: str) -> tuple[Optional[str], str]:
        """
        Извлекает директиву клетки из ответа LLM
        
        Returns:
            (cell_name, cleaned_response)
        """
        # Ищем паттерн [CELL:название]
        pattern = r'\[CELL:(\w+)\](.*?)(?=\[CELL:|$)'
        match = re.search(pattern, response, re.DOTALL)
        
        if match:
            cell_name = match.group(1)
            content = match.group(2).strip()
            return cell_name, content
        
        return None, response
    
    def get_cell_context(self, cell_name: str) -> Optional[Dict[str, Any]]:
        """
        Возвращает контекст для конкретной клетки
        
        Используется для передачи дополнительной информации в клетку
        """
        if cell_name not in self.cells:
            return None
        
        capability = self.cells[cell_name]
        
        return {
            "name": cell_name,
            "description": capability.description,
            "examples": capability.examples,
            "expected_output": self._get_expected_output(cell_name)
        }
    
    def _get_expected_output(self, cell_name: str) -> str:
        """Описывает что должна вернуть клетка"""
        outputs = {
            "ui_code_cell": "HTML файл с интерактивным UI (standalone, CSS+JS inline)",
            "code_cell": "Python код с комментариями и примерами использования",
            "analysis_cell": "Структурированный анализ с выводами и рекомендациями"
        }
        return outputs.get(cell_name, "Результат выполнения задачи")
    
    def should_use_cell(self, user_input: str) -> tuple[bool, Optional[str], str]:
        """
        Главный метод: определяет нужна ли клетка
        
        Returns:
            (use_cell, cell_name, reasoning)
        """
        detected_cell = self.detect_intent(user_input)
        
        if not detected_cell:
            return False, None, "Обычный запрос, специализированная клетка не требуется"
        
        capability = self.cells[detected_cell]
        
        # Находим триггеры которые сработали
        matched_triggers = [
            trigger for trigger in capability.triggers
            if trigger in user_input.lower()
        ]
        
        reasoning = (
            f"Обнаружен запрос для {detected_cell}: "
            f"совпадения по триггерам {matched_triggers[:3]}"
        )
        
        return True, detected_cell, reasoning


# Глобальный экземпляр (singleton)
_router = None

def get_router() -> CellRouter:
    """Получить глобальный router (ленивая инициализация)"""
    global _router
    if _router is None:
        _router = CellRouter()
    return _router


# Тесты
if __name__ == "__main__":
    router = CellRouter()
    
    test_cases = [
        "Создай интерфейс для крестиков-ноликов",
        "Напиши функцию для сортировки массива",
        "Как дела?",
        "Сделай калькулятор с ui",
        "Проанализируй код в файле main.py"
    ]
    
    print("🧪 Тестирование Cell Router\n")
    
    for case in test_cases:
        use_cell, cell_name, reasoning = router.should_use_cell(case)
        
        print(f"📝 Запрос: {case}")
        print(f"   {'✅' if use_cell else '❌'} Клетка: {cell_name or 'нет'}")
        print(f"   Обоснование: {reasoning}")
        print()
    
    print("\n📋 System Prompt Extension:\n")
    print(router.get_system_prompt_extension())
