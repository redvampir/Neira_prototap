"""
Утилиты Neira.

Модули:
- text: Обработка текста (удаление дубликатов, нормализация)
- rate_limiter: Защита от спама
- identity: Загрузка личности Нейры
"""

from neira.utils.text import (
    remove_duplicate_paragraphs,
    truncate_text,
    normalize_whitespace,
    extract_code_blocks,
)

from neira.utils.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    check_rate_limit,
    record_request,
    get_rate_limiter,
)

from neira.utils.identity import (
    load_personality,
    build_identity_prompt,
    get_creator_name,
    clear_cache as clear_identity_cache,
    IDENTITY_PROMPT,
)

from neira.utils.memory_manager import (
    MemoryManager,
)

__all__ = [
    # text
    "remove_duplicate_paragraphs",
    "truncate_text", 
    "normalize_whitespace",
    "extract_code_blocks",
    # rate_limiter
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitExceeded",
    "check_rate_limit",
    "record_request",
    "get_rate_limiter",
    # identity
    "load_personality",
    "build_identity_prompt",
    "get_creator_name",
    "clear_identity_cache",
    "IDENTITY_PROMPT",
    # memory_manager
    "MemoryManager",
]
