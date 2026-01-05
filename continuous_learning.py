"""
Neira Continuous Learning System v0.6
Система непрерывного самообучения — анализирует ошибки и автоматически улучшает код.

ВОЗМОЖНОСТИ:
1. Анализ неудачных попыток из Experience
2. Генерация патчей для исправления проблем
3. Валидация изменений (backup + rollback)
4. Автоматическое применение улучшений
5. Логирование эволюции
"""

import os
import json
import shutil
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import requests

# Импорты
from cells import (
    DEFAULT_MAX_RESPONSE_TOKENS,
    OLLAMA_NUM_CTX,
    OLLAMA_URL,
    MODEL_REASON,
    TIMEOUT,
    _MODEL_LAYERS,
    _merge_system_prompt,
)
from experience import ExperienceSystem, ExperienceEntry

# Конфигурация
EVOLUTION_LOG_FILE = "neira_evolution.json"
CODE_BACKUP_DIR = "backups/code_evolution"
MODIFIABLE_FILES = ["cells.py", "main.py", "code_cell.py", "web_cell.py", "experience.py"]
MIN_FAILURES_TO_TRIGGER = 3  # Минимум неудач для автоисправления
MIN_SCORE_THRESHOLD = 6      # Оценка ниже которой считается провалом


def _build_ollama_options(temperature: float, max_tokens: int) -> Dict[str, Any]:
    options: Dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
    if OLLAMA_NUM_CTX:
        options["num_ctx"] = OLLAMA_NUM_CTX
    if _MODEL_LAYERS is not None:
        adapter = _MODEL_LAYERS.get_active_adapter(MODEL_REASON)
        if adapter:
            options["adapter"] = adapter
    return options


def _merge_layer_system_prompt(system_prompt: str) -> str:
    if _MODEL_LAYERS is None:
        return system_prompt
    layer_prompt = _MODEL_LAYERS.get_active_prompt(MODEL_REASON)
    return _merge_system_prompt(system_prompt, layer_prompt)


@dataclass
class EvolutionEntry:
    """Запись об эволюции кода"""
    timestamp: str
    file_modified: str
    problem_description: str
    patch_description: str
    success: bool
    before_hash: str
    after_hash: str
    test_result: Optional[str] = None
    rollback: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "EvolutionEntry":
        return EvolutionEntry(**d)


class ContinuousLearningSystem:
    """Система непрерывного самообучения"""

    def __init__(self, experience: ExperienceSystem):
        self.experience = experience
        self.evolution_history: List[EvolutionEntry] = []
        self.enabled = True
        os.makedirs(CODE_BACKUP_DIR, exist_ok=True)
        self.load_evolution_history()

    def load_evolution_history(self):
        """Загрузить историю эволюции"""
        if os.path.exists(EVOLUTION_LOG_FILE):
            try:
                with open(EVOLUTION_LOG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.evolution_history = [EvolutionEntry.from_dict(e) for e in data]
                print(f"🧬 Загружено записей эволюции: {len(self.evolution_history)}")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки истории эволюции: {e}")

    def save_evolution_history(self):
        """Сохранить историю эволюции"""
        try:
            with open(EVOLUTION_LOG_FILE, "w", encoding="utf-8") as f:
                json.dump([e.to_dict() for e in self.evolution_history], f,
                         ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")

    def analyze_failures(self) -> Dict[str, List[ExperienceEntry]]:
        """Анализ провалов по типам задач"""
        failures_by_type = {}

        for exp in self.experience.experiences:
            # Провал если score < threshold или verdict != ПРИНЯТ
            if exp.score < MIN_SCORE_THRESHOLD or exp.verdict != "ПРИНЯТ":
                if exp.task_type not in failures_by_type:
                    failures_by_type[exp.task_type] = []
                failures_by_type[exp.task_type].append(exp)

        return failures_by_type

    def should_trigger_self_improvement(self) -> bool:
        """Определить нужно ли запустить самоулучшение"""
        failures = self.analyze_failures()

        for task_type, fails in failures.items():
            if len(fails) >= MIN_FAILURES_TO_TRIGGER:
                print(f"🔴 Обнаружено {len(fails)} провалов в '{task_type}' — запускаю самоулучшение")
                return True

        return False

    def generate_improvement_patch(self, task_type: str,
                                   failures: List[ExperienceEntry]) -> Optional[Dict]:
        """Генерировать патч для улучшения на основе провалов"""

        # Анализируем провалы
        problems_summary = "\n".join([
            f"- Запрос: {f.user_input[:100]}\n  Проблема: {f.problems}\n  Оценка: {f.score}/10"
            for f in failures[-5:]  # Последние 5 провалов
        ])

        prompt = f"""Ты — Neira, анализирующая собственные ошибки.

ЗАДАЧА: Проанализировать провалы и предложить улучшение кода.

ТИП ЗАДАЧИ: {task_type}

ПРОВАЛЫ:
{problems_summary}

ДОСТУПНЫЕ ФАЙЛЫ ДЛЯ МОДИФИКАЦИИ:
{', '.join(MODIFIABLE_FILES)}

ТРЕБОВАНИЯ:
1. Определи корневую причину провалов (что в коде не так)
2. Выбери ОДИН файл для модификации
3. Предложи КОНКРЕТНОЕ изменение (какую функцию/класс/промпт изменить)
4. Опиши изменение кратко и точно

ФОРМАТ ОТВЕТА (JSON):
{{
  "file": "cells.py",
  "target": "AnalyzerCell.system_prompt" или "ExecutorCell.process",
  "problem": "краткое описание проблемы",
  "solution": "краткое описание решения",
  "modification_type": "prompt" или "code"
}}

ТОЛЬКО JSON:"""

        try:
            system_prompt = _merge_layer_system_prompt("Ты - аналитик. Выводи только JSON без пояснений.")
            options = _build_ollama_options(0.3, min(DEFAULT_MAX_RESPONSE_TOKENS, 1024))
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_REASON,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": options
                },
                timeout=TIMEOUT
            )

            result = response.json().get("response", "")

            # Парсим JSON
            start = result.find("{")
            end = result.rfind("}") + 1
            if start >= 0 and end > start:
                patch_data = json.loads(result[start:end])
                return patch_data

        except Exception as e:
            print(f"⚠️ Ошибка генерации патча: {e}")

        return None

    def backup_file(self, file_path: str) -> str:
        """Создать бэкап файла"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(CODE_BACKUP_DIR, f"{timestamp}_{os.path.basename(file_path)}")
        shutil.copy2(file_path, backup_path)
        print(f"📦 Бэкап создан: {backup_path}")
        return backup_path

    def restore_file(self, backup_path: str, original_path: str):
        """Восстановить файл из бэкапа"""
        shutil.copy2(backup_path, original_path)
        print(f"🔄 Файл восстановлен из бэкапа: {original_path}")

    def file_hash(self, file_path: str) -> str:
        """Получить хеш файла для отслеживания изменений"""
        import hashlib
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def apply_prompt_modification(self, file_path: str, target: str,
                                   new_prompt: str) -> bool:
        """Применить модификацию system_prompt"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Ищем целевой промпт
            # Формат: system_prompt = """..."""
            import re

            # Простой подход: найти класс и его system_prompt
            class_name = target.split(".")[0] if "." in target else None

            if class_name:
                # Ищем блок class ClassName:
                pattern = rf'(class {class_name}.*?system_prompt = """)(.*?)(""")'
                match = re.search(pattern, content, re.DOTALL)

                if match:
                    # Заменяем содержимое промпта
                    modified = content[:match.start(2)] + new_prompt + content[match.end(2):]

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(modified)

                    print(f"✅ Промпт модифицирован: {target}")
                    return True

            print(f"⚠️ Не удалось найти целевой промпт: {target}")
            return False

        except Exception as e:
            print(f"❌ Ошибка модификации: {e}")
            return False

    def generate_improved_prompt(self, current_prompt: str,
                                 problems: str, solution: str) -> str:
        """Генерировать улучшенный промпт"""

        prompt = f"""Ты — Neira, улучшающая собственные промпты.

ТЕКУЩИЙ ПРОМПТ:
{current_prompt}

ПРОБЛЕМА:
{problems}

РЕШЕНИЕ:
{solution}

ЗАДАЧА: Улучши промпт, добавив инструкции которые решают проблему.
Сохрани общую структуру и стиль. Будь конкретной.

УЛУЧШЕННЫЙ ПРОМПТ:"""

        try:
            system_prompt = _merge_layer_system_prompt("Ты - редактор промптов. Выводи только текст промпта.")
            options = _build_ollama_options(0.4, min(DEFAULT_MAX_RESPONSE_TOKENS, 2048))
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_REASON,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": options
                },
                timeout=TIMEOUT
            )

            return response.json().get("response", current_prompt)

        except Exception as e:
            print(f"⚠️ Ошибка генерации промпта: {e}")
            return current_prompt

    def validate_changes(self, file_path: str) -> Tuple[bool, str]:
        """Валидация изменений (базовая проверка синтаксиса)"""
        try:
            # Проверка синтаксиса Python
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()

            compile(code, file_path, "exec")
            return True, "Синтаксис корректен"

        except SyntaxError as e:
            return False, f"Синтаксическая ошибка: {e}"
        except Exception as e:
            return False, f"Ошибка валидации: {e}"

    def attempt_self_improvement(self) -> Optional[EvolutionEntry]:
        """Попытка самоулучшения"""

        if not self.enabled:
            print("⏸️ Continuous learning отключен")
            return None

        print("\n" + "="*60)
        print("🧬 ЗАПУСК САМОУЛУЧШЕНИЯ")
        print("="*60)

        # Анализ провалов
        failures = self.analyze_failures()

        if not failures:
            print("✅ Провалов не обнаружено")
            return None

        # Выбираем тип задачи с наибольшим количеством провалов
        worst_task_type = max(failures.items(), key=lambda x: len(x[1]))[0]
        worst_failures = failures[worst_task_type]

        print(f"🎯 Целевой тип: {worst_task_type} ({len(worst_failures)} провалов)")

        # Генерируем патч
        patch = self.generate_improvement_patch(worst_task_type, worst_failures)

        if not patch:
            print("❌ Не удалось сгенерировать патч")
            return None

        print(f"\n📋 ПАТЧ:")
        print(f"  Файл: {patch.get('file')}")
        print(f"  Цель: {patch.get('target')}")
        print(f"  Проблема: {patch.get('problem')}")
        print(f"  Решение: {patch.get('solution')}")

        file_path = patch.get("file")

        if file_path not in MODIFIABLE_FILES:
            print(f"⚠️ Файл {file_path} не разрешён для модификации")
            return None

        # Бэкап
        before_hash = self.file_hash(file_path)
        backup_path = self.backup_file(file_path)

        # Применяем изменение
        success = False

        if patch.get("modification_type") == "prompt":
            # Читаем текущий промпт
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Находим текущий промпт (упрощенно)
            import re
            target_class = patch.get('target', '').split('.')[0]
            pattern = rf'(class {target_class}.*?system_prompt = """)(.*?)(""")'
            match = re.search(pattern, content, re.DOTALL)

            if match:
                current_prompt = match.group(2)

                # Генерируем улучшенный промпт
                new_prompt = self.generate_improved_prompt(
                    current_prompt,
                    patch.get('problem', ''),
                    patch.get('solution', '')
                )

                # Применяем
                success = self.apply_prompt_modification(
                    file_path,
                    patch.get('target'),
                    new_prompt
                )

        # Валидация
        valid, validation_msg = self.validate_changes(file_path)

        if not valid:
            print(f"❌ Валидация провалена: {validation_msg}")
            self.restore_file(backup_path, file_path)
            success = False
            rollback = True
        else:
            print(f"✅ Валидация пройдена: {validation_msg}")
            rollback = False

        after_hash = self.file_hash(file_path)

        # Логируем
        entry = EvolutionEntry(
            timestamp=datetime.now().isoformat(),
            file_modified=file_path,
            problem_description=patch.get('problem', ''),
            patch_description=patch.get('solution', ''),
            success=success and valid,
            before_hash=before_hash,
            after_hash=after_hash,
            test_result=validation_msg,
            rollback=rollback
        )

        self.evolution_history.append(entry)
        self.save_evolution_history()

        if success and valid:
            print(f"\n🎉 САМОУЛУЧШЕНИЕ ПРИМЕНЕНО!")
            print(f"   Модифицирован: {file_path}")
            print(f"   Бэкап доступен: {backup_path}")
            print(f"   Перезапусти Neira чтобы изменения вступили в силу")
        else:
            print(f"\n❌ Самоулучшение провалено, изменения откачены")

        return entry

    def get_evolution_stats(self) -> Dict:
        """Статистика эволюции"""
        if not self.evolution_history:
            return {"total": 0}

        stats = {
            "total": len(self.evolution_history),
            "successful": sum(1 for e in self.evolution_history if e.success),
            "failed": sum(1 for e in self.evolution_history if not e.success),
            "rollbacks": sum(1 for e in self.evolution_history if e.rollback),
            "files_modified": {}
        }

        for e in self.evolution_history:
            stats["files_modified"][e.file_modified] = \
                stats["files_modified"].get(e.file_modified, 0) + 1

        return stats

    def show_evolution_log(self, last_n: int = 10) -> str:
        """Показать последние записи эволюции"""
        if not self.evolution_history:
            return "🧬 История эволюции пуста"

        output = f"🧬 ИСТОРИЯ ЭВОЛЮЦИИ (последние {last_n}):\n\n"

        for entry in self.evolution_history[-last_n:]:
            status = "✅" if entry.success else "❌"
            rollback = " [ОТКАЧЕНО]" if entry.rollback else ""

            output += f"{status} {entry.timestamp[:19]}{rollback}\n"
            output += f"   Файл: {entry.file_modified}\n"
            output += f"   Проблема: {entry.problem_description}\n"
            output += f"   Решение: {entry.patch_description}\n"
            output += f"   Результат: {entry.test_result}\n\n"

        stats = self.get_evolution_stats()
        output += f"📊 СТАТИСТИКА:\n"
        output += f"   Всего попыток: {stats['total']}\n"
        output += f"   Успешных: {stats['successful']}\n"
        output += f"   Провалов: {stats['failed']}\n"
        output += f"   Откатов: {stats['rollbacks']}\n"

        return output

    def show_code_diff(self, entry_index: int) -> str:
        """Показать diff для записи эволюции"""
        import difflib

        if entry_index < 0 or entry_index >= len(self.evolution_history):
            return f"❌ Запись не найдена: индекс {entry_index} (всего записей: {len(self.evolution_history)})"

        entry = self.evolution_history[entry_index]

        # Формируем путь к бэкапу
        backup_files = []
        for filename in os.listdir(CODE_BACKUP_DIR):
            if entry.before_hash[:8] in filename or os.path.basename(entry.file_modified) in filename:
                backup_files.append(os.path.join(CODE_BACKUP_DIR, filename))

        # Сортируем по времени и берём ближайший к entry.timestamp
        if backup_files:
            backup_files.sort(key=lambda x: os.path.getmtime(x))
            # Берём бэкап ближайший по времени к записи
            entry_time = datetime.fromisoformat(entry.timestamp).timestamp()
            backup_file = min(backup_files, key=lambda x: abs(os.path.getmtime(x) - entry_time))
        else:
            return f"⚠️ Бэкап не найден для записи {entry_index}"

        # Читаем файлы
        try:
            with open(backup_file, "r", encoding="utf-8") as f:
                before_lines = f.readlines()
        except Exception as e:
            return f"❌ Ошибка чтения бэкапа: {e}"

        # Читаем текущий файл или используем бэкап с after_hash если был откат
        current_file = entry.file_modified
        try:
            with open(current_file, "r", encoding="utf-8") as f:
                after_lines = f.readlines()
        except Exception as e:
            return f"❌ Ошибка чтения файла: {e}"

        # Генерируем diff
        diff = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"{os.path.basename(entry.file_modified)} (до)",
            tofile=f"{os.path.basename(entry.file_modified)} (после)",
            lineterm=""
        )

        diff_text = "\n".join(diff)

        if not diff_text.strip():
            return f"ℹ️ Нет различий для записи {entry_index}"

        # Форматируем вывод
        output = f"📝 CODE DIFF: Запись #{entry_index}\n\n"
        output += f"Время: {entry.timestamp[:19]}\n"
        output += f"Файл: {entry.file_modified}\n"
        output += f"Проблема: {entry.problem_description}\n"
        output += f"Решение: {entry.patch_description}\n"
        output += f"Статус: {'✅ Успешно' if entry.success else '❌ Провал'}"
        output += f"{' [ОТКАЧЕНО]' if entry.rollback else ''}\n"
        output += f"\n{'='*60}\n"
        output += f"DIFF:\n"
        output += f"{'='*60}\n\n"
        output += diff_text
        output += f"\n\n{'='*60}\n"

        return output

    def list_evolution_entries(self) -> str:
        """Показать список записей эволюции для выбора"""
        if not self.evolution_history:
            return "🧬 История эволюции пуста"

        output = "🧬 ЗАПИСИ ЭВОЛЮЦИИ:\n\n"

        for i, entry in enumerate(self.evolution_history):
            status = "✅" if entry.success else "❌"
            rollback = " [ОТКАЧЕНО]" if entry.rollback else ""

            output += f"[{i}] {status} {entry.timestamp[:19]}{rollback}\n"
            output += f"    {entry.file_modified}: {entry.problem_description[:60]}...\n\n"

        output += f"\n💡 Используй /evolution diff cls <индекс> чтобы увидеть изменения\n"

        return output


# === ТЕСТ ===
if __name__ == "__main__":
    print("=" * 60)
    print("Тест ContinuousLearningSystem")
    print("=" * 60)

    exp = ExperienceSystem()
    cls = ContinuousLearningSystem(exp)

    print(f"\nПровалы по типам:")
    failures = cls.analyze_failures()
    for task_type, fails in failures.items():
        print(f"  {task_type}: {len(fails)} провалов")

    print(f"\n{'Нужно' if cls.should_trigger_self_improvement() else 'Не нужно'} запускать самоулучшение")

    print(f"\n{cls.show_evolution_log()}")
