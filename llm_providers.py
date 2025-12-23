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
    from model_layers import ModelLayersRegistry

    _MODEL_LAYERS = ModelLayersRegistry("model_layers.json")
except Exception as exc:
    _MODEL_LAYERS = None
    logger.info("Слои моделей отключены: %s", exc)


class ProviderType(Enum):
    """Типы провайдеров"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    CLAUDE = "claude"
    GROQ = "groq"
    GEMINI = "gemini"


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
        max_tokens: int = 2048
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
        max_tokens: int = 2048
    ) -> LLMResponse:
        """Генерация через Ollama"""
        try:
            options: Dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
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
        max_tokens: int = 2048
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
        max_tokens: int = 2048
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
        max_tokens: int = 2048
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


class LLMManager:
    """
    Менеджер LLM провайдеров с автоматическим fallback
    
    Приоритет:
    1. Ollama (бесплатно, приватно) - для простых задач
    2. Groq (бесплатно, быстро) - для средних задач
    3. OpenAI GPT-3.5 (дешево) - для сложных задач
    4. Claude Haiku (дешево) - для очень сложных задач
    """
    
    def __init__(self, providers: Optional[List[LLMProvider]] = None):
        """
        Args:
            providers: Список провайдеров в порядке приоритета
        """
        if providers is None:
            # Дефолтная конфигурация - используем более мощные модели
            self.providers = [
                OllamaProvider(model="neira-cell-router:latest"),  # Fine-tuned модель
                GroqProvider(model="llama-3.1-8b-instant"),
                OpenAIProvider(model="gpt-3.5-turbo"),
                ClaudeProvider(model="claude-3-haiku-20240307")
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
        max_tokens: int = 2048,
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
            return LLMResponse(
                content="Ни один LLM провайдер не доступен. Настрой Ollama или добавь API ключи (OPENAI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY).",
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
            
            response = provider.generate(
                prompt=prompt,
                system_prompt=system_prompt,
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


def create_fast_manager() -> LLMManager:
    """Менеджер для быстрых ответов (приоритет на скорость)"""
    return LLMManager([
        GroqProvider(model="llama-3.1-8b-instant"),
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
