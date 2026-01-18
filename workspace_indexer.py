"""
Workspace Indexer — Индексация и семантический поиск по проекту

Функции:
- Индексация файлов проекта
- Извлечение символов (функции, классы, переменные)
- Семантический поиск (с эмбеддингами)
- Кэширование для быстрого доступа

Использует:
- AST парсинг для Python
- Regex для других языков
- Опционально: локальные эмбеддинги (sentence-transformers)
"""

import os
import re
import ast
import json
import hashlib
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger("workspace-indexer")


@dataclass
class Symbol:
    """Символ в коде (функция, класс, переменная)"""
    name: str
    type: str  # function, class, method, variable, constant, import
    file_path: str
    line_start: int
    line_end: int
    signature: str = ""
    docstring: str = ""
    parent: str = ""  # Родительский класс/модуль
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FileIndex:
    """Индекс одного файла"""
    path: str
    language: str
    size: int
    modified: float
    hash: str
    symbols: List[Symbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['symbols'] = [s.to_dict() for s in self.symbols]
        return result


@dataclass
class SearchResult:
    """Результат поиска"""
    symbol: Symbol
    score: float
    context: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol.to_dict(),
            "score": self.score,
            "context": self.context
        }


class WorkspaceIndexer:
    """
    Индексер workspace для семантического поиска
    """
    
    # Расширения для индексации
    LANGUAGE_EXTENSIONS = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascriptreact',
        '.tsx': 'typescriptreact',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
        '.c': 'c',
        '.cpp': 'cpp',
        '.h': 'cpp',
        '.cs': 'csharp',
        '.rb': 'ruby',
        '.php': 'php',
    }
    
    IGNORE_DIRS = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        '.idea', '.vscode', 'dist', 'build', '.next', '.nuxt',
        'target', 'bin', 'obj', '.pytest_cache', '.mypy_cache',
        'coverage', '.coverage', 'htmlcov', 'egg-info', '.tox'
    }
    
    def __init__(self, workspace_root: str, cache_dir: str = None):
        self.workspace_root = Path(workspace_root).resolve()
        self.cache_dir = Path(cache_dir) if cache_dir else self.workspace_root / '.neira_cache'
        
        # Индекс в памяти
        self.index: Dict[str, FileIndex] = {}
        self.symbol_index: Dict[str, List[Symbol]] = defaultdict(list)  # name -> symbols
        
        # Статистика
        self.stats = {
            "total_files": 0,
            "total_symbols": 0,
            "indexed_at": None,
            "languages": {}
        }
        
        # Блокировка для thread-safety
        self._lock = threading.Lock()
        
        # Создаём директорию кэша
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _should_index(self, path: Path) -> bool:
        """Проверяет, нужно ли индексировать файл"""
        if any(ignored in path.parts for ignored in self.IGNORE_DIRS):
            return False
        return path.suffix.lower() in self.LANGUAGE_EXTENSIONS
    
    def _get_file_hash(self, path: Path) -> str:
        """Вычисляет хэш файла"""
        content = path.read_bytes()
        return hashlib.md5(content).hexdigest()
    
    def _detect_language(self, path: Path) -> str:
        """Определяет язык по расширению"""
        return self.LANGUAGE_EXTENSIONS.get(path.suffix.lower(), 'unknown')
    
    # ==================== INDEXING ====================
    
    def index_workspace(self, force: bool = False) -> Dict[str, Any]:
        """
        Индексирует весь workspace
        
        Args:
            force: Переиндексировать все файлы, игнорируя кэш
        """
        with self._lock:
            start_time = datetime.now()
            
            files_indexed = 0
            files_cached = 0
            
            # Находим все файлы для индексации
            for file_path in self.workspace_root.rglob('*'):
                if not file_path.is_file():
                    continue
                if not self._should_index(file_path):
                    continue
                
                rel_path = str(file_path.relative_to(self.workspace_root))
                
                # Проверяем кэш
                if not force and rel_path in self.index:
                    current_hash = self._get_file_hash(file_path)
                    if self.index[rel_path].hash == current_hash:
                        files_cached += 1
                        continue
                
                # Индексируем файл
                try:
                    file_index = self._index_file(file_path)
                    self.index[rel_path] = file_index
                    
                    # Добавляем символы в индекс
                    for symbol in file_index.symbols:
                        self.symbol_index[symbol.name.lower()].append(symbol)
                    
                    files_indexed += 1
                except Exception as e:
                    logger.warning(f"Ошибка индексации {rel_path}: {e}")
            
            # Обновляем статистику
            self.stats["total_files"] = len(self.index)
            self.stats["total_symbols"] = sum(len(fi.symbols) for fi in self.index.values())
            self.stats["indexed_at"] = datetime.now().isoformat()
            self.stats["languages"] = self._count_languages()
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Сохраняем кэш
            self._save_cache()
            
            return {
                "files_indexed": files_indexed,
                "files_cached": files_cached,
                "total_files": len(self.index),
                "total_symbols": self.stats["total_symbols"],
                "elapsed_seconds": round(elapsed, 2),
                "languages": self.stats["languages"]
            }
    
    def _index_file(self, path: Path) -> FileIndex:
        """Индексирует один файл"""
        language = self._detect_language(path)
        content = path.read_text(encoding='utf-8', errors='ignore')
        
        file_index = FileIndex(
            path=str(path.relative_to(self.workspace_root)),
            language=language,
            size=path.stat().st_size,
            modified=path.stat().st_mtime,
            hash=self._get_file_hash(path)
        )
        
        # Парсим символы в зависимости от языка
        if language == 'python':
            file_index.symbols = self._parse_python(content, file_index.path)
            file_index.imports = self._extract_python_imports(content)
        elif language in ('javascript', 'typescript', 'javascriptreact', 'typescriptreact'):
            file_index.symbols = self._parse_javascript(content, file_index.path)
        else:
            file_index.symbols = self._parse_generic(content, file_index.path, language)
        
        return file_index
    
    def _parse_python(self, content: str, file_path: str) -> List[Symbol]:
        """Парсит Python файл через AST"""
        symbols = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._parse_generic(content, file_path, 'python')
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Функция или метод
                parent = ""
                for parent_node in ast.walk(tree):
                    if isinstance(parent_node, ast.ClassDef):
                        if any(isinstance(child, type(node)) and child.name == node.name 
                               for child in ast.walk(parent_node)):
                            parent = parent_node.name
                            break
                
                # Сигнатура
                args = [a.arg for a in node.args.args]
                signature = f"def {node.name}({', '.join(args)})"
                
                # Docstring
                docstring = ast.get_docstring(node) or ""
                
                symbols.append(Symbol(
                    name=node.name,
                    type="method" if parent else "function",
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    signature=signature,
                    docstring=docstring[:500],
                    parent=parent
                ))
            
            elif isinstance(node, ast.ClassDef):
                # Класс
                bases = [b.id if isinstance(b, ast.Name) else str(b) for b in node.bases]
                signature = f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}"
                docstring = ast.get_docstring(node) or ""
                
                symbols.append(Symbol(
                    name=node.name,
                    type="class",
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=node.end_lineno or node.lineno,
                    signature=signature,
                    docstring=docstring[:500]
                ))
            
            elif isinstance(node, ast.Assign):
                # Глобальные переменные/константы
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Проверяем, константа ли это (UPPER_CASE)
                        is_constant = target.id.isupper()
                        symbols.append(Symbol(
                            name=target.id,
                            type="constant" if is_constant else "variable",
                            file_path=file_path,
                            line_start=node.lineno,
                            line_end=node.lineno
                        ))
        
        return symbols
    
    def _extract_python_imports(self, content: str) -> List[str]:
        """Извлекает импорты из Python файла"""
        imports = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        except SyntaxError:
            pass
        return imports
    
    def _parse_javascript(self, content: str, file_path: str) -> List[Symbol]:
        """Парсит JavaScript/TypeScript через regex"""
        symbols = []
        lines = content.split('\n')
        
        # Паттерны для JS/TS
        patterns = [
            # function name() {}
            (r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)', 'function'),
            # const name = () => {}
            (r'^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>', 'function'),
            # class Name {}
            (r'^(?:export\s+)?class\s+(\w+)', 'class'),
            # const NAME = value (constants)
            (r'^(?:export\s+)?const\s+([A-Z_][A-Z0-9_]*)\s*=', 'constant'),
            # interface Name {}
            (r'^(?:export\s+)?interface\s+(\w+)', 'interface'),
            # type Name = 
            (r'^(?:export\s+)?type\s+(\w+)\s*=', 'type'),
        ]
        
        for i, line in enumerate(lines, 1):
            for pattern, symbol_type in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    symbols.append(Symbol(
                        name=match.group(1),
                        type=symbol_type,
                        file_path=file_path,
                        line_start=i,
                        line_end=i,
                        signature=line.strip()[:100]
                    ))
                    break
        
        return symbols
    
    def _parse_generic(self, content: str, file_path: str, language: str) -> List[Symbol]:
        """Универсальный парсер для других языков"""
        symbols = []
        lines = content.split('\n')
        
        # Общие паттерны
        patterns = {
            'function': [
                r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:async)?\s*(?:def|function|func|fn)\s+(\w+)',
                r'^\s*(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\([^)]*\)\s*\{?',
            ],
            'class': [
                r'^\s*(?:public|private|protected)?\s*(?:abstract)?\s*class\s+(\w+)',
                r'^\s*(?:struct|interface|enum)\s+(\w+)',
            ]
        }
        
        for i, line in enumerate(lines, 1):
            for symbol_type, type_patterns in patterns.items():
                for pattern in type_patterns:
                    match = re.match(pattern, line)
                    if match:
                        symbols.append(Symbol(
                            name=match.group(1),
                            type=symbol_type,
                            file_path=file_path,
                            line_start=i,
                            line_end=i,
                            signature=line.strip()[:100]
                        ))
                        break
        
        return symbols
    
    def _count_languages(self) -> Dict[str, int]:
        """Подсчёт файлов по языкам"""
        counts = defaultdict(int)
        for file_index in self.index.values():
            counts[file_index.language] += 1
        return dict(counts)
    
    # ==================== SEARCH ====================
    
    def search_symbols(
        self, 
        query: str, 
        symbol_type: str = None,
        limit: int = 20
    ) -> List[SearchResult]:
        """
        Поиск символов по имени
        
        Args:
            query: Поисковый запрос
            symbol_type: Фильтр по типу (function, class, method, ...)
            limit: Максимум результатов
        """
        results = []
        query_lower = query.lower()
        
        for name, symbols in self.symbol_index.items():
            # Scoring
            if name == query_lower:
                score = 1.0
            elif name.startswith(query_lower):
                score = 0.8
            elif query_lower in name:
                score = 0.5
            else:
                continue
            
            for symbol in symbols:
                if symbol_type and symbol.type != symbol_type:
                    continue
                
                results.append(SearchResult(
                    symbol=symbol,
                    score=score
                ))
        
        # Сортируем по score
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
    
    def find_references(self, symbol_name: str) -> List[Dict]:
        """Находит все использования символа"""
        references = []
        
        for file_path, file_index in self.index.items():
            full_path = self.workspace_root / file_path
            
            try:
                content = full_path.read_text(encoding='utf-8', errors='ignore')
                lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    if re.search(rf'\b{re.escape(symbol_name)}\b', line):
                        references.append({
                            "file": file_path,
                            "line": i,
                            "content": line.strip()[:200]
                        })
            except Exception:
                continue
        
        return references
    
    def get_file_symbols(self, file_path: str) -> List[Symbol]:
        """Символы конкретного файла"""
        if file_path in self.index:
            return self.index[file_path].symbols
        return []
    
    def get_class_methods(self, class_name: str) -> List[Symbol]:
        """Получить все методы класса"""
        methods = []
        for symbols in self.symbol_index.values():
            for symbol in symbols:
                if symbol.type == 'method' and symbol.parent == class_name:
                    methods.append(symbol)
        return methods
    
    # ==================== CONTEXT FOR LLM ====================
    
    def get_relevant_context(
        self, 
        query: str, 
        current_file: str = None,
        max_symbols: int = 10,
        max_files: int = 5
    ) -> str:
        """
        Собирает релевантный контекст для LLM
        
        Returns:
            Строка с контекстом для добавления в промпт
        """
        context_parts = []
        
        # 1. Символы по запросу
        symbols = self.search_symbols(query, limit=max_symbols)
        if symbols:
            context_parts.append("## Релевантные символы в проекте:")
            for result in symbols[:max_symbols]:
                s = result.symbol
                context_parts.append(
                    f"- `{s.name}` ({s.type}) в {s.file_path}:{s.line_start}"
                )
                if s.signature:
                    context_parts.append(f"  ```\n  {s.signature}\n  ```")
                if s.docstring:
                    context_parts.append(f"  > {s.docstring[:200]}...")
        
        # 2. Структура текущего файла
        if current_file and current_file in self.index:
            file_index = self.index[current_file]
            if file_index.symbols:
                context_parts.append(f"\n## Символы в текущем файле ({current_file}):")
                for s in file_index.symbols[:15]:
                    context_parts.append(f"- {s.type}: `{s.name}` (строка {s.line_start})")
        
        # 3. Статистика проекта
        context_parts.append(f"\n## Проект:")
        context_parts.append(f"- Файлов: {self.stats['total_files']}")
        context_parts.append(f"- Символов: {self.stats['total_symbols']}")
        context_parts.append(f"- Языки: {', '.join(self.stats.get('languages', {}).keys())}")
        
        return '\n'.join(context_parts)
    
    # ==================== CACHE ====================
    
    def _save_cache(self):
        """Сохраняет индекс в кэш"""
        cache_file = self.cache_dir / 'index.json'
        
        data = {
            "workspace_root": str(self.workspace_root),
            "indexed_at": self.stats.get("indexed_at"),
            "files": {path: fi.to_dict() for path, fi in self.index.items()}
        }
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_cache(self) -> bool:
        """Загружает индекс из кэша"""
        cache_file = self.cache_dir / 'index.json'
        
        if not cache_file.exists():
            return False
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if data.get("workspace_root") != str(self.workspace_root):
                return False
            
            for path, file_data in data.get("files", {}).items():
                symbols = [Symbol(**s) for s in file_data.get("symbols", [])]
                file_data["symbols"] = symbols
                self.index[path] = FileIndex(**file_data)
                
                for symbol in symbols:
                    self.symbol_index[symbol.name.lower()].append(symbol)
            
            self.stats["indexed_at"] = data.get("indexed_at")
            self.stats["total_files"] = len(self.index)
            self.stats["total_symbols"] = sum(len(fi.symbols) for fi in self.index.values())
            self.stats["languages"] = self._count_languages()
            
            return True
        except Exception as e:
            logger.warning(f"Ошибка загрузки кэша: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Статистика индекса"""
        return {
            **self.stats,
            "cache_loaded": (self.cache_dir / 'index.json').exists()
        }


# Глобальный индексер
_indexer: Optional[WorkspaceIndexer] = None


def get_indexer(workspace_root: str = None) -> WorkspaceIndexer:
    """Получить или создать индексер"""
    global _indexer
    
    if _indexer is None or (workspace_root and str(_indexer.workspace_root) != workspace_root):
        _indexer = WorkspaceIndexer(workspace_root or os.getcwd())
        _indexer._load_cache()
    
    return _indexer
