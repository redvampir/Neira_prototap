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
    raise AttributeError(f"module 'neira.brain' has no attribute '{name}'")

__all__ = [
    "NeiraCortex",
    "IntentType",
    "ParallelMind",
    "parallel_mind",
]
