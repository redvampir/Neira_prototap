"""
Rate Limiter для защиты от спама LLM-запросов.
Предотвращает превышение лимитов API и перегрузку системы.
"""

import time
from collections import defaultdict
from typing import Optional
from dataclasses import dataclass, field
import threading


@dataclass
class RateLimitConfig:
    """Конфигурация rate limiting."""
    requests_per_minute: int = 30  # Макс запросов в минуту
    requests_per_hour: int = 500   # Макс запросов в час
    burst_limit: int = 5           # Макс запросов подряд без паузы
    min_interval_seconds: float = 0.5  # Минимальная пауза между запросами
    cooldown_seconds: float = 60.0  # Пауза после превышения лимита


@dataclass  
class UserStats:
    """Статистика пользователя."""
    requests: list = field(default_factory=list)  # Timestamps запросов
    last_request: float = 0.0
    burst_count: int = 0
    blocked_until: float = 0.0


class RateLimiter:
    """
    Rate limiter с поддержкой per-user и global лимитов.
    Thread-safe.
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._users: dict[str, UserStats] = defaultdict(UserStats)
        self._global = UserStats()
        self._lock = threading.Lock()
    
    def check(self, user_id: str = "global") -> tuple[bool, str]:
        """
        Проверить, можно ли выполнить запрос.
        
        Returns:
            (allowed, reason) - True если можно, иначе причина блокировки
        """
        with self._lock:
            now = time.time()
            stats = self._users[user_id]
            
            # Проверка блокировки
            if stats.blocked_until > now:
                wait = int(stats.blocked_until - now)
                return False, f"Превышен лимит. Подождите {wait} сек."
            
            # Очистка старых записей
            minute_ago = now - 60
            hour_ago = now - 3600
            stats.requests = [t for t in stats.requests if t > hour_ago]
            
            # Подсчёт запросов
            requests_last_minute = sum(1 for t in stats.requests if t > minute_ago)
            requests_last_hour = len(stats.requests)
            
            # Проверка лимита в минуту
            if requests_last_minute >= self.config.requests_per_minute:
                stats.blocked_until = now + self.config.cooldown_seconds
                return False, f"Лимит {self.config.requests_per_minute} запросов/мин."
            
            # Проверка лимита в час
            if requests_last_hour >= self.config.requests_per_hour:
                stats.blocked_until = now + self.config.cooldown_seconds * 5
                return False, f"Лимит {self.config.requests_per_hour} запросов/час."
            
            # Проверка burst (слишком частые запросы)
            if stats.last_request > 0:
                interval = now - stats.last_request
                if interval < self.config.min_interval_seconds:
                    stats.burst_count += 1
                    if stats.burst_count >= self.config.burst_limit:
                        stats.blocked_until = now + self.config.cooldown_seconds / 2
                        stats.burst_count = 0
                        return False, "Слишком частые запросы. Подождите."
                else:
                    stats.burst_count = 0
            
            return True, "OK"
    
    def record(self, user_id: str = "global") -> None:
        """Записать успешный запрос."""
        with self._lock:
            now = time.time()
            stats = self._users[user_id]
            stats.requests.append(now)
            stats.last_request = now
    
    def get_stats(self, user_id: str = "global") -> dict:
        """Получить статистику пользователя."""
        with self._lock:
            now = time.time()
            stats = self._users[user_id]
            
            minute_ago = now - 60
            hour_ago = now - 3600
            
            return {
                "requests_last_minute": sum(1 for t in stats.requests if t > minute_ago),
                "requests_last_hour": sum(1 for t in stats.requests if t > hour_ago),
                "blocked": stats.blocked_until > now,
                "blocked_for": max(0, int(stats.blocked_until - now)),
                "limits": {
                    "per_minute": self.config.requests_per_minute,
                    "per_hour": self.config.requests_per_hour,
                }
            }
    
    def reset(self, user_id: str = "global") -> None:
        """Сбросить статистику пользователя."""
        with self._lock:
            self._users[user_id] = UserStats()


# Глобальный rate limiter
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Получить глобальный rate limiter (singleton)."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def check_rate_limit(user_id: str = "global") -> tuple[bool, str]:
    """Проверить rate limit для пользователя."""
    return get_rate_limiter().check(user_id)


def record_request(user_id: str = "global") -> None:
    """Записать запрос."""
    get_rate_limiter().record(user_id)


# Декоратор для async функций
def rate_limited(user_id_arg: str = "user_id"):
    """
    Декоратор для применения rate limiting к async функциям.
    
    Использование:
        @rate_limited("chat_id")
        async def process_message(chat_id: str, text: str):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Попытка извлечь user_id из kwargs или первого arg
            uid = kwargs.get(user_id_arg, "global")
            if uid == "global" and args:
                uid = str(args[0])
            
            allowed, reason = check_rate_limit(str(uid))
            if not allowed:
                raise RateLimitExceeded(reason)
            
            record_request(str(uid))
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class RateLimitExceeded(Exception):
    """Исключение при превышении rate limit."""
    pass


if __name__ == "__main__":
    # Тест
    limiter = RateLimiter(RateLimitConfig(
        requests_per_minute=5,
        burst_limit=3,
        min_interval_seconds=0.1
    ))
    
    print("Тест rate limiter:")
    for i in range(10):
        allowed, reason = limiter.check("test_user")
        print(f"  Запрос {i+1}: {'✅' if allowed else '❌'} {reason}")
        if allowed:
            limiter.record("test_user")
        time.sleep(0.05)  # Быстрые запросы для теста burst
    
    print("\nСтатистика:")
    print(f"  {limiter.get_stats('test_user')}")
