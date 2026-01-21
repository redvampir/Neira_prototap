"""
Цель: Пространство для органов и утилит ТКП.
Инварианты: Только логика ТКП, без изменений ядра.
Риски: Неполные шаблоны → ручное уточнение.
Проверка: python -m py_compile neira/organs/tkp/__init__.py
"""

from neira.organs.tkp.generator import generate_tkp_document, TkpGenerationError

__all__ = ["generate_tkp_document", "TkpGenerationError"]
