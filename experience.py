"""
Experience System — Система опыта Neira.

DEPRECATED: Используйте neira.core.experience
Этот файл оставлен для обратной совместимости.
"""

# Реэкспорт из нового пакета
from neira.core.experience import (
    ExperienceEntry,
    ExperienceSystem,
)

__all__ = [
    "ExperienceEntry",
    "ExperienceSystem",
]
