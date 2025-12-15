"""
Конфигурация Neira v1.0 — Настройки LLM провайдеров и приоритетов
"""

import os
from typing import List, Optional
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()


class NeiraConfig:
    """Центральная конфигурация Neira"""
    
    # === API КЛЮЧИ ===
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    
    # === TELEGRAM ===
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    NEIRA_ADMIN_PASSWORD: str = os.getenv("NEIRA_ADMIN_PASSWORD", "change_me_please")
    
    # === ПРИОРИТЕТ ПРОВАЙДЕРОВ ===
    # По умолчанию: ollama (бесплатно) → groq (быстро) → openai (качество) → claude (лучшее качество)
    PROVIDER_PRIORITY: List[str] = os.getenv(
        "LLM_PROVIDER_PRIORITY",
        "ollama,groq,openai,claude"
    ).split(",")
    
    # === МОДЕЛИ ПО ЗАДАЧАМ ===
    # Для кода
    CODE_MODEL_OLLAMA: str = os.getenv("LLM_CODE_MODEL_OLLAMA", "qwen2.5-coder:7b")
    CODE_MODEL_CLOUD: str = os.getenv("LLM_CODE_MODEL_CLOUD", "gpt-4")
    
    # Для рассуждений
    REASON_MODEL_OLLAMA: str = os.getenv("LLM_REASON_MODEL_OLLAMA", "ministral-3:3b")
    REASON_MODEL_CLOUD: str = os.getenv("LLM_REASON_MODEL_CLOUD", "claude-3-haiku-20240307")
    
    # Для личности/диалогов
    PERSONALITY_MODEL_OLLAMA: str = os.getenv("LLM_PERSONALITY_MODEL_OLLAMA", "ministral-3:3b")
    PERSONALITY_MODEL_CLOUD: str = os.getenv("LLM_PERSONALITY_MODEL_CLOUD", "claude-3-5-sonnet-20241022")
    
    # === GROQ МОДЕЛИ (бесплатные) ===
    GROQ_FAST_MODEL: str = "llama-3.1-8b-instant"       # Очень быстрая
    GROQ_QUALITY_MODEL: str = "llama-3.1-70b-versatile" # Качественная
    GROQ_CODE_MODEL: str = "llama-3.3-70b-versatile"    # Для кода
    
    # === СТРАТЕГИИ ИСПОЛЬЗОВАНИЯ ===
    # Когда переключаться на облачные модели
    USE_CLOUD_IF_OLLAMA_FAILS: bool = os.getenv("USE_CLOUD_IF_OLLAMA_FAILS", "true").lower() == "true"
    USE_CLOUD_IF_COMPLEXITY: int = int(os.getenv("USE_CLOUD_IF_COMPLEXITY", "4"))  # сложность > 4
    USE_CLOUD_IF_RETRIES: int = int(os.getenv("USE_CLOUD_IF_RETRIES", "2"))  # после 2 попыток
    
    # === ЛИМИТЫ И ТАЙМАУТЫ ===
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "180"))
    CLOUD_TIMEOUT: int = int(os.getenv("CLOUD_TIMEOUT", "60"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))
    MIN_ACCEPTABLE_SCORE: int = int(os.getenv("MIN_ACCEPTABLE_SCORE", "7"))
    
    # === РЕЖИМЫ РАБОТЫ ===
    # "free" - только бесплатные провайдеры (ollama + groq)
    # "balanced" - баланс цены и качества (ollama + groq + gpt-3.5)
    # "quality" - максимальное качество (claude + gpt-4)
    MODE: str = os.getenv("NEIRA_MODE", "balanced")
    
    @classmethod
    def get_provider_config(cls, mode: Optional[str] = None) -> dict:
        """Получить конфигурацию провайдеров для выбранного режима"""
        mode = mode or cls.MODE
        
        if mode == "free":
            return {
                "providers": ["ollama", "groq"],
                "models": {
                    "code": cls.CODE_MODEL_OLLAMA,
                    "reason": cls.REASON_MODEL_OLLAMA,
                    "personality": cls.PERSONALITY_MODEL_OLLAMA
                }
            }
        
        elif mode == "balanced":
            return {
                "providers": ["ollama", "groq", "openai"],
                "models": {
                    "code": cls.CODE_MODEL_OLLAMA,
                    "reason": cls.REASON_MODEL_OLLAMA,
                    "personality": "gpt-3.5-turbo",
                    "cloud_fallback": "gpt-3.5-turbo"
                }
            }
        
        elif mode == "quality":
            return {
                "providers": ["claude", "openai", "groq", "ollama"],
                "models": {
                    "code": cls.CODE_MODEL_CLOUD,
                    "reason": cls.REASON_MODEL_CLOUD,
                    "personality": cls.PERSONALITY_MODEL_CLOUD
                }
            }
        
        else:
            # Custom mode - используем приоритет из .env
            return {
                "providers": cls.PROVIDER_PRIORITY,
                "models": {
                    "code": cls.CODE_MODEL_OLLAMA,
                    "reason": cls.REASON_MODEL_OLLAMA,
                    "personality": cls.PERSONALITY_MODEL_OLLAMA
                }
            }
    
    @classmethod
    def validate_config(cls) -> dict:
        """Проверить конфигурацию и вернуть статус"""
        status = {
            "ollama_available": True,  # Всегда доступен локально
            "groq_available": bool(cls.GROQ_API_KEY),
            "openai_available": bool(cls.OPENAI_API_KEY),
            "claude_available": bool(cls.ANTHROPIC_API_KEY),
            "gemini_available": bool(cls.GEMINI_API_KEY),
            "telegram_configured": bool(cls.TELEGRAM_BOT_TOKEN),
            "admin_password_changed": cls.NEIRA_ADMIN_PASSWORD != "change_me_please"
        }
        
        return status
    
    @classmethod
    def print_config(cls):
        """Вывести текущую конфигурацию"""
        status = cls.validate_config()
        
        print("=" * 50)
        print("🧠 NEIRA CONFIGURATION")
        print("=" * 50)
        print(f"\n📋 Режим: {cls.MODE.upper()}")
        print(f"\n🔑 API Keys:")
        print(f"  {'✓' if status['groq_available'] else '✗'} Groq")
        print(f"  {'✓' if status['openai_available'] else '✗'} OpenAI")
        print(f"  {'✓' if status['claude_available'] else '✗'} Claude (Anthropic)")
        print(f"  {'✓' if status['gemini_available'] else '✗'} Gemini")
        
        print(f"\n🎯 Приоритет провайдеров: {' → '.join(cls.PROVIDER_PRIORITY)}")
        
        config = cls.get_provider_config()
        print(f"\n🤖 Модели:")
        for task, model in config.get("models", {}).items():
            print(f"  {task}: {model}")
        
        print(f"\n⚙️ Настройки:")
        print(f"  Ollama timeout: {cls.OLLAMA_TIMEOUT}s")
        print(f"  Cloud timeout: {cls.CLOUD_TIMEOUT}s")
        print(f"  Max retries: {cls.MAX_RETRIES}")
        print(f"  Min score: {cls.MIN_ACCEPTABLE_SCORE}/10")
        
        if not status['admin_password_changed']:
            print(f"\n⚠️  ВНИМАНИЕ: Смени пароль администратора в .env!")
        
        print("=" * 50)


# Экспортируем для удобства
config = NeiraConfig

if __name__ == "__main__":
    config.print_config()
