"""
File System Agent — Работа с файлами проекта

Позволяет Нейре:
- Читать файлы
- Создавать/редактировать файлы
- Искать по содержимому (grep)
- Навигация по структуре проекта
- Понимать workspace
"""

import os
import re
import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import hashlib


@dataclass
class FileInfo:
    """Информация о файле"""
    path: str
    name: str
    extension: str
    size: int
    is_directory: bool
    modified: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass  
class SearchResult:
    """Результат поиска"""
    file_path: str
    line_number: int
    line_content: str
    match_start: int
    match_end: int
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FileEdit:
    """Редактирование файла"""
    file_path: str
    old_content: str
    new_content: str
    diff: str
    
    def to_dict(self) -> dict:
        return asdict(self)


class FileSystemAgent:
    """
    Агент для работы с файловой системой
    
    Безопасность:
    - Работает только внутри разрешённых директорий
    - Не позволяет выйти за пределы workspace
    - Логирует все операции
    """
    
    # Расширения для чтения как текст
    TEXT_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.svelte',
        '.html', '.css', '.scss', '.less', '.sass',
        '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg',
        '.md', '.txt', '.rst', '.log',
        '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
        '.c', '.cpp', '.h', '.hpp', '.cs', '.java', '.go', '.rs', '.rb',
        '.sql', '.graphql', '.prisma',
        '.env', '.gitignore', '.dockerignore', '.editorconfig',
        'Dockerfile', 'Makefile', 'CMakeLists.txt'
    }
    
    # Игнорируемые директории
    IGNORE_DIRS = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        '.idea', '.vscode', 'dist', 'build', '.next', '.nuxt',
        'target', 'bin', 'obj', '.pytest_cache', '.mypy_cache',
        'coverage', '.coverage', 'htmlcov', 'egg-info'
    }
    
    # Максимальный размер файла для чтения (5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024
    
    def __init__(self, workspace_root: str, allowed_roots: Optional[List[str]] = None):
        """
        Args:
            workspace_root: Корневая директория workspace
            allowed_roots: Дополнительные разрешённые корни (опционально)
        """
        self.workspace_root = Path(workspace_root).resolve()
        self.allowed_roots = [self.workspace_root]
        
        if allowed_roots:
            self.allowed_roots.extend([Path(r).resolve() for r in allowed_roots])
        
        self.operations_log: List[Dict] = []
    
    def _is_safe_path(self, path: str) -> bool:
        """Проверяет, что путь находится внутри разрешённых директорий"""
        try:
            resolved = Path(path).resolve()
            return any(
                resolved == root or root in resolved.parents
                for root in self.allowed_roots
            )
        except Exception:
            return False
    
    def _resolve_path(self, path: str) -> Path:
        """Преобразует относительный путь в абсолютный"""
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace_root / p
        return p.resolve()
    
    def _log_operation(self, operation: str, path: str, success: bool, details: str = ""):
        """Логирует операцию"""
        self.operations_log.append({
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "path": path,
            "success": success,
            "details": details
        })
    
    def _is_text_file(self, path: Path) -> bool:
        """Проверяет, является ли файл текстовым"""
        if path.suffix.lower() in self.TEXT_EXTENSIONS:
            return True
        if path.name in self.TEXT_EXTENSIONS:
            return True
        return False
    
    # ==================== READ OPERATIONS ====================
    
    def read_file(self, path: str, start_line: int = 1, end_line: Optional[int] = None) -> Dict[str, Any]:
        """
        Читает содержимое файла
        
        Args:
            path: Путь к файлу
            start_line: Начальная строка (1-indexed)
            end_line: Конечная строка (включительно, None = до конца)
            
        Returns:
            {success, content, total_lines, language, error}
        """
        try:
            resolved = self._resolve_path(path)
            
            if not self._is_safe_path(str(resolved)):
                return {"success": False, "error": "Доступ запрещён: путь вне workspace"}
            
            if not resolved.exists():
                return {"success": False, "error": f"Файл не найден: {path}"}
            
            if resolved.is_dir():
                return {"success": False, "error": "Это директория, не файл"}
            
            # Проверяем размер
            size = resolved.stat().st_size
            if size > self.MAX_FILE_SIZE:
                return {"success": False, "error": f"Файл слишком большой: {size / 1024 / 1024:.1f}MB > 5MB"}
            
            # Определяем язык
            language = self._detect_language(resolved)
            
            # Читаем файл
            try:
                content = resolved.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    content = resolved.read_text(encoding='cp1251')
                except Exception:
                    return {"success": False, "error": "Не удалось прочитать файл (не текстовый?)"}
            
            lines = content.split('\n')
            total_lines = len(lines)
            
            # Применяем диапазон строк
            start_idx = max(0, start_line - 1)
            end_idx = end_line if end_line else total_lines
            
            selected_lines = lines[start_idx:end_idx]
            selected_content = '\n'.join(selected_lines)
            
            self._log_operation("read", str(resolved), True, f"lines {start_line}-{end_idx}")
            
            return {
                "success": True,
                "content": selected_content,
                "total_lines": total_lines,
                "start_line": start_line,
                "end_line": min(end_idx, total_lines),
                "language": language,
                "path": str(resolved),
                "relative_path": str(resolved.relative_to(self.workspace_root)) if self._is_safe_path(str(resolved)) else path
            }
            
        except Exception as e:
            self._log_operation("read", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def _detect_language(self, path: Path) -> str:
        """Определяет язык программирования по расширению"""
        ext_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.jsx': 'javascriptreact', '.tsx': 'typescriptreact',
            '.html': 'html', '.css': 'css', '.scss': 'scss',
            '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml',
            '.md': 'markdown', '.sql': 'sql',
            '.c': 'c', '.cpp': 'cpp', '.h': 'cpp', '.hpp': 'cpp',
            '.cs': 'csharp', '.java': 'java', '.go': 'go',
            '.rs': 'rust', '.rb': 'ruby', '.php': 'php',
            '.sh': 'shellscript', '.bash': 'shellscript',
            '.ps1': 'powershell', '.bat': 'bat',
            '.vue': 'vue', '.svelte': 'svelte'
        }
        return ext_map.get(path.suffix.lower(), 'plaintext')
    
    # ==================== SEARCH OPERATIONS ====================
    
    def search_in_files(
        self, 
        query: str, 
        path: str = ".",
        file_pattern: str = "*",
        is_regex: bool = False,
        case_sensitive: bool = False,
        max_results: int = 100
    ) -> Dict[str, Any]:
        """
        Поиск по содержимому файлов (grep)
        
        Args:
            query: Строка или regex для поиска
            path: Директория для поиска
            file_pattern: Паттерн имён файлов (*.py, *.js)
            is_regex: Использовать regex
            case_sensitive: Чувствительность к регистру
            max_results: Максимум результатов
            
        Returns:
            {success, results: [SearchResult], total_matches, error}
        """
        try:
            resolved = self._resolve_path(path)
            
            if not self._is_safe_path(str(resolved)):
                return {"success": False, "error": "Доступ запрещён"}
            
            if not resolved.exists():
                return {"success": False, "error": f"Путь не найден: {path}"}
            
            # Компилируем паттерн
            flags = 0 if case_sensitive else re.IGNORECASE
            if is_regex:
                pattern = re.compile(query, flags)
            else:
                pattern = re.compile(re.escape(query), flags)
            
            results: List[SearchResult] = []
            files_searched = 0
            
            # Рекурсивный поиск
            if resolved.is_file():
                files_to_search = [resolved]
            else:
                files_to_search = self._get_files_recursive(resolved, file_pattern)
            
            for file_path in files_to_search:
                if len(results) >= max_results:
                    break
                
                if not self._is_text_file(file_path):
                    continue
                
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    lines = content.split('\n')
                    files_searched += 1
                    
                    for line_num, line in enumerate(lines, 1):
                        if len(results) >= max_results:
                            break
                        
                        match = pattern.search(line)
                        if match:
                            rel_path = str(file_path.relative_to(self.workspace_root))
                            results.append(SearchResult(
                                file_path=rel_path,
                                line_number=line_num,
                                line_content=line.strip()[:200],  # Ограничиваем длину
                                match_start=match.start(),
                                match_end=match.end()
                            ))
                except Exception:
                    continue
            
            self._log_operation("search", str(resolved), True, f"query='{query}', found={len(results)}")
            
            return {
                "success": True,
                "results": [r.to_dict() for r in results],
                "total_matches": len(results),
                "files_searched": files_searched,
                "truncated": len(results) >= max_results
            }
            
        except Exception as e:
            self._log_operation("search", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def _get_files_recursive(self, directory: Path, pattern: str = "*") -> List[Path]:
        """Получает список файлов рекурсивно"""
        files = []
        try:
            for item in directory.rglob(pattern):
                # Пропускаем игнорируемые директории
                if any(ignored in item.parts for ignored in self.IGNORE_DIRS):
                    continue
                if item.is_file():
                    files.append(item)
        except Exception:
            pass
        return files
    
    # ==================== DIRECTORY OPERATIONS ====================
    
    def list_directory(
        self, 
        path: str = ".",
        show_hidden: bool = False,
        recursive: bool = False,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        Список файлов в директории
        
        Args:
            path: Путь к директории
            show_hidden: Показывать скрытые файлы
            recursive: Рекурсивный обход
            max_depth: Максимальная глубина рекурсии
            
        Returns:
            {success, items: [FileInfo], error}
        """
        try:
            resolved = self._resolve_path(path)
            
            if not self._is_safe_path(str(resolved)):
                return {"success": False, "error": "Доступ запрещён"}
            
            if not resolved.exists():
                return {"success": False, "error": f"Путь не найден: {path}"}
            
            if not resolved.is_dir():
                return {"success": False, "error": "Это не директория"}
            
            items = self._list_dir_recursive(resolved, show_hidden, recursive, max_depth, 0)
            
            self._log_operation("list", str(resolved), True, f"items={len(items)}")
            
            return {
                "success": True,
                "items": [i.to_dict() for i in items],
                "path": str(resolved),
                "total_items": len(items)
            }
            
        except Exception as e:
            self._log_operation("list", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def _list_dir_recursive(
        self, 
        directory: Path, 
        show_hidden: bool,
        recursive: bool,
        max_depth: int,
        current_depth: int
    ) -> List[FileInfo]:
        """Рекурсивный список директории"""
        items = []
        
        try:
            for item in sorted(directory.iterdir()):
                # Пропускаем скрытые
                if not show_hidden and item.name.startswith('.'):
                    continue
                
                # Пропускаем игнорируемые директории
                if item.is_dir() and item.name in self.IGNORE_DIRS:
                    continue
                
                try:
                    stat = item.stat()
                    rel_path = str(item.relative_to(self.workspace_root))
                    
                    info = FileInfo(
                        path=rel_path,
                        name=item.name,
                        extension=item.suffix,
                        size=stat.st_size,
                        is_directory=item.is_dir(),
                        modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
                    )
                    items.append(info)
                    
                    # Рекурсия
                    if recursive and item.is_dir() and current_depth < max_depth:
                        items.extend(self._list_dir_recursive(
                            item, show_hidden, recursive, max_depth, current_depth + 1
                        ))
                except Exception:
                    continue
                    
        except Exception:
            pass
        
        return items
    
    def get_project_structure(self, max_depth: int = 3) -> Dict[str, Any]:
        """
        Получает структуру проекта в виде дерева
        
        Returns:
            {success, tree: {...}, stats: {...}}
        """
        try:
            tree = self._build_tree(self.workspace_root, max_depth, 0)
            
            # Статистика
            stats = self._calculate_stats(self.workspace_root)
            
            return {
                "success": True,
                "tree": tree,
                "stats": stats,
                "root": str(self.workspace_root)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _build_tree(self, directory: Path, max_depth: int, current_depth: int) -> Dict:
        """Строит дерево директории"""
        tree = {
            "name": directory.name or str(directory),
            "type": "directory",
            "children": []
        }
        
        if current_depth >= max_depth:
            tree["truncated"] = True
            return tree
        
        try:
            items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            
            for item in items:
                if item.name.startswith('.') or item.name in self.IGNORE_DIRS:
                    continue
                
                if item.is_dir():
                    child = self._build_tree(item, max_depth, current_depth + 1)
                else:
                    child = {
                        "name": item.name,
                        "type": "file",
                        "extension": item.suffix,
                        "size": item.stat().st_size
                    }
                tree["children"].append(child)
                
        except Exception:
            pass
        
        return tree
    
    def _calculate_stats(self, directory: Path) -> Dict:
        """Считает статистику проекта"""
        stats = {
            "total_files": 0,
            "total_dirs": 0,
            "total_size": 0,
            "by_extension": {},
            "languages": []
        }
        
        try:
            for item in directory.rglob("*"):
                if any(ignored in item.parts for ignored in self.IGNORE_DIRS):
                    continue
                
                if item.is_file():
                    stats["total_files"] += 1
                    stats["total_size"] += item.stat().st_size
                    
                    ext = item.suffix.lower() or "no_extension"
                    stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + 1
                elif item.is_dir():
                    stats["total_dirs"] += 1
            
            # Определяем основные языки
            lang_map = {
                '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
                '.java': 'Java', '.go': 'Go', '.rs': 'Rust', '.rb': 'Ruby',
                '.cpp': 'C++', '.c': 'C', '.cs': 'C#', '.php': 'PHP'
            }
            for ext, count in sorted(stats["by_extension"].items(), key=lambda x: -x[1])[:5]:
                if ext in lang_map:
                    stats["languages"].append({"name": lang_map[ext], "files": count})
                    
        except Exception:
            pass
        
        return stats
    
    # ==================== WRITE OPERATIONS ====================
    
    def write_file(self, path: str, content: str, create_dirs: bool = True) -> Dict[str, Any]:
        """
        Записывает содержимое в файл
        
        Args:
            path: Путь к файлу
            content: Содержимое
            create_dirs: Создавать директории если нужно
            
        Returns:
            {success, path, size, error}
        """
        try:
            resolved = self._resolve_path(path)
            
            if not self._is_safe_path(str(resolved)):
                return {"success": False, "error": "Доступ запрещён: путь вне workspace"}
            
            # Создаём директории
            if create_dirs:
                resolved.parent.mkdir(parents=True, exist_ok=True)
            
            # Сохраняем старое содержимое для diff
            old_content = ""
            if resolved.exists():
                try:
                    old_content = resolved.read_text(encoding='utf-8')
                except Exception:
                    pass
            
            # Записываем
            resolved.write_text(content, encoding='utf-8')
            
            self._log_operation("write", str(resolved), True, f"size={len(content)}")
            
            return {
                "success": True,
                "path": str(resolved),
                "relative_path": str(resolved.relative_to(self.workspace_root)),
                "size": len(content),
                "created": not bool(old_content),
                "diff": self._generate_diff(old_content, content) if old_content else None
            }
            
        except Exception as e:
            self._log_operation("write", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def edit_file(
        self, 
        path: str, 
        old_text: str, 
        new_text: str
    ) -> Dict[str, Any]:
        """
        Редактирует файл, заменяя old_text на new_text
        
        Args:
            path: Путь к файлу
            old_text: Текст для замены
            new_text: Новый текст
            
        Returns:
            {success, path, diff, error}
        """
        try:
            # Сначала читаем файл
            read_result = self.read_file(path)
            if not read_result["success"]:
                return read_result
            
            content = read_result["content"]
            
            # Проверяем, что old_text существует
            if old_text not in content:
                return {
                    "success": False, 
                    "error": "Текст для замены не найден в файле",
                    "hint": "Убедитесь, что old_text точно соответствует содержимому файла"
                }
            
            # Считаем количество вхождений
            occurrences = content.count(old_text)
            if occurrences > 1:
                return {
                    "success": False,
                    "error": f"Найдено {occurrences} вхождений. Укажите больше контекста для уникальной замены."
                }
            
            # Заменяем
            new_content = content.replace(old_text, new_text, 1)
            
            # Записываем
            return self.write_file(path, new_content)
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def create_file(self, path: str, content: str = "") -> Dict[str, Any]:
        """Создаёт новый файл"""
        resolved = self._resolve_path(path)
        
        if resolved.exists():
            return {"success": False, "error": f"Файл уже существует: {path}"}
        
        return self.write_file(path, content)
    
    def delete_file(self, path: str) -> Dict[str, Any]:
        """Удаляет файл"""
        try:
            resolved = self._resolve_path(path)
            
            if not self._is_safe_path(str(resolved)):
                return {"success": False, "error": "Доступ запрещён"}
            
            if not resolved.exists():
                return {"success": False, "error": f"Файл не найден: {path}"}
            
            if resolved.is_dir():
                return {"success": False, "error": "Используйте delete_directory для директорий"}
            
            resolved.unlink()
            
            self._log_operation("delete", str(resolved), True)
            
            return {"success": True, "path": str(resolved)}
            
        except Exception as e:
            self._log_operation("delete", path, False, str(e))
            return {"success": False, "error": str(e)}
    
    def _generate_diff(self, old: str, new: str) -> str:
        """Генерирует простой diff"""
        old_lines = old.split('\n')
        new_lines = new.split('\n')
        
        diff_lines = []
        
        # Простой diff (не unified, для наглядности)
        import difflib
        differ = difflib.unified_diff(
            old_lines, new_lines,
            fromfile='before', tofile='after',
            lineterm=''
        )
        
        return '\n'.join(differ)
    
    # ==================== BATCH OPERATIONS ====================
    
    def apply_edits(self, edits: List[Dict]) -> Dict[str, Any]:
        """
        Применяет несколько правок атомарно
        
        Args:
            edits: [{path, old_text, new_text}, ...]
            
        Returns:
            {success, results: [...], error}
        """
        results = []
        
        # Сначала проверяем все правки
        for edit in edits:
            path = edit.get("path")
            old_text = edit.get("old_text")
            
            read_result = self.read_file(path)
            if not read_result["success"]:
                return {
                    "success": False,
                    "error": f"Не удалось прочитать {path}: {read_result['error']}",
                    "failed_at": path
                }
            
            if old_text and old_text not in read_result["content"]:
                return {
                    "success": False,
                    "error": f"Текст не найден в {path}",
                    "failed_at": path
                }
        
        # Применяем все правки
        for edit in edits:
            result = self.edit_file(
                edit["path"],
                edit.get("old_text", ""),
                edit.get("new_text", "")
            )
            results.append({
                "path": edit["path"],
                "success": result["success"],
                "error": result.get("error")
            })
            
            if not result["success"]:
                return {
                    "success": False,
                    "results": results,
                    "error": f"Ошибка при редактировании {edit['path']}"
                }
        
        return {
            "success": True,
            "results": results,
            "total_edits": len(edits)
        }
    
    def get_operations_log(self, limit: int = 50) -> List[Dict]:
        """Возвращает лог операций"""
        return self.operations_log[-limit:]
