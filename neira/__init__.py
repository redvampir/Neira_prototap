"""
Neira - Автономная Эволюционирующая Программа

Структура пакетов:
- neira.utils     - Утилиты (text_utils, rate_limiter, identity)
- neira.core      - Ядро (cells, memory, llm_providers)
- neira.brain     - Когнитивные системы (cortex, parallel_thinking)
- neira.organs    - Система органов

Для обратной совместимости модули также доступны из корня проекта.
"""

__version__ = "0.8.4"
__author__ = "Pavel & Claude"

# Подпакеты доступны напрямую
from neira import utils
from neira import core
from neira import brain
from neira import organs

__all__ = ["utils", "core", "brain", "organs", "__version__", "__author__"]
