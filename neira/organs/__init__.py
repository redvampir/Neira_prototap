"""
Система органов Neira.

Органы — это специализированные модули которые Neira может:
- Создавать самостоятельно
- Тестировать в sandbox
- Обучать на feedback

Компоненты:
- unified: Унифицированная система органов
- executable: Исполняемые органы с обучением
- creation: Движок создания органов
"""

# Ленивый импорт
def __getattr__(name):
    if name == "UnifiedOrganSystem":
        from unified_organ_system import UnifiedOrganSystem
        return UnifiedOrganSystem
    elif name == "get_organ_system":
        from unified_organ_system import get_organ_system
        return get_organ_system
    elif name == "ExecutableOrgan":
        from executable_organs import ExecutableOrgan
        return ExecutableOrgan
    elif name == "get_organ_registry":
        from executable_organs import get_organ_registry
        return get_organ_registry
    elif name == "OrganCreationEngine":
        from organ_creation_engine import OrganCreationEngine
        return OrganCreationEngine
    raise AttributeError(f"module 'neira.organs' has no attribute '{name}'")

__all__ = [
    "UnifiedOrganSystem",
    "get_organ_system",
    "ExecutableOrgan",
    "get_organ_registry",
    "OrganCreationEngine",
]
