"""
Nervous System v1.0 — Система метрик, мониторинга и алертов Neira

Отслеживает:
- Здоровье всех систем (CPU, RAM, VRAM, диск)
- Ошибки и их частоту
- Производительность ответов
- Аномалии в поведении
"""

import time
import psutil
import threading
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NervousSystem")


class HealthStatus(Enum):
    """Статус здоровья системы"""
    HEALTHY = "healthy"          # Всё в порядке
    WARNING = "warning"          # Есть проблемы, но работает
    CRITICAL = "critical"        # Критическое состояние
    DEAD = "dead"               # Система не отвечает


class AlertSeverity(Enum):
    """Серьёзность алерта"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Алерт о проблеме"""
    id: str
    severity: AlertSeverity
    source: str              # Откуда пришёл (memory, model, cell, etc.)
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "source": self.source,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolution": self.resolution
        }


@dataclass
class Metric:
    """Метрика системы"""
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    
    def get_status(self) -> HealthStatus:
        """Определить статус по порогам"""
        if self.threshold_critical and self.value >= self.threshold_critical:
            return HealthStatus.CRITICAL
        if self.threshold_warning and self.value >= self.threshold_warning:
            return HealthStatus.WARNING
        return HealthStatus.HEALTHY


@dataclass 
class ErrorRecord:
    """Запись об ошибке"""
    error_type: str
    message: str
    source: str
    traceback: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    count: int = 1
    last_occurrence: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """Сборщик системных метрик"""
    
    def __init__(self):
        self.gpu_available = self._check_gpu()
    
    def _check_gpu(self) -> bool:
        """Проверка доступности GPU"""
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def collect_cpu(self) -> Metric:
        """Загрузка CPU"""
        return Metric(
            name="cpu_usage",
            value=psutil.cpu_percent(interval=0.1),
            unit="%",
            threshold_warning=80.0,
            threshold_critical=95.0
        )
    
    def collect_ram(self) -> Metric:
        """Использование RAM"""
        mem = psutil.virtual_memory()
        return Metric(
            name="ram_usage",
            value=mem.percent,
            unit="%",
            threshold_warning=85.0,
            threshold_critical=95.0
        )
    
    def collect_ram_available(self) -> Metric:
        """Доступная RAM в GB"""
        mem = psutil.virtual_memory()
        return Metric(
            name="ram_available",
            value=round(mem.available / (1024**3), 2),
            unit="GB"
        )
    
    def collect_vram(self) -> Optional[Metric]:
        """Использование VRAM (если есть GPU)"""
        if not self.gpu_available:
            return None
        
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                used, total = map(float, result.stdout.strip().split(", "))
                percent = (used / total) * 100
                return Metric(
                    name="vram_usage",
                    value=round(percent, 1),
                    unit="%",
                    threshold_warning=85.0,
                    threshold_critical=95.0
                )
        except:
            pass
        return None
    
    def collect_disk(self) -> Metric:
        """Использование диска"""
        disk = psutil.disk_usage('/')
        return Metric(
            name="disk_usage",
            value=disk.percent,
            unit="%",
            threshold_warning=85.0,
            threshold_critical=95.0
        )
    
    def collect_all(self) -> Dict[str, Metric]:
        """Собрать все метрики"""
        metrics = {
            "cpu": self.collect_cpu(),
            "ram": self.collect_ram(),
            "ram_available": self.collect_ram_available(),
            "disk": self.collect_disk()
        }
        
        vram = self.collect_vram()
        if vram:
            metrics["vram"] = vram
        
        return metrics


class NervousSystem:
    """
    Нервная система Neira — центральный хаб мониторинга
    
    Функции:
    - Сбор метрик (CPU, RAM, VRAM, диск)
    - Регистрация ошибок
    - Генерация алертов
    - История здоровья
    - Callbacks для реакции на проблемы
    """
    
    VERSION = "1.0"
    
    def __init__(self, data_dir: str = "."):
        self.data_dir = Path(data_dir)
        self.metrics_file = self.data_dir / "neira_metrics.json"
        self.alerts_file = self.data_dir / "neira_alerts.json"
        
        # Компоненты
        self.collector = MetricsCollector()
        
        # Хранилище
        self.current_metrics: Dict[str, Metric] = {}
        self.metrics_history: deque = deque(maxlen=1000)  # Последние 1000 записей
        self.errors: Dict[str, ErrorRecord] = {}  # Ключ = тип ошибки
        self.alerts: List[Alert] = []
        self.active_alerts: Dict[str, Alert] = {}
        
        # Счётчики
        self.total_errors = 0
        self.errors_last_hour = 0
        self.last_error_reset = datetime.now()
        
        # Производительность
        self.response_times: deque = deque(maxlen=100)
        self.avg_response_time = 0.0
        
        # Callbacks для реакции
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        self._health_callbacks: List[Callable[[HealthStatus], None]] = []
        
        # Статус
        self.overall_health = HealthStatus.HEALTHY
        self.last_check = datetime.now()
        
        # Загрузка истории
        self._load_history()
        
        # Фоновый мониторинг
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
    
    def _load_history(self):
        """Загрузка истории алертов"""
        if self.alerts_file.exists():
            try:
                data = json.loads(self.alerts_file.read_text(encoding='utf-8'))
                for a in data.get("alerts", [])[-100:]:  # Последние 100
                    alert = Alert(
                        id=a["id"],
                        severity=AlertSeverity(a["severity"]),
                        source=a["source"],
                        message=a["message"],
                        timestamp=datetime.fromisoformat(a["timestamp"]),
                        resolved=a.get("resolved", True),
                        resolution=a.get("resolution")
                    )
                    self.alerts.append(alert)
            except Exception as e:
                logger.warning(f"Не удалось загрузить историю алертов: {e}")
    
    def _save_alerts(self):
        """Сохранение алертов"""
        try:
            data = {
                "version": self.VERSION,
                "alerts": [a.to_dict() for a in self.alerts[-100:]]
            }
            self.alerts_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as e:
            logger.error(f"Ошибка сохранения алертов: {e}")
    
    # === Сбор метрик ===
    
    def collect_metrics(self) -> Dict[str, Metric]:
        """Собрать текущие метрики"""
        self.current_metrics = self.collector.collect_all()
        self.last_check = datetime.now()
        
        # Сохранить в историю
        snapshot = {
            "timestamp": self.last_check.isoformat(),
            "metrics": {k: {"value": v.value, "status": v.get_status().value} 
                       for k, v in self.current_metrics.items()}
        }
        self.metrics_history.append(snapshot)
        
        # Проверить на проблемы
        self._check_thresholds()
        
        return self.current_metrics
    
    def _check_thresholds(self):
        """Проверка порогов и генерация алертов"""
        for name, metric in self.current_metrics.items():
            status = metric.get_status()
            alert_id = f"metric_{name}"
            
            if status == HealthStatus.CRITICAL:
                self._create_alert(
                    alert_id,
                    AlertSeverity.CRITICAL,
                    "metrics",
                    f"{name} критически высок: {metric.value}{metric.unit}"
                )
            elif status == HealthStatus.WARNING:
                self._create_alert(
                    alert_id,
                    AlertSeverity.WARNING,
                    "metrics", 
                    f"{name} повышен: {metric.value}{metric.unit}"
                )
            elif alert_id in self.active_alerts:
                self._resolve_alert(alert_id, "Метрика вернулась в норму")
    
    # === Регистрация ошибок ===
    
    def record_error(self, error_type: str, message: str, source: str, 
                     traceback: Optional[str] = None) -> ErrorRecord:
        """Записать ошибку"""
        self.total_errors += 1
        self.errors_last_hour += 1
        
        # Проверяем счётчик за час
        if datetime.now() - self.last_error_reset > timedelta(hours=1):
            self.errors_last_hour = 1
            self.last_error_reset = datetime.now()
        
        key = f"{error_type}:{source}"
        
        if key in self.errors:
            # Обновляем существующую
            self.errors[key].count += 1
            self.errors[key].last_occurrence = datetime.now()
            self.errors[key].message = message
            if traceback:
                self.errors[key].traceback = traceback
        else:
            # Новая ошибка
            self.errors[key] = ErrorRecord(
                error_type=error_type,
                message=message,
                source=source,
                traceback=traceback
            )
        
        record = self.errors[key]
        
        # Алерт если ошибка повторяется
        if record.count >= 3:
            self._create_alert(
                f"error_{key}",
                AlertSeverity.ERROR,
                source,
                f"Повторяющаяся ошибка ({record.count}x): {error_type} - {message[:100]}"
            )
        
        # Критический алерт если много ошибок за час
        if self.errors_last_hour >= 10:
            self._create_alert(
                "error_rate_high",
                AlertSeverity.CRITICAL,
                "nervous_system",
                f"Высокая частота ошибок: {self.errors_last_hour} за последний час"
            )
        
        logger.warning(f"Error recorded: {error_type} from {source}")
        return record
    
    # === Алерты ===
    
    def _create_alert(self, alert_id: str, severity: AlertSeverity, 
                      source: str, message: str):
        """Создать или обновить алерт"""
        if alert_id in self.active_alerts:
            return  # Уже активен
        
        alert = Alert(
            id=alert_id,
            severity=severity,
            source=source,
            message=message
        )
        
        self.alerts.append(alert)
        self.active_alerts[alert_id] = alert
        
        # Обновить общее здоровье
        self._update_health()
        
        # Callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        self._save_alerts()
        logger.warning(f"Alert created: [{severity.value}] {message}")
    
    def _resolve_alert(self, alert_id: str, resolution: str):
        """Разрешить алерт"""
        if alert_id not in self.active_alerts:
            return
        
        alert = self.active_alerts.pop(alert_id)
        alert.resolved = True
        alert.resolution = resolution
        
        self._update_health()
        self._save_alerts()
        logger.info(f"Alert resolved: {alert_id} - {resolution}")
    
    def _update_health(self):
        """Обновить общий статус здоровья"""
        if not self.active_alerts:
            new_health = HealthStatus.HEALTHY
        else:
            severities = [a.severity for a in self.active_alerts.values()]
            if AlertSeverity.CRITICAL in severities:
                new_health = HealthStatus.CRITICAL
            elif AlertSeverity.ERROR in severities:
                new_health = HealthStatus.WARNING
            else:
                new_health = HealthStatus.WARNING
        
        if new_health != self.overall_health:
            old_health = self.overall_health
            self.overall_health = new_health
            
            # Callbacks
            for callback in self._health_callbacks:
                try:
                    callback(new_health)
                except Exception as e:
                    logger.error(f"Health callback error: {e}")
            
            logger.info(f"Health changed: {old_health.value} -> {new_health.value}")
    
    # === Производительность ===
    
    def record_response_time(self, duration_ms: float):
        """Записать время ответа"""
        self.response_times.append(duration_ms)
        self.avg_response_time = sum(self.response_times) / len(self.response_times)
        
        # Алерт если слишком медленно
        if duration_ms > 30000:  # > 30 секунд
            self._create_alert(
                "slow_response",
                AlertSeverity.WARNING,
                "performance",
                f"Медленный ответ: {duration_ms/1000:.1f} сек"
            )
    
    # === Callbacks ===
    
    def on_alert(self, callback: Callable[[Alert], None]):
        """Подписаться на алерты"""
        self._alert_callbacks.append(callback)
    
    def on_health_change(self, callback: Callable[[HealthStatus], None]):
        """Подписаться на изменения здоровья"""
        self._health_callbacks.append(callback)
    
    # === Фоновый мониторинг ===
    
    def start_monitoring(self, interval_sec: int = 60):
        """Запустить фоновый мониторинг"""
        if self._monitoring:
            return
        
        self._monitoring = True
        
        def monitor_loop():
            while self._monitoring:
                try:
                    self.collect_metrics()
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
                time.sleep(interval_sec)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Background monitoring started (interval: {interval_sec}s)")
    
    def stop_monitoring(self):
        """Остановить мониторинг"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Background monitoring stopped")
    
    # === API ===
    
    def get_health_report(self) -> Dict[str, Any]:
        """Полный отчёт о здоровье"""
        self.collect_metrics()
        
        return {
            "status": self.overall_health.value,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                name: {
                    "value": m.value,
                    "unit": m.unit,
                    "status": m.get_status().value
                }
                for name, m in self.current_metrics.items()
            },
            "errors": {
                "total": self.total_errors,
                "last_hour": self.errors_last_hour,
                "unique_types": len(self.errors)
            },
            "performance": {
                "avg_response_ms": round(self.avg_response_time, 2),
                "samples": len(self.response_times)
            },
            "active_alerts": len(self.active_alerts),
            "alerts": [a.to_dict() for a in list(self.active_alerts.values())[:10]]
        }
    
    def get_errors_summary(self) -> List[Dict]:
        """Сводка по ошибкам"""
        return [
            {
                "type": e.error_type,
                "source": e.source,
                "message": e.message[:200],
                "count": e.count,
                "last": e.last_occurrence.isoformat()
            }
            for e in sorted(self.errors.values(), key=lambda x: x.count, reverse=True)[:20]
        ]
    
    def clear_resolved_alerts(self):
        """Очистить разрешённые алерты"""
        self.alerts = [a for a in self.alerts if not a.resolved]
        self._save_alerts()
    
    def acknowledge_alert(self, alert_id: str):
        """Подтвердить алерт (не разрешить, но отметить что видели)"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].resolved = False  # Пока оставляем активным


# === Глобальный экземпляр ===
_nervous_system: Optional[NervousSystem] = None


def get_nervous_system() -> NervousSystem:
    """Получить глобальную нервную систему"""
    global _nervous_system
    if _nervous_system is None:
        _nervous_system = NervousSystem()
    return _nervous_system


# === Тестирование ===
if __name__ == "__main__":
    print("🧠 Testing Nervous System v1.0\n")
    
    ns = NervousSystem()
    
    # Тест метрик
    print("📊 Collecting metrics...")
    metrics = ns.collect_metrics()
    for name, metric in metrics.items():
        status_emoji = {"healthy": "✅", "warning": "⚠️", "critical": "🔴"}.get(metric.get_status().value, "❓")
        print(f"  {status_emoji} {name}: {metric.value}{metric.unit}")
    
    # Тест ошибок
    print("\n❌ Recording errors...")
    ns.record_error("ValueError", "Invalid input", "test")
    ns.record_error("ValueError", "Invalid input", "test")
    ns.record_error("ValueError", "Invalid input", "test")  # Должен создать алерт
    
    # Тест производительности
    print("\n⏱️ Recording response times...")
    ns.record_response_time(1500)
    ns.record_response_time(2000)
    ns.record_response_time(1800)
    
    # Отчёт
    print("\n📋 Health Report:")
    report = ns.get_health_report()
    print(f"  Status: {report['status']}")
    print(f"  Total errors: {report['errors']['total']}")
    print(f"  Avg response: {report['performance']['avg_response_ms']}ms")
    print(f"  Active alerts: {report['active_alerts']}")
    
    for alert in report['alerts']:
        print(f"    ⚠️ [{alert['severity']}] {alert['message']}")
    
    print("\n✅ Nervous System test complete!")
