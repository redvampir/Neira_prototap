"""
Neira Evolution Manager v0.6
Координатор всех систем самосовершенствования.

Объединяет:
- ContinuousLearningSystem
- PromptEvolutionSystem
- CellFactory
- DynamicCellLoader
- ABTestingFramework
- FineTuningPipeline
"""

from typing import Optional, Dict, List
from experience import ExperienceSystem
from cells import MemoryCell

# Импорты систем эволюции
try:
    from continuous_learning import ContinuousLearningSystem
    CLS_AVAILABLE = True
except ImportError as e:
    CLS_AVAILABLE = False
    print(f"⚠️ ContinuousLearningSystem недоступен: {e}")

try:
    from prompt_evolution import PromptEvolutionSystem
    PES_AVAILABLE = True
except ImportError as e:
    PES_AVAILABLE = False
    print(f"⚠️ PromptEvolutionSystem недоступен: {e}")

try:
    from cell_factory import CellFactory
    CF_AVAILABLE = True
except ImportError as e:
    CF_AVAILABLE = False
    print(f"⚠️ CellFactory недоступен: {e}")

try:
    from dynamic_cell_loader import DynamicCellLoader
    DCL_AVAILABLE = True
except ImportError as e:
    DCL_AVAILABLE = False
    print(f"⚠️ DynamicCellLoader недоступен: {e}")

try:
    from ab_testing import ABTestingFramework
    ABT_AVAILABLE = True
except ImportError as e:
    ABT_AVAILABLE = False
    print(f"⚠️ ABTestingFramework недоступен: {e}")

try:
    from finetuning_pipeline import FineTuningPipeline
    FTP_AVAILABLE = True
except ImportError as e:
    FTP_AVAILABLE = False
    print(f"⚠️ FineTuningPipeline недоступен: {e}")


class EvolutionManager:
    """Менеджер всех систем эволюции"""

    def __init__(self, experience: ExperienceSystem, memory: MemoryCell, verbose: bool = True):
        self.experience = experience
        self.memory = memory
        self.verbose = verbose

        # Инициализация систем
        self.continuous_learning = ContinuousLearningSystem(experience) if CLS_AVAILABLE else None
        self.prompt_evolution = PromptEvolutionSystem() if PES_AVAILABLE else None
        self.cell_factory = CellFactory(experience) if CF_AVAILABLE else None
        self.cell_loader = DynamicCellLoader(memory) if DCL_AVAILABLE else None
        self.ab_testing = ABTestingFramework() if ABT_AVAILABLE else None
        self.finetuning = FineTuningPipeline(experience) if FTP_AVAILABLE else None

        if verbose:
            self._print_status()

    def _print_status(self):
        """Вывести статус систем"""
        print("\n" + "="*60)
        print("🧬 СИСТЕМЫ ЭВОЛЮЦИИ")
        print("="*60)
        print(f"  Continuous Learning:  {'✅' if CLS_AVAILABLE else '❌'}")
        print(f"  Prompt Evolution:     {'✅' if PES_AVAILABLE else '❌'}")
        print(f"  Cell Factory:         {'✅' if CF_AVAILABLE else '❌'}")
        print(f"  Dynamic Cell Loader:  {'✅' if DCL_AVAILABLE else '❌'}")
        print(f"  A/B Testing:          {'✅' if ABT_AVAILABLE else '❌'}")
        print(f"  Fine-Tuning Pipeline: {'✅' if FTP_AVAILABLE else '❌'}")
        print("="*60 + "\n")

    def initialize(self):
        """Инициализация при старте"""
        if self.verbose:
            print("🧬 Инициализация систем эволюции...")

        # Загружаем динамические клетки
        if self.cell_loader:
            self.cell_loader.load_all_active_cells()

    def auto_evolution_cycle(self):
        """Автоматический цикл эволюции"""
        print("\n" + "="*60)
        print("🧬 АВТОМАТИЧЕСКАЯ ЭВОЛЮЦИЯ")
        print("="*60)

        # 1. Continuous Learning
        if self.continuous_learning and self.continuous_learning.should_trigger_self_improvement():
            print("\n🔧 Запуск самоулучшения...")
            self.continuous_learning.attempt_self_improvement()

        # 2. Cell Factory
        if self.cell_factory:
            result = self.cell_factory.should_create_cell()
            if result:
                pattern, tasks = result
                print(f"\n🏭 Создание новой клетки для паттерна: {pattern}")
                self.cell_factory.create_cell(pattern, tasks)

        # 3. Fine-Tuning
        if self.finetuning and self.finetuning.should_trigger_training():
            print("\n🎓 Запуск fine-tuning...")
            self.finetuning.train_new_version()

        print("\n✅ Цикл эволюции завершён")

    def get_global_stats(self) -> Dict:
        """Глобальная статистика всех систем"""
        stats = {
            "evolution_enabled": True,
            "systems": {}
        }

        if self.continuous_learning:
            stats["systems"]["continuous_learning"] = self.continuous_learning.get_evolution_stats()

        if self.prompt_evolution:
            stats["systems"]["prompt_evolution"] = self.prompt_evolution.get_stats()

        if self.cell_factory:
            stats["systems"]["cell_factory"] = self.cell_factory.get_stats()

        if self.cell_loader:
            stats["systems"]["cell_loader"] = self.cell_loader.get_stats()

        if self.ab_testing:
            stats["systems"]["ab_testing"] = self.ab_testing.get_stats()

        if self.finetuning:
            stats["systems"]["finetuning"] = self.finetuning.get_stats()

        return stats

    # Команды для main.py

    def cmd_evolution_stats(self) -> str:
        """Показать статистику эволюции"""
        stats = self.get_global_stats()

        output = "🧬 СТАТИСТИКА ЭВОЛЮЦИИ\n\n"

        if self.continuous_learning:
            cls_stats = stats["systems"].get("continuous_learning", {})
            output += f"Continuous Learning:\n"
            output += f"  Попыток самоулучшения: {cls_stats.get('total', 0)}\n"
            output += f"  Успешных: {cls_stats.get('successful', 0)}\n"
            output += f"  Откатов: {cls_stats.get('rollbacks', 0)}\n\n"

        if self.prompt_evolution:
            pes_stats = stats["systems"].get("prompt_evolution", {})
            output += f"Prompt Evolution:\n"
            output += f"  Клеток с версиями: {pes_stats.get('cells', 0)}\n"
            output += f"  Всего версий: {pes_stats.get('total_versions', 0)}\n"
            output += f"  Тестов: {pes_stats.get('total_tests', 0)}\n\n"

        if self.cell_factory:
            cf_stats = stats["systems"].get("cell_factory", {})
            output += f"Cell Factory:\n"
            output += f"  Сгенерировано клеток: {cf_stats.get('total_cells', 0)}\n"
            output += f"  Активных: {cf_stats.get('active_cells', 0)}\n"
            output += f"  Паттернов покрыто: {cf_stats.get('patterns_covered', 0)}\n\n"

        if self.finetuning:
            ftp_stats = stats["systems"].get("finetuning", {})
            output += f"Fine-Tuning:\n"
            output += f"  Версий модели: {ftp_stats.get('total_versions', 0)}\n"
            output += f"  Активная: {ftp_stats.get('active_version', 'нет')}\n"
            output += f"  Доступно примеров: {ftp_stats.get('available_training_samples', 0)}\n\n"

        return output

    def cmd_evolution_log(self, system: str = "all", limit: int = 10) -> str:
        """Показать лог эволюции"""
        if system == "cls" and self.continuous_learning:
            return self.continuous_learning.show_evolution_log(limit)

        elif system == "cells" and self.cell_factory:
            return self.cell_factory.show_registry()

        elif system == "loader" and self.cell_loader:
            return self.cell_loader.show_loaded_cells()

        elif system == "models" and self.finetuning:
            return self.finetuning.show_versions()

        elif system == "all":
            output = ""
            if self.continuous_learning:
                output += self.continuous_learning.show_evolution_log(5) + "\n\n"
            if self.cell_factory:
                output += self.cell_factory.show_registry() + "\n\n"
            if self.finetuning:
                output += self.finetuning.show_versions()
            return output if output else "📊 Нет данных эволюции"

        return f"❌ Неизвестная система: {system}"

    def cmd_evolution_diff(self, system: str, entry_index: int) -> str:
        """Показать diff для записи эволюции"""
        if system == "cls" and self.continuous_learning:
            return self.continuous_learning.show_code_diff(entry_index)
        else:
            return f"❌ Diff доступен только для cls (continuous learning)"

    def cmd_evolution_list(self, system: str) -> str:
        """Показать список записей эволюции"""
        if system == "cls" and self.continuous_learning:
            return self.continuous_learning.list_evolution_entries()
        else:
            return f"❌ Список доступен только для cls (continuous learning)"

    def cmd_evolve_prompt(self, cell_name: str) -> str:
        """Эволюционировать промпт клетки"""
        if not self.prompt_evolution:
            return "❌ PromptEvolutionSystem недоступен"

        version = self.prompt_evolution.evolve_prompt(cell_name)

        if version:
            return f"✅ Создана новая версия: {version.version_id}\nТребуется {5} тестов для оценки"
        else:
            return f"❌ Не удалось эволюционировать промпт для {cell_name}"

    def cmd_vote_start(self, cell_name: str, version_id_1: str,
                       version_id_2: str, task: str) -> str:
        """Начать голосование между двумя версиями промпта"""
        if not self.prompt_evolution:
            return "❌ PromptEvolutionSystem недоступен"

        session = self.prompt_evolution.start_voting_session(
            cell_name, version_id_1, version_id_2
        )

        if not session:
            return f"❌ Не удалось создать сессию голосования"

        return self.prompt_evolution.format_voting_prompt(session, task)

    def cmd_vote_record(self, cell_name: str, version_id: str,
                       score: int, feedback: str = "") -> str:
        """Записать результат голосования"""
        if not self.prompt_evolution:
            return "❌ PromptEvolutionSystem недоступен"

        success = self.prompt_evolution.record_voting_result(
            cell_name, version_id, score, feedback
        )

        if success:
            return f"✅ Голос записан: {version_id} получил оценку {score}/10"
        else:
            return f"❌ Не удалось записать результат"

    def cmd_vote_results(self, cell_name: str, version_id_1: str,
                        version_id_2: str) -> str:
        """Показать результаты сравнения версий"""
        if not self.prompt_evolution:
            return "❌ PromptEvolutionSystem недоступен"

        return self.prompt_evolution.show_voting_results(
            cell_name, version_id_1, version_id_2
        )

    def cmd_create_cell(self, description: str) -> str:
        """Создать новую клетку вручную"""
        if not self.cell_factory:
            return "❌ CellFactory недоступен"

        # Симулируем паттерн для ручного создания
        pattern = description.split()[:2]
        pattern = " ".join(pattern).lower() if len(pattern) >= 2 else description[:20].lower()

        result = self.cell_factory.create_cell(pattern, [])

        if result and result.get("success"):
            cell = result["cell"]
            return f"✅ Клетка создана: {cell.cell_name}\nФайл: {cell.file_path}"
        else:
            error_msg = result.get("error", "Неизвестная ошибка") if result else "Не удалось создать клетку"
            return f"❌ {error_msg}"

    def cmd_activate_cell(self, cell_name: str) -> str:
        """Активировать сгенерированную клетку"""
        if not self.cell_factory:
            return "❌ CellFactory недоступен"

        self.cell_factory.activate_cell(cell_name)

        # Загружаем клетку
        if self.cell_loader:
            self.cell_loader.load_all_active_cells()

        return f"✅ Клетка {cell_name} активирована и загружена"

    def cmd_train_model(self) -> str:
        """Запустить fine-tuning"""
        if not self.finetuning:
            return "❌ FineTuningPipeline недоступен"

        version = self.finetuning.train_new_version()

        if version:
            return f"✅ Fine-tuning завершён\nВерсия: {version.version_id}\nМодель: {version.model_name}"
        else:
            return "❌ Fine-tuning провален"

    def cmd_ab_test(self, test_name: str, variants: List[str]) -> str:
        """Создать A/B тест"""
        if not self.ab_testing:
            return "❌ ABTestingFramework недоступен"

        variant_tuples = [(v, f"Вариант {v}") for v in variants]
        test = self.ab_testing.create_test(test_name, variant_tuples)

        return f"✅ A/B тест создан: {test.test_id}\nВарианты: {', '.join(variants)}"

    def cmd_help_evolution(self) -> str:
        """Справка по командам эволюции"""
        return """
🧬 КОМАНДЫ ЭВОЛЮЦИИ

Общее:
  /evolution stats       — статистика всех систем
  /evolution log [system] — лог эволюции (cls/cells/models/all)
  /evolution cycle       — запустить автоэволюцию

Просмотр изменений кода:
  /evolution list cls    — список записей эволюции кода
  /evolution diff cls <индекс> — показать diff изменений

Промпты:
  /evolve-prompt <cell>  — эволюционировать промпт клетки
  /vote-start <cell> <v1> <v2> <задача> — начать сессию голосования
  /vote-record <cell> <version> <оценка> <комментарий> — записать голос
  /vote-results <cell> <v1> <v2> — результаты сравнения

Клетки:
  /create-cell <описание> — создать новую клетку
  /activate-cell <имя>   — активировать клетку
  /cells                 — список сгенерированных клеток

Fine-Tuning:
  /train-model           — запустить обучение модели
  /model-versions        — список версий модели

A/B тестирование:
  /ab-test <имя> <варианты> — создать A/B тест
  /ab-results <test_id>  — результаты теста
"""


# === ТЕСТ ===
if __name__ == "__main__":
    print("=" * 60)
    print("Тест EvolutionManager")
    print("=" * 60)

    from experience import ExperienceSystem
    from cells import MemoryCell

    exp = ExperienceSystem()
    mem = MemoryCell()

    manager = EvolutionManager(exp, mem, verbose=True)
    manager.initialize()

    print(f"\n{manager.cmd_evolution_stats()}")
