"""
Cell Watcher v1.0 — Автономный мониторинг и горячая загрузка органов

Следит за появлением новых *_cell.py файлов и автоматически
загружает их без перезапуска Neira.

ВОЗМОЖНОСТИ:
1. Фоновый мониторинг директорий
2. Автоматическая загрузка новых клеток
3. Hot reload при изменении файлов
4. Graceful degradation — не ломает систему при ошибках
5. Интеграция с NervousSystem для уведомлений
"""

import os
import sys
import time
import threading
import importlib
import importlib.util
from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import traceback


@dataclass
class WatchedCell:
    """Информация о наблюдаемой клетке"""
    file_path: str
    module_name: str
    class_name: Optional[str] = None
    instance: Optional[Any] = None
    last_modified: float = 0.0
    last_loaded: Optional[datetime] = None
    load_errors: List[str] = field(default_factory=list)
    is_healthy: bool = False


class CellWatcher:
    """
    Автономный наблюдатель за клетками
    
    Работает в фоновом потоке, следит за файлами *_cell.py
    и автоматически загружает новые/изменённые клетки.
    """
    
    VERSION = "1.0"
    
    def __init__(
        self,
        watch_dirs: Optional[List[str]] = None,
        scan_interval: float = 2.0,
        on_cell_loaded: Optional[Callable] = None,
        on_cell_error: Optional[Callable] = None,
        auto_start: bool = False
    ):
        """
        Args:
            watch_dirs: Директории для мониторинга (по умолчанию: текущая + generated/)
            scan_interval: Интервал сканирования в секундах
            on_cell_loaded: Callback при загрузке клетки
            on_cell_error: Callback при ошибке
            auto_start: Автоматически запустить мониторинг
        """
        # Определяем базовую директорию
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Директории для наблюдения
        if watch_dirs:
            self.watch_dirs = [os.path.abspath(d) for d in watch_dirs]
        else:
            self.watch_dirs = [
                self.base_dir,  # Корневая директория проекта
                os.path.join(self.base_dir, "generated"),  # generated/
            ]
        
        self.scan_interval = scan_interval
        self.on_cell_loaded = on_cell_loaded
        self.on_cell_error = on_cell_error
        
        # Состояние
        self.watched_cells: Dict[str, WatchedCell] = {}
        self.known_files: Set[str] = set()  # Уже известные файлы
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Счётчики
        self.stats = {
            "total_scans": 0,
            "cells_loaded": 0,
            "cells_reloaded": 0,
            "errors": 0,
            "start_time": None
        }
        
        # Исключения (системные клетки, которые не трогаем)
        self.excluded_files = {
            "cells.py",  # Базовые клетки
            "code_cell.py",  # Уже загружен
            "curiosity_cell.py",  # Уже загружен
            "introspection_cell.py",  # Уже загружен
        }
        
        if auto_start:
            self.start()
    
    def _is_cell_file(self, filename: str) -> bool:
        """Проверить, является ли файл клеткой"""
        if not filename.endswith("_cell.py"):
            return False
        if filename.startswith("__"):
            return False
        if filename in self.excluded_files:
            return False
        return True
    
    def _scan_directory(self, directory: str) -> List[str]:
        """Сканировать директорию на наличие cell-файлов"""
        if not os.path.exists(directory):
            return []
        
        cell_files = []
        try:
            for filename in os.listdir(directory):
                if self._is_cell_file(filename):
                    filepath = os.path.join(directory, filename)
                    cell_files.append(filepath)
        except Exception as e:
            print(f"⚠️ Ошибка сканирования {directory}: {e}")
        
        return cell_files
    
    def _load_cell_from_file(self, filepath: str) -> Optional[WatchedCell]:
        """Загрузить клетку из файла"""
        try:
            module_name = os.path.splitext(os.path.basename(filepath))[0]
            
            # Удаляем старый модуль если есть
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # Загружаем модуль
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if not spec or not spec.loader:
                raise ImportError(f"Не удалось создать spec для {filepath}")
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Ищем класс клетки
            cell_class = None
            cell_class_name = None
            
            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(module, attr_name)
                
                # Ищем класс с VERSION атрибутом (наш паттерн для клеток)
                if isinstance(attr, type) and hasattr(attr, "VERSION"):
                    cell_class = attr
                    cell_class_name = attr_name
                    break
            
            # Пробуем создать экземпляр
            instance = None
            if cell_class:
                try:
                    # Пробуем без аргументов
                    instance = cell_class()
                except TypeError:
                    # Пробуем с None (для совместимости с Cell(memory))
                    try:
                        instance = cell_class(None)
                    except:
                        pass  # Не страшно, просто не создадим экземпляр
            
            watched = WatchedCell(
                file_path=filepath,
                module_name=module_name,
                class_name=cell_class_name,
                instance=instance,
                last_modified=os.path.getmtime(filepath),
                last_loaded=datetime.now(),
                is_healthy=True
            )
            
            return watched
            
        except Exception as e:
            error_msg = f"{e}\n{traceback.format_exc()}"
            
            watched = WatchedCell(
                file_path=filepath,
                module_name=os.path.splitext(os.path.basename(filepath))[0],
                last_modified=os.path.getmtime(filepath) if os.path.exists(filepath) else 0,
                load_errors=[error_msg],
                is_healthy=False
            )
            
            if self.on_cell_error:
                self.on_cell_error(filepath, error_msg)
            
            return watched
    
    def _check_and_load_new_cells(self):
        """Проверить и загрузить новые клетки"""
        for directory in self.watch_dirs:
            cell_files = self._scan_directory(directory)
            
            for filepath in cell_files:
                with self._lock:
                    # Новый файл?
                    if filepath not in self.known_files:
                        print(f"\n🆕 Обнаружена новая клетка: {os.path.basename(filepath)}")
                        self.known_files.add(filepath)
                        
                        watched = self._load_cell_from_file(filepath)
                        if watched:
                            self.watched_cells[filepath] = watched
                            
                            if watched.is_healthy:
                                self.stats["cells_loaded"] += 1
                                print(f"✅ Загружена: {watched.class_name or watched.module_name}")
                                
                                if self.on_cell_loaded:
                                    self.on_cell_loaded(watched)
                            else:
                                self.stats["errors"] += 1
                                print(f"❌ Ошибка загрузки: {watched.load_errors[-1][:100]}...")
                    
                    # Существующий файл изменился?
                    elif filepath in self.watched_cells:
                        watched = self.watched_cells[filepath]
                        current_mtime = os.path.getmtime(filepath)
                        
                        if current_mtime > watched.last_modified:
                            print(f"\n🔄 Обнаружено изменение: {os.path.basename(filepath)}")
                            
                            new_watched = self._load_cell_from_file(filepath)
                            if new_watched:
                                self.watched_cells[filepath] = new_watched
                                
                                if new_watched.is_healthy:
                                    self.stats["cells_reloaded"] += 1
                                    print(f"✅ Перезагружена: {new_watched.class_name or new_watched.module_name}")
                                    
                                    if self.on_cell_loaded:
                                        self.on_cell_loaded(new_watched)
                                else:
                                    self.stats["errors"] += 1
    
    def _watch_loop(self):
        """Основной цикл наблюдения"""
        print(f"👁️ CellWatcher запущен. Интервал: {self.scan_interval}с")
        print(f"   Наблюдаемые директории:")
        for d in self.watch_dirs:
            print(f"   • {d}")
        
        self.stats["start_time"] = datetime.now()
        
        # Первичное сканирование
        self._initial_scan()
        
        while self.running:
            try:
                time.sleep(self.scan_interval)
                self.stats["total_scans"] += 1
                self._check_and_load_new_cells()
            except Exception as e:
                print(f"⚠️ Ошибка в цикле наблюдения: {e}")
                self.stats["errors"] += 1
    
    def _initial_scan(self):
        """Первичное сканирование — запомнить существующие файлы"""
        print("\n📂 Первичное сканирование...")
        
        for directory in self.watch_dirs:
            cell_files = self._scan_directory(directory)
            
            for filepath in cell_files:
                self.known_files.add(filepath)
                
                # Загружаем существующие динамические клетки
                if "generated" in filepath or "tic_tac_toe" in filepath:
                    watched = self._load_cell_from_file(filepath)
                    if watched:
                        self.watched_cells[filepath] = watched
                        if watched.is_healthy:
                            self.stats["cells_loaded"] += 1
        
        print(f"   Найдено cell-файлов: {len(self.known_files)}")
        print(f"   Загружено динамических: {len(self.watched_cells)}")
    
    def start(self):
        """Запустить фоновый мониторинг"""
        if self.running:
            print("⚠️ CellWatcher уже запущен")
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Остановить мониторинг"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        print("🛑 CellWatcher остановлен")
    
    def get_cell(self, name: str) -> Optional[Any]:
        """Получить экземпляр клетки по имени модуля или класса"""
        with self._lock:
            for watched in self.watched_cells.values():
                if watched.module_name == name or watched.class_name == name:
                    return watched.instance
        return None
    
    def get_loaded_cells(self) -> List[str]:
        """Получить список загруженных клеток"""
        with self._lock:
            return [
                w.class_name or w.module_name 
                for w in self.watched_cells.values() 
                if w.is_healthy
            ]
    
    def get_status(self) -> str:
        """Получить статус наблюдателя"""
        uptime = ""
        if self.stats["start_time"]:
            delta = datetime.now() - self.stats["start_time"]
            uptime = f"{delta.seconds // 60}м {delta.seconds % 60}с"
        
        status = f"""
👁️ CELL WATCHER STATUS
{'='*40}
Статус: {'🟢 Работает' if self.running else '🔴 Остановлен'}
Uptime: {uptime}
Сканирований: {self.stats['total_scans']}

📂 НАБЛЮДАЕМЫЕ ДИРЕКТОРИИ:
"""
        for d in self.watch_dirs:
            exists = "✅" if os.path.exists(d) else "❌"
            status += f"   {exists} {d}\n"
        
        status += f"""
📊 СТАТИСТИКА:
   Известных файлов: {len(self.known_files)}
   Загружено клеток: {self.stats['cells_loaded']}
   Перезагружено: {self.stats['cells_reloaded']}
   Ошибок: {self.stats['errors']}

🧬 ЗАГРУЖЕННЫЕ КЛЕТКИ:
"""
        with self._lock:
            for filepath, watched in self.watched_cells.items():
                health = "✅" if watched.is_healthy else "❌"
                name = watched.class_name or watched.module_name
                status += f"   {health} {name}\n"
                if not watched.is_healthy and watched.load_errors:
                    status += f"      └─ Ошибка: {watched.load_errors[-1][:50]}...\n"
        
        return status
    
    def force_reload(self, name: str) -> bool:
        """Принудительно перезагрузить клетку"""
        with self._lock:
            for filepath, watched in self.watched_cells.items():
                if watched.module_name == name or watched.class_name == name:
                    new_watched = self._load_cell_from_file(filepath)
                    if new_watched and new_watched.is_healthy:
                        self.watched_cells[filepath] = new_watched
                        print(f"✅ Принудительно перезагружена: {name}")
                        return True
        return False


# === ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ===
_global_watcher: Optional[CellWatcher] = None


def get_cell_watcher() -> CellWatcher:
    """Получить глобальный экземпляр CellWatcher"""
    global _global_watcher
    if _global_watcher is None:
        _global_watcher = CellWatcher()
    return _global_watcher


def start_cell_watcher():
    """Запустить глобальный CellWatcher"""
    watcher = get_cell_watcher()
    watcher.start()
    return watcher


def stop_cell_watcher():
    """Остановить глобальный CellWatcher"""
    global _global_watcher
    if _global_watcher:
        _global_watcher.stop()


# === ТЕСТ ===
if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Тест CellWatcher")
    print("=" * 60)
    
    def on_loaded(watched: WatchedCell):
        print(f"   [CALLBACK] Загружена: {watched.class_name}")
    
    def on_error(filepath: str, error: str):
        print(f"   [CALLBACK] Ошибка в {filepath}: {error[:50]}")
    
    watcher = CellWatcher(
        scan_interval=3.0,
        on_cell_loaded=on_loaded,
        on_cell_error=on_error
    )
    
    watcher.start()
    
    print("\n⏳ Наблюдаю 15 секунд... Создайте новый *_cell.py файл для теста!\n")
    
    try:
        for i in range(5):
            time.sleep(3)
            print(f"\n--- Проверка {i+1}/5 ---")
            print(f"Загруженные клетки: {watcher.get_loaded_cells()}")
    except KeyboardInterrupt:
        pass
    
    print(watcher.get_status())
    watcher.stop()
