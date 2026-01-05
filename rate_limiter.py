"""
Rate Limiter для защиты от спама.

DEPRECATED: Используйте neira.utils.rate_limiter
Этот файл оставлен для обратной совместимости.
"""

# Реэкспорт из нового пакета
from neira.utils.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitExceeded,
    UserStats,
    check_rate_limit,
    record_request,
    get_rate_limiter,
)

__all__ = [
    "RateLimiter",
    "RateLimitConfig", 
    "RateLimitExceeded",
    "UserStats",
    "check_rate_limit",
    "record_request",
    "get_rate_limiter",
]
