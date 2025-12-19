"""
Настройки сети для Telegram-бота Neira.

Этот модуль намеренно не импортирует `telegram_bot.py`, чтобы его можно было
использовать в проверочных скриптах и утилитах без обязательного наличия токена.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class TelegramNetworkConfig:
    """Параметры сети/подключения для Telegram API."""

    connect_timeout: float = 15.0
    read_timeout: float = 30.0
    write_timeout: float = 30.0
    pool_timeout: float = 30.0

    polling_timeout: int = 10
    polling_bootstrap_retries: int = -1

    startup_retries: int = -1
    startup_backoff_base_seconds: float = 2.0
    startup_backoff_max_seconds: float = 60.0

    proxy_url: str | None = None
    base_url: str | None = None


def compute_backoff_seconds(retry_index: int, *, base_seconds: float, max_seconds: float) -> float:
    """
    Экспоненциальная задержка для ретраев.

    retry_index: 0 для первого ретрая, 1 для второго, ...
    """

    if retry_index < 0:
        raise ValueError("retry_index должен быть >= 0")
    if base_seconds <= 0:
        raise ValueError("base_seconds должен быть > 0")
    if max_seconds <= 0:
        raise ValueError("max_seconds должен быть > 0")
    if max_seconds < base_seconds:
        raise ValueError("max_seconds должен быть >= base_seconds")

    delay = base_seconds * (2.0**retry_index)
    return min(max_seconds, delay)


def sanitize_url_for_log(url: str) -> str:
    """Убирает логины/пароли из URL, оставляя только схему/хост/порт/путь."""

    parsed = urlparse(url)
    scheme = parsed.scheme or "url"
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or ""

    if not host:
        return f"{scheme}://<configured>"
    return f"{scheme}://{host}{port}{path}"


def load_telegram_network_config(env: Mapping[str, str] | None = None) -> TelegramNetworkConfig:
    """
    Загружает сетевые параметры Telegram из env.

    Поддерживаемые переменные окружения:
    - NEIRA_TG_CONNECT_TIMEOUT / READ / WRITE / POOL (float, секунды)
    - NEIRA_TG_POLLING_TIMEOUT (int, секунды)
    - NEIRA_TG_POLLING_BOOTSTRAP_RETRIES (int, -1 или >=0)
    - NEIRA_TG_STARTUP_RETRIES (int, -1 или >=0)
    - NEIRA_TG_STARTUP_BACKOFF_BASE_SECONDS (float)
    - NEIRA_TG_STARTUP_BACKOFF_MAX_SECONDS (float)
    - NEIRA_TG_PROXY_URL (str, http(s)/socks5 URL)
    - NEIRA_TG_BASE_URL (str, кастомный Bot API base URL)
    """

    if env is None:
        env = os.environ

    connect_timeout = _get_env_float(env, "NEIRA_TG_CONNECT_TIMEOUT", 15.0, min_value=0.1)
    read_timeout = _get_env_float(env, "NEIRA_TG_READ_TIMEOUT", 30.0, min_value=0.1)
    write_timeout = _get_env_float(env, "NEIRA_TG_WRITE_TIMEOUT", 30.0, min_value=0.1)
    pool_timeout = _get_env_float(env, "NEIRA_TG_POOL_TIMEOUT", 30.0, min_value=0.1)

    polling_timeout = _get_env_int(env, "NEIRA_TG_POLLING_TIMEOUT", 10, min_value=1)
    polling_bootstrap_retries = _get_env_int(env, "NEIRA_TG_POLLING_BOOTSTRAP_RETRIES", -1, min_value=-1)
    startup_retries = _get_env_int(env, "NEIRA_TG_STARTUP_RETRIES", -1, min_value=-1)

    startup_backoff_base_seconds = _get_env_float(
        env, "NEIRA_TG_STARTUP_BACKOFF_BASE_SECONDS", 2.0, min_value=0.1
    )
    startup_backoff_max_seconds = _get_env_float(
        env, "NEIRA_TG_STARTUP_BACKOFF_MAX_SECONDS", 60.0, min_value=0.1
    )

    proxy_url = _get_env_optional_str(env, "NEIRA_TG_PROXY_URL")
    base_url = _get_env_optional_str(env, "NEIRA_TG_BASE_URL")

    if proxy_url is not None:
        _validate_url(proxy_url, "NEIRA_TG_PROXY_URL")
    if base_url is not None:
        _validate_url(base_url, "NEIRA_TG_BASE_URL")

    if startup_backoff_max_seconds < startup_backoff_base_seconds:
        raise ValueError("NEIRA_TG_STARTUP_BACKOFF_MAX_SECONDS должен быть >= NEIRA_TG_STARTUP_BACKOFF_BASE_SECONDS")

    return TelegramNetworkConfig(
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        write_timeout=write_timeout,
        pool_timeout=pool_timeout,
        polling_timeout=polling_timeout,
        polling_bootstrap_retries=polling_bootstrap_retries,
        startup_retries=startup_retries,
        startup_backoff_base_seconds=startup_backoff_base_seconds,
        startup_backoff_max_seconds=startup_backoff_max_seconds,
        proxy_url=proxy_url,
        base_url=base_url,
    )


def _get_env_optional_str(env: Mapping[str, str], key: str) -> str | None:
    raw = env.get(key)
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def _get_env_int(env: Mapping[str, str], key: str, default: int, *, min_value: int | None = None) -> int:
    raw = env.get(key)
    if raw is None or not raw.strip():
        value = default
    else:
        try:
            value = int(raw.strip())
        except ValueError as exc:
            raise ValueError(f"{key} должен быть целым числом, получено: {raw!r}") from exc

    if min_value is not None and value < min_value:
        raise ValueError(f"{key} должен быть >= {min_value}, получено: {value}")
    return value


def _get_env_float(
    env: Mapping[str, str],
    key: str,
    default: float,
    *,
    min_value: float | None = None,
) -> float:
    raw = env.get(key)
    if raw is None or not raw.strip():
        value = float(default)
    else:
        try:
            value = float(raw.strip())
        except ValueError as exc:
            raise ValueError(f"{key} должен быть числом, получено: {raw!r}") from exc

    if min_value is not None and value < min_value:
        raise ValueError(f"{key} должен быть >= {min_value}, получено: {value}")
    return value


def _validate_url(url: str, key: str) -> None:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"{key} должен быть валидным URL вида 'scheme://host:port', получено: {url!r}")

