"""
Центральная конфигурация проекта Neira.

Все "magic numbers" и настройки должны быть здесь,
а не хардкодиться в отдельных модулях.

Использование:
    from neira.config import MEMORY_MAX_LONG_TERM, LLM_DEFAULT_TIMEOUT
"""

import os
from pathlib import Path
from typing import Final, Iterable


def _parse_csv_env(name: str, default: Iterable[str]) -> tuple[str, ...]:
    """Читает CSV из env и возвращает tuple значений."""
    raw = os.getenv(name, "")
    if not raw:
        return tuple(default)
    parts = [item.strip() for item in raw.split(",") if item.strip()]
    return tuple(parts) if parts else tuple(default)

# ============================================================================
# ПУТИ
# ============================================================================

# Корень проекта (где лежит neira/)
PROJECT_ROOT: Final[Path] = Path(__file__).parent.parent.resolve()

# Папка для артефактов (логи, кэш, временные файлы)
ARTIFACTS_DIR: Final[Path] = PROJECT_ROOT / "artifacts"

# Папка для бэкапов памяти
MEMORY_BACKUPS_DIR: Final[Path] = PROJECT_ROOT / "memory_backups"

# ============================================================================
# ПАМЯТЬ (Memory System)
# ============================================================================

# Максимальное количество записей
MEMORY_MAX_LONG_TERM: Final[int] = int(os.getenv("NEIRA_MAX_LONG_TERM", "1000"))
MEMORY_MAX_SHORT_TERM: Final[int] = int(os.getenv("NEIRA_MAX_SHORT_TERM", "100"))
MEMORY_MAX_SEMANTIC: Final[int] = int(os.getenv("NEIRA_MAX_SEMANTIC", "500"))
MEMORY_MAX_EPISODIC: Final[int] = int(os.getenv("NEIRA_MAX_EPISODIC", "300"))

# Пороги confidence
MEMORY_MIN_CONFIDENCE: Final[float] = 0.3  # Минимум для операций очистки
MEMORY_MIN_CONFIDENCE_KEEP: Final[float] = 0.3  # Минимум для сохранения
MEMORY_MIN_CONFIDENCE_RECALL: Final[float] = 0.5  # Минимум для извлечения

# Очистка памяти
MEMORY_CLEANUP_AGE_DAYS: Final[int] = int(os.getenv("NEIRA_CLEANUP_AGE_DAYS", "30"))

# Защита от дубликатов
MEMORY_DUPLICATE_SIMILARITY_THRESHOLD: Final[float] = 0.85  # Порог схожести для дубликатов
MEMORY_DUPLICATE_TIME_WINDOW_HOURS: Final[int] = 24  # Окно проверки дубликатов

# ============================================================================
# LLM (Language Model)
# ============================================================================

# Таймауты (секунды)
LLM_DEFAULT_TIMEOUT: Final[int] = int(os.getenv("NEIRA_LLM_TIMEOUT", "60"))
LLM_CODE_TIMEOUT: Final[int] = int(os.getenv("NEIRA_CODE_TIMEOUT", "120"))
LLM_FAILURE_COOLDOWN_SECONDS: Final[int] = int(
    os.getenv("NEIRA_LLM_FAILURE_COOLDOWN_SEC", "180")
)

# Токены
LLM_MAX_RESPONSE_TOKENS: Final[int] = int(os.getenv("NEIRA_MAX_RESPONSE_TOKENS", "4096"))
LLM_CONTEXT_MAX_TOKENS: Final[int] = int(os.getenv("NEIRA_CONTEXT_MAX_TOKENS", "32000"))
LLM_CONTEXT_RESERVED_TOKENS: Final[int] = int(os.getenv("NEIRA_CONTEXT_RESERVED_TOKENS", "6000"))

# Параметры генерации по умолчанию
LLM_DEFAULT_TEMPERATURE: Final[float] = 0.7
LLM_CODE_TEMPERATURE: Final[float] = 0.3  # Ниже для кода
LLM_CREATIVE_TEMPERATURE: Final[float] = 0.9  # Выше для творчества

# Ollama специфичные
OLLAMA_DEFAULT_MODEL: Final[str] = os.getenv("NEIRA_OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_BASE_URL: Final[str] = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_NUM_CTX: Final[int] = int(os.getenv("NEIRA_OLLAMA_NUM_CTX", "32768"))

# LM Studio
LMSTUDIO_BASE_URL: Final[str] = os.getenv("LMSTUDIO_HOST", "http://localhost:1234")
LMSTUDIO_DEFAULT_MODEL: Final[str] = os.getenv("NEIRA_LMSTUDIO_MODEL", "qwen/qwen2.5-coder-14b")

# ============================================================================
# TELEGRAM
# ============================================================================

# Лимиты сообщений
TELEGRAM_MAX_MESSAGE_LENGTH: Final[int] = 4000  # Telegram limit ~4096
TELEGRAM_RATE_LIMIT_MESSAGES: Final[int] = 10  # Сообщений в минуту
TELEGRAM_RATE_LIMIT_WINDOW: Final[int] = 60  # Окно в секундах

# ============================================================================
# ТКП (Технико-коммерческие предложения)
# ============================================================================

TKP_SAMPLES_DIR: Final[Path] = PROJECT_ROOT / "training_data" / "tkp" / "samples"
TKP_CATALOGS_DIR: Final[Path] = PROJECT_ROOT / "training_data" / "tkp" / "catalogs"
TKP_OUTPUT_DIR: Final[Path] = ARTIFACTS_DIR / "tkp"
TKP_PARSED_DIR: Final[Path] = TKP_OUTPUT_DIR / "parsed"
TKP_PARSED_SCHEMA_VERSION: Final[str] = os.getenv("NEIRA_TKP_PARSED_SCHEMA_VERSION", "3")

TKP_MISSING_VALUE_TEXT: Final[str] = os.getenv(
    "NEIRA_TKP_MISSING_VALUE_TEXT",
    "Требуется уточнение",
)
TKP_SNIPPET_CHARS: Final[int] = int(os.getenv("NEIRA_TKP_SNIPPET_CHARS", "600"))
TKP_VALUE_WINDOW_CHARS: Final[int] = int(
    os.getenv("NEIRA_TKP_VALUE_WINDOW_CHARS", "180")
)
TKP_LIST_LIMIT: Final[int] = int(os.getenv("NEIRA_TKP_LIST_LIMIT", "8"))
TKP_INTRO_PARAGRAPH_LIMIT: Final[int] = int(
    os.getenv("NEIRA_TKP_INTRO_PARAGRAPH_LIMIT", "2")
)
TKP_COMPANY_PARAGRAPH_LIMIT: Final[int] = int(
    os.getenv("NEIRA_TKP_COMPANY_PARAGRAPH_LIMIT", "5")
)
TKP_PARSE_PAGE_WINDOW: Final[int] = int(
    os.getenv("NEIRA_TKP_PARSE_PAGE_WINDOW", "1")
)
TKP_PARSE_FALLBACK_PAGES: Final[int] = int(
    os.getenv("NEIRA_TKP_PARSE_FALLBACK_PAGES", "2")
)
TKP_PARAM_MATCH_MIN_SCORE: Final[float] = float(
    os.getenv("NEIRA_TKP_PARAM_MATCH_MIN_SCORE", "0.62")
)

# ============================================================================
# ОРГАНЫ (Organ System)  
# ============================================================================

# Лимиты создания органов
ORGAN_MAX_CODE_LENGTH: Final[int] = 10000  # Символов кода
ORGAN_EXEC_TIMEOUT: Final[int] = 30  # Секунд на выполнение
ORGAN_MAX_MEMORY_MB: Final[int] = 100  # Лимит памяти

# Безопасные зависимости для органов (pip-пакеты)
ORGAN_DEP_ALLOWLIST: Final[tuple[str, ...]] = _parse_csv_env(
    "NEIRA_ORGAN_DEP_ALLOWLIST",
    (
        "faster-whisper",
        "ctranslate2",
        "tokenizers",
        "huggingface-hub",
        "numpy",
        "soundfile",
        "pydub",
        "pypdf",
        "aiohttp",
        "beautifulsoup4",
        "lxml",
        "youtube-transcript-api",
        "duckduckgo-search",
        "python-docx",
        "pillow",
        "requests",
    ),
)

# Маппинг module -> pip package
ORGAN_DEP_MODULE_MAP: Final[dict[str, str]] = {
    "bs4": "beautifulsoup4",
    "pillow": "pillow",
    "pil": "pillow",
    "cv2": "opencv-python",
    "yaml": "pyyaml",
    "sklearn": "scikit-learn",
    "ffmpeg": "ffmpeg",
    "yt_dlp": "yt-dlp",
    "docx": "python-docx",
}

# Таймаут установки зависимостей (секунды)
ORGAN_DEP_INSTALL_TIMEOUT: Final[int] = int(
    os.getenv("NEIRA_ORGAN_DEP_INSTALL_TIMEOUT", "600")
)
ORGAN_DEP_INSTALL_OUTPUT_LIMIT: Final[int] = int(
    os.getenv("NEIRA_ORGAN_DEP_INSTALL_OUTPUT_LIMIT", "800")
)

# ============================================================================
# БЕЗОПАСНОСТЬ
# ============================================================================

# Sandbox для exec()
EXEC_ALLOWED_BUILTINS: Final[tuple[str, ...]] = (
    'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple', 'set',
    'range', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed',
    'min', 'max', 'sum', 'abs', 'round', 'print', 'isinstance', 'type',
    'hasattr', 'getattr', 'setattr', 'any', 'all'
)

# Запрещённые модули для импорта в sandbox
EXEC_FORBIDDEN_MODULES: Final[tuple[str, ...]] = (
    'os', 'sys', 'subprocess', 'shutil', 'pathlib',
    'socket', 'requests', 'urllib', 'http',
    'pickle', 'marshal', 'shelve',
    'ctypes', 'multiprocessing', 'threading'
)

# ============================================================================
# ЛОГИРОВАНИЕ
# ============================================================================

LOG_LEVEL: Final[str] = os.getenv("NEIRA_LOG_LEVEL", "INFO")
LOG_FORMAT: Final[str] = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"

# Файлы логов
LOG_ERROR_FILE: Final[Path] = ARTIFACTS_DIR / "neira_errors.txt"
LOG_CHAT_FILE: Final[Path] = ARTIFACTS_DIR / "neira_chat.log"
LOG_TELEGRAM_FILE: Final[Path] = ARTIFACTS_DIR / "telegram_bot.log"

# ============================================================================
# ВЕРСИЯ
# ============================================================================

VERSION: Final[str] = "0.8.5"
VERSION_CODENAME: Final[str] = "Quality Guardian"
