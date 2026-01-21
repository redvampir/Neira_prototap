"""
Neira Dynamic Cell Loader v0.6
Система динамической загрузки клеток из generated/

ВОЗМОЖНОСТИ:
1. Автоматическое сканирование generated/ при старте
2. Динамический импорт клеток без перезапуска
3. Hot reload при изменении файлов
4. Управление зависимостями и версиями
5. Интеграция с Cell Factory registry
"""

import os
import sys
import importlib
import importlib.util
import re
from typing import List, Dict, Optional, Any, Type
from dataclasses import dataclass
import json

from cells import Cell, MemoryCell
from cell_factory import GENERATED_CELLS_DIR, CELL_REGISTRY_FILE, GeneratedCell


@dataclass
class LoadedCell:
    """Метаданные загруженной клетки"""
    cell_name: str
    class_name: str
    module_name: str
    file_path: str
    cell_class: Type[Cell]
    instance: Optional[Cell] = None
    last_modified: float = 0.0


class DynamicCellLoader:
    """Загрузчик динамических клеток"""

    def __init__(self, memory: Optional[MemoryCell] = None):
        self.memory = memory
        self.loaded_cells: Dict[str, LoadedCell] = {}
        self.registry: List[GeneratedCell] = []
        self.last_error: Optional[str] = None
        self.last_missing_deps: List[str] = []

        # Загружаем реестр
        self.load_registry()

    def load_registry(self):
        """Загрузить реестр сгенерированных клеток"""
        if os.path.exists(CELL_REGISTRY_FILE):
            try:
                with open(CELL_REGISTRY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.registry = [GeneratedCell.from_dict(c) for c in data]
                print(f"📚 Загружен реестр: {len(self.registry)} клеток")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки реестра: {e}")

    def scan_generated_dir(self) -> List[str]:
        """Сканировать директорию generated/ на наличие Python файлов"""
        if not os.path.exists(GENERATED_CELLS_DIR):
            return []

        python_files = []

        for filename in os.listdir(GENERATED_CELLS_DIR):
            if filename.endswith(".py") and not filename.startswith("__"):
                filepath = os.path.join(GENERATED_CELLS_DIR, filename)
                python_files.append(filepath)

        return python_files

    def get_active_cells_from_registry(self) -> List[GeneratedCell]:
        """Получить список активных клеток из реестра"""
        return [c for c in self.registry if c.active]

    def import_cell_from_file(self, filepath: str) -> Optional[LoadedCell]:
        """Импортировать клетку из файла"""
        self.last_error = None
        self.last_missing_deps = []
        try:
            # Получаем имя модуля из пути
            module_name = os.path.splitext(os.path.basename(filepath))[0]
            spec = importlib.util.spec_from_file_location(module_name, filepath)

            if not spec or not spec.loader:
                print(f"⚠️ Не удалось создать spec для {filepath}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Ищем класс клетки (наследник Cell)
            cell_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if isinstance(attr, type) and issubclass(attr, Cell) and attr != Cell:
                    cell_class = attr
                    break

            if not cell_class:
                print(f"⚠️ Не найден класс Cell в {filepath}")
                return None

            # Создаем экземпляр
            instance = cell_class(self.memory)

            # Получаем время модификации файла
            mtime = os.path.getmtime(filepath)

            loaded = LoadedCell(
                cell_name=instance.name,
                class_name=cell_class.__name__,
                module_name=module_name,
                file_path=filepath,
                cell_class=cell_class,
                instance=instance,
                last_modified=mtime
            )

            print(f"✅ Загружена клетка: {loaded.cell_name} ({loaded.class_name})")
            return loaded

        except ModuleNotFoundError as e:
            missing = self._extract_missing_module_name(e)
            if missing:
                self.last_missing_deps = [missing]
            self.last_error = str(e)
            print(f"? Ошибка импорта {filepath}: {e}")
            return None
        except ImportError as e:
            missing = self._extract_missing_module_name(e)
            if missing:
                self.last_missing_deps = [missing]
            self.last_error = str(e)
            print(f"? Ошибка импорта {filepath}: {e}")
            return None
        except Exception as e:
            self.last_error = str(e)
            print(f"? Ошибка импорта {filepath}: {e}")
            return None

    @staticmethod
    def _extract_missing_module_name(error: BaseException) -> Optional[str]:
        """Извлечь имя отсутствующего модуля из ImportError."""
        name = getattr(error, "name", None)
        if isinstance(name, str) and name:
            return name.split(".")[0]
        match = re.search(r"No module named ['\\\"]([^'\\\"]+)['\\\"]", str(error))
        if match:
            return match.group(1).split(".")[0]
        return None

    def load_all_active_cells(self):
        """Загрузить все активные клетки из реестра"""
        print("\n" + "="*60)
        print("📚 ДИНАМИЧЕСКАЯ ЗАГРУЗКА КЛЕТОК")
        print("="*60)

        active_cells = self.get_active_cells_from_registry()

        if not active_cells:
            print("\n⏸️ Нет активных клеток для загрузки")
            return

        print(f"\nНайдено активных клеток: {len(active_cells)}")

        loaded_count = 0

        for cell_meta in active_cells:
            if not os.path.exists(cell_meta.file_path):
                print(f"⚠️ Файл не найден: {cell_meta.file_path}")
                continue

            loaded = self.import_cell_from_file(cell_meta.file_path)

            if loaded:
                self.loaded_cells[loaded.cell_name] = loaded
                loaded_count += 1

        print(f"\n✅ Загружено клеток: {loaded_count}/{len(active_cells)}")

        if loaded_count > 0:
            print("\n📋 Доступные динамические клетки:")
            for name in self.loaded_cells.keys():
                print(f"   • {name}")

    def reload_cell(self, cell_name: str) -> bool:
        """Перезагрузить клетку (hot reload)"""
        if cell_name not in self.loaded_cells:
            print(f"⚠️ Клетка не загружена: {cell_name}")
            return False

        loaded = self.loaded_cells[cell_name]
        filepath = loaded.file_path

        # Проверяем изменился ли файл
        current_mtime = os.path.getmtime(filepath)

        if current_mtime <= loaded.last_modified:
            print(f"ℹ️ Файл не изменился: {cell_name}")
            return True

        print(f"🔄 Перезагрузка клетки: {cell_name}")

        # Удаляем старый модуль
        if loaded.module_name in sys.modules:
            del sys.modules[loaded.module_name]

        # Загружаем заново
        new_loaded = self.import_cell_from_file(filepath)

        if new_loaded:
            self.loaded_cells[cell_name] = new_loaded
            print(f"✅ Клетка перезагружена: {cell_name}")
            return True
        else:
            print(f"❌ Ошибка перезагрузки: {cell_name}")
            return False

    def get_cell_instance(self, cell_name: str) -> Optional[Cell]:
        """Получить экземпляр клетки по имени"""
        if cell_name in self.loaded_cells:
            return self.loaded_cells[cell_name].instance

        return None

    def check_for_updates(self) -> List[str]:
        """Проверить обновления файлов клеток"""
        updated = []

        for name, loaded in self.loaded_cells.items():
            current_mtime = os.path.getmtime(loaded.file_path)

            if current_mtime > loaded.last_modified:
                updated.append(name)

        return updated

    def auto_reload_updated_cells(self):
        """Автоматически перезагрузить обновленные клетки"""
        updated = self.check_for_updates()

        if not updated:
            return

        print(f"\n🔄 Обнаружены обновления клеток: {', '.join(updated)}")

        for cell_name in updated:
            self.reload_cell(cell_name)

    def is_cell_available(self, cell_name: str) -> bool:
        """Проверить доступна ли клетка"""
        return cell_name in self.loaded_cells

    def get_available_cells(self) -> List[str]:
        """Получить список доступных динамических клеток"""
        return list(self.loaded_cells.keys())

    def get_stats(self) -> Dict:
        """Статистика загрузчика"""
        return {
            "loaded_cells": len(self.loaded_cells),
            "active_in_registry": len(self.get_active_cells_from_registry()),
            "total_in_registry": len(self.registry),
            "available_cells": self.get_available_cells()
        }

    def show_loaded_cells(self) -> str:
        """Показать загруженные клетки"""
        if not self.loaded_cells:
            return "📚 Нет загруженных динамических клеток"

        output = "📚 ЗАГРУЖЕННЫЕ ДИНАМИЧЕСКИЕ КЛЕТКИ:\n\n"

        for i, (name, loaded) in enumerate(self.loaded_cells.items(), 1):
            output += f"{i}. {name} ({loaded.class_name})\n"
            output += f"   Файл: {loaded.file_path}\n"
            output += f"   Модуль: {loaded.module_name}\n"
            output += f"   Экземпляр: {'✅' if loaded.instance else '❌'}\n"

            # Находим метаданные из реестра
            meta = next((c for c in self.registry if c.cell_name == name), None)
            if meta:
                output += f"   Описание: {meta.description}\n"
                output += f"   Паттерн: {meta.task_pattern}\n"

                if meta.uses_count > 0:
                    output += f"   Использований: {meta.uses_count}\n"
                    output += f"   Средний score: {meta.avg_score:.1f}/10\n"

            output += "\n"

        stats = self.get_stats()
        output += f"📊 СТАТИСТИКА:\n"
        output += f"   Загружено: {stats['loaded_cells']}\n"
        output += f"   Активных в реестре: {stats['active_in_registry']}\n"
        output += f"   Всего в реестре: {stats['total_in_registry']}\n"

        return output

    def process_with_dynamic_cell(self, cell_name: str, input_data: str):
        """Обработать запрос динамической клеткой"""
        cell = self.get_cell_instance(cell_name)

        if not cell:
            return None

        try:
            result = cell.process(input_data)
            return result
        except Exception as e:
            print(f"❌ Ошибка обработки клеткой {cell_name}: {e}")
            return None


# === ТЕСТ ===
if __name__ == "__main__":
    print("=" * 60)
    print("Тест DynamicCellLoader")
    print("=" * 60)

    loader = DynamicCellLoader()

    # Сканируем файлы
    files = loader.scan_generated_dir()
    print(f"\nНайдено файлов в generated/: {len(files)}")

    # Загружаем активные клетки
    loader.load_all_active_cells()

    # Показываем загруженные
    print(f"\n{loader.show_loaded_cells()}")

    # Статистика
    print(f"\n📊 Статистика:")
    stats = loader.get_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))
