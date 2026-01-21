"""
Утилиты для обработки текста.
Общие функции используемые в разных модулях.
"""

import re
from typing import List, Tuple


_AMBIGUOUS_ABBREVIATIONS: dict[str, tuple[str, ...]] = {
    "КП": (
        "Коммерческое предложение",
        "Контент-план",
        "Календарный план",
    ),
}


def find_ambiguous_abbreviation(text: str) -> tuple[str, tuple[str, ...]] | None:
    """
    Ищет в тексте неоднозначную аббревиатуру, по которой лучше задать уточняющий вопрос.

    Сейчас поддерживает минимальный кейс из реальной переписки: «КП».

    Args:
        text: Текст пользователя.

    Returns:
        Кортеж (аббревиатура, варианты расшифровки) или None.
    """
    if not text:
        return None

    text_lower = text.lower()

    for abbreviation, options in _AMBIGUOUS_ABBREVIATIONS.items():
        # Уже уточнено человеком: "коммерческое предложение (КП)" и т.п.
        if "коммерческ" in text_lower or "контент" in text_lower or "календар" in text_lower:
            continue

        if re.search(rf"(?i)\b{re.escape(abbreviation)}\b", text):
            return abbreviation, options

    return None


def build_abbreviation_clarification_question(abbreviation: str, options: tuple[str, ...]) -> str:
    """
    Собирает короткий уточняющий вопрос по аббревиатуре.

    Args:
        abbreviation: Аббревиатура (например, "КП").
        options: Варианты расшифровки.

    Returns:
        Текст вопроса (plain text, без Markdown).
    """
    lines = [f"Уточни, пожалуйста: что ты имеешь в виду под «{abbreviation}»?"]
    for idx, option in enumerate(options, start=1):
        lines.append(f"{idx}) {option}")
    lines.append("Ответь цифрой (1/2/3) или словами.")
    return "\n".join(lines)


def parse_abbreviation_choice(reply_text: str, options: tuple[str, ...]) -> str | None:
    """
    Пытается понять выбор пользователя в ответ на уточняющий вопрос.

    Args:
        reply_text: Ответ пользователя (например, "1" или "коммерческое предложение").
        options: Варианты расшифровки.

    Returns:
        Выбранная расшифровка или None.
    """
    if not reply_text:
        return None

    normalized = reply_text.strip().lower()
    if not normalized:
        return None

    if normalized.isdigit():
        try:
            index = int(normalized) - 1
        except ValueError:
            return None
        if 0 <= index < len(options):
            return options[index]
        return None

    # Быстрый парсинг по ключевым словам (чтобы не требовать ровного совпадения)
    if "коммерчес" in normalized:
        return options[0] if len(options) >= 1 else None
    if "контент" in normalized:
        return options[1] if len(options) >= 2 else None
    if "календар" in normalized:
        return options[2] if len(options) >= 3 else None

    # Попытка точного совпадения с вариантом (без учёта регистра)
    for option in options:
        if normalized == option.lower():
            return option

    return None


def apply_abbreviation_expansion(text: str, abbreviation: str, expansion: str) -> str:
    """
    Подставляет расшифровку аббревиатуры прямо в текст запроса.

    Пример: "как составить КП?" -> "как составить коммерческое предложение (КП)?"

    Args:
        text: Исходный текст.
        abbreviation: Аббревиатура, которую расширяем.
        expansion: Расшифровка.

    Returns:
        Текст с подстановкой.
    """
    if not text:
        return text

    replacement = f"{expansion} ({abbreviation})"
    return re.sub(rf"(?i)\b{re.escape(abbreviation)}\b", replacement, text)


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
