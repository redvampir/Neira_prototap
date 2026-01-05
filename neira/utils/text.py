"""
Утилиты для обработки текста.
Общие функции используемые в разных модулях.
"""

import re
from typing import List, Tuple


def remove_duplicate_paragraphs(text: str) -> str:
    """
    Удаляет дублирующиеся абзацы из текста.
    LLM иногда повторяет один и тот же ответ 2+ раза.
    
    Args:
        text: Исходный текст
    
    Returns:
        Текст без дублирующихся абзацев
    """
    if not text:
        return text
    
    # Разбиваем на абзацы
    paragraphs = text.split('\n\n')
    
    # Удаляем дубли, сохраняя порядок
    seen: set[str] = set()
    unique: List[str] = []
    for p in paragraphs:
        p_clean = p.strip()
        if p_clean and p_clean not in seen:
            seen.add(p_clean)
            unique.append(p)
    
    result = '\n\n'.join(unique)
    
    # Дополнительная проверка: если текст повторяется подряд
    half_len = len(result) // 2
    if half_len > 50:  # Минимальная длина для проверки
        first_half = result[:half_len].strip()
        second_half = result[half_len:].strip()
        # Если вторая половина начинается так же как первая
        if second_half.startswith(first_half[:min(100, len(first_half))]):
            return first_half
    
    return result


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    Обрезает текст до указанной длины.
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        suffix: Суффикс для обрезанного текста
    
    Returns:
        Обрезанный текст
    """
    if not text or len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def normalize_whitespace(text: str) -> str:
    """
    Нормализует пробелы в тексте.
    
    - Убирает лишние пробелы
    - Убирает пробелы в начале/конце
    - Заменяет множественные переносы на двойные
    
    Args:
        text: Исходный текст
    
    Returns:
        Нормализованный текст
    """
    if not text:
        return text
    
    # Убираем пробелы в начале/конце строк
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Заменяем 3+ переноса на 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Убираем пробелы в начале/конце
    return text.strip()


def extract_code_blocks(text: str) -> List[Tuple[str, str]]:
    """
    Извлекает блоки кода из Markdown текста.
    
    Args:
        text: Текст с markdown блоками кода
    
    Returns:
        Список кортежей (язык, код)
    """
    pattern = r'```(\w*)\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    return [(lang or 'text', code.strip()) for lang, code in matches]


def smart_split(text: str, max_chunk: int = 4000) -> List[str]:
    """
    Умно разбивает текст на части, сохраняя целостность предложений.
    
    Args:
        text: Исходный текст
        max_chunk: Максимальный размер части
    
    Returns:
        Список частей текста
    """
    if not text or len(text) <= max_chunk:
        return [text] if text else []
    
    chunks = []
    current = ""
    
    # Разбиваем по предложениям
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chunk:
            current += (" " if current else "") + sentence
        else:
            if current:
                chunks.append(current)
            current = sentence
    
    if current:
        chunks.append(current)
    
    return chunks
