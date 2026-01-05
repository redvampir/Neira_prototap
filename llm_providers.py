"""
LLM Providers v1.0 — Универсальный интерфейс для разных LLM API
Поддерживает: Ollama, OpenAI, Claude, Groq, Gemini с автоматическим fallback
"""

import os
import requests
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from local_embeddings import get_local_embedding
    LOCAL_EMBEDDINGS_AVAILABLE = True
except Exception:
    LOCAL_EMBEDDINGS_AVAILABLE = False

try:
    from model_layers import ModelLayersRegistry

    _MODEL_LAYERS = ModelLayersRegistry("model_layers.json")
except Exception as exc:
    _MODEL_LAYERS = None
    logger.info("Слои моделей отключены: %s", exc)


def _env_int(name: str, default: int, min_value: int = 1, max_value: Optional[int] = None) -> int:
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


def _env_optional_int(name: str, min_value: int = 1, max_value: Optional[int] = None) -> Optional[int]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw.strip())
    except ValueError:
        return None
    if value < min_value:
        return min_value
    if max_value is not None and value > max_value:
        return max_value
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default


DEFAULT_MAX_RESPONSE_TOKENS = _env_int("NEIRA_MAX_RESPONSE_TOKENS", 2048, min_value=128)
DEFAULT_OLLAMA_NUM_CTX = _env_optional_int("NEIRA_OLLAMA_NUM_CTX", min_value=256)


def _merge_system_prompt(base_prompt: str, layer_prompt: Optional[str]) -> str:
    if not layer_prompt:
        return base_prompt
    if not base_prompt:
        return layer_prompt
    return f"{base_prompt}\n\n[Слой модели]\n{layer_prompt}"


class ProviderType(Enum):
    """Типы провайдеров"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    CLAUDE = "claude"
    GROQ = "groq"
    GEMINI = "gemini"
    LLAMACPP = "llamacpp"  # llama.cpp server
    LMSTUDIO = "lmstudio"  # LM Studio


def _normalize_provider_name(name: str) -> str:
    return name.strip().lower().replace("-", "").replace("_", "").replace(".", "")


_PROVIDER_NAME_MAP = {
    "ollama": ProviderType.OLLAMA,
    "openai": ProviderType.OPENAI,
    "claude": ProviderType.CLAUDE,
    "groq": ProviderType.GROQ,
    "gemini": ProviderType.GEMINI,
    "llamacpp": ProviderType.LLAMACPP,
    "lmstudio": ProviderType.LMSTUDIO,
}

_DEFAULT_PROVIDER_PRIORITY = [
    ProviderType.OLLAMA,
    ProviderType.LMSTUDIO,
    ProviderType.LLAMACPP,
    ProviderType.GROQ,
    ProviderType.OPENAI,
    ProviderType.CLAUDE,
]


def _parse_provider_priority() -> List[ProviderType]:
    raw = os.getenv("LLM_PROVIDER_PRIORITY", "")
    if not raw.strip():
        return list(_DEFAULT_PROVIDER_PRIORITY)
    result: List[ProviderType] = []
    seen = set()
    for token in raw.split(","):
        normalized = _normalize_provider_name(token)
        if not normalized:
            continue
        provider = _PROVIDER_NAME_MAP.get(normalized)
        if provider and provider not in seen:
            seen.add(provider)
            result.append(provider)
    return result if result else list(_DEFAULT_PROVIDER_PRIORITY)


@dataclass
class LLMResponse:
    """Стандартный ответ от LLM"""
    content: str
    provider: ProviderType
    model: str
    success: bool
    error: Optional[str] = None
    tokens_used: Optional[int] = None
    cost: Optional[float] = None


class LLMProvider(ABC):
    """Абстрактный базовый класс для всех провайдеров"""
    
    def __init__(self, model: str, timeout: int = 180):
        self.model = model
        self.timeout = timeout
        self.available = False
        self._check_availability()
    
    @abstractmethod
    def _check_availability(self) -> bool:
        """Проверка доступности провайдера"""
        pass
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_RESPONSE_TOKENS
    ) -> LLMResponse:
        """Генерация ответа от LLM"""
        pass
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Получить эмбеддинг текста (векторное представление).
        
        Возвращает None если провайдер не поддерживает embeddings.
        Используется для семантического поиска в памяти.
        """
        return None  # По умолчанию не поддерживается
    
    @abstractmethod
    def get_provider_type(self) -> ProviderType:
        """Возвращает тип провайдера"""
        pass


class OllamaProvider(LLMProvider):
    """Провайдер для Ollama (локальный)"""
    
    def __init__(
        self,
        model: str = "qwen2.5:0.5b",
        url: str = "http://localhost:11434/api/generate",
        timeout: int = 180
    ):
        self.url = url
        super().__init__(model, timeout)
    
    def _check_availability(self) -> bool:
        """Проверяем доступность Ollama"""
        try:
            response = requests.get(
                "http://localhost:11434/api/tags",
                timeout=5
            )
            self.available = response.status_code == 200
            return self.available
        except Exception:
            self.available = False
            return False
    
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_RESPONSE_TOKENS
    ) -> LLMResponse:
        """Генерация через Ollama"""
        try:
            options: Dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
            if DEFAULT_OLLAMA_NUM_CTX is not None:
                options["num_ctx"] = DEFAULT_OLLAMA_NUM_CTX
            if _MODEL_LAYERS is not None:
                adapter = _MODEL_LAYERS.get_active_adapter(self.model)
                if adapter:
                    options["adapter"] = adapter

            response = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": options
                },
                timeout=self.timeout
            )
            
            if response.status_code == 500:
                error_msg = response.json().get("error", "unknown error")
                return LLMResponse(
                    content="",
                    provider=ProviderType.OLLAMA,
                    model=self.model,
                    success=False,
                    error=f"Ollama error: {error_msg}"
                )
            
            result = response.json().get("response", "")
            
            if not result or not result.strip():
                return LLMResponse(
                    content="",
                    provider=ProviderType.OLLAMA,
                    model=self.model,
                    success=False,
                    error="Empty response from Ollama"
                )
            
            return LLMResponse(
                content=result,
                provider=ProviderType.OLLAMA,
                model=self.model,
                success=True
            )
            
        except requests.exceptions.Timeout:
            return LLMResponse(
                content="",
                provider=ProviderType.OLLAMA,
                model=self.model,
                success=False,
                error="Timeout"
            )
        except Exception as e:
            return LLMResponse(
                content="",
                provider=ProviderType.OLLAMA,
                model=self.model,
                success=False,
                error=str(e)
            )
    
    def get_embedding(self, text: str, model: str = "nomic-embed-text") -> Optional[List[float]]:
        """
        Получить эмбеддинг через Ollama.
        
        Args:
            text: Текст для векторизации
            model: Модель эмбеддингов (по умолчанию nomic-embed-text)
        
        Returns:
            Список чисел (вектор) или None при ошибке
        """
        if not self.available:
            return None
        
        try:
            base_url = self.url.replace("/api/generate", "")
            embed_url = f"{base_url}/api/embeddings"
            
            response = requests.post(
                embed_url,
                json={"model": model, "prompt": text},
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get("embedding")
            else:
                logger.warning(f"Ollama embeddings failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"Ollama embedding error: {e}")
            return None
    
    def get_provider_type(self) -> ProviderType:
        return ProviderType.OLLAMA


class OpenAIProvider(LLMProvider):
    """Провайдер для OpenAI API (GPT-4, GPT-3.5)"""
    
    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None,
        timeout: int = 180
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.url = "https://api.openai.com/v1/chat/completions"
        super().__init__(model, timeout)
    
    def _check_availability(self) -> bool:
        """Проверяем наличие API ключа"""
        self.available = bool(self.api_key)
        if not self.available:
            logger.warning("OpenAI API key not found. Set OPENAI_API_KEY env variable.")
        return self.available
    
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_RESPONSE_TOKENS
    ) -> LLMResponse:
        """Генерация через OpenAI"""
        if not self.available:
            return LLMResponse(
                content="",
                provider=ProviderType.OPENAI,
                model=self.model,
                success=False,
                error="API key not configured"
            )
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = requests.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    content="",
                    provider=ProviderType.OPENAI,
                    model=self.model,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            
            # Примерная стоимость (обнови актуальными ценами)
            cost = self._calculate_cost(tokens)
            
            return LLMResponse(
                content=content,
                provider=ProviderType.OPENAI,
                model=self.model,
                success=True,
                tokens_used=tokens,
                cost=cost
            )
            
        except Exception as e:
            return LLMResponse(
                content="",
                provider=ProviderType.OPENAI,
                model=self.model,
                success=False,
                error=str(e)
            )
    
    def _calculate_cost(self, tokens: int) -> float:
        """Примерный расчет стоимости"""
        # GPT-3.5-turbo: $0.0015 / 1K tokens (input) + $0.002 / 1K tokens (output)
        # Усредненно: $0.002 / 1K tokens
        if "gpt-3.5" in self.model:
            return (tokens / 1000) * 0.002
        elif "gpt-4" in self.model:
            return (tokens / 1000) * 0.03  # GPT-4 дороже
        return 0.0
    
    def get_embedding(self, text: str, model: str = "text-embedding-3-small") -> Optional[List[float]]:
        """
        Получить эмбеддинг через OpenAI Embeddings API.
        
        Args:
            text: Текст для векторизации
            model: Модель (text-embedding-3-small или text-embedding-3-large)
        
        Returns:
            Вектор размерности 1536 (small) или 3072 (large), или None при ошибке
        
        Стоимость: $0.00002 / 1K tokens (text-embedding-3-small)
        """
        if not self.available:
            return None
        
        try:
            response = requests.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={"model": model, "input": text},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["data"][0]["embedding"]
            else:
                logger.warning(f"OpenAI embeddings failed: {response.status_code}")
                return None
                
        except Exception as e:
            logger.warning(f"OpenAI embedding error: {e}")
            return None
    
    def get_provider_type(self) -> ProviderType:
        return ProviderType.OPENAI


class ClaudeProvider(LLMProvider):
    """Провайдер для Anthropic Claude API"""
    
    def __init__(
        self,
        model: str = "claude-3-haiku-20240307",
        api_key: Optional[str] = None,
        timeout: int = 180
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.url = "https://api.anthropic.com/v1/messages"
        super().__init__(model, timeout)
    
    def _check_availability(self) -> bool:
        """Проверяем наличие API ключа"""
        self.available = bool(self.api_key)
        if not self.available:
            logger.warning("Anthropic API key not found. Set ANTHROPIC_API_KEY env variable.")
        return self.available
    
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_RESPONSE_TOKENS
    ) -> LLMResponse:
        """Генерация через Claude"""
        if not self.available:
            return LLMResponse(
                content="",
                provider=ProviderType.CLAUDE,
                model=self.model,
                success=False,
                error="API key not configured"
            )
        
        try:
            payload = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            response = requests.post(
                self.url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    content="",
                    provider=ProviderType.CLAUDE,
                    model=self.model,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
            
            data = response.json()
            content = data["content"][0]["text"]
            tokens = data.get("usage", {}).get("input_tokens", 0) + \
                     data.get("usage", {}).get("output_tokens", 0)
            
            cost = self._calculate_cost(tokens)
            
            return LLMResponse(
                content=content,
                provider=ProviderType.CLAUDE,
                model=self.model,
                success=True,
                tokens_used=tokens,
                cost=cost
            )
            
        except Exception as e:
            return LLMResponse(
                content="",
                provider=ProviderType.CLAUDE,
                model=self.model,
                success=False,
                error=str(e)
            )
    
    def _calculate_cost(self, tokens: int) -> float:
        """Примерный расчет стоимости"""
        # Claude Haiku: $0.25 / 1M input, $1.25 / 1M output
        # Усредненно: $0.75 / 1M tokens = $0.00075 / 1K
        if "haiku" in self.model:
            return (tokens / 1000) * 0.00075
        elif "sonnet" in self.model:
            return (tokens / 1000) * 0.003
        elif "opus" in self.model:
            return (tokens / 1000) * 0.015
        return 0.0
    
    def get_provider_type(self) -> ProviderType:
        return ProviderType.CLAUDE


class GroqProvider(LLMProvider):
    """Провайдер для Groq API (очень быстрый)"""
    
    def __init__(
        self,
        model: str = "llama-3.1-8b-instant",
        api_key: Optional[str] = None,
        timeout: int = 60
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.url = "https://api.groq.com/openai/v1/chat/completions"
        super().__init__(model, timeout)
    
    def _check_availability(self) -> bool:
        """Проверяем наличие API ключа"""
        self.available = bool(self.api_key)
        if not self.available:
            logger.warning("Groq API key not found. Set GROQ_API_KEY env variable.")
        return self.available
    
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_RESPONSE_TOKENS
    ) -> LLMResponse:
        """Генерация через Groq"""
        if not self.available:
            return LLMResponse(
                content="",
                provider=ProviderType.GROQ,
                model=self.model,
                success=False,
                error="API key not configured"
            )
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = requests.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    content="",
                    provider=ProviderType.GROQ,
                    model=self.model,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            
            return LLMResponse(
                content=content,
                provider=ProviderType.GROQ,
                model=self.model,
                success=True,
                tokens_used=tokens,
                cost=0.0  # Groq бесплатный (пока)
            )
            
        except Exception as e:
            return LLMResponse(
                content="",
                provider=ProviderType.GROQ,
                model=self.model,
                success=False,
                error=str(e)
            )
    
    def get_provider_type(self) -> ProviderType:
        return ProviderType.GROQ


class LlamaCppProvider(LLMProvider):
    """
    Провайдер для llama.cpp server (OpenAI-совместимый API)
    
    Запуск сервера: ./server -m model.gguf --port 8080
    Или: llama-server -m model.gguf --port 8080
    """
    
    def __init__(
        self,
        model: str = "local-model",
        url: str = "http://localhost:8080/v1/chat/completions",
        timeout: int = 300
    ):
        self.url = url
        self.base_url = url.replace("/v1/chat/completions", "")
        super().__init__(model, timeout)
    
    def _check_availability(self) -> bool:
        """Проверяем доступность llama.cpp сервера"""
        try:
            # Пробуем health endpoint
            health_url = f"{self.base_url}/health"
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                self.available = True
                return True
            
            # Fallback: пробуем models endpoint
            models_url = f"{self.base_url}/v1/models"
            response = requests.get(models_url, timeout=5)
            self.available = response.status_code == 200
            return self.available
        except Exception:
            self.available = False
            return False
    
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_RESPONSE_TOKENS
    ) -> LLMResponse:
        """Генерация через llama.cpp server"""
        if not self.available:
            return LLMResponse(
                content="",
                provider=ProviderType.LLAMACPP,
                model=self.model,
                success=False,
                error="llama.cpp server not available"
            )
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = requests.post(
                self.url,
                headers={"Content-Type": "application/json"},
                json={
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    content="",
                    provider=ProviderType.LLAMACPP,
                    model=self.model,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            
            return LLMResponse(
                content=content,
                provider=ProviderType.LLAMACPP,
                model=self.model,
                success=True,
                tokens_used=tokens,
                cost=0.0  # Локальная модель — бесплатно
            )
            
        except Exception as e:
            return LLMResponse(
                content="",
                provider=ProviderType.LLAMACPP,
                model=self.model,
                success=False,
                error=str(e)
            )
    
    def get_provider_type(self) -> ProviderType:
        return ProviderType.LLAMACPP


class LMStudioProvider(LLMProvider):
    """
    Провайдер для LM Studio (OpenAI-совместимый локальный сервер)
    
    В LM Studio: Local Server → Start Server (порт 1234 по умолчанию)
    """
    
    def __init__(
        self,
        model: str = "local-model",
        url: str = "http://localhost:1234/v1/chat/completions",
        timeout: int = 300
    ):
        self.url = url
        self.base_url = url.replace("/v1/chat/completions", "")
        super().__init__(model, timeout)
    
    def _check_availability(self) -> bool:
        """Проверяем доступность LM Studio"""
        try:
            models_url = f"{self.base_url}/v1/models"
            response = requests.get(models_url, timeout=5)
            if response.status_code == 200:
                self.available = True
                # Пробуем получить имя модели
                data = response.json()
                if data.get("data"):
                    self.model = data["data"][0].get("id", self.model)
                return True
            self.available = False
            return False
        except Exception:
            self.available = False
            return False
    
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_RESPONSE_TOKENS
    ) -> LLMResponse:
        """Генерация через LM Studio"""
        if not self.available:
            return LLMResponse(
                content="",
                provider=ProviderType.LMSTUDIO,
                model=self.model,
                success=False,
                error="LM Studio server not available"
            )
        
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = requests.post(
                self.url,
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                    # Предотвращаем дублирование текста
                    "frequency_penalty": 0.3,  # Штраф за повторение токенов
                    "presence_penalty": 0.2,   # Штраф за повторение тем
                    "repeat_penalty": 1.1      # Общий штраф (если поддерживается)
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return LLMResponse(
                    content="",
                    provider=ProviderType.LMSTUDIO,
                    model=self.model,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            
            return LLMResponse(
                content=content,
                provider=ProviderType.LMSTUDIO,
                model=self.model,
                success=True,
                tokens_used=tokens,
                cost=0.0  # Локальная модель — бесплатно
            )
            
        except Exception as e:
            return LLMResponse(
                content="",
                provider=ProviderType.LMSTUDIO,
                model=self.model,
                success=False,
                error=str(e)
            )
    
    def get_provider_type(self) -> ProviderType:
        return ProviderType.LMSTUDIO


OLLAMA_DISABLED = _env_bool("NEIRA_DISABLE_OLLAMA", False)


def _build_default_providers() -> List[LLMProvider]:
    providers: List[LLMProvider] = []
    priority = _parse_provider_priority()
    ollama_disabled = _env_bool("NEIRA_DISABLE_OLLAMA", False)

    for provider_type in priority:
        if provider_type == ProviderType.OLLAMA:
            if ollama_disabled:
                continue
            model = os.getenv("NEIRA_OLLAMA_MODEL", "nemotron-mini")
            providers.append(OllamaProvider(model=model))
        elif provider_type == ProviderType.LMSTUDIO:
            url = os.getenv("NEIRA_LMSTUDIO_URL", "http://localhost:1234/v1/chat/completions")
            model = os.getenv("NEIRA_LMSTUDIO_MODEL", "local-model")
            providers.append(LMStudioProvider(model=model, url=url))
        elif provider_type == ProviderType.LLAMACPP:
            url = os.getenv("NEIRA_LLAMACPP_URL", "http://localhost:8080/v1/chat/completions")
            model = os.getenv("NEIRA_LLAMACPP_MODEL", "local-model")
            providers.append(LlamaCppProvider(model=model, url=url))
        elif provider_type == ProviderType.GROQ:
            model = os.getenv("NEIRA_GROQ_MODEL", "llama-3.1-8b-instant")
            providers.append(GroqProvider(model=model))
        elif provider_type == ProviderType.OPENAI:
            model = os.getenv("NEIRA_OPENAI_MODEL", "gpt-3.5-turbo")
            providers.append(OpenAIProvider(model=model))
        elif provider_type == ProviderType.CLAUDE:
            model = os.getenv("NEIRA_CLAUDE_MODEL", "claude-3-haiku-20240307")
            providers.append(ClaudeProvider(model=model))

    return providers


class LLMManager:
    """
    Менеджер LLM провайдеров с автоматическим fallback
    
    Приоритет локальных провайдеров:
    1. Ollama (самый популярный)
    2. LM Studio (удобный GUI)
    3. llama.cpp server (легковесный)
    4. Groq (бесплатно, быстро, облако)
    5. OpenAI, Claude (платные облачные)
    """
    
    def __init__(self, providers: Optional[List[LLMProvider]] = None):
        """
        Args:
            providers: Список провайдеров в порядке приоритета
        """
        if providers is None:
            self.providers = _build_default_providers()
        else:
            if OLLAMA_DISABLED:
                self.providers = [
                    p for p in providers
                    if p.get_provider_type() != ProviderType.OLLAMA
                ]
            else:
                self.providers = providers
        
        # Фильтруем только доступные провайдеры
        self.available_providers = [p for p in self.providers if p.available]
        
        logger.info(f"LLM Manager initialized with {len(self.available_providers)} available providers:")
        for p in self.available_providers:
            logger.info(f"  ✓ {p.get_provider_type().value}: {p.model}")
    
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_RESPONSE_TOKENS,
        preferred_provider: Optional[ProviderType] = None
    ) -> LLMResponse:
        """
        Генерация с автоматическим fallback
        
        Args:
            prompt: Запрос пользователя
            system_prompt: Системный промпт
            temperature: Температура генерации
            max_tokens: Максимум токенов
            preferred_provider: Предпочитаемый провайдер (если None, используется первый доступный)
        
        Returns:
            LLMResponse с результатом
        """
        if not self.available_providers:
            if OLLAMA_DISABLED:
                message = (
                    "Ни один LLM провайдер не доступен. Запусти LM Studio/llama.cpp "
                    "или добавь API ключи (OPENAI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY)."
                )
            else:
                message = (
                    "Ни один LLM провайдер не доступен. Настрой Ollama или добавь API ключи "
                    "(OPENAI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY)."
                )
            return LLMResponse(
                content=message,
                provider=ProviderType.OLLAMA,
                model="none",
                success=False,
                error="No providers available"
            )
        
        # Если указан предпочитаемый провайдер, пробуем его первым
        providers_to_try = self.available_providers.copy()
        if preferred_provider:
            # Сортируем: предпочитаемый провайдер первым
            providers_to_try.sort(
                key=lambda p: 0 if p.get_provider_type() == preferred_provider else 1
            )
        
        last_error = None
        
        for provider in providers_to_try:
            logger.info(f"Trying {provider.get_provider_type().value} ({provider.model})...")
            layer_prompt = _MODEL_LAYERS.get_active_prompt(provider.model) if _MODEL_LAYERS else None
            effective_system_prompt = _merge_system_prompt(system_prompt, layer_prompt)
            response = provider.generate(
                prompt=prompt,
                system_prompt=effective_system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if response.success:
                logger.info(f"✓ Success with {response.provider.value}")
                if response.cost:
                    logger.info(f"  Cost: ${response.cost:.4f}")
                return response
            else:
                logger.warning(f"✗ Failed with {provider.get_provider_type().value}: {response.error}")
                last_error = response.error
        
        # Все провайдеры не справились
        return LLMResponse(
            content="",
            provider=ProviderType.OLLAMA,
            model="none",
            success=False,
            error=f"All providers failed. Last error: {last_error}"
        )
    
    def get_embedding(self, text: str, preferred_provider: Optional[ProviderType] = None) -> Optional[List[float]]:
        """
        Получить эмбеддинг текста с автоматическим fallback.
        
        Args:
            text: Текст для векторизации
            preferred_provider: Предпочитаемый провайдер (по умолчанию Ollama)
        
        Returns:
            Вектор чисел или None при ошибке всех провайдеров
        """
        if not text or not text.strip():
            return None
        if LOCAL_EMBEDDINGS_AVAILABLE:
            try:
                local_embedding = get_local_embedding(text)
                if local_embedding:
                    logger.info("✓ Embedding from local")
                    return local_embedding
            except Exception as e:
                logger.warning(f"Local embedding error: {e}")
        if not self.available_providers:
            logger.warning("No providers available for embeddings")
            return None
        
        # Приоритет для embeddings: Ollama (бесплатно) → OpenAI (дешево)
        providers_order = self.available_providers.copy()
        if preferred_provider:
            providers_order.sort(
                key=lambda p: 0 if p.get_provider_type() == preferred_provider else 1
            )
        else:
            # По умолчанию сначала Ollama, потом OpenAI
            providers_order.sort(
                key=lambda p: 0 if p.get_provider_type() == ProviderType.OLLAMA else 
                             1 if p.get_provider_type() == ProviderType.OPENAI else 2
            )
        
        for provider in providers_order:
            try:
                embedding = provider.get_embedding(text)
                if embedding:
                    logger.info(f"✓ Embedding from {provider.get_provider_type().value}")
                    return embedding
            except Exception as e:
                logger.warning(f"Embedding failed with {provider.get_provider_type().value}: {e}")
                continue
        
        logger.warning("All providers failed to generate embedding")
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика провайдеров"""
        return {
            "total_providers": len(self.providers),
            "available_providers": len(self.available_providers),
            "providers": [
                {
                    "type": p.get_provider_type().value,
                    "model": p.model,
                    "available": p.available
                }
                for p in self.providers
            ]
        }


# === Convenience функции ===

def create_default_manager() -> LLMManager:
    """Создать менеджер с дефолтной конфигурацией"""
    return LLMManager()


def create_local_only_manager() -> LLMManager:
    """
    Менеджер только с локальными провайдерами (без облака)
    Полностью приватно, работает офлайн
    """
    return LLMManager([
        OllamaProvider(model="nemotron-mini"),
    ])


def create_fast_manager() -> LLMManager:
    """Менеджер для быстрых ответов (приоритет на скорость)"""
    return LLMManager([
        GroqProvider(model="llama-3.1-8b-instant"),
        LMStudioProvider(model="local-model"),
        OllamaProvider(model="ministral-3:3b"),
        OpenAIProvider(model="gpt-3.5-turbo")
    ])


def create_quality_manager() -> LLMManager:
    """Менеджер для качественных ответов (приоритет на качество)"""
    return LLMManager([
        ClaudeProvider(model="claude-3-5-sonnet-20241022"),
        OpenAIProvider(model="gpt-4"),
        GroqProvider(model="llama-3.1-70b-versatile"),
        OllamaProvider(model="qwen2.5-coder:7b")
    ])


def create_free_manager() -> LLMManager:
    """Менеджер только с бесплатными провайдерами"""
    return LLMManager([
        OllamaProvider(model="ministral-3:3b"),
        LMStudioProvider(model="local-model"),
        LlamaCppProvider(model="local-model"),
        GroqProvider(model="llama-3.1-8b-instant")
    ])


# === Тестирование ===
if __name__ == "__main__":
    print("=== LLM Providers Test ===\n")
    
    manager = create_default_manager()
    
    print(f"\nСтатус провайдеров:")
    stats = manager.get_stats()
    for p in stats["providers"]:
        status = "✓" if p["available"] else "✗"
        print(f"{status} {p['type']}: {p['model']}")
    
    print(f"\n\n=== Тест генерации ===")
    response = manager.generate(
        prompt="Привет! Представься кратко в одном предложении.",
        system_prompt="Ты - Нейра, живая программа."
    )
    
    if response.success:
        print(f"✓ Провайдер: {response.provider.value}")
        print(f"✓ Модель: {response.model}")
        print(f"✓ Ответ: {response.content}")
        if response.tokens_used:
            print(f"✓ Токенов: {response.tokens_used}")
        if response.cost:
            print(f"✓ Стоимость: ${response.cost:.4f}")
    else:
        print(f"✗ Ошибка: {response.error}")
