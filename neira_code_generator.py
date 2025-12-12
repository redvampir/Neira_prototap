"""
💻 NEIRA CODE GENERATOR
Автономная генерация кода с обучением на исправлениях
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

class CodeLanguage(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    HTML = "html"
    CSS = "css"
    SQL = "sql"
    BASH = "bash"

class CodeComplexity(Enum):
    SIMPLE = "simple"      # 1-10 строк
    MEDIUM = "medium"      # 10-50 строк
    COMPLEX = "complex"    # 50+ строк

@dataclass
class CodeTemplate:
    """Шаблон кода, который Neira знает"""
    id: str
    language: CodeLanguage
    pattern: str           # Что генерирует (например "функция сортировки")
    template: str          # Код-шаблон
    variables: List[str]   # Заменяемые переменные
    complexity: CodeComplexity
    success_count: int = 0
    failure_count: int = 0
    
@dataclass
class CodeGeneration:
    """Результат генерации кода"""
    id: str
    request: str           # Что просил пользователь
    generated_code: str    # Сгенерированный код
    language: CodeLanguage
    template_used: Optional[str] = None
    timestamp: datetime = None
    
    # Обратная связь
    user_rating: Optional[int] = None  # 1-5
    corrections: List[str] = None      # Что исправили
    final_code: Optional[str] = None   # Финальная версия после правок
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.corrections is None:
            self.corrections = []

class NeiraCodeGenerator:
    """
    Система генерации кода Neira
    
    Умеет:
    - Генерировать код по паттернам
    - Учиться на исправлениях
    - Создавать новые шаблоны
    - Улучшать существующие
    """
    
    def __init__(self):
        self.templates_file = "neira_code_templates.json"
        self.history_file = "neira_code_history.json"
        
        self.templates: Dict[str, CodeTemplate] = {}
        self.history: List[CodeGeneration] = []
        
        self.load()
        
        # Если нет шаблонов - создаём базовые
        if not self.templates:
            self._create_basic_templates()
    
    def _create_basic_templates(self):
        """Создать базовые шаблоны кода"""
        
        basic = [
            # Python
            CodeTemplate(
                id="python_function",
                language=CodeLanguage.PYTHON,
                pattern="функция",
                template='''def {function_name}({parameters}):
    """
    {description}
    """
    {body}
    return {return_value}''',
                variables=["function_name", "parameters", "description", "body", "return_value"],
                complexity=CodeComplexity.SIMPLE
            ),
            
            CodeTemplate(
                id="python_class",
                language=CodeLanguage.PYTHON,
                pattern="класс",
                template='''class {class_name}:
    """
    {description}
    """
    
    def __init__(self, {init_params}):
        {init_body}
    
    def {method_name}(self, {method_params}):
        """
        {method_description}
        """
        {method_body}''',
                variables=["class_name", "description", "init_params", "init_body", 
                          "method_name", "method_params", "method_description", "method_body"],
                complexity=CodeComplexity.MEDIUM
            ),
            
            CodeTemplate(
                id="python_list_comprehension",
                language=CodeLanguage.PYTHON,
                pattern="list comprehension",
                template="{result} = [{expression} for {item} in {iterable} if {condition}]",
                variables=["result", "expression", "item", "iterable", "condition"],
                complexity=CodeComplexity.SIMPLE
            ),
            
            # JavaScript
            CodeTemplate(
                id="js_function",
                language=CodeLanguage.JAVASCRIPT,
                pattern="функция",
                template='''function {function_name}({parameters}) {{
    // {description}
    {body}
    return {return_value};
}}''',
                variables=["function_name", "parameters", "description", "body", "return_value"],
                complexity=CodeComplexity.SIMPLE
            ),
            
            CodeTemplate(
                id="js_arrow_function",
                language=CodeLanguage.JAVASCRIPT,
                pattern="arrow function",
                template="const {name} = ({parameters}) => {body};",
                variables=["name", "parameters", "body"],
                complexity=CodeComplexity.SIMPLE
            ),
            
            # HTML
            CodeTemplate(
                id="html_page",
                language=CodeLanguage.HTML,
                pattern="html страница",
                template='''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body>
    {content}
</body>
</html>''',
                variables=["title", "content"],
                complexity=CodeComplexity.SIMPLE
            ),
            
            # SQL
            CodeTemplate(
                id="sql_select",
                language=CodeLanguage.SQL,
                pattern="выборка данных",
                template="SELECT {columns}\nFROM {table}\nWHERE {condition};",
                variables=["columns", "table", "condition"],
                complexity=CodeComplexity.SIMPLE
            ),
        ]
        
        for template in basic:
            self.templates[template.id] = template
        
        self.save()
        print(f"✅ Создано {len(basic)} базовых шаблонов кода")
    
    def generate(
        self, 
        request: str, 
        language: Optional[CodeLanguage] = None,
        context: Optional[Dict] = None
    ) -> CodeGeneration:
        """
        Сгенерировать код по запросу
        
        Args:
            request: Описание что нужно сгенерировать
            language: Язык программирования (auto-detect если None)
            context: Дополнительный контекст
            
        Returns:
            CodeGeneration с результатом
        """
        
        # Определяем язык если не указан
        if language is None:
            language = self._detect_language(request)
        
        # Ищем подходящий шаблон
        template = self._find_best_template(request, language)
        
        if template:
            # Генерируем по шаблону
            code = self._generate_from_template(template, request, context)
            template_id = template.id
        else:
            # Генерируем "с нуля" (упрощённо - просто комментарий)
            code = self._generate_fallback(request, language)
            template_id = None
        
        # Создаём запись генерации
        generation = CodeGeneration(
            id=f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            request=request,
            generated_code=code,
            language=language,
            template_used=template_id
        )
        
        self.history.append(generation)
        self.save()
        
        return generation
    
    def _detect_language(self, request: str) -> CodeLanguage:
        """Определить язык по запросу"""
        request_lower = request.lower()
        
        keywords = {
            CodeLanguage.PYTHON: ["python", "питон", "функция", "класс", "def", "import"],
            CodeLanguage.JAVASCRIPT: ["javascript", "js", "function", "const", "let", "react"],
            CodeLanguage.HTML: ["html", "страница", "page", "веб"],
            CodeLanguage.CSS: ["css", "стили", "style"],
            CodeLanguage.SQL: ["sql", "база данных", "select", "таблица"],
            CodeLanguage.BASH: ["bash", "скрипт", "shell"],
        }
        
        scores = {lang: 0 for lang in CodeLanguage}
        
        for lang, kws in keywords.items():
            for kw in kws:
                if kw in request_lower:
                    scores[lang] += 1
        
        # Возвращаем язык с максимальным счётом
        best_lang = max(scores.items(), key=lambda x: x[1])
        
        # Если ничего не нашли - по умолчанию Python
        return best_lang[0] if best_lang[1] > 0 else CodeLanguage.PYTHON
    
    def _find_best_template(
        self, 
        request: str, 
        language: CodeLanguage
    ) -> Optional[CodeTemplate]:
        """Найти лучший шаблон для запроса"""
        
        request_lower = request.lower()
        best_match = None
        best_score = 0
        
        for template in self.templates.values():
            if template.language != language:
                continue
            
            # Считаем совпадения паттерна
            pattern_words = template.pattern.lower().split()
            score = sum(1 for word in pattern_words if word in request_lower)
            
            # Бонус за успешность шаблона
            if template.success_count > 0:
                score += template.success_count / 10
            
            if score > best_score:
                best_score = score
                best_match = template
        
        return best_match if best_score > 0 else None
    
    def _generate_from_template(
        self,
        template: CodeTemplate,
        request: str,
        context: Optional[Dict]
    ) -> str:
        """Сгенерировать код из шаблона"""
        
        # Извлекаем значения переменных из запроса (упрощённо)
        values = self._extract_variables(request, template.variables, context)
        
        # Заполняем шаблон
        code = template.template
        for var, value in values.items():
            code = code.replace(f"{{{var}}}", value)
        
        return code
    
    def _extract_variables(
        self,
        request: str,
        variables: List[str],
        context: Optional[Dict]
    ) -> Dict[str, str]:
        """Извлечь значения переменных из запроса"""
        
        values = {}
        
        # Упрощённая логика - ищем ключевые слова
        request_lower = request.lower()
        
        # Общие паттерны
        if "function_name" in variables or "name" in variables:
            # Ищем имя после "создай функцию", "функция" и т.д.
            import re
            match = re.search(r'(?:функци[юя]|function)\s+(\w+)', request_lower)
            name = match.group(1) if match else "my_function"
            values["function_name"] = name
            values["name"] = name
        
        if "class_name" in variables:
            import re
            match = re.search(r'(?:класс|class)\s+(\w+)', request_lower)
            values["class_name"] = match.group(1) if match else "MyClass"
        
        # Дефолтные значения для остальных
        defaults = {
            "parameters": "arg1, arg2",
            "description": request,
            "body": "    # TODO: Реализовать логику\n    pass",
            "return_value": "None",
            "init_params": "name",
            "init_body": "    self.name = name",
            "method_name": "process",
            "method_params": "",
            "method_description": "Обработка",
            "method_body": "    pass",
            "title": "Моя страница",
            "content": "<h1>Заголовок</h1>",
            "columns": "*",
            "table": "users",
            "condition": "id = 1",
        }
        
        for var in variables:
            if var not in values:
                values[var] = defaults.get(var, "TODO")
        
        # Контекст может переопределить
        if context:
            values.update(context)
        
        return values
    
    def _generate_fallback(self, request: str, language: CodeLanguage) -> str:
        """Генерация когда нет подходящего шаблона"""
        
        comments = {
            CodeLanguage.PYTHON: f"# {request}\n# TODO: Реализовать\npass",
            CodeLanguage.JAVASCRIPT: f"// {request}\n// TODO: Implement",
            CodeLanguage.HTML: f"<!-- {request} -->\n<div>TODO</div>",
            CodeLanguage.CSS: f"/* {request} */\n/* TODO: Add styles */",
            CodeLanguage.SQL: f"-- {request}\n-- TODO: Write query",
            CodeLanguage.BASH: f"# {request}\n# TODO: Implement",
        }
        
        return comments.get(language, f"# {request}")
    
    def provide_feedback(
        self,
        generation_id: str,
        rating: int,
        corrections: Optional[List[str]] = None,
        final_code: Optional[str] = None
    ):
        """
        Дать обратную связь на генерацию
        
        Args:
            generation_id: ID генерации
            rating: Оценка 1-5
            corrections: Что было исправлено
            final_code: Финальная версия кода
        """
        
        for gen in self.history:
            if gen.id == generation_id:
                gen.user_rating = rating
                if corrections:
                    gen.corrections.extend(corrections)
                if final_code:
                    gen.final_code = final_code
                
                # Обновляем статистику шаблона
                if gen.template_used:
                    template = self.templates.get(gen.template_used)
                    if template:
                        if rating >= 4:
                            template.success_count += 1
                        else:
                            template.failure_count += 1
                
                self.save()
                break
    
    def learn_from_correction(self, generation_id: str):
        """
        Создать новый шаблон из успешной коррекции
        """
        
        for gen in self.history:
            if gen.id == generation_id and gen.final_code and gen.user_rating >= 4:
                # Создаём новый шаблон
                new_template = CodeTemplate(
                    id=f"learned_{generation_id}",
                    language=gen.language,
                    pattern=gen.request.lower()[:50],  # Первые 50 символов
                    template=gen.final_code,
                    variables=self._extract_template_vars(gen.final_code),
                    complexity=self._estimate_complexity(gen.final_code),
                    success_count=1
                )
                
                self.templates[new_template.id] = new_template
                self.save()
                
                print(f"✅ Создан новый шаблон из генерации {generation_id}")
                break
    
    def _extract_template_vars(self, code: str) -> List[str]:
        """Извлечь переменные для шаблона (упрощённо)"""
        # TODO: Более умное извлечение
        return ["var1", "var2"]
    
    def _estimate_complexity(self, code: str) -> CodeComplexity:
        """Оценить сложность кода"""
        lines = code.count('\n') + 1
        
        if lines <= 10:
            return CodeComplexity.SIMPLE
        elif lines <= 50:
            return CodeComplexity.MEDIUM
        else:
            return CodeComplexity.COMPLEX
    
    def save(self):
        """Сохранить шаблоны и историю"""
        
        # Шаблоны
        templates_data = {
            tid: {
                **asdict(t),
                "language": t.language.value,
                "complexity": t.complexity.value
            }
            for tid, t in self.templates.items()
        }
        
        with open(self.templates_file, 'w', encoding='utf-8') as f:
            json.dump(templates_data, f, indent=2, ensure_ascii=False)
        
        # История
        history_data = []
        for gen in self.history:
            data = asdict(gen)
            data["language"] = gen.language.value
            data["timestamp"] = gen.timestamp.isoformat()
            history_data.append(data)
        
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)
    
    def load(self):
        """Загрузить шаблоны и историю"""
        
        # Шаблоны
        if os.path.exists(self.templates_file):
            try:
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for tid, tdata in data.items():
                    tdata["language"] = CodeLanguage(tdata["language"])
                    tdata["complexity"] = CodeComplexity(tdata["complexity"])
                    self.templates[tid] = CodeTemplate(**tdata)
                
                print(f"✅ Загружено {len(self.templates)} шаблонов кода")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки шаблонов: {e}")
        
        # История
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for gdata in data:
                    gdata["language"] = CodeLanguage(gdata["language"])
                    gdata["timestamp"] = datetime.fromisoformat(gdata["timestamp"])
                    self.history.append(CodeGeneration(**gdata))
                
                print(f"✅ Загружена история: {len(self.history)} генераций")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки истории: {e}")


# Демонстрация
if __name__ == "__main__":
    print("=" * 60)
    print("💻 NEIRA CODE GENERATOR - DEMO")
    print("=" * 60)
    
    generator = NeiraCodeGenerator()
    
    # Тест 1: Простая функция
    print("\n📝 Тест 1: Создай функцию сортировки")
    result = generator.generate("Создай функцию sort_numbers на Python")
    print(f"\n```python\n{result.generated_code}\n```")
    
    # Тест 2: Класс
    print("\n📝 Тест 2: Создай класс Person")
    result = generator.generate("Создай класс Person на Python")
    print(f"\n```python\n{result.generated_code}\n```")
    
    # Тест 3: HTML
    print("\n📝 Тест 3: Создай HTML страницу")
    result = generator.generate("Создай HTML страницу с заголовком 'Привет'")
    print(f"\n```html\n{result.generated_code}\n```")
    
    print("\n" + "=" * 60)
    print("✅ DEMO ЗАВЕРШЕНА")
    print("=" * 60)
