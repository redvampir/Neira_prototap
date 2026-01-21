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
    find_ambiguous_abbreviation,
    build_abbreviation_clarification_question,
    parse_abbreviation_choice,
    apply_abbreviation_expansion,
)

__all__ = [
    "remove_duplicate_paragraphs",
    "truncate_text",
    "normalize_whitespace",
    "extract_code_blocks",
    "smart_split",
    "find_ambiguous_abbreviation",
    "build_abbreviation_clarification_question",
    "parse_abbreviation_choice",
    "apply_abbreviation_expansion",
]
