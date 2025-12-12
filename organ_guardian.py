"""
Organ Guardian v1.0 - Система защиты от вредоносных органов
Многоуровневая защита при сохранении открытости функциональности

ПРИНЦИП: Trust but Verify
- Разрешаем создание органов ВСЕМ пользователям
- Но применяем защиты:
  1. Static Analysis - проверка кода перед выполнением
  2. Sandboxing - ограничение capabilities
  3. Quarantine - карантин новых органов
  4. Monitoring - мониторинг поведения
  5. Human-in-the-loop - админ утверждает критичные органы
"""

import ast
import os
import re
import json
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path


class ThreatLevel(Enum):
    """Уровень угрозы органа"""
    SAFE = "safe"              # Безопасен - запускается сразу
    SUSPICIOUS = "suspicious"  # Подозрителен - в карантин на 24ч
    DANGEROUS = "dangerous"    # Опасен - требует одобрения админа
    CRITICAL = "critical"      # Критичен - блокируется автоматически


class OrganCapability(Enum):
    """Разрешённые возможности органов"""
    # Безопасные (всегда разрешены)
    TEXT_PROCESSING = "text"
    MATH = "math"
    DATA_ANALYSIS = "data"
    JSON_PARSING = "json"
    DATETIME = "datetime"
    
    # Требуют карантина
    FILE_READ = "file_read"
    HTTP_REQUEST = "http"
    
    # Требуют одобрения админа
    FILE_WRITE = "file_write"
    DATABASE = "database"
    EXTERNAL_API = "api"
    
    # Запрещены полностью
    SYSTEM_EXEC = "exec"
    NETWORK_RAW = "network"
    CODE_EVAL = "eval"


@dataclass
class OrganScanResult:
    """Результат проверки органа"""
    threat_level: ThreatLevel
    issues: List[str]
    required_capabilities: List[OrganCapability]
    suspicious_patterns: List[str]
    recommendations: List[str]
    
    def is_safe(self) -> bool:
        return self.threat_level == ThreatLevel.SAFE
    
    def requires_admin_approval(self) -> bool:
        return self.threat_level in (ThreatLevel.DANGEROUS, ThreatLevel.CRITICAL)
    
    def to_dict(self) -> dict:
        return {
            "threat_level": self.threat_level.value,
            "issues": self.issues,
            "required_capabilities": [c.value for c in self.required_capabilities],
            "suspicious_patterns": self.suspicious_patterns,
            "recommendations": self.recommendations
        }


@dataclass
class QuarantinedOrgan:
    """Орган в карантине"""
    organ_id: str
    name: str
    description: str
    code: str
    author_id: int
    created_at: str
    scan_result: dict  # OrganScanResult.to_dict()
    quarantine_until: str  # ISO timestamp
    approved_by: Optional[int] = None
    status: str = "pending"  # pending, approved, rejected, expired
    
    def to_dict(self) -> dict:
        return asdict(self)


class OrganGuardian:
    """Страж органов - проверка безопасности"""
    
    # === ПАТТЕРНЫ УГРОЗ ===
    
    # Критичные - автоблокировка
    CRITICAL_PATTERNS = [
        r'eval\s*\(',
        r'exec\s*\(',
        r'__import__\s*\(',
        r'compile\s*\(',
        r'globals\s*\(',
        r'locals\s*\(',
        r'\.system\s*\(',
        r'subprocess\.',
        r'os\.popen',
        r'os\.spawn',
        r'socket\.socket',
        r'requests\.post.*password',  # Отправка паролей
        r'open.*\.env',               # Чтение .env
        r'TELEGRAM_BOT_TOKEN',        # Утечка токенов
        r'_ADMIN_',                   # Доступ к админ-данным
    ]
    
    # Опасные - требуют одобрения
    DANGEROUS_PATTERNS = [
        r'import\s+requests',
        r'import\s+urllib',
        r'import\s+socket',
        r'\.write\s*\(',
        r'\.remove\s*\(',
        r'\.unlink\s*\(',
        r'shutil\.',
        r'pickle\.',
        r'marshal\.',
        r'input\s*\(',          # Интерактивный ввод
        r'raw_input\s*\(',
    ]
    
    # Подозрительные - карантин
    SUSPICIOUS_PATTERNS = [
        r'import\s+os',
        r'from\s+os\s+import',
        r'\.read\s*\(',
        r'\.readlines\s*\(',
        r'open\s*\(',
        r'Path\s*\(',
        r'with\s+open',
    ]
    
    # Запрещённые модули
    FORBIDDEN_MODULES = {
        'os', 'sys', 'subprocess', 'socket', 'threading', 'multiprocessing',
        'ctypes', 'importlib', '__builtin__', 'builtins', 'pickle', 'marshal',
        'shelve', 'eval', 'exec', 'compile'
    }
    
    # Разрешённые модули
    SAFE_MODULES = {
        'json', 'math', 're', 'datetime', 'random', 'string', 'collections',
        'itertools', 'functools', 'typing', 'dataclasses', 'enum', 'pathlib'
    }
    
    # Условно-безопасные (требуют карантина)
    CONDITIONAL_MODULES = {
        'requests': OrganCapability.HTTP_REQUEST,
        'aiohttp': OrganCapability.HTTP_REQUEST,
        'urllib': OrganCapability.HTTP_REQUEST,
        'sqlite3': OrganCapability.DATABASE,
        'psycopg2': OrganCapability.DATABASE,
    }
    
    def __init__(self, quarantine_dir: str = "quarantine"):
        self.quarantine_dir = Path(quarantine_dir)
        self.quarantine_dir.mkdir(exist_ok=True)
        self.quarantine_file = self.quarantine_dir / "organs.json"
        self.quarantined: List[QuarantinedOrgan] = []
        self._load_quarantine()
    
    def scan_organ_code(self, code: str, name: str = "unknown") -> OrganScanResult:
        """
        Глубокая проверка кода органа
        
        Проверяет:
        1. Опасные паттерны в коде
        2. AST анализ импортов и вызовов
        3. Требуемые capabilities
        4. Потенциальные утечки данных
        """
        issues = []
        suspicious_patterns = []
        required_capabilities = []
        recommendations = []
        
        # 1. КРИТИЧНЫЕ ПАТТЕРНЫ
        for pattern in self.CRITICAL_PATTERNS:
            matches = re.findall(pattern, code, re.IGNORECASE)
            if matches:
                issues.append(f"🚨 КРИТИЧНО: Обнаружен опасный паттерн '{pattern}'")
                return OrganScanResult(
                    threat_level=ThreatLevel.CRITICAL,
                    issues=issues,
                    required_capabilities=[],
                    suspicious_patterns=[pattern],
                    recommendations=["Орган заблокирован. Обратитесь к администратору."]
                )
        
        # 2. ОПАСНЫЕ ПАТТЕРНЫ
        dangerous_count = 0
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(f"⚠️ ОПАСНО: Паттерн '{pattern}'")
                dangerous_count += 1
        
        # 3. ПОДОЗРИТЕЛЬНЫЕ ПАТТЕРНЫ
        suspicious_count = 0
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                suspicious_patterns.append(pattern)
                suspicious_count += 1
        
        # 4. AST АНАЛИЗ
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Проверка импортов
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split('.')[0]
                        
                        if module in self.FORBIDDEN_MODULES:
                            issues.append(f"🚫 Запрещённый импорт: {alias.name}")
                            dangerous_count += 1
                        
                        elif module in self.CONDITIONAL_MODULES:
                            capability = self.CONDITIONAL_MODULES[module]
                            required_capabilities.append(capability)
                            recommendations.append(f"Требуется capability: {capability.value}")
                        
                        elif module not in self.SAFE_MODULES:
                            suspicious_patterns.append(f"import {alias.name}")
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split('.')[0]
                        
                        if module in self.FORBIDDEN_MODULES:
                            issues.append(f"🚫 Запрещённый from-импорт: {node.module}")
                            dangerous_count += 1
                        
                        elif module in self.CONDITIONAL_MODULES:
                            capability = self.CONDITIONAL_MODULES[module]
                            required_capabilities.append(capability)
                
                # Проверка опасных функций
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', 'compile', '__import__']:
                            issues.append(f"🚨 Опасная функция: {node.func.id}")
                            dangerous_count += 1
        
        except SyntaxError as e:
            issues.append(f"Синтаксическая ошибка: {e}")
            return OrganScanResult(
                threat_level=ThreatLevel.DANGEROUS,
                issues=issues,
                required_capabilities=[],
                suspicious_patterns=[],
                recommendations=["Исправьте синтаксические ошибки"]
            )
        
        # 5. ОПРЕДЕЛЕНИЕ УРОВНЯ УГРОЗЫ
        if dangerous_count > 0:
            threat_level = ThreatLevel.DANGEROUS
            recommendations.append("⚠️ Орган требует одобрения администратора")
        elif suspicious_count >= 3 or required_capabilities:
            threat_level = ThreatLevel.SUSPICIOUS
            recommendations.append("🔍 Орган помещён в 24-часовой карантин")
        else:
            threat_level = ThreatLevel.SAFE
            recommendations.append("✅ Орган безопасен и готов к использованию")
        
        return OrganScanResult(
            threat_level=threat_level,
            issues=issues,
            required_capabilities=list(set(required_capabilities)),
            suspicious_patterns=suspicious_patterns,
            recommendations=recommendations
        )
    
    def quarantine_organ(self, name: str, description: str, code: str,
                        author_id: int, scan_result: OrganScanResult,
                        quarantine_hours: int = 24) -> QuarantinedOrgan:
        """Помещает орган в карантин"""
        from datetime import datetime, timedelta
        
        organ_id = f"organ_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        quarantine_until = (datetime.now() + timedelta(hours=quarantine_hours)).isoformat()
        
        organ = QuarantinedOrgan(
            organ_id=organ_id,
            name=name,
            description=description,
            code=code,
            author_id=author_id,
            created_at=datetime.now().isoformat(),
            scan_result=scan_result.to_dict(),
            quarantine_until=quarantine_until
        )
        
        self.quarantined.append(organ)
        self._save_quarantine()
        
        return organ
    
    def approve_organ(self, organ_id: str, admin_id: int) -> bool:
        """Администратор одобряет орган"""
        for organ in self.quarantined:
            if organ.organ_id == organ_id and organ.status == "pending":
                organ.status = "approved"
                organ.approved_by = admin_id
                self._save_quarantine()
                return True
        return False
    
    def reject_organ(self, organ_id: str, admin_id: int) -> bool:
        """Администратор отклоняет орган"""
        for organ in self.quarantined:
            if organ.organ_id == organ_id and organ.status == "pending":
                organ.status = "rejected"
                organ.approved_by = admin_id
                self._save_quarantine()
                return True
        return False
    
    def get_pending_organs(self) -> List[QuarantinedOrgan]:
        """Органы ожидающие проверки"""
        return [o for o in self.quarantined if o.status == "pending"]
    
    def get_expired_quarantine(self) -> List[QuarantinedOrgan]:
        """Органы с истёкшим карантином"""
        from datetime import datetime
        now = datetime.now()
        expired = []
        
        for organ in self.quarantined:
            if organ.status == "pending":
                quarantine_end = datetime.fromisoformat(organ.quarantine_until)
                if now >= quarantine_end:
                    organ.status = "expired"
                    expired.append(organ)
        
        if expired:
            self._save_quarantine()
        
        return expired
    
    def _load_quarantine(self):
        """Загрузка из JSON"""
        if self.quarantine_file.exists():
            try:
                with open(self.quarantine_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.quarantined = [QuarantinedOrgan(**d) for d in data]
            except Exception as e:
                print(f"⚠️ Ошибка загрузки карантина: {e}")
    
    def _save_quarantine(self):
        """Сохранение в JSON"""
        try:
            with open(self.quarantine_file, 'w', encoding='utf-8') as f:
                json.dump([o.to_dict() for o in self.quarantined], f, 
                         indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения карантина: {e}")
    
    def generate_safety_report(self, scan_result: OrganScanResult, organ_name: str) -> str:
        """Генерирует отчёт безопасности для пользователя"""
        emoji_map = {
            ThreatLevel.SAFE: "✅",
            ThreatLevel.SUSPICIOUS: "🔍",
            ThreatLevel.DANGEROUS: "⚠️",
            ThreatLevel.CRITICAL: "🚨"
        }
        
        emoji = emoji_map[scan_result.threat_level]
        
        report = [
            f"{emoji} **Проверка безопасности: {organ_name}**\n",
            f"Уровень угрозы: **{scan_result.threat_level.value.upper()}**\n"
        ]
        
        if scan_result.issues:
            report.append("⚠️ **Обнаруженные проблемы:**")
            for issue in scan_result.issues:
                report.append(f"  • {issue}")
            report.append("")
        
        if scan_result.required_capabilities:
            report.append("🔧 **Требуемые разрешения:**")
            for cap in scan_result.required_capabilities:
                report.append(f"  • {cap.value}")
            report.append("")
        
        if scan_result.suspicious_patterns:
            report.append("🔍 **Подозрительные паттерны:**")
            for pattern in scan_result.suspicious_patterns[:5]:  # Первые 5
                report.append(f"  • {pattern}")
            if len(scan_result.suspicious_patterns) > 5:
                report.append(f"  • ...и ещё {len(scan_result.suspicious_patterns) - 5}")
            report.append("")
        
        report.append("💡 **Рекомендации:**")
        for rec in scan_result.recommendations:
            report.append(f"  • {rec}")
        
        return "\n".join(report)


# === ПУБЛИЧНЫЙ API ===

# Глобальный экземпляр
_guardian = None

def get_guardian() -> OrganGuardian:
    """Получить экземпляр Guardian (singleton)"""
    global _guardian
    if _guardian is None:
        _guardian = OrganGuardian()
    return _guardian


def scan_organ(code: str, name: str = "unknown") -> OrganScanResult:
    """Быстрая проверка кода органа"""
    return get_guardian().scan_organ_code(code, name)


def is_organ_safe(code: str) -> bool:
    """Проверка безопасности органа (простой API)"""
    result = scan_organ(code)
    return result.is_safe()


if __name__ == "__main__":
    # Тесты
    guardian = OrganGuardian()
    
    # Тест 1: Безопасный орган
    safe_code = """
class MathOrgan(Cell):
    def process(self, input_data: str) -> CellResult:
        import math
        result = math.sqrt(float(input_data))
        return CellResult(str(result), 1.0, self.name)
"""
    
    result = guardian.scan_organ_code(safe_code, "MathOrgan")
    print(guardian.generate_safety_report(result, "MathOrgan"))
    print("\n" + "="*60 + "\n")
    
    # Тест 2: Подозрительный орган
    suspicious_code = """
class FileOrgan(Cell):
    def process(self, input_data: str) -> CellResult:
        import os
        with open('data.txt', 'r') as f:
            data = f.read()
        return CellResult(data, 0.8, self.name)
"""
    
    result = guardian.scan_organ_code(suspicious_code, "FileOrgan")
    print(guardian.generate_safety_report(result, "FileOrgan"))
    print("\n" + "="*60 + "\n")
    
    # Тест 3: Опасный орган
    dangerous_code = """
class HackerOrgan(Cell):
    def process(self, input_data: str) -> CellResult:
        import os
        os.system('rm -rf /')
        return CellResult("hacked", 1.0, self.name)
"""
    
    result = guardian.scan_organ_code(dangerous_code, "HackerOrgan")
    print(guardian.generate_safety_report(result, "HackerOrgan"))
