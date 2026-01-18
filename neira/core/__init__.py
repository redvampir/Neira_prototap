"""
Ядро Neira.

Основные компоненты системы:
- cells: Базовые клетки (память, анализ, планирование)
- memory: Система памяти
- llm: LLM провайдеры
"""

# Ленивый импорт для ускорения загрузки
def __getattr__(name):
    if name == "Cell":
        from cells import Cell
        return Cell
    elif name == "MemoryCell":
        from cells import MemoryCell
        return MemoryCell
    elif name == "AnalyzerCell":
        from cells import AnalyzerCell
        return AnalyzerCell
    elif name == "MemorySystem":
        from memory_system import MemorySystem
        return MemorySystem
    elif name == "LLMManager":
        from llm_providers import LLMManager
        return LLMManager
    elif name == "ExperienceSystem":
        from neira.core.experience import ExperienceSystem
        return ExperienceSystem
    elif name == "get_local_embedding":
        from neira.core.embeddings import get_local_embedding
        return get_local_embedding
    elif name == "LLMClient":
        from neira.core.llm_adapter import LLMClient
        return LLMClient
    elif name == "LLMResult":
        from neira.core.llm_adapter import LLMResult
        return LLMResult
    elif name == "build_default_llm_client":
        from neira.core.llm_adapter import build_default_llm_client
        return build_default_llm_client
    raise AttributeError(f"module 'neira.core' has no attribute '{name}'")

__all__ = [
    "Cell",
    "MemoryCell", 
    "AnalyzerCell",
    "MemorySystem",
    "LLMManager",
    "ExperienceSystem",
    "get_local_embedding",
    "LLMClient",
    "LLMResult",
    "build_default_llm_client",
]
