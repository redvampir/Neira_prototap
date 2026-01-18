"""
Realtime File Watcher для проекта Neira.
Следит за изменениями Python файлов и автоматически проверяет их.

Использование:
    python scripts/watch_code.py

Требует: pip install watchdog
"""

import sys
import time
import subprocess
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
except ImportError:
    print("❌ Требуется watchdog: pip install watchdog")
    sys.exit(1)


# Папки которые игнорируем
IGNORE_DIRS = {
    '__pycache__', '.venv', 'venv', 'ollamy-env', 'node_modules',
    '.git', 'neira-app', 'neira-mobile', 'frontend', 'neira-vscode',
    'build_pdc', '.pytest_cache', '.neira_cache'
}

# Файлы которые разрешены в корне
ALLOWED_ROOT_FILES = {
    'main.py', 'neira.py', 'telegram_bot.py', 'neira_server.py',
    'conftest.py'
}


def get_project_root() -> Path:
    """Находит корень проекта."""
    return Path(__file__).resolve().parent.parent


class CodeWatcher(FileSystemEventHandler):
    """Обработчик событий файловой системы."""
    
    def __init__(self, root: Path):
        self.root = root
        self.last_check = {}
        self.debounce_seconds = 1.0  # Задержка между проверками одного файла
    
    def should_check(self, path: Path) -> bool:
        """Проверяет нужно ли проверять файл."""
        # Только Python файлы
        if not path.suffix == '.py':
            return False
        
        # Игнорируем определённые папки
        for part in path.parts:
            if part in IGNORE_DIRS:
                return False
        
        # Debounce - не проверять слишком часто
        now = time.time()
        last = self.last_check.get(str(path), 0)
        if now - last < self.debounce_seconds:
            return False
        
        self.last_check[str(path)] = now
        return True
    
    def check_file(self, filepath: Path):
        """Запускает проверку файла."""
        print(f"\n{'='*60}")
        print(f"🔍 Проверяю: {filepath.relative_to(self.root)}")
        print(f"{'='*60}")
        
        # Проверка расположения
        if filepath.parent == self.root:
            if filepath.name not in ALLOWED_ROOT_FILES:
                print(f"⚠️  WARNING: Файл в корне проекта!")
                print(f"   Перенеси в neira/ или scripts/")
        
        # Запуск валидатора
        result = subprocess.run(
            [sys.executable, 'scripts/validate_code.py', str(filepath)],
            cwd=self.root,
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        if result.returncode == 0:
            print("✅ Файл прошёл проверку")
        else:
            print("❌ Найдены проблемы (см. выше)")
    
    def on_modified(self, event):
        """Обработка изменения файла."""
        if isinstance(event, FileModifiedEvent):
            path = Path(event.src_path)
            if self.should_check(path):
                self.check_file(path)
    
    def on_created(self, event):
        """Обработка создания файла."""
        if isinstance(event, FileCreatedEvent):
            path = Path(event.src_path)
            if self.should_check(path):
                # Для новых файлов — дополнительное предупреждение
                print(f"\n🆕 Создан новый файл: {path.name}")
                self.check_file(path)


def main():
    """Точка входа."""
    root = get_project_root()
    
    print(f"""
╔══════════════════════════════════════════════════════════╗
║       🔍 NEIRA CODE WATCHER v1.0                        ║
║       Автоматическая проверка кода при сохранении       ║
╠══════════════════════════════════════════════════════════╣
║  Корень проекта: {str(root)[:40]:<40} ║
║  Ctrl+C для остановки                                    ║
╚══════════════════════════════════════════════════════════╝
""")
    
    event_handler = CodeWatcher(root)
    observer = Observer()
    observer.schedule(event_handler, str(root), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Остановка watcher...")
        observer.stop()
    
    observer.join()


if __name__ == '__main__':
    main()
