"""
Neira Server v1.0 — HTTP/WebSocket сервер для VS Code Extension
Обеспечивает связь между расширением и ядром Нейры.

Запуск: python neira_server.py
Порт по умолчанию: 8765
"""

import asyncio
import errno
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple, TYPE_CHECKING

# Загружаем .env как можно раньше, чтобы настройки применялись ко всем модулям.
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("neira-server")

ERROR_LOG_PATH = os.getenv("NEIRA_ERROR_LOG_PATH", str(Path("artifacts") / "neira_errors.txt"))
ERROR_LOG_FILTER_CONNRESET = os.getenv("NEIRA_LOG_FILTER_CONNRESET", "1").strip().lower() in {
    "1", "true", "yes", "on"
}
CHAT_LOG_PATH = os.getenv("NEIRA_CHAT_LOG_PATH", str(Path("artifacts") / "neira_chat.log"))
CHAT_LOG_ENABLED = os.getenv("NEIRA_CHAT_LOG_ENABLED", "1").strip().lower() in {
    "1", "true", "yes", "on"
}
CHAT_LOG_INCLUDE_CONTEXT = os.getenv("NEIRA_CHAT_LOG_INCLUDE_CONTEXT", "0").strip().lower() in {
    "1", "true", "yes", "on"
}
_CHAT_LOG_MAX_CHARS_RAW = os.getenv("NEIRA_CHAT_LOG_MAX_CHARS", "").strip()
try:
    CHAT_LOG_MAX_CHARS = max(int(_CHAT_LOG_MAX_CHARS_RAW), 0) if _CHAT_LOG_MAX_CHARS_RAW else 0
except ValueError:
    CHAT_LOG_MAX_CHARS = 0

_NAME_TOKEN = r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\-]{1,}"
_SELF_NAME_PATTERN = re.compile(
    rf"(?:^|[\s,])я\s*(?:-|—)?\s*({_NAME_TOKEN})",
    re.IGNORECASE,
)
_EXPLICIT_NAME_PATTERNS = (
    re.compile(rf"меня\s+зовут\s*({_NAME_TOKEN})", re.IGNORECASE),
    re.compile(rf"(?:зови|зовите)\s+меня\s*({_NAME_TOKEN})", re.IGNORECASE),
    re.compile(rf"(?:можешь|можете)\s+звать\s+меня\s*({_NAME_TOKEN})", re.IGNORECASE),
    re.compile(rf"(?:называй|называйте)\s+меня\s*({_NAME_TOKEN})", re.IGNORECASE),
)


class _IgnoreConnectionResetFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not ERROR_LOG_FILTER_CONNRESET:
            return True
        if not record.name.startswith("asyncio"):
            return True
        if not record.exc_info:
            return True
        exc = record.exc_info[1]
        if isinstance(exc, ConnectionResetError):
            return False
        if isinstance(exc, OSError):
            if getattr(exc, "errno", None) == 10054:
                return False
            if getattr(exc, "winerror", None) == 64:
                return False
            if getattr(exc, "errno", None) == 64:
                return False
        return True


def _attach_connreset_filter(handler: logging.Handler) -> None:
    for existing in handler.filters:
        if isinstance(existing, _IgnoreConnectionResetFilter):
            return
    handler.addFilter(_IgnoreConnectionResetFilter())


def _setup_error_logging(path: str) -> None:
    """Подключить файловый логгер для ошибок."""
    try:
        log_path = Path(path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        root_logger = logging.getLogger()
        file_handler_exists = False
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_path:
                file_handler_exists = True
            _attach_connreset_filter(handler)
        if file_handler_exists:
            return

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.ERROR)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        _attach_connreset_filter(file_handler)
        root_logger.addHandler(file_handler)
        logger.info(f"📝 Лог ошибок: {log_path}")
    except Exception as exc:
        logger.warning(f"Не удалось настроить файл ошибок: {exc}")


def _setup_chat_logging(path: str) -> Optional[logging.Logger]:
    """Настроить логирование ответов Нейры в отдельный файл."""
    if not CHAT_LOG_ENABLED:
        return None
    try:
        log_path = Path(path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        chat_logger = logging.getLogger("neira-chat")
        chat_logger.setLevel(logging.INFO)
        chat_logger.propagate = False

        for handler in chat_logger.handlers:
            if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_path:
                return chat_logger

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
        chat_logger.addHandler(file_handler)
        logger.info(f"📝 Лог чата: {log_path}")
        return chat_logger
    except Exception as exc:
        logger.warning(f"Не удалось настроить лог чата Neira: {exc}")
        return None


def _truncate_for_log(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if CHAT_LOG_MAX_CHARS <= 0 or len(value) <= CHAT_LOG_MAX_CHARS:
        return value
    return value[:CHAT_LOG_MAX_CHARS] + "...(truncated)"


_setup_error_logging(ERROR_LOG_PATH)
CHAT_LOGGER = _setup_chat_logging(CHAT_LOG_PATH)

# Попытка импорта aiohttp
try:
    from aiohttp import web
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp не установлен. Установите: pip install aiohttp")

if TYPE_CHECKING:
    from main import Neira
    from file_system_agent import FileSystemAgent

# Конфигурация
HOST = os.getenv("NEIRA_HOST", "127.0.0.1")
PORT = int(os.getenv("NEIRA_PORT", "8765"))
CORS_ORIGINS = ["vscode-webview://", "cursor://", "http://localhost:*"]

MODULE_CORE = "core"
MODULE_STREAM = "stream"
MODULE_WS = "ws"
MODULE_FILES = "files"
MODULE_TOOLS = "tools"
MODULE_INDEXER = "indexer"
MODULE_CONTEXT = "context"
MODULE_MODELS = "models"
MODULE_LAYERS = "layers"
MODULE_SELF = "self"
MODULE_LEARNING = "learning"

KNOWN_MODULES = frozenset({
    MODULE_CORE,
    MODULE_STREAM,
    MODULE_WS,
    MODULE_FILES,
    MODULE_TOOLS,
    MODULE_INDEXER,
    MODULE_CONTEXT,
    MODULE_MODELS,
    MODULE_LAYERS,
    MODULE_SELF,
    MODULE_LEARNING,
})

DEFAULT_MODULES = frozenset({
    MODULE_CORE,
    MODULE_STREAM,
    MODULE_WS,
    MODULE_FILES,
    MODULE_TOOLS,
    MODULE_INDEXER,
    MODULE_CONTEXT,
    MODULE_MODELS,
    MODULE_LAYERS,
    MODULE_SELF,
    MODULE_LEARNING,
})

MESSAGE_PREVIEW_LIMIT = 50
EXECUTABLE_ORGAN_CONFIDENCE = 0.6
CORTEX_MIN_CONFIDENCE = 0.6
CORTEX_SKIP_STRATEGIES = frozenset({"template"})
BYTES_IN_MB = 1024 * 1024

DEFAULT_OFFLINE_LEARNING_DIRS = ("training_data", "training_scenarios", "docs", "data")
DEFAULT_OFFLINE_LEARNING_INTERVAL_SEC = 3600
DEFAULT_OFFLINE_LEARNING_IDLE_SEC = 600
DEFAULT_OFFLINE_LEARNING_MAX_FILES = 20
DEFAULT_OFFLINE_LEARNING_MAX_MB = 2
DEFAULT_OFFLINE_LEARNING_INITIAL_DELAY_SEC = 30
DEFAULT_OFFLINE_LEARNING_EXCLUDE_DIRS = (".git", "node_modules", ".next", ".neira_cache", ".cursor", "_archive")
DEFAULT_OFFLINE_LEARNING_INCLUDE_GLOBS: tuple[str, ...] = ()
DEFAULT_OFFLINE_LEARNING_MAX_ERROR_ENTRIES = 30
DEFAULT_OFFLINE_LEARNING_MAX_SOURCES_PREVIEW = 8
DEFAULT_LEARNING_HISTORY_RECENT_LIMIT = 20
MAX_LEARNING_HISTORY_RECENT_LIMIT = 200

DEFAULT_EVOLUTION_INTERVAL_SEC = 4 * 3600
DEFAULT_EVOLUTION_CHECK_INTERVAL_SEC = 300
DEFAULT_EVOLUTION_IDLE_SEC = 1200
DEFAULT_EVOLUTION_MIN_REQUESTS = 30
DEFAULT_EVOLUTION_AUTONOMY_THRESHOLD = 70
DEFAULT_EVOLUTION_MIN_INTERVAL_SEC = 1800
DEFAULT_LLM_TIMEOUT_SEC = 600
DEFAULT_OFFLINE_LLM_PROVIDER_PRIORITY = "mistralrs,lmstudio,ollama"
DEFAULT_OFFLINE_OLLAMA_MODEL = "qwen2.5-coder:7b"
DEFAULT_OFFLINE_OLLAMA_NUM_CTX = 2048
DEFAULT_OFFLINE_OLLAMA_NUM_GPU = 0
DEFAULT_MAX_RESPONSE_TOKENS = 1024

DEFAULT_AUTONOMY_OPTIMIZE_ENABLED = True
DEFAULT_AUTONOMY_OPTIMIZE_INTERVAL_SEC = 3600
DEFAULT_AUTONOMY_OPTIMIZE_IDLE_SEC = 600

SERVICE_PRESETS: Dict[str, FrozenSet[str]] = {
    "all": DEFAULT_MODULES,
    "core": frozenset({MODULE_CORE, MODULE_STREAM, MODULE_WS}),
    "lite": frozenset({MODULE_CORE}),
    "tools": frozenset({MODULE_FILES, MODULE_TOOLS}),
    "indexer": frozenset({MODULE_INDEXER, MODULE_CONTEXT}),
    "models": frozenset({MODULE_MODELS, MODULE_LAYERS}),
    "learning": frozenset({MODULE_LEARNING}),
    "self": frozenset({MODULE_SELF}),
}


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, min_value: int = 0, max_value: Optional[int] = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    if value < min_value:
        return min_value
    if max_value is not None and value > max_value:
        return max_value
    return value


def _parse_modules(raw: str) -> Set[str]:
    tokens = {t.strip().lower() for t in raw.split(",") if t.strip()}
    if not tokens:
        return set(DEFAULT_MODULES)
    if "all" in tokens:
        return set(DEFAULT_MODULES)
    unknown = tokens - KNOWN_MODULES
    if unknown:
        logger.warning(f"Неизвестные модули: {', '.join(sorted(unknown))}")
    return {t for t in tokens if t in KNOWN_MODULES}


@dataclass(frozen=True)
class ServerModules:
    enabled: FrozenSet[str]

    @classmethod
    def from_env(cls) -> "ServerModules":
        service_mode = os.getenv("NEIRA_SERVICE_MODE", "").strip().lower()
        raw_modules = os.getenv("NEIRA_MODULES", "").strip().lower()

        if service_mode:
            preset = SERVICE_PRESETS.get(service_mode)
            if preset is None:
                logger.warning(f"Неизвестный режим сервиса: {service_mode}")
                preset = DEFAULT_MODULES
            return cls(enabled=preset)

        if raw_modules:
            return cls(enabled=frozenset(_parse_modules(raw_modules)))

        return cls(enabled=DEFAULT_MODULES)

    def is_enabled(self, name: str) -> bool:
        return name in self.enabled


@dataclass
class ToolSystem:
    executor: Any
    registry: Any


@dataclass
class ContextFunctions:
    get_context_manager: Callable[..., Any]  # Принимает опциональный max_tokens
    estimate_tokens: Callable[[str], int]
    optimal_context_size: Callable[[str, str], int]


@dataclass
class ModelLayersSystem:
    registry: Any
    layer_class: Any
    error_class: Any


@dataclass
class ModelManagerModule:
    manager_class: Any
    models: Any


@dataclass
class ServerResponse:
    """Стандартный ответ сервера"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class NeiraServer:
    """HTTP/WebSocket сервер для Нейры"""
    
    def __init__(self, host: str = HOST, port: int = PORT, workspace_root: Optional[str] = None):
        self.host = host
        self.port = port
        self.modules = ServerModules.from_env()
        self.lazy_neira = _env_flag("NEIRA_LAZY_INIT", False)
        self.neira: Optional["Neira"] = None
        self.app: Optional[web.Application] = None
        self.websockets: set = set()
        self.request_count = 0
        self.start_time = datetime.now()
        self._neira_lock = asyncio.Lock()
        self._neira_error: Optional[str] = None
        
        # File System Agent
        self.workspace_root = workspace_root or os.getcwd()
        self.fs_agent: Optional["FileSystemAgent"] = None
        self._fs_agent_error: Optional[str] = None
        # Registry слоёв моделей
        self.layers_registry: Optional[Any] = None
        self._layers_system: Optional[ModelLayersSystem] = None
        self._layers_error: Optional[str] = None
        # ModelManager
        self.model_manager: Optional[Any] = None
        self._model_manager_module: Optional[ModelManagerModule] = None
        self._model_manager_error: Optional[str] = None
        # Tool System
        self._tool_system: Optional[ToolSystem] = None
        self._tool_system_error: Optional[str] = None
        # Indexer
        self._indexer_getter: Optional[Callable[[str], Any]] = None
        self._indexer_error: Optional[str] = None
        # Context Manager
        self._context_functions: Optional[ContextFunctions] = None
        self._context_error: Optional[str] = None

        # Режимы автономности
        self._offline_mode = _env_flag("NEIRA_OFFLINE_MODE", True)
        self._offline_allow_local_llm = _env_flag("NEIRA_OFFLINE_ALLOW_LOCAL_LLM", True)
        self._cortex_enabled = _env_flag("NEIRA_CORTEX_ENABLED", True)
        if self._offline_mode:
            os.environ.setdefault("NEIRA_WEB_SEARCH_ENABLED", "0")
            os.environ.setdefault("NEIRA_WEB_SEARCH_HTML_FALLBACK", "0")
            os.environ.setdefault("NEIRA_ENABLE_WEB", "0")
            os.environ.setdefault("LLM_PROVIDER_PRIORITY", DEFAULT_OFFLINE_LLM_PROVIDER_PRIORITY)
            os.environ["NEIRA_OLLAMA_MODEL"] = DEFAULT_OFFLINE_OLLAMA_MODEL
            os.environ["NEIRA_MAX_RESPONSE_TOKENS"] = str(DEFAULT_MAX_RESPONSE_TOKENS)
            os.environ.setdefault("NEIRA_OLLAMA_NUM_CTX", str(DEFAULT_OFFLINE_OLLAMA_NUM_CTX))
            os.environ.setdefault("NEIRA_OLLAMA_NUM_GPU", str(DEFAULT_OFFLINE_OLLAMA_NUM_GPU))
            os.environ.setdefault(
                "NEIRA_DISABLE_OLLAMA",
                "0" if self._offline_allow_local_llm else "1",
            )
        self._cortex_use_llm = (not self._offline_mode) or self._offline_allow_local_llm
        self._llm_timeout_sec = _env_int("NEIRA_LLM_TIMEOUT_SEC", DEFAULT_LLM_TIMEOUT_SEC, min_value=0)
        self._offline_learning_enabled = _env_flag("NEIRA_OFFLINE_LEARNING_ENABLED", True)
        self._offline_learning_summarize = _env_flag("NEIRA_OFFLINE_LEARNING_SUMMARIZE", True)
        self._offline_learning_category = os.getenv("NEIRA_OFFLINE_LEARNING_CATEGORY", "offline").strip() or "offline"
        offline_dirs_raw = os.getenv(
            "NEIRA_OFFLINE_LEARNING_DIRS",
            ",".join(DEFAULT_OFFLINE_LEARNING_DIRS),
        )
        self._offline_learning_dirs = [d.strip() for d in offline_dirs_raw.split(",") if d.strip()]
        include_globs_raw = os.getenv("NEIRA_OFFLINE_LEARNING_INCLUDE_GLOBS", "").strip()
        if include_globs_raw:
            self._offline_learning_include_globs = [g.strip() for g in include_globs_raw.split(",") if g.strip()]
        else:
            self._offline_learning_include_globs = list(DEFAULT_OFFLINE_LEARNING_INCLUDE_GLOBS)
        exclude_raw = os.getenv(
            "NEIRA_OFFLINE_LEARNING_EXCLUDE_DIRS",
            ",".join(DEFAULT_OFFLINE_LEARNING_EXCLUDE_DIRS),
        )
        self._offline_learning_exclude_dirs = [d.strip() for d in exclude_raw.split(",") if d.strip()]
        self._offline_learning_interval = _env_int(
            "NEIRA_OFFLINE_LEARNING_INTERVAL_SEC",
            DEFAULT_OFFLINE_LEARNING_INTERVAL_SEC,
            min_value=60,
        )
        self._offline_learning_idle_seconds = _env_int(
            "NEIRA_OFFLINE_LEARNING_IDLE_SEC",
            DEFAULT_OFFLINE_LEARNING_IDLE_SEC,
            min_value=60,
        )
        self._offline_learning_max_files = _env_int(
            "NEIRA_OFFLINE_LEARNING_MAX_FILES",
            DEFAULT_OFFLINE_LEARNING_MAX_FILES,
            min_value=1,
        )
        self._offline_learning_initial_delay = _env_int(
            "NEIRA_OFFLINE_LEARNING_INITIAL_DELAY_SEC",
            DEFAULT_OFFLINE_LEARNING_INITIAL_DELAY_SEC,
            min_value=0,
        )
        max_mb = _env_int(
            "NEIRA_OFFLINE_LEARNING_MAX_MB",
            DEFAULT_OFFLINE_LEARNING_MAX_MB,
            min_value=1,
        )
        self._offline_learning_max_bytes = max_mb * BYTES_IN_MB

        self._evolution_enabled = _env_flag("NEIRA_EVOLUTION_ENABLED", True)
        self._evolution_interval = _env_int(
            "NEIRA_EVOLUTION_INTERVAL_SEC",
            DEFAULT_EVOLUTION_INTERVAL_SEC,
            min_value=60,
        )
        self._evolution_check_interval = _env_int(
            "NEIRA_EVOLUTION_CHECK_INTERVAL_SEC",
            DEFAULT_EVOLUTION_CHECK_INTERVAL_SEC,
            min_value=60,
        )
        self._evolution_idle_seconds = _env_int(
            "NEIRA_EVOLUTION_IDLE_SEC",
            DEFAULT_EVOLUTION_IDLE_SEC,
            min_value=60,
        )
        self._evolution_min_requests = _env_int(
            "NEIRA_EVOLUTION_MIN_REQUESTS",
            DEFAULT_EVOLUTION_MIN_REQUESTS,
            min_value=1,
        )
        self._evolution_autonomy_threshold = _env_int(
            "NEIRA_EVOLUTION_AUTONOMY_THRESHOLD",
            DEFAULT_EVOLUTION_AUTONOMY_THRESHOLD,
            min_value=0,
            max_value=100,
        )
        self._evolution_min_interval = _env_int(
            "NEIRA_EVOLUTION_MIN_INTERVAL_SEC",
            DEFAULT_EVOLUTION_MIN_INTERVAL_SEC,
            min_value=60,
        )

        self._autonomy_optimize_enabled = _env_flag(
            "NEIRA_AUTONOMY_OPTIMIZE_ENABLED",
            DEFAULT_AUTONOMY_OPTIMIZE_ENABLED,
        )
        self._autonomy_optimize_interval = _env_int(
            "NEIRA_AUTONOMY_OPTIMIZE_INTERVAL_SEC",
            DEFAULT_AUTONOMY_OPTIMIZE_INTERVAL_SEC,
            min_value=60,
        )
        self._autonomy_optimize_idle_seconds = _env_int(
            "NEIRA_AUTONOMY_OPTIMIZE_IDLE_SEC",
            DEFAULT_AUTONOMY_OPTIMIZE_IDLE_SEC,
            min_value=60,
        )

        self._last_activity = time.time()
        self._last_learning_run = 0.0
        self._last_evolution_run = 0.0
        self._last_autonomy_optimize_run = 0.0
        self._last_learning_run_stats: Optional[Dict[str, Any]] = None
        self._last_learning_sources: list[str] = []
        self._offline_learning_recent_errors: list[Dict[str, Any]] = []
        self._background_tasks: Set[asyncio.Task] = set()
        
        # === Phase 1: Новые модули автономности ===
        self._neira_brain = None
        self._organ_system = None
        self._response_engine = None
        self._cortex = None
        self._cortex_error: Optional[str] = None
        self._autonomy_modules_error: Optional[str] = None
        self._init_autonomy_modules()

        logger.info(f"🧩 Модули сервера: {', '.join(sorted(self.modules.enabled))}")
        
    def _init_autonomy_modules(self):
        """Инициализация модулей автономности (Phase 1 + Phase 3)"""
        try:
            from neira_brain import get_brain
            from unified_organ_system import get_organ_system
            from response_engine import get_response_engine
            
            self._neira_brain = get_brain()
            self._ensure_pathways_seeded()
            self._organ_system = get_organ_system()
            self._response_engine = get_response_engine()

            # 🧠 Neira Cortex
            if self._cortex_enabled:
                try:
                    from neira_cortex import create_cortex
                    self._cortex = create_cortex(
                        pathways_file="neural_pathways.json",
                        use_llm=self._cortex_use_llm,
                    )
                    logger.info("🧠 Cortex инициализирован")
                except (ImportError, RuntimeError, OSError, ValueError, AttributeError) as e:
                    self._cortex = None
                    self._cortex_error = str(e)
                    logger.warning(f"⚠️ Cortex недоступен: {e}")
            
            # 🧬 ExecutableOrgans v1.0
            try:
                from executable_organs import get_organ_registry, FeedbackType
                self._executable_organs = get_organ_registry()
                self._feedback_type_class = FeedbackType
                logger.info(f"🧬 ExecutableOrgans: {len(self._executable_organs.organs)} органов")
            except Exception as e:
                self._executable_organs = None
                self._feedback_type_class = None
                logger.warning(f"⚠️ ExecutableOrgans недоступны: {e}")
            
            logger.info("🧠 Phase 1: Модули автономности инициализированы")
            
            # === Phase 3: AutonomyEngine ===
            try:
                from autonomy_engine import get_autonomy_engine
                self._autonomy_engine = get_autonomy_engine()
                logger.info("🚀 Phase 3: AutonomyEngine инициализирован")
            except Exception as e:
                self._autonomy_engine = None
                logger.warning(f"⚠️ Phase 3 недоступен: {e}")
            
            # Получаем статистику
            stats = self._response_engine.get_autonomy_stats()
            autonomy_rate = stats.get('metrics', {}).get('autonomy_rate_strict', stats.get('metrics', {}).get('autonomy_rate', 0))
            logger.info(f"📊 Текущая автономность: {autonomy_rate}%")
            
        except Exception as e:
            self._autonomy_modules_error = str(e)
            logger.warning(f"⚠️ Модули автономности недоступны: {e}")

    def _ensure_pathways_seeded(self, pathways_file: str = "neural_pathways.json") -> None:
        """Загрузить базовые pathways в БД, если она пустая."""
        if not self._neira_brain:
            return
        import sqlite3
        try:
            rows = self._neira_brain.query("SELECT COUNT(*) AS count FROM pathways")
            current = int(rows[0]["count"]) if rows else 0
        except (RuntimeError, ValueError, OSError, sqlite3.Error) as exc:
            logger.warning(f"⚠️ Не удалось проверить pathways: {exc}")
            return
        if current > 0:
            return
        try:
            migrated = self._neira_brain.migrate_from_json(pathways_file)
        except (RuntimeError, ValueError, OSError, sqlite3.Error) as exc:
            logger.warning(f"⚠️ Не удалось мигрировать pathways: {exc}")
            return
        if migrated > 0:
            logger.info(f"🧠 Pathways загружены из {pathways_file}: {migrated}")

    def _record_response_metric(
        self,
        event_type: str,
        source: str,
        message: str,
        latency_ms: float,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Записать метрику ответа."""
        if not self._neira_brain:
            return
        payload = {
            "source": source,
            "message_preview": message[:MESSAGE_PREVIEW_LIMIT],
            "latency_ms": latency_ms,
        }
        if extra:
            payload.update(extra)
        self._neira_brain.record_metric(event_type, "server", payload)

    def _finalize_autonomous_response(
        self,
        response: str,
        source: str,
        message: str,
        user_id: Optional[str],
        latency_ms: float,
        autonomy_engine: Optional[Any],
        record_latency: bool,
        event_type: str = "autonomous_response",
        was_autonomous: bool = True,
        record_in_monitor: bool = True,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str]:
        """Зафиксировать автономный ответ и обновить контекст."""
        self._record_response_metric(event_type, source, message, latency_ms, extra)
        if autonomy_engine and record_latency and record_in_monitor:
            autonomy_engine.record_response(source, latency_ms, was_autonomous)
        self._update_autonomy_context(autonomy_engine, user_id, message, response)
        return response, source

    def _update_autonomy_context(
        self,
        autonomy_engine: Optional[Any],
        user_id: Optional[str],
        message: str,
        response: str,
    ) -> None:
        """Обновить контекст AutonomyEngine."""
        if not autonomy_engine or not user_id:
            return
        autonomy_engine.update_context(user_id, "user", message)
        autonomy_engine.update_context(user_id, "assistant", response)

    def _get_user_context(self, user_id: Optional[str]) -> Dict[str, Any]:
        """Получить контекст пользователя для автономных ответов."""
        if not user_id or not self._neira_brain:
            return {}
        prefs = self._neira_brain.get_user_prefs(user_id)
        if not prefs:
            return {}
        context = dict(prefs.get("variables", {}))
        name = prefs.get("name")
        if name:
            context["user_name"] = name
        return context

    def _try_executable_organs_response(
        self,
        message: str,
        user_id: Optional[str],
        start_time: float,
    ) -> Tuple[Optional[str], Optional[str], Optional[float]]:
        """Пробовать ответ через ExecutableOrgans."""
        if not self._executable_organs:
            return None, None, None
        best_organ, confidence = self._executable_organs.find_best_organ(message)
        if not best_organ or confidence < EXECUTABLE_ORGAN_CONFIDENCE:
            return None, None, None
        result, organ_id, record_id = self._executable_organs.process_command(message)
        latency = (time.perf_counter() - start_time) * 1000

        self._last_organ_response = {
            "organ_id": organ_id,
            "record_id": record_id,
            "user_id": user_id,
        }

        logger.info(f"🧬 ExecutableOrgan {organ_id} за {latency:.1f}ms (confidence={confidence:.2f})")
        return result, f"executable_organ:{organ_id}", latency

    def _try_context_cache_response(
        self,
        message: str,
        user_id: Optional[str],
        autonomy_engine: Optional[Any],
        start_time: float,
        record_latency: bool,
    ) -> Tuple[Optional[str], Optional[float]]:
        """Пробовать контекстный ответ AutonomyEngine."""
        if not autonomy_engine or not user_id:
            return None, None
        contextual = autonomy_engine.get_contextual_response(message, user_id)
        if not contextual:
            return None, None
        latency = (time.perf_counter() - start_time) * 1000
        if record_latency:
            autonomy_engine.record_response("context_cache", latency, True)
        logger.info(f"🗂️ Контекстный ответ за {latency:.1f}ms")
        return contextual, latency

    def _try_cortex_response(
        self,
        message: str,
        user_id: Optional[str],
        user_context: Dict[str, Any],
        start_time: float,
    ) -> Optional[Dict[str, Any]]:
        """Пробовать ответ через Cortex."""
        if self._cortex is None:
            return None
        try:
            result = self._cortex.process(message, user_id or "server", context=user_context)
        except (RuntimeError, ValueError, OSError, AttributeError) as exc:
            logger.warning(f"⚠️ Cortex ошибка: {exc}")
            return None

        response = str(getattr(result, "response", "")).strip()
        if not response:
            return None

        latency_ms = getattr(result, "latency_ms", None)
        if latency_ms is None:
            latency_ms = (time.perf_counter() - start_time) * 1000

        llm_used = bool(getattr(result, "llm_used", False))
        strategy = getattr(getattr(result, "strategy", None), "value", None) or str(getattr(result, "strategy", "unknown"))
        intent = getattr(getattr(result, "intent", None), "value", None) or str(getattr(result, "intent", "unknown"))

        extra = {
            "strategy": strategy,
            "intent": intent,
            "confidence": getattr(result, "confidence", None),
            "pathway_id": getattr(result, "pathway_id", None),
            "llm_used": llm_used,
        }

        return {
            "response": response,
            "source": f"cortex:{strategy}",
            "latency_ms": float(latency_ms),
            "llm_used": llm_used,
            "extra": extra,
        }

    def _should_accept_cortex_result(self, cortex_result: Dict[str, Any]) -> bool:
        """Проверить, что ответ Cortex достаточно качественный, чтобы прерывать дальнейший пайплайн."""
        response = str(cortex_result.get("response", "")).strip()
        if not response:
            return False

        extra = cortex_result.get("extra") or {}
        confidence = extra.get("confidence")
        if isinstance(confidence, (int, float)) and float(confidence) < CORTEX_MIN_CONFIDENCE:
            return False

        llm_used = bool(cortex_result.get("llm_used", False))
        strategy = str(extra.get("strategy", "")).strip().lower()
        if not llm_used and strategy in CORTEX_SKIP_STRATEGIES:
            return False

        return True

    async def _call_neira_process(self, prompt: str) -> str:
        """Безопасно вызвать синхронный `Neira.process` без блокировки event loop."""
        if self.neira is None:
            raise RuntimeError("Neira not initialized")
        work = asyncio.to_thread(self.neira.process, prompt)
        if self._llm_timeout_sec <= 0:
            return await work
        return await asyncio.wait_for(work, timeout=self._llm_timeout_sec)

    def _try_response_engine_response(
        self,
        message: str,
        user_context: Dict[str, Any],
        start_time: float,
    ) -> Tuple[Optional[str], Optional[str], Optional[float]]:
        """Пробовать ответ через ResponseEngine."""
        if self._response_engine is None:
            return None, None, None
        response, source = self._response_engine.try_respond_autonomous(message, user_context)
        if not response:
            return None, None, None
        latency = (time.perf_counter() - start_time) * 1000
        return response, source, latency

    def _handle_executable_organs_stage(
        self,
        message: str,
        user_id: Optional[str],
        autonomy_engine: Optional[Any],
        start_time: float,
        record_latency: bool,
    ) -> Optional[Tuple[str, str]]:
        """Стадия ExecutableOrgans."""
        response, source, latency = self._try_executable_organs_response(message, user_id, start_time)
        if not (response and source and latency is not None):
            return None
        return self._finalize_autonomous_response(
            response=response,
            source=source,
            message=message,
            user_id=user_id,
            latency_ms=latency,
            autonomy_engine=autonomy_engine,
            record_latency=record_latency,
            extra={"organ_id": source.split(":", 1)[-1]},
        )

    def _should_skip_autonomous(
        self,
        autonomy_engine: Optional[Any],
        message: str,
        user_id: Optional[str],
    ) -> bool:
        """Проверить, нужно ли пропустить автономный ответ."""
        if not autonomy_engine:
            return False
        decision = autonomy_engine.should_respond_autonomous(message, user_id)
        if decision.decision.value == "llm_required" and (not self._offline_mode or self._offline_allow_local_llm):
            logger.debug(f"🤔 Decision: LLM required ({decision.reasoning})")
            return True
        return False

    def _handle_context_cache_stage(
        self,
        message: str,
        user_id: Optional[str],
        autonomy_engine: Optional[Any],
        start_time: float,
        record_latency: bool,
    ) -> Optional[Tuple[str, str]]:
        """Стадия контекстного кэша AutonomyEngine."""
        contextual, latency = self._try_context_cache_response(
            message=message,
            user_id=user_id,
            autonomy_engine=autonomy_engine,
            start_time=start_time,
            record_latency=record_latency,
        )
        if not (contextual and latency is not None):
            return None
        return self._finalize_autonomous_response(
            response=contextual,
            source="context_cache",
            message=message,
            user_id=user_id,
            latency_ms=latency,
            autonomy_engine=autonomy_engine,
            record_latency=record_latency,
            record_in_monitor=False,
        )

    def _handle_cortex_stage(
        self,
        message: str,
        user_id: Optional[str],
        user_context: Dict[str, Any],
        autonomy_engine: Optional[Any],
        start_time: float,
        record_latency: bool,
    ) -> Optional[Tuple[str, str]]:
        """Стадия Cortex."""
        cortex_result = self._try_cortex_response(message, user_id, user_context, start_time)
        if not cortex_result:
            return None
        if not self._should_accept_cortex_result(cortex_result):
            logger.info(
                "🧠 Cortex пропущен (strategy=%s, confidence=%s, llm_used=%s)",
                cortex_result["extra"].get("strategy"),
                cortex_result["extra"].get("confidence"),
                cortex_result["llm_used"],
            )
            return None
        event_type = "autonomous_response"
        was_autonomous = True
        if cortex_result["llm_used"]:
            event_type = "hybrid_response"
            was_autonomous = False
            self._record_response_metric(
                "llm_call",
                "cortex",
                message,
                cortex_result["latency_ms"],
                cortex_result["extra"],
            )

        response, source = self._finalize_autonomous_response(
            response=cortex_result["response"],
            source=cortex_result["source"],
            message=message,
            user_id=user_id,
            latency_ms=cortex_result["latency_ms"],
            autonomy_engine=autonomy_engine,
            record_latency=record_latency,
            event_type=event_type,
            was_autonomous=was_autonomous,
            extra=cortex_result["extra"],
        )
        logger.info(
            f"🧠 Cortex ответ за {cortex_result['latency_ms']:.1f}ms "
            f"(strategy={cortex_result['extra'].get('strategy')}, llm_used={cortex_result['llm_used']})"
        )
        return response, source

    def _handle_response_engine_stage(
        self,
        message: str,
        user_id: Optional[str],
        user_context: Dict[str, Any],
        autonomy_engine: Optional[Any],
        start_time: float,
        record_latency: bool,
    ) -> Optional[Tuple[str, str]]:
        """Стадия ResponseEngine."""
        response, source, latency = self._try_response_engine_response(message, user_context, start_time)
        if not (response and source and latency is not None):
            return None
        response, source = self._finalize_autonomous_response(
            response=response,
            source=source,
            message=message,
            user_id=user_id,
            latency_ms=latency,
            autonomy_engine=autonomy_engine,
            record_latency=record_latency,
        )
        logger.info(f"🤖 Автономный ответ за {latency:.1f}ms (источник: {source})")
        return response, source
    
    def _try_autonomous_response(
        self, 
        message: str, 
        user_id: Optional[str] = None,
        record_latency: bool = True
    ) -> Tuple[Optional[str], Optional[str]]:
        """Попытаться ответить автономно (без LLM)."""
        start_time = time.perf_counter()

        autonomy_engine = getattr(self, "_autonomy_engine", None)
        if not (self._response_engine or self._executable_organs or autonomy_engine or self._cortex):
            return None, None

        try:
            result = self._handle_executable_organs_stage(
                message=message,
                user_id=user_id,
                autonomy_engine=autonomy_engine,
                start_time=start_time,
                record_latency=record_latency,
            )
            if result:
                return result

            if self._should_skip_autonomous(autonomy_engine, message, user_id):
                return None, None

            result = self._handle_context_cache_stage(
                message=message,
                user_id=user_id,
                autonomy_engine=autonomy_engine,
                start_time=start_time,
                record_latency=record_latency,
            )
            if result:
                return result

            user_context = self._get_user_context(user_id)

            result = self._handle_cortex_stage(
                message=message,
                user_id=user_id,
                user_context=user_context,
                autonomy_engine=autonomy_engine,
                start_time=start_time,
                record_latency=record_latency,
            )
            if result:
                return result

            result = self._handle_response_engine_stage(
                message=message,
                user_id=user_id,
                user_context=user_context,
                autonomy_engine=autonomy_engine,
                start_time=start_time,
                record_latency=record_latency,
            )
            if result:
                return result

            return None, None
            
        except Exception as e:
            logger.warning(f"Ошибка автономного ответа: {e}")
            return None, None
    
    def _store_llm_response(self, query: str, response: str, success: bool = True):
        """Сохранить ответ LLM для будущего использования"""
        if self._response_engine is None:
            return
        
        try:
            self._response_engine.store_llm_response(query, response, success)
        except Exception as e:
            logger.warning(f"Не удалось сохранить ответ: {e}")

    def _touch_activity(self) -> None:
        """Зафиксировать активность сервера."""
        self._last_activity = time.time()

    def _is_idle(self, idle_seconds: int) -> bool:
        """Проверить, что сервер простаивает."""
        return (time.time() - self._last_activity) >= idle_seconds

    @web.middleware
    async def _activity_middleware(self, request: web.Request, handler: Callable[..., Any]) -> web.StreamResponse:
        """Middleware для фиксации активности."""
        self._touch_activity()
        return await handler(request)

    def _is_url_source(self, source: str) -> bool:
        """Проверить, является ли источник URL."""
        return source.strip().lower().startswith(("http://", "https://", "www."))

    def _load_learning_history_sources(self) -> Set[str]:
        """Загрузить список уже изученных источников."""
        history_path = Path("data") / "learning_history.json"
        if not history_path.exists():
            return set()
        try:
            data = json.loads(history_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return set()
        if not isinstance(data, list):
            return set()
        learned: Set[str] = set()
        for entry in data:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source")
            if source:
                learned.add(str(source))
        return learned

    def _load_learning_history_recent(self, limit: int) -> list[Dict[str, Any]]:
        """Загрузить последние записи из learning_history.json (последние -> первые)."""
        safe_limit = min(max(limit, 1), MAX_LEARNING_HISTORY_RECENT_LIMIT)
        history_path = Path("data") / "learning_history.json"
        if not history_path.exists():
            return []
        try:
            data = json.loads(history_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        if not isinstance(data, list):
            return []

        recent = data[-safe_limit:]
        recent.reverse()

        sanitized: list[Dict[str, Any]] = []
        for entry in recent:
            if not isinstance(entry, dict):
                continue
            sanitized.append(
                {
                    "source": str(entry.get("source", "")),
                    "source_type": str(entry.get("source_type", "")),
                    "title": str(entry.get("title", "")),
                    "word_count": int(entry.get("word_count", 0) or 0),
                    "category": str(entry.get("category", "")),
                    "learned_at": str(entry.get("learned_at", "")),
                    "summary": str(entry.get("summary", "")),
                }
            )
        return sanitized

    def _append_offline_learning_error(self, source: str, exc: BaseException) -> None:
        """Сохранить краткую ошибку офлайн-обучения (для прозрачности)."""
        self._offline_learning_recent_errors.append(
            {
                "ts": time.time(),
                "source": source,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        if len(self._offline_learning_recent_errors) > DEFAULT_OFFLINE_LEARNING_MAX_ERROR_ENTRIES:
            self._offline_learning_recent_errors[:] = self._offline_learning_recent_errors[
                -DEFAULT_OFFLINE_LEARNING_MAX_ERROR_ENTRIES:
            ]

    def _query_int(
        self,
        request: web.Request,
        name: str,
        default: int,
        *,
        min_value: int = 0,
        max_value: Optional[int] = None,
    ) -> int:
        """Безопасно распарсить int-параметр из query string."""
        raw = request.query.get(name, "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        if value < min_value:
            return min_value
        if max_value is not None and value > max_value:
            return max_value
        return value

    def _collect_offline_sources(self) -> List[str]:
        """Собрать локальные источники для офлайн-обучения."""
        import os

        from content_extractor import ContentExtractor

        learned_sources = self._load_learning_history_sources()
        allowed_ext = {ext.lower() for ext in ContentExtractor.TEXT_EXTENSIONS}
        candidates: List[Tuple[float, str]] = []

        exclude_dirs = set(self._offline_learning_exclude_dirs)

        for root in self._offline_learning_dirs:
            root_path = (Path(self.workspace_root) / root).resolve()
            if not root_path.exists():
                continue
            iterator: List[Path] = []
            if self._offline_learning_include_globs:
                for pattern in self._offline_learning_include_globs:
                    try:
                        iterator.extend([p for p in root_path.glob(pattern) if p.is_file()])
                    except (OSError, ValueError):
                        continue
            else:
                for current_root, dirnames, filenames in os.walk(root_path):
                    dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
                    for filename in filenames:
                        iterator.append(Path(current_root) / filename)

            for file_path in iterator:
                if file_path.suffix.lower() not in allowed_ext:
                    continue
                try:
                    resolved = file_path.resolve()
                except OSError:
                    continue
                if not resolved.is_relative_to(root_path):
                    continue
                if any(part in exclude_dirs for part in resolved.parts):
                    continue
                try:
                    stat = resolved.stat()
                except OSError:
                    continue
                if stat.st_size > self._offline_learning_max_bytes:
                    continue
                abs_path = str(resolved)
                if abs_path in learned_sources:
                    continue
                candidates.append((stat.st_mtime, abs_path))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [path for _, path in candidates[:self._offline_learning_max_files]]

    async def _learn_offline_sources(self, sources: List[str]) -> Dict[str, int]:
        """Офлайн-обучение по локальным источникам."""
        from content_extractor import LearningManager

        memory = None
        if self.neira and hasattr(self.neira, "memory"):
            memory = self.neira.memory
        manager = LearningManager(memory)

        success = 0
        total_words = 0
        for source in sources:
            try:
                result = await manager.learn_from_source(
                    source,
                    self._offline_learning_category,
                    self._offline_learning_summarize,
                )
            except (
                FileNotFoundError,
                PermissionError,
                OSError,
                UnicodeDecodeError,
                ValueError,
                TypeError,
                KeyError,
                RuntimeError,
            ) as exc:
                logger.warning(f"⚠️ Offline learning error для {source}: {exc}")
                self._append_offline_learning_error(source, exc)
                continue
            if result.get("success"):
                success += 1
                total_words += int(result.get("word_count", 0))

        return {"total": len(sources), "success": success, "total_words": total_words}

    async def _run_offline_learning_once(self) -> None:
        """Запустить единичный цикл офлайн-обучения."""
        if not await self._ensure_neira():
            return
        started = time.time()
        sources = self._collect_offline_sources()
        self._last_learning_sources = list(sources)[:DEFAULT_OFFLINE_LEARNING_MAX_SOURCES_PREVIEW]
        if not sources:
            self._last_learning_run = time.time()
            self._last_learning_run_stats = {
                "total": 0,
                "success": 0,
                "total_words": 0,
                "duration_sec": round(time.time() - started, 3),
            }
            return
        stats = await self._learn_offline_sources(sources)
        if stats["total"] > 0:
            logger.info(
                f"🎓 Оффлайн-обучение: {stats['success']}/{stats['total']} источников, {stats['total_words']} слов"
            )
        self._last_learning_run = time.time()
        self._last_learning_run_stats = {
            **stats,
            "duration_sec": round(time.time() - started, 3),
        }

    async def _offline_learning_loop(self) -> None:
        """Фоновый цикл офлайн-обучения."""
        if self._offline_learning_initial_delay > 0:
            await asyncio.sleep(self._offline_learning_initial_delay)
        while True:
            await asyncio.sleep(self._offline_learning_interval)
            if not self._offline_learning_enabled:
                continue
            if not self._is_idle(self._offline_learning_idle_seconds):
                continue
            try:
                await self._run_offline_learning_once()
            except (OSError, RuntimeError, ValueError, TypeError, KeyError) as exc:
                logger.warning(f"⚠️ Offline learning loop error: {exc}")
                self._append_offline_learning_error("<offline_learning_loop>", exc)

    async def _run_autonomy_optimize_once(self) -> None:
        """Запустить единичный цикл оптимизации автономности (Phase 3)."""
        autonomy_engine = getattr(self, "_autonomy_engine", None)
        if not autonomy_engine:
            return
        self._last_autonomy_optimize_run = time.time()
        await asyncio.to_thread(autonomy_engine.optimize)

    async def _autonomy_optimize_loop(self) -> None:
        """Фоновый цикл оптимизации автономности (Phase 3)."""
        while True:
            await asyncio.sleep(self._autonomy_optimize_interval)
            if not self._autonomy_optimize_enabled:
                continue
            if not self._is_idle(self._autonomy_optimize_idle_seconds):
                continue
            try:
                await self._run_autonomy_optimize_once()
            except Exception as exc:
                logger.warning(f"Autonomy optimize loop error: {exc}")

    def _get_autonomy_metrics_snapshot(self) -> Dict[str, Any]:
        """Снимок метрик автономности."""
        if self._response_engine:
            stats = self._response_engine.get_autonomy_stats()
            return stats.get("metrics", {})
        if self._neira_brain:
            return self._neira_brain.get_metrics_summary(hours=24)
        return {}

    def _should_run_evolution(self, now: float) -> bool:
        """Проверить условия для запуска эволюции."""
        if now - self._last_evolution_run >= self._evolution_interval:
            return True
        if now - self._last_evolution_run < self._evolution_min_interval:
            return False
        metrics = self._get_autonomy_metrics_snapshot()
        total_requests = int(metrics.get("total_requests", 0))
        autonomy_rate = float(metrics.get("autonomy_rate_strict", metrics.get("autonomy_rate", 0)))
        if total_requests < self._evolution_min_requests:
            return False
        return autonomy_rate < self._evolution_autonomy_threshold

    async def _run_evolution_once(self) -> None:
        """Запустить единичный цикл эволюции."""
        if not await self._ensure_neira():
            return
        if not self.neira:
            return
        evolution = getattr(self.neira, "evolution", None)
        if evolution is None and hasattr(self.neira, "_ensure_evolution"):
            ok = self.neira._ensure_evolution()
            if not ok:
                return
            evolution = getattr(self.neira, "evolution", None)
        if evolution is None:
            logger.info("⚠️ EvolutionManager недоступен")
            return
        self._last_evolution_run = time.time()
        await asyncio.to_thread(evolution.auto_evolution_cycle)

    async def _evolution_loop(self) -> None:
        """Фоновый цикл эволюции (гибрид)."""
        while True:
            await asyncio.sleep(self._evolution_check_interval)
            if not self._evolution_enabled:
                continue
            if not self._is_idle(self._evolution_idle_seconds):
                continue
            now = time.time()
            if not self._should_run_evolution(now):
                continue
            try:
                await self._run_evolution_once()
            except Exception as exc:
                logger.warning(f"⚠️ Evolution loop error: {exc}")

    def _start_background_tasks(self) -> None:
        """Запустить фоновые задачи."""
        if self._offline_learning_enabled:
            self._background_tasks.add(asyncio.create_task(self._offline_learning_loop()))
        if self._evolution_enabled:
            self._background_tasks.add(asyncio.create_task(self._evolution_loop()))
        if self._autonomy_optimize_enabled:
            self._background_tasks.add(asyncio.create_task(self._autonomy_optimize_loop()))

    async def _stop_background_tasks(self) -> None:
        """Остановить фоновые задачи."""
        if not self._background_tasks:
            return
        for task in self._background_tasks:
            task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

    async def initialize_neira(self) -> bool:
        """Инициализация Нейры"""
        if self.neira is not None:
            return True

        neira_class = self._import_neira_class()
        if neira_class is None:
            logger.error("Neira недоступна")
            return False
        
        try:
            logger.info("🧠 Инициализация Нейры...")
            self.neira = neira_class(verbose=False)
            logger.info("✅ Нейра готова к работе")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Нейры: {e}")
            return False

    def _import_neira_class(self) -> Optional[type]:
        if self._neira_error:
            return None
        try:
            from main import Neira

            return Neira
        except Exception as e:
            self._neira_error = str(e)
            logger.warning(f"Не удалось импортировать Neira: {e}")
            return None

    async def _ensure_neira(self) -> bool:
        if self.neira is not None:
            return True
        async with self._neira_lock:
            if self.neira is not None:
                return True
            return await self.initialize_neira()

    async def _require_neira(self, request_id: Optional[str] = None) -> Optional[web.Response]:
        if await self._ensure_neira():
            return None
        return web.json_response(
            json.loads(ServerResponse(
                success=False,
                error="Нейра не инициализирована",
                request_id=request_id
            ).to_json()),
            status=503,
            headers=self._cors_headers()
        )

    def _get_fs_agent(self) -> Optional["FileSystemAgent"]:
        if self.fs_agent is not None or self._fs_agent_error:
            return self.fs_agent
        if not self.modules.is_enabled(MODULE_FILES):
            return None
        try:
            from file_system_agent import FileSystemAgent
        except Exception as e:
            self._fs_agent_error = str(e)
            logger.warning(f"FileSystemAgent недоступен: {e}")
            return None

        try:
            self.fs_agent = FileSystemAgent(self.workspace_root)
            logger.info(f"📂 FileSystemAgent: {self.workspace_root}")
        except Exception as e:
            self._fs_agent_error = str(e)
            logger.warning(f"FileSystemAgent не создан: {e}")
        return self.fs_agent

    def _get_tool_system(self) -> Optional[ToolSystem]:
        if self._tool_system is not None or self._tool_system_error:
            return self._tool_system
        if not self.modules.is_enabled(MODULE_TOOLS):
            return None
        try:
            from tool_system import tool_executor, tool_registry
        except Exception as e:
            self._tool_system_error = str(e)
            logger.warning(f"Tool System недоступен: {e}")
            return None

        self._tool_system = ToolSystem(executor=tool_executor, registry=tool_registry)
        return self._tool_system

    def _get_indexer_getter(self) -> Optional[Callable[[str], Any]]:
        if self._indexer_getter is not None or self._indexer_error:
            return self._indexer_getter
        if not self.modules.is_enabled(MODULE_INDEXER):
            return None
        try:
            from workspace_indexer import get_indexer
        except Exception as e:
            self._indexer_error = str(e)
            logger.warning(f"Workspace Indexer недоступен: {e}")
            return None

        self._indexer_getter = get_indexer
        return self._indexer_getter

    def _get_context_functions(self) -> Optional[ContextFunctions]:
        if self._context_functions is not None or self._context_error:
            return self._context_functions
        if not self.modules.is_enabled(MODULE_CONTEXT):
            return None
        try:
            from context_manager import (
                get_context_manager,
                estimate_tokens,
                calculate_optimal_context_size,
            )
        except Exception as e:
            self._context_error = str(e)
            logger.warning(f"Context Manager недоступен: {e}")
            return None

        self._context_functions = ContextFunctions(
            get_context_manager=get_context_manager,
            estimate_tokens=estimate_tokens,
            optimal_context_size=calculate_optimal_context_size,
        )
        return self._context_functions

    def _get_layers_system(self) -> Optional[ModelLayersSystem]:
        if self._layers_system is not None or self._layers_error:
            return self._layers_system
        if not self.modules.is_enabled(MODULE_LAYERS):
            return None
        try:
            from model_layers import ModelLayersRegistry, ModelLayer, ModelLayersError
        except Exception as e:
            self._layers_error = str(e)
            logger.warning(f"Model layers недоступны: {e}")
            return None

        if self.layers_registry is None:
            try:
                self.layers_registry = ModelLayersRegistry(Path(self.workspace_root) / "model_layers.json")
                logger.info(f"🧩 ModelLayersRegistry: {self.layers_registry.path}")
            except Exception as e:
                self._layers_error = str(e)
                logger.warning(f"ModelLayersRegistry не создан: {e}")
                return None

        self._layers_system = ModelLayersSystem(
            registry=self.layers_registry,
            layer_class=ModelLayer,
            error_class=ModelLayersError,
        )
        return self._layers_system

    def _get_model_manager_module(self) -> Optional[ModelManagerModule]:
        if self._model_manager_module is not None or self._model_manager_error:
            return self._model_manager_module
        if not self.modules.is_enabled(MODULE_MODELS):
            return None
        try:
            import model_manager
        except Exception as e:
            self._model_manager_error = str(e)
            logger.warning(f"ModelManager недоступен: {e}")
            return None

        self._model_manager_module = ModelManagerModule(
            manager_class=model_manager.ModelManager,
            models=model_manager.MODELS,
        )
        return self._model_manager_module

    def _get_model_manager(self) -> Optional[Any]:
        if self.model_manager is not None:
            return self.model_manager

        module = self._get_model_manager_module()
        if module is None:
            return None

        try:
            self.model_manager = module.manager_class(verbose=False)
            logger.info("🧠 ModelManager инициализирован")
        except Exception as e:
            self._model_manager_error = str(e)
            logger.warning(f"ModelManager не создан: {e}")
        return self.model_manager

    def _needs_neira(self) -> bool:
        return any(
            self.modules.is_enabled(module)
            for module in (MODULE_CORE, MODULE_STREAM, MODULE_WS, MODULE_SELF)
        )

    def _is_address_in_use(self, error: OSError) -> bool:
        winerror = getattr(error, "winerror", None)
        return (
            error.errno in {errno.EADDRINUSE, 98, 48, 10048}
            or winerror == 10048
        )

    async def _probe_existing_server(self) -> Optional[Dict[str, Any]]:
        if not AIOHTTP_AVAILABLE:
            return None
        url = f"http://{self.host}:{self.port}/health"
        try:
            timeout = aiohttp.ClientTimeout(total=1.5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    payload = await response.json()
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _log_chat_event(
        self,
        *,
        request_id: str,
        endpoint: str,
        message: str,
        response: Optional[str] = None,
        error: Optional[str] = None,
        context: Optional[str] = None,
        duration_ms: Optional[int] = None,
        model: Optional[str] = None,
    ) -> None:
        if CHAT_LOGGER is None:
            return

        entry: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "endpoint": endpoint,
            "message": _truncate_for_log(message) or "",
            "status": "error" if error else "ok",
        }
        if model:
            entry["model"] = model
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms
        if response is not None:
            entry["response"] = _truncate_for_log(response) or ""
        if error:
            entry["error"] = error
        if CHAT_LOG_INCLUDE_CONTEXT and context:
            entry["context"] = _truncate_for_log(context) or ""

        try:
            CHAT_LOGGER.info(json.dumps(entry, ensure_ascii=False))
        except Exception as exc:
            logger.warning(f"Не удалось записать лог чата: {exc}")

    def _extract_self_name(self, message: str) -> Optional[str]:
        match = _SELF_NAME_PATTERN.search(message)
        if not match:
            return None
        return match.group(1)

    def _extract_explicit_name(self, message: str) -> Optional[str]:
        for pattern in _EXPLICIT_NAME_PATTERNS:
            match = pattern.search(message)
            if match:
                return match.group(1)
        return None

    def _update_user_name(self, user_id: str, name: str) -> None:
        if not self._neira_brain:
            return
        cleaned = name.strip()
        if not cleaned:
            return
        prefs = self._neira_brain.get_user_prefs(user_id)
        if prefs.get("name") == cleaned:
            return
        prefs["name"] = cleaned
        self._neira_brain.save_user_prefs(user_id, prefs)

    def _build_user_identity_header(
        self,
        message: str,
        user_id: Optional[str],
        user_name: Optional[str],
    ) -> str:
        resolved_name = user_name.strip() if user_name else None
        if user_id and resolved_name:
            self._update_user_name(user_id, resolved_name)

        if not resolved_name and user_id and self._neira_brain:
            prefs = self._neira_brain.get_user_prefs(user_id)
            resolved_name = prefs.get("name") or None

        explicit_name = self._extract_explicit_name(message)
        if user_id and explicit_name:
            self._update_user_name(user_id, explicit_name)
            if not resolved_name:
                resolved_name = explicit_name

        try:
            from neira.utils.identity import resolve_creator_identity
        except ImportError:
            resolve_creator_identity = None

        creator_info = None
        if resolve_creator_identity:
            if resolved_name:
                creator_info = resolve_creator_identity(resolved_name)
            if not creator_info and user_id:
                creator_info = resolve_creator_identity(user_id)
            if not creator_info:
                self_name = self._extract_self_name(message)
                if self_name:
                    creator_info = resolve_creator_identity(self_name)

        if creator_info:
            label = f"{creator_info['display_name']} ({creator_info['role']})"
            return f"[Собеседник]\n{label}"
        if resolved_name:
            return f"[Собеседник]\n{resolved_name} (пользователь)"
        return ""

    def _compose_full_message(
        self,
        *,
        message: str,
        context: Optional[str],
        user_id: Optional[str],
        user_name: Optional[str],
    ) -> str:
        parts = []
        identity_header = self._build_user_identity_header(message, user_id, user_name)
        if identity_header:
            parts.append(identity_header)

        self_model = self._build_self_model_context()
        if self_model:
            parts.append(self_model)
        if context:
            parts.append(f"[Контекст из редактора]\n```\n{context}\n```")
        parts.append(message)
        return "\n\n".join(parts)

    def _build_self_model_context(self) -> str:
        """Сформировать краткую «самомодель» — список возможностей и ограничений для LLM."""
        organ_names: list[str] = []
        if self._organ_system and hasattr(self._organ_system, "organs"):
            try:
                organ_names.extend([str(o.name) for o in self._organ_system.organs.values() if getattr(o, "name", None)])
            except (AttributeError, RuntimeError, ValueError, TypeError):
                pass
        if self._executable_organs and hasattr(self._executable_organs, "organs"):
            try:
                organ_names.extend([str(o.name) for o in self._executable_organs.organs.values() if getattr(o, "name", None)])
            except (AttributeError, RuntimeError, ValueError, TypeError):
                pass

        organ_names = sorted({name.strip() for name in organ_names if str(name).strip()})
        organ_preview = ", ".join(organ_names[:12]) if organ_names else "(нет)"

        # === Фоновая активность (обучение + эволюция) ===
        now = time.time()
        background_activity = self._build_background_activity_summary(now)

        lines = [
            "[Самомодель Neira]",
            f"- offline_mode: {self._offline_mode}",
            f"- offline_allow_local_llm: {self._offline_allow_local_llm}",
            f"- cortex_enabled: {self._cortex_enabled}",
            f"- organs: {organ_preview}",
            "",
            background_activity,
            "",
            "[Правила]",
            "- Не утверждай, что создала/установила/изменила что-либо без факта.",
            "- Создание органов допустимо только по явной команде (/grow или фраза «создай орган»).",
            "- Если просят создать орган — объясни, как правильно сделать это через /grow, но не «создавай» в тексте.",
            "- Если спрашивают о фоновой активности — используй данные из [Фоновая активность].",
        ]
        return "\n".join([line for line in lines if line])

    def _build_background_activity_summary(self, now: float) -> str:
        """Сформировать описание фоновой активности для самомодели."""
        lines = ["[Фоновая активность]"]

        # --- Офлайн-обучение ---
        if self._offline_learning_enabled:
            if self._last_learning_run > 0:
                ago_sec = now - self._last_learning_run
                ago_str = self._format_time_ago(ago_sec)
                lines.append(f"- Обучение: последний запуск {ago_str}")
            else:
                lines.append("- Обучение: ещё не запускалось")

            if self._last_learning_run_stats:
                total = int(self._last_learning_run_stats.get("total", 0) or 0)
                success = int(self._last_learning_run_stats.get("success", 0) or 0)
                words = int(self._last_learning_run_stats.get("total_words", 0) or 0)
                duration = float(self._last_learning_run_stats.get("duration_sec", 0) or 0)
                lines.append(f"  - Обработано: {success}/{total} источников, ~{words} слов за {duration:.1f}с")

            # Последние выученные источники (до 5)
            recent = self._load_learning_history_recent(5)
            if recent:
                lines.append("  - Недавно выучено:")
                for item in recent:
                    title = item.get("title") or item.get("source", "(без названия)")
                    # Сокращаем длинные пути
                    if len(title) > 60:
                        title = "..." + title[-57:]
                    word_count = item.get("word_count", 0)
                    lines.append(f"    • {title} ({word_count} слов)")

            # Ошибки обучения (если есть недавние)
            if self._offline_learning_recent_errors:
                recent_errors = [e for e in self._offline_learning_recent_errors if now - e.get("ts", 0) < 3600]
                if recent_errors:
                    lines.append(f"  - ⚠️ Ошибки за последний час: {len(recent_errors)}")
        else:
            lines.append("- Обучение: отключено")

        # --- Эволюция ---
        if self._evolution_enabled:
            if self._last_evolution_run > 0:
                ago_sec = now - self._last_evolution_run
                ago_str = self._format_time_ago(ago_sec)
                lines.append(f"- Эволюция: последний цикл {ago_str}")
            else:
                lines.append("- Эволюция: ещё не запускалась")
        else:
            lines.append("- Эволюция: отключена")

        # --- Оптимизация автономности ---
        if self._autonomy_optimize_enabled and self._last_autonomy_optimize_run > 0:
            ago_sec = now - self._last_autonomy_optimize_run
            ago_str = self._format_time_ago(ago_sec)
            lines.append(f"- Оптимизация: последний запуск {ago_str}")

        return "\n".join(lines)

    def _format_time_ago(self, seconds: float) -> str:
        """Форматировать время назад в читаемом виде."""
        if seconds < 60:
            return "только что"
        if seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} мин. назад"
        if seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} ч. назад"
        days = int(seconds / 86400)
        return f"{days} дн. назад"

    def _is_explicit_organ_request(self, message: str) -> bool:
        """Проверить, что пользователь явно просит создать орган."""
        lowered = message.lower()
        return any(token in lowered for token in ("/grow", "#создай_орган", "#grow_organ", "#create_organ", "создай орган", "вырасти орган", "отрасти орган"))

    def _guard_llm_response(self, response: str, user_message: str | None = None) -> str:
        """Удалить опасные/ложные утверждения и эхо пользователя из ответа LLM."""
        text = response.strip()
        if not text:
            return text

        lowered = text.lower()
        blocked_claims = (
            "я создал орган",
            "я создала орган",
            "создал(а) орган",
            "я создал новый орган",
            "я создала новый орган",
            "я добавил орган",
            "я добавила орган",
        )
        if any(claim in lowered for claim in blocked_claims):
            return (
                "Я не создаю органы автоматически в ответе.\n"
                "Если действительно нужен новый орган — используйте явную команду `/grow <описание>` "
                "или напишите «создай орган <описание>», и я подскажу следующий шаг."
            )
        if user_message:
            cleaned_message = user_message.strip()
            if len(cleaned_message) >= 120:
                msg_lower = cleaned_message.lower()
                idx = lowered.find(msg_lower)
                if idx != -1:
                    text = (text[:idx] + text[idx + len(cleaned_message):]).strip()
                else:
                    prefix = msg_lower[:200]
                    idx = lowered.find(prefix)
                    if idx != -1:
                        text = (text[:idx] + text[idx + len(prefix):]).strip()
                if len(text) < 30:
                    return (
                        "Похоже, я повторила ваш текст вместо ответа.\n"
                        "Сформулируйте запрос короче (1-2 предложения) или уточните, какой результат нужен."
                    )
        return text
    
    def _cors_headers(self) -> Dict[str, str]:
        """CORS заголовки для VS Code / Cursor"""
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600"
        }
    
    async def handle_options(self, request: web.Request) -> web.Response:
        """Обработка CORS preflight"""
        return web.Response(headers=self._cors_headers())
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """Проверка состояния сервера"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        response = ServerResponse(
            success=True,
            data={
                "status": "online",
                "neira_ready": self.neira is not None,
                "uptime_seconds": round(uptime, 2),
                "requests_processed": self.request_count,
                "websocket_clients": len(self.websockets),
                "version": "1.0.0",
                "modules_enabled": sorted(self.modules.enabled),
                "lazy_neira": self.lazy_neira
            }
        )
        
        return web.json_response(
            json.loads(response.to_json()),
            headers=self._cors_headers()
        )
    
    async def handle_autonomy_stats(self, request: web.Request) -> web.Response:
        """Статистика автономности (Phase 1)"""
        try:
            now = time.time()
            stats = {
                "autonomy_available": self._response_engine is not None,
                "error": self._autonomy_modules_error,
                "offline_mode": self._offline_mode,
                "offline_allow_local_llm": self._offline_allow_local_llm,
                "cortex_available": self._cortex is not None,
            }
            if self._cortex_error:
                stats["cortex_error"] = self._cortex_error

            stats["llm_config"] = {
                "provider_priority": os.getenv("LLM_PROVIDER_PRIORITY", ""),
                "ollama_model": os.getenv("NEIRA_OLLAMA_MODEL", ""),
                "ollama_disabled": os.getenv("NEIRA_DISABLE_OLLAMA", ""),
                "ollama_num_ctx": int(os.getenv("NEIRA_OLLAMA_NUM_CTX", "0") or 0),
                "ollama_num_gpu": int(os.getenv("NEIRA_OLLAMA_NUM_GPU", "0") or 0),
                "max_response_tokens": int(os.getenv("NEIRA_MAX_RESPONSE_TOKENS", "0") or 0),
                "timeout_sec": self._llm_timeout_sec,
            }
            stats["offline_learning"] = {
                "enabled": self._offline_learning_enabled,
                "summarize": self._offline_learning_summarize,
                "category": self._offline_learning_category,
                "dirs": list(self._offline_learning_dirs),
                "include_globs": list(self._offline_learning_include_globs),
                "exclude_dirs": list(self._offline_learning_exclude_dirs),
                "interval_sec": self._offline_learning_interval,
                "idle_sec": self._offline_learning_idle_seconds,
                "max_files": self._offline_learning_max_files,
                "max_mb": int(self._offline_learning_max_bytes // BYTES_IN_MB),
                "initial_delay_sec": self._offline_learning_initial_delay,
                "last_run_ts": self._last_learning_run,
                "last_run_ago_sec": (now - self._last_learning_run) if self._last_learning_run else None,
                "last_run_stats": self._last_learning_run_stats,
                "last_sources": list(self._last_learning_sources),
                "recent_errors": list(self._offline_learning_recent_errors),
            }
            stats["evolution"] = {
                "enabled": self._evolution_enabled,
                "interval_sec": self._evolution_interval,
                "check_interval_sec": self._evolution_check_interval,
                "idle_sec": self._evolution_idle_seconds,
                "min_requests": self._evolution_min_requests,
                "autonomy_threshold": self._evolution_autonomy_threshold,
                "min_interval_sec": self._evolution_min_interval,
                "last_run_ts": self._last_evolution_run,
                "last_run_ago_sec": (now - self._last_evolution_run) if self._last_evolution_run else None,
            }
            stats["autonomy_optimize"] = {
                "enabled": self._autonomy_optimize_enabled,
                "interval_sec": self._autonomy_optimize_interval,
                "idle_sec": self._autonomy_optimize_idle_seconds,
                "last_run_ts": self._last_autonomy_optimize_run,
                "last_run_ago_sec": (now - self._last_autonomy_optimize_run) if self._last_autonomy_optimize_run else None,
            }
            
            if self._response_engine:
                engine_stats = self._response_engine.get_autonomy_stats()
                stats.update(engine_stats)
                
            if self._organ_system:
                stats["organs_count"] = len(self._organ_system.organs)
                stats["organs"] = [
                    {"id": o.id, "name": o.name, "status": o.status.value}
                    for o in list(self._organ_system.organs.values())[:10]
                ]
            
            response = ServerResponse(
                success=True,
                data=stats
            )
            
            return web.json_response(
                json.loads(response.to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_offline_learning_run(self, request: web.Request) -> web.Response:
        """Запустить офлайн-обучение вручную (один цикл)."""
        try:
            neira_error = await self._require_neira()
            if neira_error:
                return neira_error

            sources = self._collect_offline_sources()
            if not sources:
                self._last_learning_run = time.time()
                return web.json_response(
                    json.loads(ServerResponse(
                        success=True,
                        data={"message": "Нет новых источников для обучения", "total": 0, "success": 0, "total_words": 0}
                    ).to_json()),
                    headers=self._cors_headers()
                )

            stats = await self._learn_offline_sources(sources)
            self._last_learning_run = time.time()
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={**stats, "sources": sources}
                ).to_json()),
                headers=self._cors_headers()
            )
        except Exception as e:
            logger.error(f"Ошибка ручного офлайн-обучения: {e}")
            return web.json_response(
                json.loads(ServerResponse(success=False, error=str(e)).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_offline_evolution_run(self, request: web.Request) -> web.Response:
        """Запустить эволюцию вручную (один цикл)."""
        try:
            await self._run_evolution_once()
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"message": "Цикл эволюции запущен", "last_run_ts": self._last_evolution_run}
                ).to_json()),
                headers=self._cors_headers()
            )
        except Exception as e:
            logger.error(f"Ошибка ручной эволюции: {e}")
            return web.json_response(
                json.loads(ServerResponse(success=False, error=str(e)).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_offline_learning_status(self, request: web.Request) -> web.Response:
        """Статус офлайн-обучения: что запускалось и какие ошибки были."""
        self.request_count += 1

        now = time.time()
        payload = {
            "enabled": self._offline_learning_enabled,
            "last_run_ts": self._last_learning_run,
            "last_run_ago_sec": (now - self._last_learning_run) if self._last_learning_run else None,
            "last_run_stats": self._last_learning_run_stats,
            "last_sources": list(self._last_learning_sources),
            "recent_errors": list(self._offline_learning_recent_errors),
        }
        return web.json_response(
            json.loads(ServerResponse(success=True, data=payload).to_json()),
            headers=self._cors_headers(),
        )
    
    async def handle_pathway_feedback(self, request: web.Request) -> web.Response:
        """
        Обработка обратной связи по pathway (Phase 2).
        
        POST /pathway/feedback
        {
            "query": "исходный запрос",
            "response": "ответ который дали",
            "feedback": "positive" | "negative" | "neutral",
            "score": 0.0-1.0 (опционально),
            "user_id": "user123" (опционально),
            "source": "telegram" | "vscode" | "desktop" (опционально)
        }
        
        При положительном feedback:
        - Увеличивает success_count у pathway (если есть)
        - Создаёт новый pathway если запрос частый
        - Кэширует ответ для будущих запросов
        """
        try:
            data = await request.json()
            query = data.get("query", "").strip()
            response_text = data.get("response", "").strip()
            feedback = data.get("feedback", "neutral")  # positive/negative/neutral
            score = data.get("score", 0.5)
            user_id = data.get("user_id")
            source = data.get("source", "unknown")
            
            if not query:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="query обязателен"
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            result = {
                "query": query[:50],
                "feedback": feedback,
                "actions_taken": []
            }
            
            # Записываем метрику
            if self._neira_brain:
                self._neira_brain.record_metric('feedback', source, {
                    'feedback': feedback,
                    'score': score,
                    'query_preview': query[:50]
                })
            
            # Positive feedback - обучаем систему
            if feedback == "positive" and score >= 0.5:
                # 1. Ищем существующий pathway
                if self._response_engine:
                    pathway = self._response_engine.pathway_generator.find_matching_pathway(query)
                    
                    if pathway:
                        # Увеличиваем success_count
                        if self._neira_brain:
                            self._neira_brain.execute("""
                                UPDATE pathways 
                                SET success_count = success_count + 1,
                                    last_used = CURRENT_TIMESTAMP
                                WHERE id = ?
                            """, (pathway['id'],))
                            result["actions_taken"].append(f"pathway_success_incremented:{pathway['id']}")
                    
                    # 2. Кэшируем ответ если его ещё нет
                    if response_text:
                        cached = self._response_engine.cache.get_cached_response(query)
                        if not cached:
                            self._response_engine.cache.cache_response(
                                query=query,
                                response=response_text,
                                source=source,
                                confidence=score
                            )
                            result["actions_taken"].append("response_cached")
                    
                    # 3. Возможно создаём новый pathway
                    if not pathway and response_text:
                        new_pathway = self._response_engine.pathway_generator.maybe_create_pathway(
                            query=query,
                            response=response_text,
                            success=True
                        )
                        if new_pathway:
                            result["actions_taken"].append(f"pathway_created:{new_pathway}")
            
            # Negative feedback - помечаем как плохой ответ
            elif feedback == "negative":
                if self._response_engine:
                    pathway = self._response_engine.pathway_generator.find_matching_pathway(query)
                    if pathway:
                        # Уменьшаем confidence
                        if self._neira_brain:
                            self._neira_brain.execute("""
                                UPDATE pathways 
                                SET confidence = MAX(0.1, confidence - 0.1)
                                WHERE id = ?
                            """, (pathway['id'],))
                            result["actions_taken"].append(f"pathway_confidence_decreased:{pathway['id']}")
                    
                    # Удаляем из кэша плохой ответ
                    if self._neira_brain:
                        self._neira_brain.execute("""
                            DELETE FROM cache 
                            WHERE query = ? AND response = ?
                        """, (query, response_text))
                        result["actions_taken"].append("bad_response_removed_from_cache")
            
            logger.info(f"📊 Feedback '{feedback}' для запроса: {query[:30]}... Actions: {result['actions_taken']}")
            
            # Phase 3: Записываем feedback в monitor
            autonomy_engine = getattr(self, '_autonomy_engine', None)
            if autonomy_engine:
                autonomy_engine.record_feedback(feedback == "positive")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data=result
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            logger.error(f"Ошибка обработки feedback: {e}")
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_autonomy_optimize(self, request: web.Request) -> web.Response:
        """
        Запустить оптимизацию автономности (Phase 3)
        
        POST /autonomy/optimize
        
        Выполняет:
        - Кластеризацию pathways
        - Поиск паттернов
        - Обновление тиров
        """
        try:
            autonomy_engine = getattr(self, '_autonomy_engine', None)
            
            if not autonomy_engine:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="AutonomyEngine не инициализирован"
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            # Запускаем оптимизацию
            results = autonomy_engine.optimize()
            
            # Также обновляем тиры
            if self._response_engine:
                tier_results = self._response_engine.evaluate_all_pathways()
                results['tier_evaluation'] = tier_results
            
            logger.info(f"🔧 Оптимизация завершена: clusters={results.get('clustering', {}).get('clusters', 0)}")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data=results
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации: {e}")
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_autonomy_dashboard(self, request: web.Request) -> web.Response:
        """
        Дашборд автономности (Phase 3)
        
        GET /autonomy/dashboard
        
        Возвращает:
        - Метрики автономности
        - Статистику по тирам
        - Рекомендации
        """
        try:
            dashboard: Dict[str, Any] = {
                "phase1_available": self._response_engine is not None,
                "phase3_available": hasattr(self, '_autonomy_engine') and self._autonomy_engine is not None
            }
            
            # Phase 1 stats
            if self._response_engine:
                phase1_stats = self._response_engine.get_autonomy_stats()
                dashboard["phase1"] = phase1_stats
            
            # Phase 3 dashboard
            autonomy_engine = getattr(self, '_autonomy_engine', None)
            if autonomy_engine:
                dashboard["phase3"] = autonomy_engine.get_stats()
            
            # Organs stats
            if self._organ_system:
                dashboard["organs_count"] = len(self._organ_system.organs)
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data=dashboard
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения dashboard: {e}")
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_organs_list(self, request: web.Request) -> web.Response:
        """
        Список исполняемых органов
        
        GET /organs
        
        Возвращает информацию обо всех ExecutableOrgans
        """
        try:
            organs_info = []
            
            # ExecutableOrgans (с кодом)
            if self._executable_organs:
                for organ in self._executable_organs.organs.values():
                    info = organ.get_info()
                    info['type'] = 'executable'
                    organs_info.append(info)
            
            # UnifiedOrganSystem (метаданные)
            if self._organ_system:
                for organ in self._organ_system.organs.values():
                    organs_info.append({
                        'id': organ.id,
                        'name': organ.name,
                        'description': organ.description,
                        'type': 'unified',
                        'cell_type': organ.cell_type,
                        'triggers': organ.triggers,
                        'status': organ.status.value,
                        'version': getattr(organ, 'version', '1.0.0')
                    })
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={
                        "organs": organs_info,
                        "total": len(organs_info),
                        "executable_count": len(self._executable_organs.organs) if self._executable_organs else 0
                    }
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            logger.error(f"Ошибка получения списка органов: {e}")
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_organs_feedback(self, request: web.Request) -> web.Response:
        """
        Feedback для органа
        
        POST /organs/feedback
        {
            "organ_id": "graphics_organ",
            "feedback": "positive" | "negative" | "correction",
            "correction": "исправленный ответ" (опционально)
        }
        """
        try:
            data = await request.json()
            organ_id = data.get("organ_id")
            feedback_str = data.get("feedback", "neutral")
            correction = data.get("correction")
            
            if not organ_id:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="organ_id обязателен"
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            if not self._executable_organs or not self._feedback_type_class:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="ExecutableOrgans недоступны"
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            # Конвертируем строку в FeedbackType
            feedback_map = {
                "positive": self._feedback_type_class.POSITIVE,
                "negative": self._feedback_type_class.NEGATIVE,
                "neutral": self._feedback_type_class.NEUTRAL,
                "correction": self._feedback_type_class.CORRECTION,
            }
            feedback_type = feedback_map.get(feedback_str, self._feedback_type_class.NEUTRAL)
            
            # Добавляем feedback
            self._executable_organs.add_feedback(organ_id, feedback_type, correction)
            
            logger.info(f"🧬 Feedback для {organ_id}: {feedback_str}")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={
                        "organ_id": organ_id,
                        "feedback": feedback_str,
                        "message": f"Орган {organ_id} получил feedback"
                    }
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            logger.error(f"Ошибка feedback органа: {e}")
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_chat(self, request: web.Request) -> web.Response:
        """Обработка сообщения в чат"""
        self.request_count += 1
        
        try:
            data = await request.json()
            message = data.get("message", "").strip()
            context = data.get("context", "")  # Контекст из редактора
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            user_id = data.get("user_id")  # Для персонализации
            user_name = data.get("user_name")
            
            if not message:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Пустое сообщение",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            # Записываем метрику запроса
            if self._neira_brain:
                self._neira_brain.record_metric('request', 'server', {
                    'message_preview': message[:MESSAGE_PREVIEW_LIMIT],
                    'has_context': bool(context)
                })
            
            logger.info(f"[{request_id}] 📨 Запрос: {message[:MESSAGE_PREVIEW_LIMIT]}...")
            start_time = time.perf_counter()
            
            if self._is_explicit_organ_request(message):
                policy_text = (
                    "Создание органов разрешено только по явной команде.\n"
                    "Используйте `/grow <описание>` (в Telegram) или напишите «создай орган <описание>» — "
                    "я подскажу следующий шаг, но не буду «создавать» орган в тексте."
                )
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                self._log_chat_event(
                    request_id=request_id,
                    endpoint="/chat",
                    message=message,
                    response=policy_text,
                    context=context,
                    duration_ms=duration_ms,
                    model="policy",
                )
                return web.json_response(
                    json.loads(ServerResponse(
                        success=True,
                        data={
                            "response": policy_text,
                            "model": "policy",
                            "task_type": "chat",
                            "model_source": "policy"
                        },
                        request_id=request_id
                    ).to_json()),
                    headers=self._cors_headers()
                )

            # === Phase 1+3: Попытка автономного ответа ===
            autonomous_response, response_source = self._try_autonomous_response(message, user_id)
            if autonomous_response:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                logger.info(f"[{request_id}] ⚡ Автономный ответ за {duration_ms}ms (src: {response_source})")
                
                self._log_chat_event(
                    request_id=request_id,
                    endpoint="/chat",
                    message=message,
                    response=autonomous_response,
                    context=context,
                    duration_ms=duration_ms,
                    model="autonomous",
                )
                
                response = ServerResponse(
                    success=True,
                    data={
                        "response": autonomous_response,
                        "model": "autonomous",
                        "task_type": "chat",
                        "model_source": response_source or "local_pathways"
                    },
                    request_id=request_id
                )
                
                return web.json_response(
                    json.loads(response.to_json()),
                    headers=self._cors_headers()
                )
            
            # === Fallback на LLM ===
            neira_error = await self._require_neira(request_id)
            if neira_error:
                return neira_error
            
            full_message = self._compose_full_message(
                message=message,
                context=context,
                user_id=user_id,
                user_name=user_name,
            )
            
            # Обработка через Нейру (LLM)
            llm_start = time.perf_counter()
            autonomy_engine = getattr(self, "_autonomy_engine", None)
            try:
                response_text = await self._call_neira_process(full_message)
                response_text = self._guard_llm_response(response_text, message)
                llm_latency_ms = (time.perf_counter() - llm_start) * 1000

                if self._neira_brain:
                    self._neira_brain.record_metric("llm_call", "server", {
                        "message_preview": message[:MESSAGE_PREVIEW_LIMIT],
                        "latency_ms": llm_latency_ms,
                        "success": True,
                    })

                if autonomy_engine:
                    autonomy_engine.record_response("llm", llm_latency_ms, False)
                    self._update_autonomy_context(autonomy_engine, user_id, message, response_text)

                # Сохраняем ответ для будущего использования
                self._store_llm_response(message, response_text, success=True)

            except asyncio.TimeoutError:
                llm_latency_ms = (time.perf_counter() - llm_start) * 1000
                if self._neira_brain:
                    self._neira_brain.record_metric("llm_call", "server", {
                        "message_preview": message[:MESSAGE_PREVIEW_LIMIT],
                        "latency_ms": llm_latency_ms,
                        "success": False,
                        "error": "timeout",
                    })
                if autonomy_engine:
                    autonomy_engine.record_response("llm_timeout", llm_latency_ms, False)
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                self._log_chat_event(
                    request_id=request_id,
                    endpoint="/chat",
                    message=message,
                    error="LLM timeout",
                    context=context,
                    duration_ms=duration_ms,
                    model="ollama",
                )
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error=f"Таймаут генерации ({self._llm_timeout_sec}s). Попробуйте короче запрос или уменьшите max_tokens.",
                        request_id=request_id
                    ).to_json()),
                    status=504,
                    headers=self._cors_headers()
                )
            except Exception as e:
                llm_latency_ms = (time.perf_counter() - llm_start) * 1000
                if self._neira_brain:
                    self._neira_brain.record_metric("llm_call", "server", {
                        "message_preview": message[:MESSAGE_PREVIEW_LIMIT],
                        "latency_ms": llm_latency_ms,
                        "success": False,
                        "error": str(e),
                    })
                if autonomy_engine:
                    autonomy_engine.record_response("llm_error", llm_latency_ms, False)
                logger.error(f"[{request_id}] ❌ Ошибка Нейры: {e}")
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                self._log_chat_event(
                    request_id=request_id,
                    endpoint="/chat",
                    message=message,
                    error=str(e),
                    context=context,
                    duration_ms=duration_ms,
                    model="ollama",
                )
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error=f"Ошибка обработки: {str(e)}",
                        request_id=request_id
                    ).to_json()),
                    status=500,
                    headers=self._cors_headers()
                )
            
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(f"[{request_id}] ✅ Ответ: {len(response_text)} символов")
            self._log_chat_event(
                request_id=request_id,
                endpoint="/chat",
                message=message,
                response=response_text,
                context=context,
                duration_ms=duration_ms,
                model="ollama",
            )
            
            response = ServerResponse(
                success=True,
                data={
                    "response": response_text,
                    "model": "ollama",
                    "task_type": "chat",
                    "model_source": "local"
                },
                request_id=request_id
            )
            
            return web.json_response(
                json.loads(response.to_json()),
                headers=self._cors_headers()
            )
            
        except json.JSONDecodeError:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error="Неверный формат JSON"
                ).to_json()),
                status=400,
                headers=self._cors_headers()
            )
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_explain(self, request: web.Request) -> web.Response:
        """Объяснение выделенного кода"""
        self.request_count += 1
        
        try:
            data = await request.json()
            code = data.get("code", "").strip()
            language = data.get("language", "")
            filename = data.get("filename", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not code:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Код не предоставлен",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            neira_error = await self._require_neira(request_id)
            if neira_error:
                return neira_error
            
            # Формируем запрос
            prompt = f"Объясни этот код"
            if language:
                prompt += f" на {language}"
            if filename:
                prompt += f" из файла {filename}"
            prompt += f":\n\n```{language}\n{code}\n```"
            
            logger.info(f"[{request_id}] 🔍 Объяснение кода: {len(code)} символов")
            
            try:
                response_text = await self._call_neira_process(prompt)
            except Exception as e:
                logger.error(f"[{request_id}] ❌ Ошибка: {e}")
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error=str(e),
                        request_id=request_id
                    ).to_json()),
                    status=500,
                    headers=self._cors_headers()
                )
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"response": response_text},
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_generate(self, request: web.Request) -> web.Response:
        """Генерация кода"""
        self.request_count += 1
        
        try:
            data = await request.json()
            description = data.get("description", "").strip()
            language = data.get("language", "python")
            context = data.get("context", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not description:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Описание не предоставлено",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            neira_error = await self._require_neira(request_id)
            if neira_error:
                return neira_error
            
            # Формируем запрос
            prompt = f"Напиши код на {language}: {description}"
            if context:
                prompt = f"[Существующий код]\n```\n{context}\n```\n\n{prompt}"
            
            logger.info(f"[{request_id}] ⚡ Генерация: {description[:50]}...")
            
            try:
                response_text = await self._call_neira_process(prompt)
            except Exception as e:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error=str(e),
                        request_id=request_id
                    ).to_json()),
                    status=500,
                    headers=self._cors_headers()
                )
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"response": response_text},
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_complete(self, request: web.Request) -> web.Response:
        """Inline completion (автодополнение для ghost text)"""
        self.request_count += 1
        
        try:
            data = await request.json()
            prefix = data.get("prefix", "")
            suffix = data.get("suffix", "")
            language = data.get("language", "")
            max_tokens = data.get("max_tokens", 150)
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not prefix.strip():
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Нет контекста для автодополнения",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            neira_error = await self._require_neira(request_id)
            if neira_error:
                return neira_error
            
            # Формируем промпт для completion
            prompt = f"""Ты — AI-автодополнение кода. Продолжи код ТОЧНО с того места, где он заканчивается.
Верни ТОЛЬКО код продолжения (1-3 строки), без объяснений и markdown.

Язык: {language}
Код до курсора:
```
{prefix[-1500:]}
```

Код после курсора:
```
{suffix[:500]}
```

Продолжение (только код):"""

            logger.info(f"[{request_id}] 💡 Completion: {len(prefix)} символов контекста")
            
            try:
                response_text = await self._call_neira_process(prompt)
                # Очищаем ответ от markdown и лишнего
                completion = self._clean_completion(response_text)
                
                completions = [completion] if completion else []
                
            except Exception as e:
                logger.error(f"[{request_id}] ❌ Ошибка completion: {e}")
                completions = []
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"completions": completions},
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    def _clean_completion(self, text: str) -> str:
        """Очистка ответа от markdown и лишнего"""
        text = text.strip()
        # Убираем markdown блоки
        if text.startswith("```"):
            lines = text.split("\n")
            # Убираем первую и последнюю строки с ```
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        # Убираем пустые строки в начале
        text = text.lstrip("\n")
        # Ограничиваем длину
        lines = text.split("\n")[:5]  # Максимум 5 строк
        return "\n".join(lines)
    
    async def handle_fix(self, request: web.Request) -> web.Response:
        """Исправление ошибки в коде"""
        self.request_count += 1
        
        try:
            data = await request.json()
            code = data.get("code", "")
            error = data.get("error", "")
            language = data.get("language", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not code or not error:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Код или ошибка не указаны",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            neira_error = await self._require_neira(request_id)
            if neira_error:
                return neira_error
            
            prompt = f"""Исправь ошибку в коде.

Ошибка: {error}

Код ({language}):
```{language}
{code}
```

Верни исправленный код с кратким объяснением что было не так."""

            logger.info(f"[{request_id}] 🔧 Fix: {error[:50]}...")
            
            try:
                response_text = await self._call_neira_process(prompt)
            except Exception as e:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error=str(e),
                        request_id=request_id
                    ).to_json()),
                    status=500,
                    headers=self._cors_headers()
                )
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"fix": response_text},
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_generate_tests(self, request: web.Request) -> web.Response:
        """Генерация тестов для кода"""
        self.request_count += 1
        
        try:
            data = await request.json()
            code = data.get("code", "")
            language = data.get("language", "python")
            framework = data.get("framework", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not code:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Код не указан",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            neira_error = await self._require_neira(request_id)
            if neira_error:
                return neira_error
            
            # Определяем фреймворк тестирования
            test_frameworks = {
                "python": framework or "pytest",
                "javascript": framework or "jest",
                "typescript": framework or "jest",
                "java": framework or "JUnit",
                "csharp": framework or "xUnit",
                "go": framework or "testing",
                "rust": framework or "built-in"
            }
            fw = test_frameworks.get(language, "unittest")
            
            prompt = f"""Сгенерируй тесты для следующего кода.

Язык: {language}
Фреймворк: {fw}

Код:
```{language}
{code}
```

Создай полноценные тесты с:
- Тестами на нормальное поведение
- Тестами на граничные случаи
- Тестами на ошибки (если применимо)

Верни только код тестов."""

            logger.info(f"[{request_id}] 🧪 Генерация тестов ({fw})")
            
            try:
                response_text = await self._call_neira_process(prompt)
            except Exception as e:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error=str(e),
                        request_id=request_id
                    ).to_json()),
                    status=500,
                    headers=self._cors_headers()
                )
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"tests": response_text},
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_generate_docs(self, request: web.Request) -> web.Response:
        """Генерация документации для кода"""
        self.request_count += 1
        
        try:
            data = await request.json()
            code = data.get("code", "")
            language = data.get("language", "python")
            style = data.get("style", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not code:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Код не указан",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            neira_error = await self._require_neira(request_id)
            if neira_error:
                return neira_error
            
            # Определяем стиль документации
            doc_styles = {
                "python": style or "Google-style docstrings",
                "javascript": style or "JSDoc",
                "typescript": style or "TSDoc",
                "java": style or "Javadoc",
                "csharp": style or "XML documentation",
                "go": style or "GoDoc",
                "rust": style or "rustdoc"
            }
            ds = doc_styles.get(language, "standard docstrings")
            
            prompt = f"""Добавь документацию к следующему коду.

Язык: {language}
Стиль: {ds}

Код:
```{language}
{code}
```

Добавь:
- Описание функции/класса
- Описание параметров
- Описание возвращаемого значения
- Примеры использования (если уместно)

Верни полный код с документацией."""

            logger.info(f"[{request_id}] 📝 Генерация документации ({ds})")
            
            try:
                response_text = await self._call_neira_process(prompt)
            except Exception as e:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error=str(e),
                        request_id=request_id
                    ).to_json()),
                    status=500,
                    headers=self._cors_headers()
                )
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"docs": response_text},
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_refactor(self, request: web.Request) -> web.Response:
        """Рефакторинг кода"""
        self.request_count += 1
        
        try:
            data = await request.json()
            code = data.get("code", "")
            language = data.get("language", "")
            instruction = data.get("instruction", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not code:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Код не указан",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            neira_error = await self._require_neira(request_id)
            if neira_error:
                return neira_error
            
            prompt = f"""Улучши и отрефактори следующий код.

Язык: {language}
{"Инструкция: " + instruction if instruction else "Общее улучшение: читаемость, производительность, best practices"}

Код:
```{language}
{code}
```

Выполни рефакторинг:
- Улучши читаемость
- Оптимизируй производительность
- Примени best practices для {language}
- Добавь типизацию (если поддерживается)

Верни улучшенный код с краткими комментариями о изменениях."""

            logger.info(f"[{request_id}] ♻️ Рефакторинг: {instruction[:30] if instruction else 'общий'}...")
            
            try:
                response_text = await self._call_neira_process(prompt)
            except Exception as e:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error=str(e),
                        request_id=request_id
                    ).to_json()),
                    status=500,
                    headers=self._cors_headers()
                )
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"refactored": response_text},
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_commit_message(self, request: web.Request) -> web.Response:
        """Генерация commit message по diff"""
        self.request_count += 1
        
        try:
            data = await request.json()
            diff = data.get("diff", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not diff:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Diff не указан",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            neira_error = await self._require_neira(request_id)
            if neira_error:
                return neira_error
            
            prompt = f"""Сгенерируй commit message для следующих изменений.

Формат: Conventional Commits (type: description)
Типы: feat, fix, docs, style, refactor, test, chore

Diff:
```diff
{diff[:3000]}
```

Требования:
- Первая строка: краткое описание (до 72 символов)
- Пустая строка
- Детальное описание изменений (если нужно)
- На русском языке

Верни только commit message, без объяснений."""

            logger.info(f"[{request_id}] 📝 Генерация commit message")
            
            try:
                response_text = await self._call_neira_process(prompt)
                # Очищаем от лишнего
                message = response_text.strip()
                if message.startswith("```"):
                    message = "\n".join(message.split("\n")[1:-1])
            except Exception as e:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error=str(e),
                        request_id=request_id
                    ).to_json()),
                    status=500,
                    headers=self._cors_headers()
                )
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"message": message},
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_explain_diff(self, request: web.Request) -> web.Response:
        """Объяснение изменений (diff)"""
        self.request_count += 1
        
        try:
            data = await request.json()
            diff = data.get("diff", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not diff:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Diff не указан",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            neira_error = await self._require_neira(request_id)
            if neira_error:
                return neira_error
            
            prompt = f"""Проанализируй и объясни следующие изменения в коде.

Diff:
```diff
{diff[:4000]}
```

Опиши:
1. Какие файлы изменены
2. Суть каждого изменения
3. Возможные последствия
4. Рекомендации (если есть)

Формат: структурированный markdown."""

            logger.info(f"[{request_id}] 🔍 Анализ diff")
            
            try:
                response_text = await self._call_neira_process(prompt)
            except Exception as e:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error=str(e),
                        request_id=request_id
                    ).to_json()),
                    status=500,
                    headers=self._cors_headers()
                )
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"explanation": response_text},
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    # ==================== FILE SYSTEM ENDPOINTS ====================
    
    async def handle_fs_read(self, request: web.Request) -> web.Response:
        """Чтение файла"""
        self.request_count += 1
        
        try:
            data = await request.json()
            path = data.get("path", "")
            start_line = data.get("start_line", 1)
            end_line = data.get("end_line")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not path:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Путь не указан",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            fs_agent = self._get_fs_agent()
            if not fs_agent:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="FileSystemAgent недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            result = fs_agent.read_file(path, start_line, end_line)
            
            logger.info(f"[{request_id}] 📖 Чтение: {path}")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=result["success"],
                    data=result if result["success"] else None,
                    error=result.get("error"),
                    request_id=request_id
                ).to_json()),
                status=200 if result["success"] else 400,
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_fs_write(self, request: web.Request) -> web.Response:
        """Запись файла"""
        self.request_count += 1
        
        try:
            data = await request.json()
            path = data.get("path", "")
            content = data.get("content", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not path:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Путь не указан",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            fs_agent = self._get_fs_agent()
            if not fs_agent:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="FileSystemAgent недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            result = fs_agent.write_file(path, content)
            
            logger.info(f"[{request_id}] 📝 Запись: {path}")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=result["success"],
                    data=result if result["success"] else None,
                    error=result.get("error"),
                    request_id=request_id
                ).to_json()),
                status=200 if result["success"] else 400,
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_fs_edit(self, request: web.Request) -> web.Response:
        """Редактирование файла (замена текста)"""
        self.request_count += 1
        
        try:
            data = await request.json()
            path = data.get("path", "")
            old_text = data.get("old_text", "")
            new_text = data.get("new_text", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not path or not old_text:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Путь и old_text обязательны",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            fs_agent = self._get_fs_agent()
            if not fs_agent:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="FileSystemAgent недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            result = fs_agent.edit_file(path, old_text, new_text)
            
            logger.info(f"[{request_id}] ✏️ Редактирование: {path}")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=result["success"],
                    data=result if result["success"] else None,
                    error=result.get("error"),
                    request_id=request_id
                ).to_json()),
                status=200 if result["success"] else 400,
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_fs_search(self, request: web.Request) -> web.Response:
        """Поиск в файлах (grep)"""
        self.request_count += 1
        
        try:
            data = await request.json()
            query = data.get("query", "")
            path = data.get("path", ".")
            file_pattern = data.get("file_pattern", "*")
            is_regex = data.get("is_regex", False)
            case_sensitive = data.get("case_sensitive", False)
            max_results = data.get("max_results", 100)
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not query:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Запрос не указан",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            fs_agent = self._get_fs_agent()
            if not fs_agent:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="FileSystemAgent недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            result = fs_agent.search_in_files(
                query, path, file_pattern, is_regex, case_sensitive, max_results
            )
            
            logger.info(f"[{request_id}] 🔍 Поиск: '{query}' найдено {result.get('total_matches', 0)}")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=result["success"],
                    data=result if result["success"] else None,
                    error=result.get("error"),
                    request_id=request_id
                ).to_json()),
                status=200 if result["success"] else 400,
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_fs_list(self, request: web.Request) -> web.Response:
        """Список файлов в директории"""
        self.request_count += 1
        
        try:
            data = await request.json()
            path = data.get("path", ".")
            show_hidden = data.get("show_hidden", False)
            recursive = data.get("recursive", False)
            max_depth = data.get("max_depth", 3)
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            fs_agent = self._get_fs_agent()
            if not fs_agent:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="FileSystemAgent недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            result = fs_agent.list_directory(path, show_hidden, recursive, max_depth)
            
            logger.info(f"[{request_id}] 📂 Список: {path}")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=result["success"],
                    data=result if result["success"] else None,
                    error=result.get("error"),
                    request_id=request_id
                ).to_json()),
                status=200 if result["success"] else 400,
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_fs_structure(self, request: web.Request) -> web.Response:
        """Структура проекта"""
        self.request_count += 1
        
        try:
            data = await request.json()
            max_depth = data.get("max_depth", 3)
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            fs_agent = self._get_fs_agent()
            if not fs_agent:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="FileSystemAgent недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            result = fs_agent.get_project_structure(max_depth)
            
            logger.info(f"[{request_id}] 🗂️ Структура проекта")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=result["success"],
                    data=result if result["success"] else None,
                    error=result.get("error"),
                    request_id=request_id
                ).to_json()),
                status=200 if result["success"] else 400,
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_fs_batch_edit(self, request: web.Request) -> web.Response:
        """Пакетное редактирование файлов"""
        self.request_count += 1
        
        try:
            data = await request.json()
            edits = data.get("edits", [])
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not edits:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Список правок пуст",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            fs_agent = self._get_fs_agent()
            if not fs_agent:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="FileSystemAgent недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            result = fs_agent.apply_edits(edits)
            
            logger.info(f"[{request_id}] 📦 Пакетное редактирование: {len(edits)} файлов")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=result["success"],
                    data=result if result["success"] else None,
                    error=result.get("error"),
                    request_id=request_id
                ).to_json()),
                status=200 if result["success"] else 400,
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_fs_set_workspace(self, request: web.Request) -> web.Response:
        """Установка рабочей директории"""
        self.request_count += 1
        
        try:
            data = await request.json()
            workspace_path = data.get("workspace_path", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not workspace_path:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Путь не указан",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            if not os.path.isdir(workspace_path):
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error=f"Директория не существует: {workspace_path}",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            # Создаём новый FileSystemAgent с указанным workspace
            fs_agent = self._get_fs_agent()
            if not fs_agent:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="FileSystemAgent недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )

            try:
                from file_system_agent import FileSystemAgent
            except Exception as e:
                self._fs_agent_error = str(e)
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="FileSystemAgent недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )

            self.workspace_root = workspace_path
            self.fs_agent = FileSystemAgent(workspace_path)
            self._fs_agent_error = None

            logger.info(f"[{request_id}] 📂 Workspace установлен: {workspace_path}")

            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={
                        "workspace_path": workspace_path,
                        "message": "Workspace успешно установлен"
                    },
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    # ==================== STREAMING ENDPOINTS ====================
    
    async def handle_stream_chat(self, request: web.Request) -> web.StreamResponse:
        """Потоковый чат с Server-Sent Events"""
        self.request_count += 1
        
        # Подготавливаем SSE response
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                **self._cors_headers()
            }
        )
        await response.prepare(request)
        
        try:
            data = await request.json()
            message = data.get("message", "").strip()
            context = data.get("context", "")
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            user_id = data.get("user_id")
            user_name = data.get("user_name")
            user_id = data.get("user_id")
            
            if not message:
                await response.write(b'data: {"error": "Empty message"}\n\n')
                await response.write(b'data: [DONE]\n\n')
                return response

            if self._is_explicit_organ_request(message):
                policy_text = (
                    "Создание органов разрешено только по явной команде.\n"
                    "Используйте `/grow <описание>` (в Telegram) или напишите «создай орган <описание>» — "
                    "я подскажу следующий шаг, но не буду «создавать» орган в тексте."
                )
                sse_data = json.dumps({"token": policy_text}, ensure_ascii=False)
                await response.write(f'data: {sse_data}\n\n'.encode('utf-8'))
                await response.write(b'data: [DONE]\n\n')
                self._log_chat_event(
                    request_id=request_id,
                    endpoint="/stream/chat",
                    message=message,
                    response=policy_text,
                    context=context,
                    duration_ms=0,
                    model="policy",
                )
                return response
            
            if not await self._ensure_neira():
                await response.write(b'data: {"error": "Neira not initialized"}\n\n')
                await response.write(b'data: [DONE]\n\n')
                return response
            
            full_message = self._compose_full_message(
                message=message,
                context=context,
                user_id=user_id,
                user_name=user_name,
            )
            
            logger.info(f"[{request_id}] 📡 Stream chat: {message[:MESSAGE_PREVIEW_LIMIT]}...")
            start_time = time.perf_counter()
            
            # Получаем ответ от Нейры
            try:
                response_text = await self._call_neira_process(full_message)
                response_text = self._guard_llm_response(response_text, message)
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                self._log_chat_event(
                    request_id=request_id,
                    endpoint="/stream/chat",
                    message=message,
                    response=response_text,
                    context=context,
                    duration_ms=duration_ms,
                    model="ollama",
                )
                
                # Симулируем стриминг - отправляем по словам
                words = response_text.split(' ')
                for i, word in enumerate(words):
                    token = word + (' ' if i < len(words) - 1 else '')
                    sse_data = json.dumps({"token": token}, ensure_ascii=False)
                    await response.write(f'data: {sse_data}\n\n'.encode('utf-8'))
                    await asyncio.sleep(0.01)  # Небольшая задержка для реалистичности
                
            except Exception as e:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                self._log_chat_event(
                    request_id=request_id,
                    endpoint="/stream/chat",
                    message=message,
                    error=str(e),
                    context=context,
                    duration_ms=duration_ms,
                    model="ollama",
                )
                error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
                await response.write(f'data: {error_data}\n\n'.encode('utf-8'))
            
            await response.write(b'data: [DONE]\n\n')
            
        except Exception as e:
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            await response.write(f'data: {error_data}\n\n'.encode('utf-8'))
            await response.write(b'data: [DONE]\n\n')
        
        return response
    
    async def handle_stream_explain(self, request: web.Request) -> web.StreamResponse:
        """Потоковое объяснение кода"""
        self.request_count += 1
        
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                **self._cors_headers()
            }
        )
        await response.prepare(request)
        
        try:
            data = await request.json()
            code = data.get("code", "")
            language = data.get("language", "")
            
            if not code:
                await response.write(b'data: {"error": "No code provided"}\n\n')
                await response.write(b'data: [DONE]\n\n')
                return response
            
            if not await self._ensure_neira():
                await response.write(b'data: {"error": "Neira not initialized"}\n\n')
                await response.write(b'data: [DONE]\n\n')
                return response
            
            prompt = f"""Объясни подробно этот код на языке {language or 'неизвестном'}:

```{language}
{code[:3000]}
```

Опиши:
1. Что делает код
2. Ключевые части
3. Возможные улучшения"""
            
            try:
                response_text = await self._call_neira_process(prompt)
                
                # Стриминг по словам
                words = response_text.split(' ')
                for i, word in enumerate(words):
                    token = word + (' ' if i < len(words) - 1 else '')
                    sse_data = json.dumps({"token": token}, ensure_ascii=False)
                    await response.write(f'data: {sse_data}\n\n'.encode('utf-8'))
                    await asyncio.sleep(0.01)
                
            except Exception as e:
                error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
                await response.write(f'data: {error_data}\n\n'.encode('utf-8'))
            
            await response.write(b'data: [DONE]\n\n')
            
        except Exception as e:
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            await response.write(f'data: {error_data}\n\n'.encode('utf-8'))
            await response.write(b'data: [DONE]\n\n')
        
        return response
    
    async def handle_stream_generate(self, request: web.Request) -> web.StreamResponse:
        """Потоковая генерация кода"""
        self.request_count += 1
        
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                **self._cors_headers()
            }
        )
        await response.prepare(request)
        
        try:
            data = await request.json()
            description = data.get("description", "")
            language = data.get("language", "python")
            
            if not description:
                await response.write(b'data: {"error": "No description"}\n\n')
                await response.write(b'data: [DONE]\n\n')
                return response
            
            if not await self._ensure_neira():
                await response.write(b'data: {"error": "Neira not initialized"}\n\n')
                await response.write(b'data: [DONE]\n\n')
                return response
            
            prompt = f"""Сгенерируй код на языке {language}.

Задача: {description}

Требования:
- Чистый, читаемый код
- Комментарии на русском
- Обработка ошибок

Код:"""
            
            try:
                response_text = await self._call_neira_process(prompt)
                
                # Стриминг по строкам для кода
                lines = response_text.split('\n')
                for i, line in enumerate(lines):
                    token = line + ('\n' if i < len(lines) - 1 else '')
                    sse_data = json.dumps({"token": token}, ensure_ascii=False)
                    await response.write(f'data: {sse_data}\n\n'.encode('utf-8'))
                    await asyncio.sleep(0.02)
                
            except Exception as e:
                error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
                await response.write(f'data: {error_data}\n\n'.encode('utf-8'))
            
            await response.write(b'data: [DONE]\n\n')
            
        except Exception as e:
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            await response.write(f'data: {error_data}\n\n'.encode('utf-8'))
            await response.write(b'data: [DONE]\n\n')
        
        return response

    # ==================== TOOL ENDPOINTS ====================
    
    async def handle_tools_list(self, request: web.Request) -> web.Response:
        """Список доступных инструментов"""
        self.request_count += 1
        
        tool_system = self._get_tool_system()
        if not tool_system:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error="Tool System недоступен"
                ).to_json()),
                status=503,
                headers=self._cors_headers()
            )
        
        schemas = tool_system.registry.get_all_schemas()
        
        return web.json_response(
            json.loads(ServerResponse(
                success=True,
                data={
                    "tools": schemas,
                    "total": len(schemas)
                }
            ).to_json()),
            headers=self._cors_headers()
        )
    
    async def handle_tools_execute(self, request: web.Request) -> web.Response:
        """Выполнение инструмента"""
        self.request_count += 1
        
        try:
            data = await request.json()
            tool_name = data.get("name", "")
            parameters = data.get("parameters", {})
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not tool_name:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Имя инструмента не указано",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            tool_system = self._get_tool_system()
            if not tool_system:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Tool System недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            logger.info(f"[{request_id}] 🔧 Инструмент: {tool_name}")
            
            # Выполняем инструмент
            result = await tool_system.executor.registry.execute(tool_name, **parameters)
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=result.success,
                    data={
                        "output": result.output,
                        "execution_time": result.execution_time,
                        "tool_name": result.tool_name
                    },
                    error=result.error,
                    request_id=request_id
                ).to_json()),
                status=200 if result.success else 400,
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_tools_batch(self, request: web.Request) -> web.Response:
        """Пакетное выполнение инструментов"""
        self.request_count += 1
        
        try:
            data = await request.json()
            calls = data.get("calls", [])
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not calls:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Список вызовов пуст",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            tool_system = self._get_tool_system()
            if not tool_system:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Tool System недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            logger.info(f"[{request_id}] 🔧 Пакетное выполнение: {len(calls)} инструментов")
            
            # Выполняем все инструменты
            results = await tool_system.executor.execute_tool_calls(calls)
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=all(r.success for r in results),
                    data={
                        "results": [r.to_dict() for r in results],
                        "total": len(results),
                        "successful": sum(1 for r in results if r.success)
                    },
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_tools_prompt(self, request: web.Request) -> web.Response:
        """Получить промпт с описанием инструментов для LLM"""
        self.request_count += 1
        
        tool_system = self._get_tool_system()
        if not tool_system:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error="Tool System недоступен"
                ).to_json()),
                status=503,
                headers=self._cors_headers()
            )
        
        prompt = tool_system.executor.get_tools_prompt()
        
        return web.json_response(
            json.loads(ServerResponse(
                success=True,
                data={"prompt": prompt}
            ).to_json()),
            headers=self._cors_headers()
        )

    # ==================== INDEXER ENDPOINTS ====================
    
    async def handle_index_workspace(self, request: web.Request) -> web.Response:
        """Индексация workspace"""
        self.request_count += 1
        
        try:
            data = await request.json()
            force = data.get("force", False)
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            indexer_getter = self._get_indexer_getter()
            if not indexer_getter:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Workspace Indexer недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            logger.info(f"[{request_id}] 📑 Индексация workspace...")
            
            indexer = indexer_getter(self.workspace_root)
            result = indexer.index_workspace(force=force)
            
            logger.info(f"[{request_id}] ✅ Индексировано: {result['total_files']} файлов, {result['total_symbols']} символов")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data=result,
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_search_symbols(self, request: web.Request) -> web.Response:
        """Поиск символов в индексе"""
        self.request_count += 1
        
        try:
            data = await request.json()
            query = data.get("query", "")
            symbol_type = data.get("symbol_type")
            limit = data.get("limit", 20)
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            if not query:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Запрос не указан",
                        request_id=request_id
                    ).to_json()),
                    status=400,
                    headers=self._cors_headers()
                )
            
            indexer_getter = self._get_indexer_getter()
            if not indexer_getter:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Workspace Indexer недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            indexer = indexer_getter(self.workspace_root)
            results = indexer.search_symbols(query, symbol_type, limit)
            
            logger.info(f"[{request_id}] 🔍 Поиск '{query}': {len(results)} результатов")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={
                        "results": [r.to_dict() for r in results],
                        "total": len(results)
                    },
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_get_context(self, request: web.Request) -> web.Response:
        """Получить контекст для LLM"""
        self.request_count += 1
        
        try:
            data = await request.json()
            query = data.get("query", "")
            current_file = data.get("current_file")
            max_symbols = data.get("max_symbols", 10)
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            indexer_getter = self._get_indexer_getter()
            if not indexer_getter:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Workspace Indexer недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            indexer = indexer_getter(self.workspace_root)
            context = indexer.get_relevant_context(query, current_file, max_symbols)
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"context": context},
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_index_stats(self, request: web.Request) -> web.Response:
        """Статистика индекса"""
        self.request_count += 1
        
        indexer_getter = self._get_indexer_getter()
        if not indexer_getter:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error="Workspace Indexer недоступен"
                ).to_json()),
                status=503,
                headers=self._cors_headers()
            )
        
        indexer = indexer_getter(self.workspace_root)
        stats = indexer.get_stats()
        
        return web.json_response(
            json.loads(ServerResponse(
                success=True,
                data=stats
            ).to_json()),
            headers=self._cors_headers()
        )

    # ==================== CONTEXT MANAGER ENDPOINTS ====================

    async def handle_build_context(self, request: web.Request) -> web.Response:
        """Собрать оптимизированный контекст для LLM"""
        self.request_count += 1
        
        try:
            data = await request.json()
            request_id = data.get("request_id", str(uuid.uuid4())[:8])
            
            context_functions = self._get_context_functions()
            if not context_functions:
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Context Manager недоступен",
                        request_id=request_id
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            # Получаем параметры
            user_query = data.get("query", "")
            current_file = data.get("current_file")
            current_code = data.get("current_code")
            chat_history = data.get("chat_history", [])
            related_files = data.get("related_files", [])
            tool_results = data.get("tool_results", [])
            system_prompt = data.get("system_prompt")
            max_tokens = data.get("max_tokens")
            
            # Собираем контекст
            if isinstance(max_tokens, int) and max_tokens > 0:
                manager = context_functions.get_context_manager(max_tokens)
            else:
                manager = context_functions.get_context_manager()
            window = manager.build_context(
                user_query=user_query,
                current_file=current_file,
                current_code=current_code,
                chat_history=chat_history,
                related_files=related_files,
                tool_results=tool_results,
                system_prompt=system_prompt
            )
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={
                        "prompt": window.build_prompt(),
                        "total_tokens": window.total_tokens,
                        "available_tokens": window.available_tokens,
                        "chunks_count": len(window.chunks)
                    },
                    request_id=request_id
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            logger.error(f"Ошибка build_context: {e}")
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_estimate_tokens(self, request: web.Request) -> web.Response:
        """Оценить количество токенов в тексте"""
        self.request_count += 1
        
        try:
            data = await request.json()
            text = data.get("text", "")
            
            context_functions = self._get_context_functions()
            if not context_functions:
                tokens = len(text) // 4
            else:
                tokens = context_functions.estimate_tokens(text)
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={
                        "tokens": tokens,
                        "characters": len(text),
                        "words": len(text.split())
                    }
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_optimal_context_size(self, request: web.Request) -> web.Response:
        """Получить оптимальный размер контекста для модели"""
        self.request_count += 1
        
        try:
            data = await request.json()
            model = data.get("model", "llama3")
            task_type = data.get("task_type", "chat")
            
            context_functions = self._get_context_functions()
            if not context_functions:
                size = 6000  # Default
            else:
                size = context_functions.optimal_context_size(model, task_type)
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={
                        "optimal_tokens": size,
                        "model": model,
                        "task_type": task_type
                    }
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    # ==================== NEIRA SELF-AWARE ENDPOINTS ====================

    async def handle_introspection(self, request: web.Request) -> web.Response:
        """Состояние самосознания Нейры"""
        self.request_count += 1
        
        try:
            neira_error = await self._require_neira()
            if neira_error:
                return neira_error

            state = {
                "organs": [],
                "experience": [],
                "personality": {
                    "curiosity": 0.7,
                    "helpfulness": 0.8,
                    "self_awareness": 0.5,
                    "creativity": 0.6
                },
                "memory_stats": {
                    "short_term": 0,
                    "long_term": 0
                }
            }
            
            # Получаем органы
            if self.neira and hasattr(self.neira, 'introspection') and self.neira.introspection:
                organs_data = self.neira.introspection.get_all_organs()
                state["organs"] = [
                    {
                        "name": o.name,
                        "file": o.file,
                        "description": o.description,
                        "capabilities": o.capabilities,
                        "status": o.status
                    }
                    for o in organs_data.values()
                ] if isinstance(organs_data, dict) else []
            
            # Получаем опыт
            if self.neira and hasattr(self.neira, 'experience') and self.neira.experience:
                exp = self.neira.experience
                state["experience"] = [
                    {
                        "timestamp": e.timestamp,
                        "task_type": e.task_type,
                        "verdict": e.verdict,
                        "score": e.score,
                        "lesson": e.lesson
                    }
                    for e in exp.experiences[-10:]
                ]
                
                if hasattr(exp, 'personality'):
                    state["personality"] = exp.personality.get("traits", state["personality"])
            
            # Статистика памяти
            if self.neira and hasattr(self.neira, 'memory') and self.neira.memory:
                mem = self.neira.memory
                if hasattr(mem, 'memory_system') and mem.memory_system:
                    ms = mem.memory_system
                    state["memory_stats"]["short_term"] = len(getattr(ms, 'short_term', []))
                    state["memory_stats"]["long_term"] = len(getattr(ms, 'long_term', []))
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data=state
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            logger.error(f"Introspection error: {e}")
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_experience_relevant(self, request: web.Request) -> web.Response:
        """Получить релевантный опыт"""
        self.request_count += 1
        
        try:
            neira_error = await self._require_neira()
            if neira_error:
                return neira_error

            data = await request.json()
            task_type = data.get("task_type", "")
            limit = data.get("limit", 5)
            
            lessons = []
            
            if self.neira and hasattr(self.neira, 'experience') and self.neira.experience:
                lessons = self.neira.experience.get_relevant_experience(task_type, limit)
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"lessons": lessons}
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_experience_record(self, request: web.Request) -> web.Response:
        """Записать опыт"""
        self.request_count += 1
        
        try:
            neira_error = await self._require_neira()
            if neira_error:
                return neira_error

            data = await request.json()
            
            if self.neira and hasattr(self.neira, 'experience') and self.neira.experience:
                self.neira.experience.record_experience(
                    task_type=data.get("task_type", "unknown"),
                    user_input=data.get("user_input", ""),
                    verdict=data.get("verdict", "ДОРАБОТАТЬ"),
                    score=data.get("score", 5),
                    problems=data.get("problems", "")
                )
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_curiosity_question(self, request: web.Request) -> web.Response:
        """Получить вопрос от любопытной Нейры"""
        self.request_count += 1
        
        try:
            data = await request.json()
            user_message = data.get("user_message", "")
            neira_response = data.get("neira_response", "")
            
            question = None
            
            # Используем CuriosityCell если доступен
            try:
                from cells import maybe_ask_question
                question = maybe_ask_question(user_message, neira_response)
            except ImportError:
                pass
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"question": question}
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_curiosity_reflect(self, request: web.Request) -> web.Response:
        """Рефлексия Нейры"""
        self.request_count += 1
        
        try:
            reflection = None
            
            try:
                from cells import get_reflection
                reflection = get_reflection()
            except ImportError:
                reflection = "Каждый разговор учит меня чему-то новому."
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"reflection": reflection}
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_memory_search(self, request: web.Request) -> web.Response:
        """Поиск в памяти"""
        self.request_count += 1
        
        try:
            neira_error = await self._require_neira()
            if neira_error:
                return neira_error

            data = await request.json()
            query = data.get("query", "")
            limit = data.get("limit", 10)
            
            memories = []
            
            if self.neira and hasattr(self.neira, 'memory') and self.neira.memory:
                mem = self.neira.memory
                if hasattr(mem, 'search'):
                    results = mem.search(query, limit=limit)
                    memories = [r.get('content', str(r)) if isinstance(r, dict) else str(r) for r in results]
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={"memories": memories}
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_memory_remember(self, request: web.Request) -> web.Response:
        """Запомнить что-то"""
        self.request_count += 1
        
        try:
            neira_error = await self._require_neira()
            if neira_error:
                return neira_error

            data = await request.json()
            content = data.get("content", "")
            category = data.get("category", "general")
            
            if self.neira and hasattr(self.neira, 'memory') and self.neira.memory:
                mem = self.neira.memory
                if hasattr(mem, 'remember'):
                    mem.remember(content, category=category)
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    async def handle_feedback_quick(self, request: web.Request) -> web.Response:
        """Быстрый фидбек"""
        self.request_count += 1
        
        try:
            data = await request.json()
            positive = data.get("positive", True)
            
            # Можно использовать для обучения
            logger.info(f"Quick feedback: {'👍' if positive else '👎'}")
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )

    # ==================== Learning System ====================
    
    async def handle_learn(self, request: web.Request) -> web.Response:
        """Обучение из источника (файл, URL, YouTube)"""
        self.request_count += 1
        
        try:
            data = await request.json()
            source = data.get("source", "")
            category = data.get("category", "knowledge")
            summarize = data.get("summarize", True)
            
            if not source:
                return web.json_response(
                    {"success": False, "error": "source is required"},
                    status=400,
                    headers=self._cors_headers()
                )
            if self._offline_mode and self._is_url_source(source):
                return web.json_response(
                    {"success": False, "error": "Офлайн-режим: доступны только локальные файлы"},
                    status=400,
                    headers=self._cors_headers()
                )
            
            # Импортируем LearningManager
            from content_extractor import LearningManager
            
            # Создаём менеджер с памятью Нейры
            memory = None
            if self.neira and hasattr(self.neira, 'memory'):
                memory = self.neira.memory
            
            manager = LearningManager(memory)
            
            # Обучаемся
            result = await manager.learn_from_source(source, category, summarize)
            
            logger.info(f"🎓 Learned: {result.get('title')} ({result.get('word_count')} words)")
            
            return web.json_response(
                result,
                headers=self._cors_headers()
            )
            
        except Exception as e:
            logger.error(f"Learning error: {e}")
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_learn_batch(self, request: web.Request) -> web.Response:
        """Пакетное обучение из нескольких источников"""
        self.request_count += 1
        
        try:
            data = await request.json()
            sources = data.get("sources", [])
            category = data.get("category", "knowledge")
            
            if not sources:
                return web.json_response(
                    {"success": False, "error": "sources array is required"},
                    status=400,
                    headers=self._cors_headers()
                )
            if self._offline_mode:
                blocked = [s for s in sources if self._is_url_source(str(s))]
                if blocked:
                    return web.json_response(
                        {"success": False, "error": "Офлайн-режим: URL запрещены", "blocked": blocked},
                        status=400,
                        headers=self._cors_headers()
                    )
            
            from content_extractor import LearningManager
            
            memory = None
            if self.neira and hasattr(self.neira, 'memory'):
                memory = self.neira.memory
            
            manager = LearningManager(memory)
            result = await manager.learn_batch(sources, category)
            
            logger.info(f"🎓 Batch learning: {result['success']}/{result['total']} sources")
            
            return web.json_response(
                result,
                headers=self._cors_headers()
            )
            
        except Exception as e:
            logger.error(f"Batch learning error: {e}")
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_learning_stats(self, request: web.Request) -> web.Response:
        """Статистика обучения"""
        self.request_count += 1
        
        try:
            from content_extractor import LearningManager
            
            manager = LearningManager()
            stats = manager.get_learning_stats()
            
            return web.json_response(
                {"success": True, **stats},
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
                headers=self._cors_headers()
            )

    async def handle_learning_history(self, request: web.Request) -> web.Response:
        """Вернуть последние изученные источники (learning_history.json)."""
        self.request_count += 1

        limit = self._query_int(
            request,
            "limit",
            DEFAULT_LEARNING_HISTORY_RECENT_LIMIT,
            min_value=1,
            max_value=MAX_LEARNING_HISTORY_RECENT_LIMIT,
        )
        recent = self._load_learning_history_recent(limit)
        return web.json_response(
            {"success": True, "limit": limit, "recent": recent},
            headers=self._cors_headers(),
        )
    
    async def handle_extract_content(self, request: web.Request) -> web.Response:
        """Извлечение контента без сохранения (превью)"""
        self.request_count += 1
        
        try:
            data = await request.json()
            source = data.get("source", "")
            
            if not source:
                return web.json_response(
                    {"success": False, "error": "source is required"},
                    status=400,
                    headers=self._cors_headers()
                )
            if self._offline_mode and self._is_url_source(source):
                return web.json_response(
                    {"success": False, "error": "Офлайн-режим: URL запрещены"},
                    status=400,
                    headers=self._cors_headers()
                )
            
            from content_extractor import ContentExtractor
            
            extractor = ContentExtractor()
            content = await extractor.extract(source)
            
            # Ограничиваем превью
            preview = content.content[:2000] + "..." if len(content.content) > 2000 else content.content
            
            return web.json_response(
                {
                    "success": True,
                    "title": content.title,
                    "source_type": content.source_type,
                    "word_count": content.word_count,
                    "preview": preview,
                    "metadata": content.metadata
                },
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
                headers=self._cors_headers()
            )

    async def handle_memory(self, request: web.Request) -> web.Response:
        """Работа с памятью Нейры"""
        try:
            neira_error = await self._require_neira()
            if neira_error:
                return neira_error

            if not self.neira or not hasattr(self.neira, 'memory'):
                return web.json_response(
                    json.loads(ServerResponse(
                        success=False,
                        error="Память недоступна"
                    ).to_json()),
                    status=503,
                    headers=self._cors_headers()
                )
            
            # Получаем последние воспоминания
            memories = []
            if hasattr(self.neira.memory, 'search'):
                try:
                    results = self.neira.memory.search("", limit=10)
                    memories = [str(r) for r in results]
                except Exception:
                    pass
            
            return web.json_response(
                json.loads(ServerResponse(
                    success=True,
                    data={
                        "memory_count": len(memories),
                        "recent": memories[:5]
                    }
                ).to_json()),
                headers=self._cors_headers()
            )
            
        except Exception as e:
            return web.json_response(
                json.loads(ServerResponse(
                    success=False,
                    error=str(e)
                ).to_json()),
                status=500,
                headers=self._cors_headers()
            )
    
    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket для real-time общения"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.websockets.add(ws)
        client_id = str(uuid.uuid4())[:8]
        logger.info(f"[WS:{client_id}] Клиент подключился")
        
        try:
            async for msg in ws:
                self._touch_activity()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        action = data.get("action", "chat")
                        
                        if action == "chat":
                            message = data.get("message", "")
                            if message:
                                user_id = data.get("user_id")
                                user_name = data.get("user_name")

                                if self._is_explicit_organ_request(message):
                                    policy_text = (
                                        "Создание органов разрешено только по явной команде.\n"
                                        "Используйте `/grow <описание>` (в Telegram) или напишите «создай орган <описание>» — "
                                        "я подскажу следующий шаг, но не буду «создавать» орган в тексте."
                                    )
                                    await ws.send_json({
                                        "type": "response",
                                        "content": policy_text,
                                        "meta": {"model": "policy", "model_source": "policy"}
                                    })
                                    continue

                                autonomous_response, response_source = self._try_autonomous_response(message, user_id)
                                if autonomous_response:
                                    await ws.send_json({
                                        "type": "response",
                                        "content": autonomous_response,
                                        "meta": {"model": "autonomous", "model_source": response_source or "local_pathways"}
                                    })
                                    continue

                                if not await self._ensure_neira():
                                    await ws.send_json({
                                        "type": "error",
                                        "error": "Neira not initialized"
                                    })
                                    continue
                                # Отправляем статус "печатает"
                                await ws.send_json({
                                    "type": "typing",
                                    "status": True
                                })
                                
                                try:
                                    full_message = self._compose_full_message(
                                        message=message,
                                        context=None,
                                        user_id=user_id,
                                        user_name=user_name,
                                    )
                                    response = await self._call_neira_process(full_message)
                                    response = self._guard_llm_response(response, message)
                                    await ws.send_json({
                                        "type": "response",
                                        "content": response,
                                        "meta": {"model": "ollama", "model_source": "local"}
                                    })
                                except Exception as e:
                                    await ws.send_json({
                                        "type": "error",
                                        "error": str(e)
                                    })
                                finally:
                                    await ws.send_json({
                                        "type": "typing",
                                        "status": False
                                    })
                        
                        elif action == "ping":
                            await ws.send_json({"type": "pong"})
                            
                    except json.JSONDecodeError:
                        await ws.send_json({
                            "type": "error",
                            "error": "Неверный JSON"
                        })
                        
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"[WS:{client_id}] Ошибка: {ws.exception()}")
                    
        finally:
            self.websockets.discard(ws)
            logger.info(f"[WS:{client_id}] Клиент отключился")
        
        return ws
    
    async def broadcast(self, message: Dict[str, Any]):
        """Отправка сообщения всем WebSocket клиентам"""
        if self.websockets:
            await asyncio.gather(*[
                ws.send_json(message) 
                for ws in self.websockets 
                if not ws.closed
            ])

    # === Endpoints для управления слоями моделей ===
    async def handle_layers_list(self, request: web.Request) -> web.Response:
        """Вернуть список моделей и их слоёв"""
        layers_system = self._get_layers_system()
        if not layers_system:
            return web.json_response(json.loads(ServerResponse(success=False, error="Model layers disabled").to_json()), status=503, headers=self._cors_headers())

        try:
            models = layers_system.registry.list_models()
            payload = {}
            for m in models:
                layers = layers_system.registry.list_layers(m)
                payload[m] = [layer.to_dict() for layer in layers]

            return web.json_response(json.loads(ServerResponse(success=True, data={"models": payload}).to_json()), headers=self._cors_headers())
        except Exception as e:
            return web.json_response(json.loads(ServerResponse(success=False, error=str(e)).to_json()), status=500, headers=self._cors_headers())

    async def handle_layers_add(self, request: web.Request) -> web.Response:
        """Добавить слой"""
        layers_system = self._get_layers_system()
        if not layers_system:
            return web.json_response(json.loads(ServerResponse(success=False, error="Model layers disabled").to_json()), status=503, headers=self._cors_headers())

        try:
            data = await request.json()
            model = data.get("model")
            layer_raw = data.get("layer")
            activate = bool(data.get("activate", False))
            overwrite = bool(data.get("overwrite", False))

            if not model or not layer_raw:
                return web.json_response(json.loads(ServerResponse(success=False, error="Missing model or layer").to_json()), status=400, headers=self._cors_headers())

            layer = layers_system.layer_class.from_dict(layer_raw)
            layers_system.registry.add_layer(model, layer, activate=activate, overwrite=overwrite)
            layers_system.registry.save()

            return web.json_response(json.loads(ServerResponse(success=True, data={"message": "layer added"}).to_json()), headers=self._cors_headers())
        except layers_system.error_class as me:
            return web.json_response(json.loads(ServerResponse(success=False, error=str(me)).to_json()), status=400, headers=self._cors_headers())
        except Exception as e:
            return web.json_response(json.loads(ServerResponse(success=False, error=str(e)).to_json()), status=500, headers=self._cors_headers())

    async def handle_layers_activate(self, request: web.Request) -> web.Response:
        """Активировать слой (или очистить)"""
        layers_system = self._get_layers_system()
        if not layers_system:
            return web.json_response(json.loads(ServerResponse(success=False, error="Model layers disabled").to_json()), status=503, headers=self._cors_headers())

        try:
            data = await request.json()
            model = data.get("model")
            layer_id = data.get("id")
            if not model:
                return web.json_response(json.loads(ServerResponse(success=False, error="Missing model").to_json()), status=400, headers=self._cors_headers())

            layers_system.registry.set_active_layer(model, layer_id)
            layers_system.registry.save()
            return web.json_response(json.loads(ServerResponse(success=True, data={"message": "activated"}).to_json()), headers=self._cors_headers())
        except layers_system.error_class as me:
            return web.json_response(json.loads(ServerResponse(success=False, error=str(me)).to_json()), status=400, headers=self._cors_headers())
        except Exception as e:
            return web.json_response(json.loads(ServerResponse(success=False, error=str(e)).to_json()), status=500, headers=self._cors_headers())

    async def handle_layers_delete(self, request: web.Request) -> web.Response:
        """Удалить слой"""
        layers_system = self._get_layers_system()
        if not layers_system:
            return web.json_response(json.loads(ServerResponse(success=False, error="Model layers disabled").to_json()), status=503, headers=self._cors_headers())

        try:
            data = await request.json()
            model = data.get("model")
            layer_id = data.get("id")
            if not model or not layer_id:
                return web.json_response(json.loads(ServerResponse(success=False, error="Missing model or id").to_json()), status=400, headers=self._cors_headers())

            layers_system.registry.remove_layer(model, layer_id)
            layers_system.registry.save()
            return web.json_response(json.loads(ServerResponse(success=True, data={"message": "deleted"}).to_json()), headers=self._cors_headers())
        except layers_system.error_class as me:
            return web.json_response(json.loads(ServerResponse(success=False, error=str(me)).to_json()), status=400, headers=self._cors_headers())
        except Exception as e:
            return web.json_response(json.loads(ServerResponse(success=False, error=str(e)).to_json()), status=500, headers=self._cors_headers())

    async def handle_models_list(self, request: web.Request) -> web.Response:
        """Вернуть список доступных моделей (из ModelManager)"""
        module = self._get_model_manager_module()
        if not module:
            return web.json_response(json.loads(ServerResponse(success=False, error="Model manager unavailable").to_json()), status=503, headers=self._cors_headers())

        try:
            payload = {
                k: {
                    "name": v.name,
                    "size_gb": v.size_gb,
                    "type": v.type,
                    "use_case": v.use_case
                }
                for k, v in module.models.items()
            }
        except Exception:
            payload = {}

        payload.setdefault("neira", {"name": "Neira Assistant", "size_gb": 0, "type": "local", "use_case": "Assistant"})

        manager_stats = None
        if self.model_manager:
            manager_stats = self.model_manager.get_stats()
        elif _env_flag("NEIRA_MODEL_MANAGER_EAGER", False):
            manager = self._get_model_manager()
            if manager:
                manager_stats = manager.get_stats()

        data = {"models": payload}
        if manager_stats is not None:
            data["manager"] = manager_stats

        return web.json_response(json.loads(ServerResponse(success=True, data=data).to_json()), headers=self._cors_headers())

    async def handle_models_switch(self, request: web.Request) -> web.Response:
        """Переключить активную модель через ModelManager.switch_to(key)"""
        try:
            data = await request.json()
            key = data.get("key")
            if not key:
                return web.json_response(json.loads(ServerResponse(success=False, error="Missing key").to_json()), status=400, headers=self._cors_headers())

            if key == "neira":
                current = self.model_manager.current_model if self.model_manager else "neira"
                return web.json_response(json.loads(ServerResponse(success=True, data={"message": "switched", "current": current}).to_json()), headers=self._cors_headers())

            manager = self._get_model_manager()
            if not manager:
                return web.json_response(json.loads(ServerResponse(success=False, error="ModelManager unavailable").to_json()), status=503, headers=self._cors_headers())

            ok = manager.switch_to(key)
            if ok:
                current = manager.current_model
                return web.json_response(json.loads(ServerResponse(success=True, data={"message": "switched", "current": current}).to_json()), headers=self._cors_headers())

            return web.json_response(json.loads(ServerResponse(success=False, error="switch failed").to_json()), status=500, headers=self._cors_headers())
        except Exception as e:
            return web.json_response(json.loads(ServerResponse(success=False, error=str(e)).to_json()), status=500, headers=self._cors_headers())
    
    def setup_routes(self):
        """Настройка маршрутов"""
        self.app = web.Application(middlewares=[self._activity_middleware])
        
        # CORS preflight
        self.app.router.add_route("OPTIONS", "/{path:.*}", self.handle_options)
        
        # API endpoints
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/autonomy/stats", self.handle_autonomy_stats)  # Phase 1
        self.app.router.add_post("/pathway/feedback", self.handle_pathway_feedback)  # Phase 2
        self.app.router.add_post("/autonomy/optimize", self.handle_autonomy_optimize)  # Phase 3
        self.app.router.add_get("/autonomy/dashboard", self.handle_autonomy_dashboard)  # Phase 3
        self.app.router.add_post("/offline/learning/run", self.handle_offline_learning_run)
        self.app.router.add_get("/offline/learning/status", self.handle_offline_learning_status)
        self.app.router.add_post("/offline/evolution/run", self.handle_offline_evolution_run)
        
        # 🧬 ExecutableOrgans API
        self.app.router.add_get("/organs", self.handle_organs_list)
        self.app.router.add_post("/organs/feedback", self.handle_organs_feedback)
        
        if self.modules.is_enabled(MODULE_CORE):
            self.app.router.add_post("/chat", self.handle_chat)
            self.app.router.add_post("/explain", self.handle_explain)
            self.app.router.add_post("/generate", self.handle_generate)
            self.app.router.add_get("/memory", self.handle_memory)
            # Новые endpoints
            self.app.router.add_post("/complete", self.handle_complete)
            self.app.router.add_post("/fix", self.handle_fix)
            self.app.router.add_post("/generate-tests", self.handle_generate_tests)
            self.app.router.add_post("/generate-docs", self.handle_generate_docs)
            self.app.router.add_post("/refactor", self.handle_refactor)
            self.app.router.add_post("/commit-message", self.handle_commit_message)
            self.app.router.add_post("/explain-diff", self.handle_explain_diff)

        if self.modules.is_enabled(MODULE_LAYERS):
            self.app.router.add_get("/layers", self.handle_layers_list)
            self.app.router.add_post("/layers/add", self.handle_layers_add)
            self.app.router.add_post("/layers/activate", self.handle_layers_activate)
            self.app.router.add_post("/layers/delete", self.handle_layers_delete)

        if self.modules.is_enabled(MODULE_FILES):
            self.app.router.add_post("/files/read", self.handle_fs_read)
            self.app.router.add_post("/files/write", self.handle_fs_write)
            self.app.router.add_post("/files/edit", self.handle_fs_edit)
            self.app.router.add_post("/files/search", self.handle_fs_search)
            self.app.router.add_post("/files/list", self.handle_fs_list)
            self.app.router.add_post("/files/structure", self.handle_fs_structure)
            self.app.router.add_post("/files/batch-edit", self.handle_fs_batch_edit)
            self.app.router.add_post("/files/set-workspace", self.handle_fs_set_workspace)

        if self.modules.is_enabled(MODULE_STREAM):
            self.app.router.add_post("/stream/chat", self.handle_stream_chat)
            self.app.router.add_post("/stream/explain", self.handle_stream_explain)
            self.app.router.add_post("/stream/generate", self.handle_stream_generate)

        if self.modules.is_enabled(MODULE_TOOLS):
            self.app.router.add_get("/tools", self.handle_tools_list)
            self.app.router.add_post("/tools/execute", self.handle_tools_execute)
            self.app.router.add_post("/tools/batch", self.handle_tools_batch)
            self.app.router.add_get("/tools/prompt", self.handle_tools_prompt)

        if self.modules.is_enabled(MODULE_INDEXER):
            self.app.router.add_post("/index/workspace", self.handle_index_workspace)
            self.app.router.add_post("/index/search", self.handle_search_symbols)
            self.app.router.add_post("/index/context", self.handle_get_context)
            self.app.router.add_get("/index/stats", self.handle_index_stats)

        if self.modules.is_enabled(MODULE_CONTEXT):
            self.app.router.add_post("/context/build", self.handle_build_context)
            self.app.router.add_post("/context/estimate-tokens", self.handle_estimate_tokens)
            self.app.router.add_post("/context/optimal-size", self.handle_optimal_context_size)

        if self.modules.is_enabled(MODULE_MODELS):
            self.app.router.add_get("/models", self.handle_models_list)
            self.app.router.add_post("/models/switch", self.handle_models_switch)

        if self.modules.is_enabled(MODULE_SELF):
            self.app.router.add_post("/introspection", self.handle_introspection)
            self.app.router.add_post("/experience/relevant", self.handle_experience_relevant)
            self.app.router.add_post("/experience/record", self.handle_experience_record)
            self.app.router.add_post("/curiosity/question", self.handle_curiosity_question)
            self.app.router.add_post("/curiosity/reflect", self.handle_curiosity_reflect)
            self.app.router.add_post("/memory/search", self.handle_memory_search)
            self.app.router.add_post("/memory/remember", self.handle_memory_remember)
            self.app.router.add_post("/feedback/quick", self.handle_feedback_quick)

        if self.modules.is_enabled(MODULE_LEARNING):
            self.app.router.add_post("/learn", self.handle_learn)
            self.app.router.add_post("/learn/batch", self.handle_learn_batch)
            self.app.router.add_get("/learn/stats", self.handle_learning_stats)
            self.app.router.add_get("/learn/history", self.handle_learning_history)
            self.app.router.add_post("/learn/extract", self.handle_extract_content)
        
        # Server management
        self.app.router.add_post("/shutdown", self.handle_shutdown)
        
        # WebSocket
        if self.modules.is_enabled(MODULE_WS):
            self.app.router.add_get("/ws", self.handle_websocket)
        
        # Статическая страница для тестирования
        self.app.router.add_get("/", self.handle_index)
    
    async def handle_shutdown(self, request: web.Request) -> web.Response:
        """Graceful shutdown сервера"""
        logger.info("🛑 Получен запрос на остановку сервера")
        
        # Отправляем ответ перед остановкой
        response = web.json_response({
            "success": True,
            "message": "Сервер останавливается..."
        })
        
        # Планируем остановку через 1 секунду
        import asyncio
        asyncio.get_event_loop().call_later(1.0, self._shutdown)
        
        return response
    
    def _shutdown(self):
        """Выполнение остановки"""
        import sys
        logger.info("🛑 Сервер остановлен")
        sys.exit(0)
    
    async def handle_index(self, request: web.Request) -> web.Response:
        """Тестовая страница"""
        html = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Neira Server</title>
    <style>
        body { 
            font-family: 'Segoe UI', sans-serif; 
            max-width: 800px; 
            margin: 50px auto; 
            padding: 20px;
            background: #1e1e1e;
            color: #d4d4d4;
        }
        h1 { color: #569cd6; }
        .status { 
            padding: 10px; 
            border-radius: 5px; 
            background: #2d2d2d;
            margin: 10px 0;
        }
        .online { border-left: 4px solid #4ec9b0; }
        code { 
            background: #2d2d2d; 
            padding: 2px 6px; 
            border-radius: 3px;
            color: #ce9178;
        }
        a { color: #569cd6; }
    </style>
</head>
<body>
    <h1>🧠 Neira Server</h1>
    <div class="status online">
        <strong>Статус:</strong> Онлайн<br>
        <strong>Порт:</strong> """ + str(self.port) + """<br>
        <strong>Версия:</strong> 1.0.0
    </div>
    <h2>API Endpoints</h2>
    <ul>
        <li><code>GET /health</code> — Проверка состояния</li>
        <li><code>POST /chat</code> — Отправка сообщения</li>
        <li><code>POST /explain</code> — Объяснение кода</li>
        <li><code>POST /generate</code> — Генерация кода</li>
        <li><code>GET /memory</code> — Состояние памяти</li>
        <li><code>WS /ws</code> — WebSocket соединение</li>
    </ul>
    <h2>Подключение</h2>
    <p>Установите расширение <strong>Neira</strong> в VS Code или Cursor.</p>
</body>
</html>
"""
        return web.Response(text=html, content_type="text/html")
    
    async def start(self):
        """Запуск сервера"""
        if not AIOHTTP_AVAILABLE:
            logger.error("aiohttp не установлен!")
            logger.info("Установите: pip install aiohttp")
            return
        
        # Инициализация Нейры
        if not self.lazy_neira and self._needs_neira():
            await self.initialize_neira()
        
        # Настройка маршрутов
        self.setup_routes()
        
        # Запуск
        if self.app is None:
            raise RuntimeError("Application not initialized")
        runner = web.AppRunner(self.app)
        await runner.setup()

        try:
            site = web.TCPSite(runner, self.host, self.port)
            await site.start()
        except OSError as e:
            await runner.cleanup()
            if self._is_address_in_use(e):
                existing = await self._probe_existing_server()
                if existing and existing.get("success") is True:
                    logger.error(f"Порт {self.port} уже занят: Neira уже запущена.")
                    data = existing.get("data")
                    if isinstance(data, dict):
                        uptime = data.get("uptime_seconds")
                        requests = data.get("requests_processed")
                        if uptime is not None or requests is not None:
                            logger.info(f"Текущий сервер: uptime={uptime}s, запросов={requests}.")
                    logger.info(f"Остановить Neira: POST http://{self.host}:{self.port}/shutdown")
                else:
                    logger.error(f"Порт {self.port} уже занят другим процессом.")
                logger.info("Остановите старый сервер или задайте другой порт через NEIRA_PORT.")
                return
            raise
        
        logger.info("=" * 50)
        logger.info(f"🚀 Neira Server запущен")
        logger.info(f"   HTTP: http://{self.host}:{self.port}")
        logger.info(f"   WebSocket: ws://{self.host}:{self.port}/ws")
        logger.info("=" * 50)
        logger.info("Нажмите Ctrl+C для остановки")

        self._start_background_tasks()
        
        # Держим сервер запущенным
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            await self._stop_background_tasks()
            await runner.cleanup()


def _configure_io_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def start_server() -> None:
    """Запуск сервера (используется лаунчером neira.py)."""
    _configure_io_encoding()
    server = NeiraServer()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("\n👋 Сервер остановлен")


def main():
    """Точка входа"""
    _configure_io_encoding()
    print("""
    ╔═══════════════════════════════════════╗
    ║      🧠 NEIRA SERVER v1.0             ║
    ║   HTTP/WebSocket для VS Code/Cursor   ║
    ╚═══════════════════════════════════════╝
    """)
    
    server = NeiraServer()
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("\n👋 Сервер остановлен")


if __name__ == "__main__":
    main()
