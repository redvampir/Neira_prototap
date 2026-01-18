"""
LLM-адаптер для мозга Neira.

Интерфейс изолирует зависимости от внешних провайдеров и
позволяет мозгу работать без LLM по умолчанию.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

ENV_DISABLE_LLM = "NEIRA_DISABLE_LLM"
MIN_MAX_TOKENS = 128
DEFAULT_TEMPERATURE = 0.7


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value.strip())
    except ValueError:
        return default
    return parsed if parsed >= min_value else min_value


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


DEFAULT_MAX_TOKENS = _env_int("NEIRA_MAX_RESPONSE_TOKENS", 2048, MIN_MAX_TOKENS)


@dataclass(frozen=True)
class LLMResult:
    """Результат обращения к LLM."""

    content: str
    success: bool
    provider: str | None = None
    model: str | None = None
    error: str | None = None


class LLMClient(Protocol):
    """Контракт для LLM-провайдера."""

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResult:
        """Генерирует ответ на запрос."""


class NullLLMClient:
    """Пустой LLM-клиент, всегда возвращает ошибку."""

    def __init__(self, reason: str = "LLM отключён"):
        self._reason = reason

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResult:
        return LLMResult(content="", success=False, error=self._reason)


class ProviderLLMClient:
    """Адаптер над LLMManager из llm_providers."""

    def __init__(self, manager: object):
        self._manager = manager

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResult:
        response = self._manager.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        provider = getattr(response.provider, "value", str(response.provider))
        return LLMResult(
            content=response.content,
            success=response.success,
            provider=provider,
            model=response.model,
            error=response.error,
        )


def build_default_llm_client() -> LLMClient:
    """
    Создаёт LLM-клиент с учётом настроек окружения.
    """
    if _env_bool(ENV_DISABLE_LLM, False):
        return NullLLMClient("LLM отключён через окружение")
    try:
        from llm_providers import create_default_manager
    except ImportError:
        logger.info("LLM провайдеры недоступны, используем NullLLMClient")
        return NullLLMClient("LLM провайдеры недоступны")

    manager = create_default_manager()
    available = getattr(manager, "available_providers", [])
    if not available:
        return NullLLMClient("LLM провайдеры не найдены")
    return ProviderLLMClient(manager)


__all__ = ["LLMClient", "LLMResult", "build_default_llm_client", "NullLLMClient"]
