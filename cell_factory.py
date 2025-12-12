"""
Neira Cell Factory v0.7
Фабрика автоматического создания специализированных клеток.

ВОЗМОЖНОСТИ:
1. Обнаружение повторяющихся паттернов задач
2. Генерация кода новой клетки по шаблону
3. ✨ НОВОЕ: Проверка безопасности через OrganGuardian
4. Автоматическое тестирование клетки
5. Сохранение в generated/ для динамической загрузки
6. Версионирование и управление жизненным циклом
"""

import os
import json
import subprocess
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import requests

from cells import OLLAMA_URL, MODEL_CODE, MODEL_REASON, TIMEOUT
from experience import ExperienceSystem
from organ_guardian import OrganGuardian, ThreatLevel  # ✨ НОВОЕ


# Конфигурация
GENERATED_CELLS_DIR = "generated"
CELL_REGISTRY_FILE = "neira_cell_registry.json"
MIN_PATTERN_OCCURRENCES = 3  # Минимум повторений для генерации клетки


@dataclass
class CellSpec:
    """Спецификация новой клетки"""
    cell_name: str
    description: str
    purpose: str
    system_prompt: str
    methods: List[str]
    task_pattern: str  # Паттерн задач для которых создана


@dataclass
class GeneratedCell:
    """Метаданные сгенерированной клетки"""
    cell_id: str
    cell_name: str
    file_path: str
    created_at: str
    task_pattern: str
    description: str

    # Метрики
    uses_count: int = 0
    avg_score: float = 0.0
    active: bool = False

    # Версионирование
    version: int = 1
    parent_cell: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "GeneratedCell":
        return GeneratedCell(**d)


class CellFactory:
    """Фабрика клеток с проверкой безопасности"""

    def __init__(self, experience: ExperienceSystem):
        self.experience = experience
        self.registry: List[GeneratedCell] = []
        os.makedirs(GENERATED_CELLS_DIR, exist_ok=True)
        self.load_registry()
        
        # ✨ НОВОЕ: Система защиты органов
        self.guardian = OrganGuardian()

        # Шаблон клетки
        self.cell_template = '''"""
{description}
Автоматически сгенерированная клетка v{version}
Создана: {created_at}
"""

from typing import Optional
from cells import Cell, CellResult, MemoryCell


class {class_name}(Cell):
    """
    {purpose}
    """

    name = "{cell_name}"
    system_prompt = """{system_prompt}"""

    def __init__(self, memory: Optional[MemoryCell] = None):
        super().__init__(memory)

    def process(self, input_data: str) -> CellResult:
        """Основной метод обработки"""
        result = self.call_llm(input_data)

        return CellResult(
            content=result,
            confidence=0.7,
            cell_name=self.name,
            metadata={{"generated": True, "version": {version}}}
        )


# Экспорт для динамического импорта
__all__ = ["{class_name}"]
'''

    def load_registry(self):
        """Загрузить реестр сгенерированных клеток"""
        if os.path.exists(CELL_REGISTRY_FILE):
            try:
                with open(CELL_REGISTRY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.registry = [GeneratedCell.from_dict(c) for c in data]
                print(f"🏭 Загружено сгенерированных клеток: {len(self.registry)}")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки реестра: {e}")

    def save_registry(self):
        """Сохранить реестр"""
        try:
            with open(CELL_REGISTRY_FILE, "w", encoding="utf-8") as f:
                json.dump([c.to_dict() for c in self.registry], f,
                         ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения реестра: {e}")

    def detect_task_patterns(self) -> Dict[str, List]:
        """Обнаружить повторяющиеся паттерны задач"""

        # Группируем задачи по ключевым словам
        patterns = {}

        for exp in self.experience.experiences:
            # Извлекаем ключевые слова из запроса
            words = exp.user_input.lower().split()

            # Ищем паттерны (упрощенно: первые 2-3 слова)
            if len(words) >= 2:
                pattern = " ".join(words[:2])

                if pattern not in patterns:
                    patterns[pattern] = []

                patterns[pattern].append(exp)

        # Фильтруем паттерны с достаточным количеством повторений
        significant_patterns = {
            pattern: tasks
            for pattern, tasks in patterns.items()
            if len(tasks) >= MIN_PATTERN_OCCURRENCES
        }

        return significant_patterns

    def should_create_cell(self) -> Optional[Tuple[str, List]]:
        """Определить нужно ли создавать новую клетку"""

        patterns = self.detect_task_patterns()

        if not patterns:
            return None

        # Проверяем есть ли паттерн для которого нет специализированной клетки
        for pattern, tasks in patterns.items():
            # Проверяем нет ли уже клетки для этого паттерна
            exists = any(c.task_pattern == pattern for c in self.registry)

            if not exists:
                print(f"🎯 Обнаружен новый паттерн: '{pattern}' ({len(tasks)} задач)")
                return pattern, tasks

        return None

    def generate_cell_spec(self, pattern: str, tasks: List) -> Optional[CellSpec]:
        """Генерировать спецификацию клетки"""

        # Анализируем задачи
        task_examples = "\n".join([
            f"- {t.get('description', str(t))[:100]}" if isinstance(t, dict) else f"- {str(t)[:100]}"
            for t in tasks[:5]
        ])

        prompt = f"""Ты — Neira, создающая новую специализированную клетку.

ПАТТЕРН ЗАДАЧ: {pattern}

ПРИМЕРЫ ЗАДАЧ:
{task_examples}

ЗАДАЧА: Спроектировать новую клетку для обработки этого типа задач.

ТРЕБОВАНИЯ:
1. cell_name: короткое имя (snake_case)
2. description: что делает клетка (1 предложение)
3. purpose: зачем нужна (2-3 предложения)
4. system_prompt: инструкции для LLM (детальный промпт)

ФОРМАТ (JSON):
{{
  "cell_name": "pattern_handler",
  "description": "Описание",
  "purpose": "Зачем нужна клетка",
  "system_prompt": "Ты — специалист по X. Делай Y."
}}

ТОЛЬКО JSON:"""

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_REASON,
                    "prompt": prompt,
                    "system": "Ты — архитектор клеток. Выводи только JSON.",
                    "stream": False,
                    "options": {"temperature": 0.4, "num_predict": 2048}
                },
                timeout=TIMEOUT
            )

            result = response.json().get("response", "")

            # Парсим JSON
            start = result.find("{")
            end = result.rfind("}") + 1
            if start >= 0 and end > start:
                spec_data = json.loads(result[start:end])

                return CellSpec(
                    cell_name=spec_data["cell_name"],
                    description=spec_data["description"],
                    purpose=spec_data["purpose"],
                    system_prompt=spec_data["system_prompt"],
                    methods=["process"],  # Базовый набор
                    task_pattern=pattern
                )

        except Exception as e:
            print(f"⚠️ Ошибка генерации спецификации: {e}")

        return None

    def create_cell_file(self, spec: CellSpec) -> str:
        """Создать файл клетки"""

        class_name = "".join(word.capitalize() for word in spec.cell_name.split("_")) + "Cell"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{spec.cell_name}_{timestamp}.py"
        filepath = os.path.join(GENERATED_CELLS_DIR, filename)

        code = self.cell_template.format(
            description=spec.description,
            version=1,
            created_at=datetime.now().isoformat(),
            class_name=class_name,
            cell_name=spec.cell_name,
            purpose=spec.purpose,
            system_prompt=spec.system_prompt
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        print(f"📝 Создан файл: {filepath}")
        return filepath

    def validate_cell(self, filepath: str) -> Tuple[bool, str]:
        """Валидация клетки (синтаксис + базовая проверка)"""

        try:
            # Проверка синтаксиса
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()

            compile(code, filepath, "exec")

            # Пробуем импортировать
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_cell", filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            return True, "Валидация пройдена"

        except SyntaxError as e:
            return False, f"Синтаксическая ошибка: {e}"
        except Exception as e:
            return False, f"Ошибка импорта: {e}"

    def create_cell(self, pattern: str, tasks: List, author_id: int = 0) -> Dict[str, Any]:
        """
        Создать новую клетку с проверкой безопасности
        
        Returns:
            {
                "success": bool,
                "cell": GeneratedCell | None,
                "threat_level": str,
                "report": str,
                "quarantined": bool,
                "organ_id": str | None
            }
        """

        print("\n" + "="*60)
        print("🏭 СОЗДАНИЕ НОВОЙ КЛЕТКИ")
        print("="*60)

        # Генерируем спецификацию
        spec = self.generate_cell_spec(pattern, tasks)

        if not spec:
            print("❌ Не удалось создать спецификацию")
            return {
                "success": False,
                "error": "Не удалось создать спецификацию органа",
                "threat_level": "unknown"
            }

        print(f"\n📋 СПЕЦИФИКАЦИЯ:")
        print(f"   Имя: {spec.cell_name}")
        print(f"   Описание: {spec.description}")
        print(f"   Паттерн: {spec.task_pattern}")

        # ✨ НОВОЕ: Генерируем код
        code = self.cell_template.format(
            description=spec.description,
            version=1,
            created_at=datetime.now().isoformat(),
            class_name=spec.cell_name.title().replace("_", ""),
            cell_name=spec.cell_name,
            purpose=spec.purpose,
            system_prompt=spec.system_prompt
        )
        
        # ✨ НОВОЕ: ПРОВЕРКА БЕЗОПАСНОСТИ
        print(f"\n🔍 ПРОВЕРКА БЕЗОПАСНОСТИ...")
        scan_result = self.guardian.scan_organ_code(code, spec.cell_name)
        safety_report = self.guardian.generate_safety_report(scan_result, spec.cell_name)
        
        print(safety_report)
        
        # Обработка по уровню угрозы
        if scan_result.threat_level == ThreatLevel.CRITICAL:
            print("\n🚨 ОРГАН ЗАБЛОКИРОВАН - критическая угроза!")
            return {
                "success": False,
                "threat_level": "critical",
                "report": safety_report,
                "error": "Орган содержит критически опасный код и был заблокирован"
            }
        
        elif scan_result.threat_level == ThreatLevel.DANGEROUS:
            print("\n⚠️ ОРГАН ТРЕБУЕТ ОДОБРЕНИЯ АДМИНИСТРАТОРА")
            quarantined_organ = self.guardian.quarantine_organ(
                name=spec.cell_name,
                description=spec.description,
                code=code,
                author_id=author_id,
                scan_result=scan_result
            )
            return {
                "success": False,
                "threat_level": "dangerous",
                "report": safety_report,
                "quarantined": True,
                "organ_id": quarantined_organ.organ_id,
                "message": "Орган помещён в карантин. Ожидайте одобрения администратора."
            }
        
        elif scan_result.threat_level == ThreatLevel.SUSPICIOUS:
            print("\n🔍 ОРГАН ПОМЕЩЁН В 24-ЧАСОВОЙ КАРАНТИН")
            quarantined_organ = self.guardian.quarantine_organ(
                name=spec.cell_name,
                description=spec.description,
                code=code,
                author_id=author_id,
                scan_result=scan_result,
                quarantine_hours=24
            )
            return {
                "success": False,
                "threat_level": "suspicious",
                "report": safety_report,
                "quarantined": True,
                "organ_id": quarantined_organ.organ_id,
                "message": "Орган помещён в 24-часовой карантин для мониторинга."
            }
        
        # ✅ БЕЗОПАСЕН - создаём файл
        print(f"\n✅ ОРГАН БЕЗОПАСЕН - создаём файл")
        filepath = os.path.join(GENERATED_CELLS_DIR, f"{spec.cell_name}.py")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)

        print(f"📝 Создан файл: {filepath}")

        # Валидация
        valid, validation_msg = self.validate_cell(filepath)

        if not valid:
            print(f"❌ Валидация провалена: {validation_msg}")
            os.remove(filepath)
            return {
                "success": False,
                "threat_level": "safe",
                "error": f"Синтаксическая ошибка: {validation_msg}"
            }

        print(f"✅ Валидация пройдена")

        # Регистрируем
        cell_id = f"{spec.cell_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        generated_cell = GeneratedCell(
            cell_id=cell_id,
            cell_name=spec.cell_name,
            file_path=filepath,
            created_at=datetime.now().isoformat(),
            task_pattern=pattern,
            description=spec.description,
            active=True  # ✨ Безопасный орган активен сразу
        )

        self.registry.append(generated_cell)
        self.save_registry()

        print(f"\n🎉 КЛЕТКА СОЗДАНА: {cell_id}")
        print(f"   Файл: {filepath}")
        print(f"   Статус: Активна и готова к использованию")
        
        return {
            "success": True,
            "cell": generated_cell,
            "threat_level": "safe",
            "report": safety_report,
            "message": "✅ Орган создан и готов к использованию!"
        }

        if not valid:
            print(f"❌ Валидация провалена: {validation_msg}")
            os.remove(filepath)
            return None

        print(f"✅ Валидация пройдена")

        # Регистрируем
        cell_id = f"{spec.cell_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        generated_cell = GeneratedCell(
            cell_id=cell_id,
            cell_name=spec.cell_name,
            file_path=filepath,
            created_at=datetime.now().isoformat(),
            task_pattern=pattern,
            description=spec.description,
            active=False  # Требуется тестирование перед активацией
        )

        self.registry.append(generated_cell)
        self.save_registry()

        print(f"\n🎉 КЛЕТКА СОЗДАНА: {cell_id}")
        print(f"   Файл: {filepath}")
        print(f"   Статус: требуется тестирование")
        print(f"   Используй /load-cell {spec.cell_name} для активации")

        return generated_cell

    def auto_creation_cycle(self) -> List[GeneratedCell]:
        """Автоматический цикл создания клеток"""

        print("\n" + "="*60)
        print("🏭 АВТОМАТИЧЕСКОЕ СОЗДАНИЕ КЛЕТОК")
        print("="*60)

        created = []

        # Обнаруживаем паттерны
        patterns = self.detect_task_patterns()

        print(f"\nОбнаружено паттернов: {len(patterns)}")

        for pattern, tasks in patterns.items():
            # Проверяем нет ли уже клетки
            exists = any(c.task_pattern == pattern for c in self.registry)

            if not exists:
                print(f"\n🎯 Новый паттерн: '{pattern}' ({len(tasks)} задач)")

                cell = self.create_cell(pattern, tasks)

                if cell:
                    created.append(cell)
            else:
                print(f"\n✅ Паттерн '{pattern}': клетка уже существует")

        if not created:
            print("\n✅ Новых клеток не требуется")

        return created

    def activate_cell(self, cell_name: str):
        """Активировать клетку"""
        for cell in self.registry:
            if cell.cell_name == cell_name:
                cell.active = True
                self.save_registry()
                print(f"✅ Клетка активирована: {cell_name}")
                print(f"   Файл: {cell.file_path}")
                print(f"   Перезапусти Neira для загрузки клетки")
                return

        print(f"⚠️ Клетка не найдена: {cell_name}")

    def get_active_cells(self) -> List[GeneratedCell]:
        """Получить список активных клеток"""
        return [c for c in self.registry if c.active]

    def get_stats(self) -> Dict:
        """Статистика фабрики"""
        return {
            "total_cells": len(self.registry),
            "active_cells": len(self.get_active_cells()),
            "total_uses": sum(c.uses_count for c in self.registry),
            "patterns_covered": len(set(c.task_pattern for c in self.registry))
        }

    def show_registry(self) -> str:
        """Показать реестр клеток"""
        if not self.registry:
            return "🏭 Реестр клеток пуст"

        output = "🏭 РЕЕСТР СГЕНЕРИРОВАННЫХ КЛЕТОК:\n\n"

        for i, cell in enumerate(self.registry, 1):
            status = "🟢 ACTIVE" if cell.active else "⏸️  INACTIVE"

            output += f"{i}. {cell.cell_name} {status}\n"
            output += f"   ID: {cell.cell_id}\n"
            output += f"   Описание: {cell.description}\n"
            output += f"   Паттерн: {cell.task_pattern}\n"
            output += f"   Создана: {cell.created_at[:19]}\n"
            output += f"   Файл: {cell.file_path}\n"

            if cell.uses_count > 0:
                output += f"   Использований: {cell.uses_count}\n"
                output += f"   Средний score: {cell.avg_score:.1f}/10\n"

            output += "\n"

        stats = self.get_stats()
        output += f"📊 СТАТИСТИКА:\n"
        output += f"   Всего клеток: {stats['total_cells']}\n"
        output += f"   Активных: {stats['active_cells']}\n"
        output += f"   Паттернов покрыто: {stats['patterns_covered']}\n"

        return output


# === ТЕСТ ===
if __name__ == "__main__":
    print("=" * 60)
    print("Тест CellFactory")
    print("=" * 60)

    from experience import ExperienceSystem

    exp = ExperienceSystem()
    factory = CellFactory(exp)

    print(f"\n{factory.show_registry()}")

    # Обнаружение паттернов
    patterns = factory.detect_task_patterns()
    print(f"\nОбнаружено паттернов: {len(patterns)}")

    for pattern, tasks in list(patterns.items())[:3]:
        print(f"  '{pattern}': {len(tasks)} задач")
