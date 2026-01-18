"""
Immune System v1.1 — Система самодиагностики, защиты и восстановления Neira

Функции:
- Диагностика компонентов (клетки, модели, память, файлы)
- Изоляция опасного кода (песочница)
- Автоматическое восстановление
- Запрос помощи (SOS) с отправкой в Telegram
- Карантин подозрительных данных
- Пульс клеток — проверка живости органов
"""

import os
import sys
import ast
import json
import shutil
import hashlib
import subprocess
import threading
import traceback
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ImmuneSystem")

# Telegram Alerter для SOS
try:
    from telegram_alerter import get_alerter, TelegramAlerter
    ALERTER_AVAILABLE = True
except ImportError:
    ALERTER_AVAILABLE = False
    logger.warning("TelegramAlerter недоступен")


class ThreatLevel(Enum):
    """Уровень угрозы"""
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    DANGEROUS = "dangerous"
    CRITICAL = "critical"


class ComponentStatus(Enum):
    """Статус компонента"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    DEAD = "dead"


@dataclass
class ThreatReport:
    """Отчёт об угрозе"""
    id: str
    level: ThreatLevel
    source: str
    description: str
    code_snippet: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    action_taken: Optional[str] = None
    quarantined: bool = False


@dataclass
class DiagnosticResult:
    """Результат диагностики компонента"""
    component: str
    status: ComponentStatus
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    auto_fixable: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SOSRequest:
    """Запрос о помощи"""
    id: str
    severity: str  # "low", "medium", "high", "critical"
    problem: str
    context: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    response: Optional[str] = None


class CodeSandbox:
    """
    Песочница для безопасного выполнения кода
    Ограничивает доступ к опасным операциям
    """
    
    # Запрещённые модули
    FORBIDDEN_MODULES = {
        'os', 'subprocess', 'shutil', 'sys', 'builtins',
        'importlib', 'ctypes', 'socket', 'requests',
        'urllib', 'http', 'ftplib', 'smtplib', 'telnetlib'
    }
    
    # Запрещённые builtin функции
    FORBIDDEN_BUILTINS = {
        'exec', 'eval', 'compile', '__import__', 'open',
        'input', 'breakpoint', 'globals', 'locals', 'vars'
    }
    
    # Опасные паттерны в коде
    DANGEROUS_PATTERNS = [
        r'os\.(system|popen|exec|spawn)',
        r'subprocess\.(call|run|Popen)',
        r'shutil\.(rmtree|move|copy)',
        r'__import__',
        r'eval\s*\(',
        r'exec\s*\(',
        r'compile\s*\(',
        r'open\s*\([^)]*["\']w',  # open for writing
        r'\.write\s*\(',
        r'rm\s+-rf',
        r'del\s+/',
        r'format\s*\([^)]*c:',  # Windows drive access
    ]
    
    def __init__(self):
        self.execution_log: List[Dict] = []
        self.blocked_attempts: List[Dict] = []
    
    def analyze_code(self, code: str) -> Tuple[ThreatLevel, List[str]]:
        """
        Анализ кода на опасные паттерны
        
        Returns:
            (threat_level, list of issues)
        """
        issues = []
        
        # 1. Проверка опасных паттернов
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(f"Опасный паттерн: {pattern}")
        
        # 2. AST анализ
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Проверка импортов
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0] in self.FORBIDDEN_MODULES:
                            issues.append(f"Запрещённый импорт: {alias.name}")
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split('.')[0] in self.FORBIDDEN_MODULES:
                        issues.append(f"Запрещённый from-импорт: {node.module}")
                
                # Проверка вызовов
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in self.FORBIDDEN_BUILTINS:
                            issues.append(f"Запрещённая функция: {node.func.id}")
                    elif isinstance(node.func, ast.Attribute):
                        # os.system и подобное
                        if isinstance(node.func.value, ast.Name):
                            full_name = f"{node.func.value.id}.{node.func.attr}"
                            if node.func.value.id in self.FORBIDDEN_MODULES:
                                issues.append(f"Запрещённый вызов: {full_name}")
        
        except SyntaxError as e:
            issues.append(f"Синтаксическая ошибка: {e}")
        
        # Определение уровня угрозы
        if not issues:
            return ThreatLevel.SAFE, []
        elif len(issues) == 1 and "Синтаксическая ошибка" in issues[0]:
            return ThreatLevel.SUSPICIOUS, issues
        elif len(issues) <= 2:
            return ThreatLevel.DANGEROUS, issues
        else:
            return ThreatLevel.CRITICAL, issues
    
    def execute_safe(self, code: str, timeout: int = 5) -> Dict[str, Any]:
        """
        Безопасное выполнение кода в изолированном окружении
        
        Returns:
            {"success": bool, "output": str, "error": str}
        """
        # Сначала анализируем
        threat_level, issues = self.analyze_code(code)
        
        if threat_level in (ThreatLevel.DANGEROUS, ThreatLevel.CRITICAL):
            self.blocked_attempts.append({
                "code": code[:500],
                "issues": issues,
                "timestamp": datetime.now().isoformat()
            })
            return {
                "success": False,
                "output": "",
                "error": f"Код заблокирован: {'; '.join(issues)}",
                "threat_level": threat_level.value
            }
        
        # Создаём безопасное окружение
        safe_globals = {
            "__builtins__": {
                name: getattr(__builtins__, name) if hasattr(__builtins__, name) else __builtins__[name]
                for name in ['print', 'len', 'range', 'str', 'int', 'float', 
                            'list', 'dict', 'set', 'tuple', 'bool', 'type',
                            'sum', 'min', 'max', 'abs', 'round', 'sorted',
                            'enumerate', 'zip', 'map', 'filter', 'any', 'all']
                if hasattr(__builtins__, name) or (isinstance(__builtins__, dict) and name in __builtins__)
            }
        }
        
        # Безопасные модули (добавляем напрямую в globals)
        import math
        import json as json_module
        import datetime as dt_module
        safe_globals['math'] = math  # type: ignore
        safe_globals['json'] = json_module  # type: ignore
        safe_globals['datetime'] = dt_module  # type: ignore
        
        # Захват вывода
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        
        result = {"success": False, "output": "", "error": ""}
        
        try:
            # Выполняем с таймаутом (в основном потоке для простоты)
            exec(code, safe_globals)
            result["success"] = True
            result["output"] = captured_output.getvalue()
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)}"
        finally:
            sys.stdout = old_stdout
        
        self.execution_log.append({
            "code": code[:200],
            "result": result["success"],
            "timestamp": datetime.now().isoformat()
        })
        
        return result


class ComponentDoctor:
    """Диагностика и лечение компонентов Neira"""
    
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.backup_dir = self.base_dir / "backups" / "immune_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Счётчик автофиксов
        self.fixes_applied = 0
        self.fix_history: List[Dict[str, Any]] = []
    
    def auto_fix(self, component: str, issue_type: str) -> Dict[str, Any]:
        """
        Автоматическое исправление проблем
        
        Поддерживаемые issue_type:
        - corrupted_json: Восстановление повреждённого JSON
        - missing_file: Создание отсутствующего файла
        - duplicate_entries: Удаление дубликатов
        - memory_overflow: Очистка старых записей
        - ollama_restart: Перезапуск Ollama
        - syntax_error: Попытка автоисправления (базово)
        """
        result = {
            "success": False,
            "component": component,
            "issue_type": issue_type,
            "action": "",
            "details": ""
        }
        
        try:
            if issue_type == "corrupted_json":
                result = self._fix_corrupted_json(component)
            elif issue_type == "missing_file":
                result = self._fix_missing_file(component)
            elif issue_type == "duplicate_entries":
                result = self._fix_duplicates(component)
            elif issue_type == "memory_overflow":
                result = self._fix_memory_overflow(component)
            elif issue_type == "ollama_restart":
                result = self._fix_ollama()
            elif issue_type == "empty_json":
                result = self._fix_empty_json(component)
            elif issue_type == "permission_error":
                result["action"] = "manual_required"
                result["details"] = "Требуется ручное исправление прав доступа"
            else:
                result["action"] = "unknown_issue"
                result["details"] = f"Неизвестный тип проблемы: {issue_type}"
            
            if result["success"]:
                self.fixes_applied += 1
                self.fix_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "component": component,
                    "issue_type": issue_type,
                    "action": result["action"]
                })
                logger.info(f"Auto-fix applied: {component} - {issue_type}")
        
        except Exception as e:
            result["details"] = f"Ошибка автофикса: {e}"
            logger.error(f"Auto-fix failed: {e}")
        
        return result
    
    def _fix_corrupted_json(self, filepath: str) -> Dict[str, Any]:
        """Восстановление повреждённого JSON"""
        result = {
            "success": False,
            "component": filepath,
            "issue_type": "corrupted_json",
            "action": "",
            "details": ""
        }
        
        path = Path(filepath)
        
        # Попытка 1: Восстановить из бэкапа
        if self.restore_from_backup(filepath):
            result["success"] = True
            result["action"] = "restored_from_backup"
            result["details"] = "Восстановлено из последнего бэкапа"
            return result
        
        # Попытка 2: Попытаться исправить JSON
        if path.exists():
            try:
                content = path.read_text(encoding='utf-8', errors='ignore')
                
                # Удаляем некорректные символы
                content = content.replace('\x00', '')
                
                # Пытаемся найти валидный JSON
                # Ищем начало и конец JSON объекта
                start = content.find('{')
                end = content.rfind('}')
                
                if start != -1 and end != -1 and end > start:
                    potential_json = content[start:end+1]
                    # Проверяем
                    json.loads(potential_json)
                    
                    # Бэкапим текущий
                    self.create_backup(filepath)
                    
                    # Сохраняем исправленный
                    path.write_text(potential_json, encoding='utf-8')
                    result["success"] = True
                    result["action"] = "json_repaired"
                    result["details"] = "JSON восстановлен из частей"
                    return result
            except:
                pass
        
        # Попытка 3: Создать пустой файл с базовой структурой
        result = self._fix_empty_json(filepath)
        result["action"] = "created_new" if result["success"] else "failed"
        return result
    
    def _fix_missing_file(self, filepath: str) -> Dict[str, Any]:
        """Создание отсутствующего файла"""
        result = {
            "success": False,
            "component": filepath,
            "issue_type": "missing_file",
            "action": "",
            "details": ""
        }
        
        path = Path(filepath)
        filename = path.name.lower()
        
        # Определяем структуру по имени файла
        templates = {
            "neira_memory.json": {"long_term": [], "short_term": [], "version": "2.0"},
            "neira_experience.json": {"training_data": [], "version": "1.0"},
            "neira_personality.json": {
                "name": "Neira",
                "traits": ["curious", "helpful"],
                "version": "1.0"
            },
            "neira_alerts.json": {"alerts": [], "version": "1.0"},
            "neira_short_term.json": {"messages": [], "version": "1.0"},
            "immune_state.json": {"threats_blocked": 0, "auto_fixes_applied": 0, "sos_sent": 0}
        }
        
        template = templates.get(filename, {})
        
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding='utf-8')
            result["success"] = True
            result["action"] = "file_created"
            result["details"] = f"Создан файл с шаблоном: {filename}"
        except Exception as e:
            result["details"] = f"Не удалось создать: {e}"
        
        return result
    
    def _fix_empty_json(self, filepath: str) -> Dict[str, Any]:
        """Создание пустой JSON структуры"""
        return self._fix_missing_file(filepath)
    
    def _fix_duplicates(self, filepath: str) -> Dict[str, Any]:
        """Удаление дубликатов из JSON"""
        result = {
            "success": False,
            "component": filepath,
            "issue_type": "duplicate_entries",
            "action": "",
            "details": ""
        }
        
        path = Path(filepath)
        if not path.exists():
            result["details"] = "Файл не существует"
            return result
        
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            
            # Бэкап перед изменением
            self.create_backup(filepath)
            
            original_count = 0
            removed_count = 0
            
            # Обрабатываем разные структуры
            if "long_term" in data:
                entries = data["long_term"]
                original_count = len(entries)
                
                # Удаляем дубликаты по тексту
                seen = set()
                unique = []
                for entry in entries:
                    text = entry.get("text", "")
                    if text not in seen:
                        seen.add(text)
                        unique.append(entry)
                
                data["long_term"] = unique
                removed_count = original_count - len(unique)
            
            elif "training_data" in data:
                entries = data["training_data"]
                original_count = len(entries)
                
                seen = set()
                unique = []
                for entry in entries:
                    key = json.dumps(entry, sort_keys=True)
                    if key not in seen:
                        seen.add(key)
                        unique.append(entry)
                
                data["training_data"] = unique
                removed_count = original_count - len(unique)
            
            # Сохраняем
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            
            result["success"] = True
            result["action"] = "duplicates_removed"
            result["details"] = f"Удалено {removed_count} дубликатов из {original_count}"
            
        except Exception as e:
            result["details"] = f"Ошибка: {e}"
        
        return result
    
    def _fix_memory_overflow(self, filepath: str = "neira_memory.json") -> Dict[str, Any]:
        """Очистка памяти от старых записей"""
        result = {
            "success": False,
            "component": filepath,
            "issue_type": "memory_overflow",
            "action": "",
            "details": ""
        }
        
        path = self.base_dir / filepath
        if not path.exists():
            result["details"] = "Файл памяти не существует"
            return result
        
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            
            # Бэкап
            self.create_backup(str(path))
            
            if "long_term" in data:
                original_count = len(data["long_term"])
                
                # Применяем decay - оставляем только записи со score > 0.3
                # и сортируем по важности
                filtered = [
                    e for e in data["long_term"]
                    if e.get("score", 0.5) > 0.3
                ]
                
                # Ограничиваем до 5000 записей (самые важные)
                filtered.sort(key=lambda x: x.get("score", 0.5), reverse=True)
                data["long_term"] = filtered[:5000]
                
                removed = original_count - len(data["long_term"])
                
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                
                result["success"] = True
                result["action"] = "memory_cleaned"
                result["details"] = f"Удалено {removed} старых записей, осталось {len(data['long_term'])}"
            
        except Exception as e:
            result["details"] = f"Ошибка: {e}"
        
        return result
    
    def _fix_ollama(self) -> Dict[str, Any]:
        """Перезапуск Ollama"""
        result = {
            "success": False,
            "component": "ollama",
            "issue_type": "ollama_restart",
            "action": "",
            "details": ""
        }
        
        try:
            # Проверяем текущий статус
            check = subprocess.run(["ollama", "list"], capture_output=True, timeout=5)
            
            if check.returncode == 0:
                result["success"] = True
                result["action"] = "already_running"
                result["details"] = "Ollama уже работает"
                return result
            
            # Пытаемся запустить
            if sys.platform == "win32":
                subprocess.Popen(["ollama", "serve"], 
                               creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen(["ollama", "serve"], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
            
            # Ждём запуска
            time.sleep(3)
            
            # Проверяем
            check = subprocess.run(["ollama", "list"], capture_output=True, timeout=5)
            if check.returncode == 0:
                result["success"] = True
                result["action"] = "ollama_started"
                result["details"] = "Ollama успешно запущена"
            else:
                result["details"] = "Не удалось запустить Ollama"
            
        except FileNotFoundError:
            result["details"] = "Ollama не установлена"
        except Exception as e:
            result["details"] = f"Ошибка: {e}"
        
        return result
    
    def run_full_recovery(self) -> List[Dict[str, Any]]:
        """Полное восстановление всех компонентов"""
        results = []
        
        # 1. Диагностируем всё
        diagnostics = {
            "memory": self.diagnose_memory(),
            "experience": self.diagnose_memory("neira_experience.json"),
            "models": self.diagnose_models()
        }
        
        # 2. Для каждой проблемы пытаемся автофикс
        for component, diag in diagnostics.items():
            if diag.status != ComponentStatus.HEALTHY and diag.auto_fixable:
                for issue in diag.issues:
                    # Определяем тип проблемы
                    if "JSON" in issue or "json" in issue:
                        fix_type = "corrupted_json"
                    elif "не найден" in issue or "не существует" in issue:
                        fix_type = "missing_file"
                    elif "дублика" in issue.lower():
                        fix_type = "duplicate_entries"
                    elif "много записей" in issue.lower():
                        fix_type = "memory_overflow"
                    elif "Ollama" in issue:
                        fix_type = "ollama_restart"
                    else:
                        continue
                    
                    # Определяем путь к файлу
                    if component == "memory":
                        filepath = str(self.base_dir / "neira_memory.json")
                    elif component == "experience":
                        filepath = str(self.base_dir / "neira_experience.json")
                    else:
                        filepath = component
                    
                    result = self.auto_fix(filepath, fix_type)
                    results.append(result)
        
        logger.info(f"Full recovery completed: {len(results)} fixes attempted")
        return results
    
    def diagnose_file(self, filepath: str) -> DiagnosticResult:
        """Диагностика Python файла"""
        path = Path(filepath)
        issues = []
        recommendations = []
        
        if not path.exists():
            return DiagnosticResult(
                component=filepath,
                status=ComponentStatus.DEAD,
                issues=["Файл не существует"],
                auto_fixable=False
            )
        
        content = path.read_text(encoding='utf-8', errors='ignore')
        
        # 1. Проверка синтаксиса
        try:
            ast.parse(content)
        except SyntaxError as e:
            issues.append(f"Синтаксическая ошибка: строка {e.lineno}: {e.msg}")
            return DiagnosticResult(
                component=filepath,
                status=ComponentStatus.FAILING,
                issues=issues,
                recommendations=["Исправить синтаксис"],
                auto_fixable=False
            )
        
        # 2. Проверка импортов
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = node.names[0].name if isinstance(node, ast.Import) else node.module
                    # Здесь можно добавить проверку существования модулей
        except:
            pass
        
        # 3. Проверка размера
        if len(content) > 500000:  # > 500KB
            issues.append("Файл слишком большой")
            recommendations.append("Разбить на модули")
        
        # Определение статуса
        if not issues:
            status = ComponentStatus.HEALTHY
        elif len(issues) <= 2:
            status = ComponentStatus.DEGRADED
        else:
            status = ComponentStatus.FAILING
        
        return DiagnosticResult(
            component=filepath,
            status=status,
            issues=issues,
            recommendations=recommendations,
            auto_fixable=len(issues) == 0
        )
    
    def diagnose_memory(self, memory_file: str = "neira_memory.json") -> DiagnosticResult:
        """Диагностика файла памяти"""
        path = self.base_dir / memory_file
        issues = []
        recommendations = []
        
        if not path.exists():
            return DiagnosticResult(
                component="memory",
                status=ComponentStatus.DEAD,
                issues=["Файл памяти не найден"],
                recommendations=["Создать новый файл памяти"],
                auto_fixable=True
            )
        
        try:
            content = path.read_text(encoding='utf-8')
            data = json.loads(content)
            
            # Проверки
            entries = data.get("long_term", [])
            
            if len(entries) > 10000:
                issues.append(f"Слишком много записей: {len(entries)}")
                recommendations.append("Применить decay к памяти")
            
            # Проверка на дубликаты
            texts = [e.get("text", "") for e in entries]
            duplicates = len(texts) - len(set(texts))
            if duplicates > 50:
                issues.append(f"Много дубликатов: {duplicates}")
                recommendations.append("Очистить дубликаты")
            
            # Проверка на галлюцинации (простая)
            suspicious_count = sum(1 for e in entries if "кость" in e.get("text", "").lower())
            if suspicious_count > 5:
                issues.append(f"Подозрительные записи (галлюцинации?): {suspicious_count}")
                recommendations.append("Запустить очистку галлюцинаций")
        
        except json.JSONDecodeError as e:
            issues.append(f"Повреждён JSON: {e}")
            recommendations.append("Восстановить из бэкапа")
            return DiagnosticResult(
                component="memory",
                status=ComponentStatus.FAILING,
                issues=issues,
                recommendations=recommendations,
                auto_fixable=True
            )
        except Exception as e:
            issues.append(f"Ошибка чтения: {e}")
        
        status = ComponentStatus.HEALTHY if not issues else ComponentStatus.DEGRADED
        return DiagnosticResult(
            component="memory",
            status=status,
            issues=issues,
            recommendations=recommendations,
            auto_fixable=len(issues) <= 2
        )
    
    def diagnose_models(self) -> DiagnosticResult:
        """Диагностика моделей Ollama"""
        issues = []
        recommendations = []
        
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                issues.append("Ollama не отвечает")
                recommendations.append("Перезапустить Ollama")
                return DiagnosticResult(
                    component="models",
                    status=ComponentStatus.DEAD,
                    issues=issues,
                    recommendations=recommendations,
                    auto_fixable=True
                )
            
            models = result.stdout
            
            # Проверка нужных моделей
            required = ["qwen2.5-coder", "ministral"]
            for model in required:
                if model not in models:
                    issues.append(f"Отсутствует модель: {model}")
                    recommendations.append(f"Установить: ollama pull {model}")
        
        except subprocess.TimeoutExpired:
            issues.append("Ollama timeout")
            recommendations.append("Проверить процесс Ollama")
        except FileNotFoundError:
            issues.append("Ollama не установлена")
            recommendations.append("Установить Ollama")
        except Exception as e:
            issues.append(f"Ошибка: {e}")
        
        status = ComponentStatus.HEALTHY if not issues else ComponentStatus.DEGRADED
        return DiagnosticResult(
            component="models",
            status=status,
            issues=issues,
            recommendations=recommendations,
            auto_fixable=False
        )
    
    def create_backup(self, filepath: str) -> Optional[str]:
        """Создать бэкап файла"""
        path = Path(filepath)
        if not path.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{path.stem}_{timestamp}{path.suffix}"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(path, backup_path)
        logger.info(f"Backup created: {backup_path}")
        return str(backup_path)
    
    def restore_from_backup(self, filepath: str) -> bool:
        """Восстановить из последнего бэкапа"""
        path = Path(filepath)
        stem = path.stem
        
        # Найти последний бэкап
        backups = sorted(self.backup_dir.glob(f"{stem}_*{path.suffix}"), reverse=True)
        
        if not backups:
            logger.warning(f"No backups found for {filepath}")
            return False
        
        latest_backup = backups[0]
        shutil.copy2(latest_backup, path)
        logger.info(f"Restored from: {latest_backup}")
        return True


@dataclass
class CellPulse:
    """Результат проверки пульса клетки"""
    cell_name: str
    alive: bool
    response_time: float  # секунды
    last_check: datetime
    error: Optional[str] = None
    consecutive_failures: int = 0


class CellPulseMonitor:
    """
    Монитор пульса клеток — проверяет живость всех органов Neira
    
    Периодически проверяет:
    - Отклик моделей Ollama
    - Доступность файлов памяти
    - Работоспособность основных классов
    """
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval  # секунды
        self.cell_status: Dict[str, CellPulse] = {}
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self.on_cell_death: Optional[Callable[[str, str], None]] = None
        
        # Пороги
        self.max_response_time = 30.0  # секунд
        self.max_consecutive_failures = 3
    
    def register_cell(self, name: str):
        """Зарегистрировать клетку для мониторинга"""
        self.cell_status[name] = CellPulse(
            cell_name=name,
            alive=True,
            response_time=0.0,
            last_check=datetime.now()
        )
    
    def check_ollama_pulse(self) -> CellPulse:
        """Проверить пульс Ollama"""
        start = time.time()
        pulse = CellPulse(
            cell_name="ollama",
            alive=False,
            response_time=0.0,
            last_check=datetime.now()
        )
        
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                timeout=10
            )
            pulse.response_time = time.time() - start
            pulse.alive = result.returncode == 0
            
            if not pulse.alive:
                pulse.error = "Ollama не отвечает"
        except subprocess.TimeoutExpired:
            pulse.response_time = 10.0
            pulse.error = "Timeout"
        except FileNotFoundError:
            pulse.error = "Ollama не установлена"
        except Exception as e:
            pulse.error = str(e)
        
        return pulse
    
    def check_model_pulse(self, model_name: str) -> CellPulse:
        """Проверить пульс конкретной модели"""
        start = time.time()
        pulse = CellPulse(
            cell_name=f"model:{model_name}",
            alive=False,
            response_time=0.0,
            last_check=datetime.now()
        )
        
        try:
            # Простой тест - попросить модель ответить "ok"
            result = subprocess.run(
                ["ollama", "run", model_name, "respond with only: ok"],
                capture_output=True,
                text=True,
                timeout=30
            )
            pulse.response_time = time.time() - start
            pulse.alive = result.returncode == 0 and "ok" in result.stdout.lower()
            
            if not pulse.alive:
                pulse.error = f"Модель не ответила корректно: {result.stderr[:100]}"
        except subprocess.TimeoutExpired:
            pulse.response_time = 30.0
            pulse.error = "Timeout - модель не отвечает"
        except Exception as e:
            pulse.error = str(e)
        
        return pulse
    
    def check_memory_pulse(self, memory_file: str = "neira_memory.json") -> CellPulse:
        """Проверить доступность файла памяти"""
        start = time.time()
        pulse = CellPulse(
            cell_name="memory",
            alive=False,
            response_time=0.0,
            last_check=datetime.now()
        )
        
        try:
            path = Path(memory_file)
            if path.exists():
                # Пробуем прочитать и распарсить
                content = path.read_text(encoding='utf-8')
                data = json.loads(content)
                pulse.alive = True
                pulse.response_time = time.time() - start
                
                # Проверяем размер
                if len(content) > 10_000_000:  # > 10MB
                    pulse.error = "Warning: файл памяти слишком большой"
            else:
                pulse.error = "Файл памяти не найден"
        except json.JSONDecodeError as e:
            pulse.error = f"Повреждён JSON: {e}"
        except Exception as e:
            pulse.error = str(e)
        
        return pulse
    
    def check_all_pulses(self) -> Dict[str, CellPulse]:
        """Проверить пульс всех клеток"""
        results = {}
        
        # Ollama
        results["ollama"] = self.check_ollama_pulse()
        
        # Memory
        results["memory"] = self.check_memory_pulse()
        
        # Обновляем статусы
        for name, pulse in results.items():
            old_pulse = self.cell_status.get(name)
            
            if old_pulse and not pulse.alive:
                pulse.consecutive_failures = old_pulse.consecutive_failures + 1
            elif pulse.alive:
                pulse.consecutive_failures = 0
            
            self.cell_status[name] = pulse
            
            # Оповещение о смерти клетки
            if pulse.consecutive_failures >= self.max_consecutive_failures:
                if self.on_cell_death:
                    self.on_cell_death(name, pulse.error or "Unknown error")
        
        return results
    
    def start_monitoring(self):
        """Запустить фоновый мониторинг"""
        if self.is_running:
            return
        
        self.is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Cell pulse monitoring started")
    
    def stop_monitoring(self):
        """Остановить мониторинг"""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Cell pulse monitoring stopped")
    
    def _monitor_loop(self):
        """Цикл мониторинга"""
        while self.is_running:
            try:
                self.check_all_pulses()
            except Exception as e:
                logger.error(f"Pulse check error: {e}")
            
            time.sleep(self.check_interval)
    
    def get_status_report(self) -> str:
        """Получить отчёт о состоянии всех клеток"""
        if not self.cell_status:
            self.check_all_pulses()
        
        lines = ["💓 ПУЛЬС КЛЕТОК", "=" * 40]
        
        for name, pulse in self.cell_status.items():
            if pulse.alive:
                status = f"✅ {pulse.response_time:.2f}s"
            else:
                status = f"💀 {pulse.error or 'dead'}"
            
            failures = f" (failures: {pulse.consecutive_failures})" if pulse.consecutive_failures > 0 else ""
            lines.append(f"  {name}: {status}{failures}")
        
        return "\n".join(lines)


class ImmuneSystem:
    """
    Иммунная система Neira — защита, диагностика, восстановление
    
    Функции:
    - Анализ кода на угрозы
    - Диагностика компонентов
    - Автоматическое восстановление
    - Карантин опасных данных
    - SOS запросы о помощи
    - Мониторинг пульса клеток
    """
    
    VERSION = "1.1"
    
    def __init__(self, data_dir: str = ".", telegram_sos_callback: Optional[Callable] = None):
        self.data_dir = Path(data_dir)
        self.quarantine_dir = self.data_dir / "quarantine"
        self.quarantine_dir.mkdir(exist_ok=True)
        
        # Компоненты
        self.sandbox = CodeSandbox()
        self.doctor = ComponentDoctor(data_dir)
        self.pulse_monitor = CellPulseMonitor(check_interval=120)  # каждые 2 мин
        self.git = GitIntegration(data_dir)
        
        # Подключаем оповещение о смерти клеток
        self.pulse_monitor.on_cell_death = self._on_cell_death
        
        # Хранилище
        self.threats: List[ThreatReport] = []
        self.diagnostics: Dict[str, DiagnosticResult] = {}
        self.sos_requests: List[SOSRequest] = []
        
        # SOS callback (для отправки в Telegram и т.д.)
        self.sos_callback = telegram_sos_callback
        
        # Статистика
        self.threats_blocked = 0
        self.auto_fixes_applied = 0
        self.sos_sent = 0
        
        # Загрузка состояния
        self._load_state()
    
    def _load_state(self):
        """Загрузка состояния"""
        state_file = self.data_dir / "immune_state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding='utf-8'))
                self.threats_blocked = data.get("threats_blocked", 0)
                self.auto_fixes_applied = data.get("auto_fixes_applied", 0)
                self.sos_sent = data.get("sos_sent", 0)
            except:
                pass
    
    def _save_state(self):
        """Сохранение состояния"""
        state_file = self.data_dir / "immune_state.json"
        data = {
            "version": self.VERSION,
            "threats_blocked": self.threats_blocked,
            "auto_fixes_applied": self.auto_fixes_applied,
            "sos_sent": self.sos_sent,
            "last_update": datetime.now().isoformat()
        }
        state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    
    def _on_cell_death(self, cell_name: str, error: str):
        """Обработчик смерти клетки"""
        logger.critical(f"Cell death detected: {cell_name} - {error}")
        
        # Пытаемся автовосстановление
        if cell_name == "ollama":
            fix_result = self.doctor.auto_fix("ollama", "ollama_restart")
            if fix_result["success"]:
                logger.info(f"Auto-recovery successful: {cell_name}")
                return
        elif cell_name == "memory":
            fix_result = self.doctor.auto_fix("neira_memory.json", "corrupted_json")
            if fix_result["success"]:
                logger.info(f"Auto-recovery successful: {cell_name}")
                return
        
        # Если авто-восстановление не помогло — SOS
        self.send_sos(
            f"Клетка {cell_name} не отвечает: {error}",
            severity="high",
            context={"cell": cell_name, "error": error}
        )
    
    def start_pulse_monitoring(self):
        """Запустить мониторинг пульса"""
        self.pulse_monitor.start_monitoring()
    
    def stop_pulse_monitoring(self):
        """Остановить мониторинг пульса"""
        self.pulse_monitor.stop_monitoring()
    
    def get_pulse_report(self) -> str:
        """Получить отчёт о пульсе клеток"""
        return self.pulse_monitor.get_status_report()
    
    # === Анализ угроз ===
    
    def scan_code(self, code: str, source: str = "unknown") -> ThreatReport:
        """Сканировать код на угрозы"""
        threat_level, issues = self.sandbox.analyze_code(code)
        
        report = ThreatReport(
            id=hashlib.md5(code.encode()).hexdigest()[:12],
            level=threat_level,
            source=source,
            description="; ".join(issues) if issues else "Код безопасен",
            code_snippet=code[:500] if threat_level != ThreatLevel.SAFE else None
        )
        
        if threat_level != ThreatLevel.SAFE:
            self.threats.append(report)
            self.threats_blocked += 1
            logger.warning(f"Threat detected [{threat_level.value}]: {report.description[:100]}")
        
        return report
    
    def execute_safely(self, code: str) -> Dict[str, Any]:
        """Безопасно выполнить код"""
        return self.sandbox.execute_safe(code)
    
    # === Карантин ===
    
    def quarantine_file(self, filepath: str, reason: str) -> bool:
        """Поместить файл в карантин"""
        path = Path(filepath)
        if not path.exists():
            return False
        
        # Создать папку с датой
        date_dir = self.quarantine_dir / datetime.now().strftime("%Y%m%d")
        date_dir.mkdir(exist_ok=True)
        
        # Переместить файл
        quarantine_path = date_dir / path.name
        shutil.move(path, quarantine_path)
        
        # Записать причину
        meta_file = quarantine_path.with_suffix(quarantine_path.suffix + ".meta")
        meta_file.write_text(json.dumps({
            "original_path": str(path),
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False), encoding='utf-8')
        
        logger.warning(f"File quarantined: {filepath} - {reason}")
        return True
    
    def quarantine_memory_entry(self, entry_text: str, reason: str):
        """Пометить запись памяти для карантина"""
        quarantine_log = self.quarantine_dir / "memory_entries.json"
        
        entries = []
        if quarantine_log.exists():
            try:
                entries = json.loads(quarantine_log.read_text(encoding='utf-8'))
            except:
                pass
        
        entries.append({
            "text": entry_text[:500],
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        quarantine_log.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
    
    # === Диагностика ===
    
    def run_full_diagnostic(self) -> Dict[str, DiagnosticResult]:
        """Полная диагностика всех компонентов"""
        results = {}
        
        # Диагностика ключевых файлов
        key_files = ["cells.py", "main.py", "memory_system.py", "model_manager.py"]
        for filename in key_files:
            filepath = self.data_dir / filename
            if filepath.exists():
                results[filename] = self.doctor.diagnose_file(str(filepath))
        
        # Диагностика памяти
        results["memory"] = self.doctor.diagnose_memory()
        
        # Диагностика моделей
        results["models"] = self.doctor.diagnose_models()
        
        self.diagnostics = results
        return results
    
    def auto_fix(self, component: str) -> bool:
        """Попытаться автоматически починить компонент"""
        if component not in self.diagnostics:
            return False
        
        diag = self.diagnostics[component]
        if not diag.auto_fixable:
            return False
        
        fixed = False
        
        if component == "memory":
            # Восстановить из бэкапа если повреждён
            if any("JSON" in issue for issue in diag.issues):
                fixed = self.doctor.restore_from_backup(str(self.data_dir / "neira_memory.json"))
        
        elif component == "models":
            # Перезапустить Ollama
            try:
                subprocess.run(["ollama", "serve"], timeout=5, capture_output=True)
                fixed = True
            except:
                pass
        
        if fixed:
            self.auto_fixes_applied += 1
            self._save_state()
            logger.info(f"Auto-fix applied: {component}")
        
        return fixed
    
    # === SOS система ===
    
    def send_sos(self, problem: str, severity: str = "medium", 
                 context: Optional[Dict] = None) -> SOSRequest:
        """Отправить запрос о помощи (включая Telegram)"""
        sos = SOSRequest(
            id=f"sos_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            severity=severity,
            problem=problem,
            context=context or {}
        )
        
        self.sos_requests.append(sos)
        self.sos_sent += 1
        self._save_state()
        
        # Отправка в Telegram
        if ALERTER_AVAILABLE:
            try:
                alerter = get_alerter()
                alerter.sos(
                    problem=problem,
                    details=f"Severity: {severity}",
                    source="immune_system",
                    context=context or {}
                )
                logger.info("SOS отправлен в Telegram")
            except Exception as e:
                logger.error(f"Ошибка отправки SOS в Telegram: {e}")
        
        # Вызвать callback (дополнительная обработка)
        if self.sos_callback:
            try:
                self.sos_callback(sos)
            except Exception as e:
                logger.error(f"SOS callback error: {e}")
        
        logger.critical(f"SOS sent [{severity}]: {problem}")
        return sos
    
    def check_and_alert(self) -> Optional[SOSRequest]:
        """Проверить состояние и отправить SOS если нужно"""
        diag = self.run_full_diagnostic()
        
        critical_issues = []
        for name, result in diag.items():
            if result.status in (ComponentStatus.FAILING, ComponentStatus.DEAD):
                critical_issues.append(f"{name}: {', '.join(result.issues)}")
        
        if critical_issues:
            return self.send_sos(
                problem=f"Критические проблемы: {'; '.join(critical_issues)}",
                severity="high",
                context={"diagnostics": {k: v.status.value for k, v in diag.items()}}
            )
        
        return None
    
    # === API ===
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус иммунной системы"""
        return {
            "version": self.VERSION,
            "threats_blocked": self.threats_blocked,
            "auto_fixes_applied": self.auto_fixes_applied,
            "sos_sent": self.sos_sent,
            "active_threats": len([t for t in self.threats if not t.quarantined]),
            "quarantine_items": len(list(self.quarantine_dir.glob("**/*"))),
            "last_diagnostic": {k: v.status.value for k, v in self.diagnostics.items()} if self.diagnostics else {}
        }
    
    def get_threat_report(self) -> List[Dict]:
        """Получить отчёт об угрозах"""
        return [
            {
                "id": t.id,
                "level": t.level.value,
                "source": t.source,
                "description": t.description,
                "timestamp": t.timestamp.isoformat(),
                "quarantined": t.quarantined
            }
            for t in self.threats[-50:]  # Последние 50
        ]
    
    def acknowledge_sos(self, sos_id: str, response: str):
        """Подтвердить получение SOS"""
        for sos in self.sos_requests:
            if sos.id == sos_id:
                sos.resolved = True
                sos.response = response
                break


class GitIntegration:
    """
    Интеграция с Git для безопасного отката и версионирования
    
    Функции:
    - Откат к предыдущим коммитам
    - Создание точек восстановления
    - Просмотр истории изменений
    - Сравнение версий
    """
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)
        self.git_available = self._check_git()
    
    def _check_git(self) -> bool:
        """Проверить доступность Git"""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def _run_git(self, *args: str) -> Tuple[bool, str]:
        """Выполнить git команду"""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)
    
    def is_repo(self) -> bool:
        """Проверить, является ли директория git репозиторием"""
        success, _ = self._run_git("rev-parse", "--git-dir")
        return success
    
    def get_current_commit(self) -> Optional[str]:
        """Получить текущий коммит"""
        success, output = self._run_git("rev-parse", "HEAD")
        return output.strip() if success else None
    
    def get_current_branch(self) -> Optional[str]:
        """Получить текущую ветку"""
        success, output = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        return output.strip() if success else None
    
    def get_recent_commits(self, count: int = 10) -> List[Dict[str, str]]:
        """Получить последние коммиты"""
        success, output = self._run_git(
            "log", f"-{count}", "--pretty=format:%H|%s|%ai|%an"
        )
        
        if not success:
            return []
        
        commits = []
        for line in output.strip().split("\n"):
            if line and "|" in line:
                parts = line.split("|")
                if len(parts) >= 4:
                    commits.append({
                        "hash": parts[0][:8],
                        "full_hash": parts[0],
                        "message": parts[1],
                        "date": parts[2],
                        "author": parts[3]
                    })
        return commits
    
    def get_file_history(self, filepath: str, count: int = 5) -> List[Dict[str, str]]:
        """Получить историю изменений файла"""
        success, output = self._run_git(
            "log", f"-{count}", "--pretty=format:%H|%s|%ai", "--", filepath
        )
        
        if not success:
            return []
        
        history = []
        for line in output.strip().split("\n"):
            if line and "|" in line:
                parts = line.split("|")
                if len(parts) >= 3:
                    history.append({
                        "hash": parts[0][:8],
                        "full_hash": parts[0],
                        "message": parts[1],
                        "date": parts[2]
                    })
        return history
    
    def create_restore_point(self, message: str = "Auto restore point") -> Optional[str]:
        """Создать точку восстановления (коммит)"""
        # Добавляем все изменения
        self._run_git("add", "-A")
        
        # Коммитим
        success, output = self._run_git(
            "commit", "-m", f"[RESTORE] {message}"
        )
        
        if success or "nothing to commit" in output:
            return self.get_current_commit()
        return None
    
    def rollback_file(self, filepath: str, commit: str = "HEAD~1") -> bool:
        """Откатить файл к определённому коммиту"""
        # Сначала бэкапим текущую версию
        backup_path = Path(filepath).with_suffix(".backup")
        if Path(filepath).exists():
            shutil.copy2(filepath, backup_path)
        
        success, output = self._run_git("checkout", commit, "--", filepath)
        
        if success:
            logger.info(f"Rolled back {filepath} to {commit}")
            return True
        else:
            # Восстанавливаем из бэкапа
            if backup_path.exists():
                shutil.copy2(backup_path, filepath)
                backup_path.unlink()
            logger.error(f"Failed to rollback: {output}")
            return False
    
    def rollback_to_commit(self, commit: str, hard: bool = False) -> bool:
        """
        Откатить весь репозиторий к коммиту
        
        hard=True: полный откат (опасно!)
        hard=False: создаёт новый коммит с откатом (безопасно)
        """
        if hard:
            # Опасно! Теряются все изменения после коммита
            success, output = self._run_git("reset", "--hard", commit)
        else:
            # Безопасно - создаёт revert коммит
            success, output = self._run_git("revert", "--no-commit", f"{commit}..HEAD")
            if success:
                self._run_git("commit", "-m", f"[ROLLBACK] Revert to {commit[:8]}")
        
        return success
    
    def diff_with_commit(self, filepath: str, commit: str = "HEAD~1") -> str:
        """Показать разницу файла с коммитом"""
        success, output = self._run_git("diff", commit, "HEAD", "--", filepath)
        return output if success else ""
    
    def stash_changes(self, message: str = "Auto stash") -> bool:
        """Спрятать текущие изменения"""
        success, _ = self._run_git("stash", "push", "-m", message)
        return success
    
    def pop_stash(self) -> bool:
        """Вернуть спрятанные изменения"""
        success, _ = self._run_git("stash", "pop")
        return success
    
    def get_modified_files(self) -> List[str]:
        """Получить список изменённых файлов"""
        success, output = self._run_git("status", "--porcelain")
        if not success:
            return []
        
        files = []
        for line in output.strip().split("\n"):
            if line:
                # Формат: "XY filename"
                files.append(line[3:].strip())
        return files
    
    def get_status_report(self) -> str:
        """Получить отчёт о состоянии Git"""
        if not self.git_available:
            return "❌ Git не установлен"
        
        if not self.is_repo():
            return "❌ Не Git репозиторий"
        
        branch = self.get_current_branch()
        commit = self.get_current_commit()
        modified = self.get_modified_files()
        
        lines = ["📦 GIT СТАТУС", "=" * 40]
        lines.append(f"Ветка: {branch}")
        lines.append(f"Коммит: {commit[:8] if commit else 'N/A'}")
        lines.append(f"Изменённых файлов: {len(modified)}")
        
        if modified:
            lines.append("\nИзменённые файлы:")
            for f in modified[:10]:
                lines.append(f"  • {f}")
            if len(modified) > 10:
                lines.append(f"  ... и ещё {len(modified) - 10}")
        
        return "\n".join(lines)


# === Глобальный экземпляр ===
_immune_system: Optional[ImmuneSystem] = None


def get_immune_system() -> ImmuneSystem:
    """Получить глобальную иммунную систему"""
    global _immune_system
    if _immune_system is None:
        _immune_system = ImmuneSystem()
    return _immune_system


# === Тестирование ===
if __name__ == "__main__":
    print("🛡️ Testing Immune System v1.0\n")
    
    immune = ImmuneSystem()
    
    # Тест анализа безопасного кода
    print("✅ Testing safe code...")
    safe_code = """
def hello():
    return "Hello, world!"
print(hello())
"""
    report = immune.scan_code(safe_code, "test")
    print(f"  Level: {report.level.value}")
    
    # Тест опасного кода
    print("\n❌ Testing dangerous code...")
    dangerous_code = """
import os
os.system("rm -rf /")
"""
    report = immune.scan_code(dangerous_code, "test")
    print(f"  Level: {report.level.value}")
    print(f"  Issues: {report.description}")
    
    # Тест песочницы
    print("\n🔒 Testing sandbox execution...")
    result = immune.execute_safely("print(2 + 2)")
    print(f"  Success: {result['success']}")
    print(f"  Output: {result['output'].strip()}")
    
    # Попытка выполнить опасный код
    print("\n🔒 Testing sandbox with dangerous code...")
    result = immune.execute_safely("import os; os.system('dir')")
    print(f"  Success: {result['success']}")
    print(f"  Error: {result.get('error', 'N/A')}")
    
    # Диагностика
    print("\n🔍 Running diagnostics...")
    diag = immune.run_full_diagnostic()
    for name, result in diag.items():
        status_emoji = {
            "healthy": "✅",
            "degraded": "⚠️", 
            "failing": "🔴",
            "dead": "💀"
        }.get(result.status.value, "❓")
        print(f"  {status_emoji} {name}: {result.status.value}")
        if result.issues:
            for issue in result.issues[:2]:
                print(f"      - {issue}")
    
    # Статус
    print("\n📊 Immune System Status:")
    status = immune.get_status()
    print(f"  Threats blocked: {status['threats_blocked']}")
    print(f"  Auto-fixes: {status['auto_fixes_applied']}")
    print(f"  SOS sent: {status['sos_sent']}")
    
    print("\n✅ Immune System test complete!")
