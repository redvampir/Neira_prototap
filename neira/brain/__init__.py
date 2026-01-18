"""
Когнитивные системы Neira.

Компоненты:
- cortex: Автономная когнитивная система (Neira Cortex)
- thinking: Параллельное мышление
- context: Управление контекстом
"""

# Ленивый импорт
def __getattr__(name):
    if name == "NeiraCortex":
        from neira_cortex import NeiraCortex
        return NeiraCortex
    elif name == "IntentType":
        from neira_cortex import IntentType
        return IntentType
    elif name == "ParallelMind":
        from parallel_thinking import ParallelMind
        return ParallelMind
    elif name == "parallel_mind":
        from parallel_thinking import parallel_mind
        return parallel_mind
    elif name == "get_brain_store":
        from neira.brain.store import get_brain_store
        return get_brain_store
    raise AttributeError(f"module 'neira.brain' has no attribute '{name}'")

__all__ = [
    "NeiraCortex",
    "IntentType",
    "ParallelMind",
    "parallel_mind",
    "get_brain_store",
]
