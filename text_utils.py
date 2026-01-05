"""
Утилиты для обработки текста.

DEPRECATED: Используйте neira.utils.text
Этот файл оставлен для обратной совместимости.
"""

# Реэкспорт из нового пакета
from neira.utils.text import (
    remove_duplicate_paragraphs,
    truncate_text,
    normalize_whitespace,
    extract_code_blocks,
    smart_split,
)

__all__ = [
    "remove_duplicate_paragraphs",
    "truncate_text",
    "normalize_whitespace",
    "extract_code_blocks",
    "smart_split",
]
