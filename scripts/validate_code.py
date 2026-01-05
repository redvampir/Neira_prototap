#!/usr/bin/env python3
"""
Валидатор кода для проекта Neira.
Запускается перед коммитом или вручную для проверки качества.

Использование:
    python scripts/validate_code.py [файлы...]
    python scripts/validate_code.py --all
    python scripts/validate_code.py --staged
"""

import ast
import sys
import subprocess
from pathlib import Path
from typing import NamedTuple

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        pass


class Issue(NamedTuple):
    """Найденная проблема в коде."""
    file: str
    line: int
    severity: str  # ERROR, WARNING
    rule: str
    message: str


# Папки которые игнорируем
IGNORE_DIRS = {
    '__pycache__', '.venv', 'venv', 'ollamy-env', 'node_modules',
    '.git', 'neira-app', 'neira-mobile', 'frontend', 'neira-vscode',
    'build_pdc', '.pytest_cache', '.neira_cache'
}

# Файлы в корне которые разрешены (legacy)
ALLOWED_ROOT_FILES = {
    'main.py', 'neira.py', 'telegram_bot.py', 'neira_server.py',
    'requirements.txt', 'requirements.lock', 'pytest.ini', 'setup.py',
    'conftest.py', 'Modelfile', 'Modelfile_nemotron'
}


def get_project_root() -> Path:
    """Находит корень проекта по наличию .git или AGENTS.md."""
    current = Path(__file__).resolve().parent.parent
    if (current / '.git').exists() or (current / 'AGENTS.md').exists():
        return current
    return Path.cwd()


def check_file_location(filepath: Path, root: Path) -> list[Issue]:
    """Проверяет что файл не в корне проекта."""
    issues = []
    
    if filepath.parent == root:
        if filepath.name.endswith('.py') and filepath.name not in ALLOWED_ROOT_FILES:
            issues.append(Issue(
                file=str(filepath.relative_to(root)),
                line=0,
                severity='WARNING',
                rule='NO_ROOT_FILES',
                message=f'Python файл в корне проекта. Перенеси в neira/ или scripts/'
            ))
    
    return issues


def check_function_length(filepath: Path, root: Path, max_lines: int = 60) -> list[Issue]:
    """Проверяет длину функций."""
    issues = []
    
    try:
        content = filepath.read_text(encoding='utf-8')
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return issues
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if hasattr(node, 'end_lineno') and node.end_lineno:
                length = node.end_lineno - node.lineno + 1
                if length > max_lines:
                    issues.append(Issue(
                        file=str(filepath.relative_to(root)),
                        line=node.lineno,
                        severity='WARNING',
                        rule='LONG_FUNCTION',
                        message=f'Функция `{node.name}` слишком длинная: {length} строк (макс {max_lines})'
                    ))
    
    return issues


def check_bare_except(filepath: Path, root: Path) -> list[Issue]:
    """Находит bare except и except Exception."""
    issues = []
    
    try:
        content = filepath.read_text(encoding='utf-8')
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return issues
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                issues.append(Issue(
                    file=str(filepath.relative_to(root)),
                    line=node.lineno,
                    severity='ERROR',
                    rule='BARE_EXCEPT',
                    message='Bare `except:` запрещён. Укажи конкретные исключения.'
                ))
            elif isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                # Проверяем есть ли хоть какая-то обработка
                has_logging = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Attribute):
                            if child.func.attr in ('warning', 'error', 'exception', 'info'):
                                has_logging = True
                                break
                
                if not has_logging:
                    issues.append(Issue(
                        file=str(filepath.relative_to(root)),
                        line=node.lineno,
                        severity='WARNING',
                        rule='BROAD_EXCEPT',
                        message='`except Exception` без логирования. Добавь logger или конкретизируй исключение.'
                    ))
    
    return issues


def check_magic_numbers(filepath: Path, root: Path) -> list[Issue]:
    """Находит подозрительные magic numbers."""
    issues = []
    
    try:
        content = filepath.read_text(encoding='utf-8')
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return issues
    
    # Числа которые обычно OK
    OK_NUMBERS = {0, 1, 2, -1, 100, 10, 1000}
    
    for node in ast.walk(tree):
        # Проверяем сравнения типа `if x > 500:`
        if isinstance(node, ast.Compare):
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant):
                    val = comparator.value
                    if isinstance(val, (int, float)) and val not in OK_NUMBERS and val > 10:
                        # Проверяем это не константа в начале файла
                        issues.append(Issue(
                            file=str(filepath.relative_to(root)),
                            line=node.lineno,
                            severity='WARNING',
                            rule='MAGIC_NUMBER',
                            message=f'Magic number {val}. Вынеси в константу.'
                        ))
    
    return issues


def check_nesting_depth(filepath: Path, root: Path, max_depth: int = 4) -> list[Issue]:
    """Проверяет глубину вложенности."""
    issues = []
    
    try:
        content = filepath.read_text(encoding='utf-8')
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return issues
    
    def get_depth(node: ast.AST, current: int = 0) -> int:
        """Рекурсивно вычисляет максимальную глубину."""
        max_d = current
        
        nesting_nodes = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)
        
        for child in ast.iter_child_nodes(node):
            if isinstance(child, nesting_nodes):
                child_depth = get_depth(child, current + 1)
                max_d = max(max_d, child_depth)
            else:
                child_depth = get_depth(child, current)
                max_d = max(max_d, child_depth)
        
        return max_d
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            depth = get_depth(node)
            if depth > max_depth:
                issues.append(Issue(
                    file=str(filepath.relative_to(root)),
                    line=node.lineno,
                    severity='WARNING',
                    rule='DEEP_NESTING',
                    message=f'Функция `{node.name}` имеет вложенность {depth} (макс {max_depth})'
                ))
    
    return issues


def check_syntax(filepath: Path, root: Path) -> list[Issue]:
    """Проверяет синтаксис Python."""
    issues = []
    
    result = subprocess.run(
        [sys.executable, '-m', 'py_compile', str(filepath)],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        issues.append(Issue(
            file=str(filepath.relative_to(root)),
            line=0,
            severity='ERROR',
            rule='SYNTAX_ERROR',
            message=result.stderr.strip() or 'Синтаксическая ошибка'
        ))
    
    return issues


def get_staged_files() -> list[Path]:
    """Возвращает список файлов в git staging."""
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
        capture_output=True,
        text=True
    )
    
    files = []
    for line in result.stdout.strip().split('\n'):
        if line.endswith('.py'):
            files.append(Path(line))
    
    return files


def get_all_python_files(root: Path) -> list[Path]:
    """Возвращает все Python файлы в проекте."""
    files = []
    
    for path in root.rglob('*.py'):
        # Пропускаем игнорируемые папки
        if any(ignored in path.parts for ignored in IGNORE_DIRS):
            continue
        files.append(path)
    
    return files


def validate_files(files: list[Path], root: Path) -> list[Issue]:
    """Запускает все проверки на списке файлов."""
    all_issues = []
    
    for filepath in files:
        # Преобразуем в абсолютный путь
        if not filepath.is_absolute():
            filepath = root / filepath
        
        filepath = filepath.resolve()
        
        if not filepath.exists():
            continue
        
        # Проверяем что файл внутри root
        try:
            filepath.relative_to(root.resolve())
        except ValueError:
            # Файл вне проекта - пропускаем
            continue
        
        # Запускаем проверки
        all_issues.extend(check_syntax(filepath, root.resolve()))
        all_issues.extend(check_file_location(filepath, root.resolve()))
        all_issues.extend(check_bare_except(filepath, root.resolve()))
        all_issues.extend(check_function_length(filepath, root.resolve()))
        all_issues.extend(check_nesting_depth(filepath, root.resolve()))
        # check_magic_numbers пока отключен - слишком много false positives
    
    return all_issues


def print_report(issues: list[Issue]) -> int:
    """Выводит отчёт и возвращает код выхода."""
    if not issues:
        print("✅ Все проверки пройдены!")
        return 0
    
    errors = [i for i in issues if i.severity == 'ERROR']
    warnings = [i for i in issues if i.severity == 'WARNING']
    
    print(f"\n{'='*60}")
    print(f"📊 Найдено проблем: {len(errors)} ошибок, {len(warnings)} предупреждений")
    print(f"{'='*60}\n")
    
    for issue in sorted(issues, key=lambda x: (x.severity != 'ERROR', x.file, x.line)):
        icon = '❌' if issue.severity == 'ERROR' else '⚠️'
        loc = f"{issue.file}:{issue.line}" if issue.line else issue.file
        print(f"{icon} [{issue.rule}] {loc}")
        print(f"   {issue.message}\n")
    
    # Ошибки блокируют коммит, предупреждения нет
    return 1 if errors else 0


def main():
    """Точка входа."""
    root = get_project_root()
    
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        return 0
    
    if '--staged' in sys.argv:
        files = get_staged_files()
        if not files:
            print("Нет staged Python файлов для проверки")
            return 0
    elif '--all' in sys.argv:
        files = get_all_python_files(root)
    elif len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:] if f.endswith('.py')]
    else:
        # По умолчанию проверяем staged
        files = get_staged_files()
        if not files:
            print("Использование: python scripts/validate_code.py --all | --staged | файлы...")
            return 0
    
    print(f"🔍 Проверяю {len(files)} файлов...\n")
    
    issues = validate_files(files, root)
    return print_report(issues)


if __name__ == '__main__':
    sys.exit(main())
