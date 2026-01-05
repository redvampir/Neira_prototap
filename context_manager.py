"""
Neira Context Window Management System
======================================

Умное управление контекстным окном для LLM.
Оптимизация и сжатие контекста для эффективной работы с большими кодовыми базами.

Возможности:
- Подсчёт токенов (приблизительный и точный)
- Приоритезация контекста по релевантности
- Сжатие и суммаризация длинных фрагментов
- Скользящее окно для истории чата
- Умное включение/исключение файлов

Автор: Pavel & Neira
Версия: 1.0.0
"""

import re
import json
import hashlib
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


def _env_int(name: str, default: int, min_value: int = 1, max_value: Optional[int] = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    if value < min_value:
        return min_value
    if max_value is not None and value > max_value:
        return max_value
    return value


def _clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, value))


DEFAULT_CONTEXT_MAX_TOKENS = _env_int("NEIRA_CONTEXT_MAX_TOKENS", 8000, min_value=1024)
DEFAULT_MAX_RESPONSE_TOKENS = _env_int("NEIRA_MAX_RESPONSE_TOKENS", 2000, min_value=128)
DEFAULT_CONTEXT_RESERVED_TOKENS = _env_int(
    "NEIRA_CONTEXT_RESERVED_TOKENS",
    max(512, DEFAULT_MAX_RESPONSE_TOKENS),
    min_value=128,
)


class ContextPriority(Enum):
    """Приоритет контекста"""
    CRITICAL = 1     # Текущий файл, выделенный код
    HIGH = 2         # Связанные файлы, определения
    MEDIUM = 3       # Импорты, история чата
    LOW = 4          # Общий контекст, документация
    OPTIONAL = 5     # Дополнительная информация


@dataclass
class ContextChunk:
    """Фрагмент контекста"""
    content: str
    source: str                    # Источник: file, chat, system, tool
    priority: ContextPriority
    tokens: int = 0                # Оценка токенов
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.tokens == 0:
            self.tokens = estimate_tokens(self.content)


@dataclass
class ContextWindow:
    """Контекстное окно для LLM"""
    chunks: List[ContextChunk] = field(default_factory=list)
    max_tokens: int = DEFAULT_CONTEXT_MAX_TOKENS         # Максимум токенов
    reserved_for_response: int = DEFAULT_CONTEXT_RESERVED_TOKENS  # Резерв для ответа
    
    @property
    def total_tokens(self) -> int:
        return sum(chunk.tokens for chunk in self.chunks)
    
    @property
    def available_tokens(self) -> int:
        return max(self.max_tokens - self.reserved_for_response - self.total_tokens, 0)
    
    def add(self, chunk: ContextChunk) -> bool:
        """Добавить chunk если есть место"""
        if chunk.tokens <= self.available_tokens:
            self.chunks.append(chunk)
            return True
        return False
    
    def build_prompt(self) -> str:
        """Собрать финальный промпт"""
        # Сортируем по приоритету
        sorted_chunks = sorted(self.chunks, key=lambda c: c.priority.value)
        
        parts = []
        for chunk in sorted_chunks:
            if chunk.source == 'system':
                parts.append(chunk.content)
            elif chunk.source == 'file':
                file_path = chunk.metadata.get('file_path', 'unknown')
                parts.append(f"```{file_path}\n{chunk.content}\n```")
            elif chunk.source == 'chat':
                role = chunk.metadata.get('role', 'user')
                parts.append(f"{role}: {chunk.content}")
            else:
                parts.append(chunk.content)
        
        return "\n\n".join(parts)


# ==================== ПОДСЧЁТ ТОКЕНОВ ====================

def estimate_tokens(text: str) -> int:
    """
    Быстрая оценка количества токенов.
    Использует эвристику: ~4 символа = 1 токен для английского,
    ~2 символа = 1 токен для кода/русского.
    """
    if not text:
        return 0
    
    # Считаем слова и специальные символы
    words = len(re.findall(r'\w+', text))
    special_chars = len(re.findall(r'[^\w\s]', text))
    newlines = text.count('\n')
    
    # Кириллица считается как ~2 символа на токен
    cyrillic = len(re.findall(r'[а-яА-ЯёЁ]', text))
    latin = len(re.findall(r'[a-zA-Z]', text))
    
    # Эвристика
    base_tokens = words + special_chars + newlines
    
    # Корректировка для разных типов контента
    if cyrillic > latin:
        # Больше русского текста
        return int(base_tokens * 1.2)
    else:
        return base_tokens


def count_tokens_precise(text: str, model: str = "gpt-3.5") -> int:
    """
    Более точный подсчёт токенов.
    Использует tiktoken если доступен.
    """
    try:
        import tiktoken
        
        # Выбираем энкодер по модели
        if "gpt-4" in model or "gpt-3.5" in model:
            encoding = tiktoken.get_encoding("cl100k_base")
        else:
            encoding = tiktoken.get_encoding("p50k_base")
        
        return len(encoding.encode(text))
    except ImportError:
        # Fallback на эвристику
        return estimate_tokens(text)


# ==================== СЖАТИЕ КОНТЕКСТА ====================

class ContextCompressor:
    """Сжатие контекста для экономии токенов"""
    
    @staticmethod
    def compress_code(code: str, max_lines: int = 50) -> str:
        """Сжать код, сохраняя важные части"""
        lines = code.split('\n')
        
        if len(lines) <= max_lines:
            return code
        
        result = []
        important_patterns = [
            r'^(def |async def |class |import |from )',  # Определения
            r'^\s*(return |raise |yield )',              # Ключевые операторы
            r'^\s*#.*TODO|FIXME|BUG|HACK',              # Важные комментарии
            r'@\w+',                                     # Декораторы
        ]
        
        in_important_block = False
        block_lines = 0
        
        for i, line in enumerate(lines):
            is_important = any(re.match(p, line) for p in important_patterns)
            
            if is_important:
                in_important_block = True
                block_lines = 0
                result.append(line)
            elif in_important_block:
                result.append(line)
                block_lines += 1
                
                # Конец важного блока после 10 строк или пустой строки
                if block_lines > 10 or not line.strip():
                    in_important_block = False
                    if len(result) < max_lines:
                        result.append(f"    # ... [{len(lines) - i - 1} more lines]")
            elif len(result) < max_lines // 3:
                # Добавляем начало файла
                result.append(line)
        
        return '\n'.join(result)
    
    @staticmethod
    def compress_chat_history(
        messages: List[Dict[str, str]], 
        max_messages: int = 10,
        max_tokens: int = 2000
    ) -> List[Dict[str, str]]:
        """Сжать историю чата, сохраняя важные сообщения"""
        if len(messages) <= max_messages:
            return messages
        
        result = []
        total_tokens = 0
        
        # Всегда сохраняем системный промпт
        for msg in messages:
            if msg.get('role') == 'system':
                result.append(msg)
                total_tokens += estimate_tokens(msg.get('content', ''))
        
        # Добавляем последние сообщения
        recent = [m for m in messages if m.get('role') != 'system'][-max_messages:]
        
        for msg in recent:
            tokens = estimate_tokens(msg.get('content', ''))
            if total_tokens + tokens <= max_tokens:
                result.append(msg)
                total_tokens += tokens
            else:
                # Сжимаем длинные сообщения
                compressed = ContextCompressor.summarize_text(
                    msg.get('content', ''),
                    max_tokens=max_tokens - total_tokens
                )
                result.append({
                    'role': msg.get('role'),
                    'content': compressed
                })
                break
        
        return result
    
    @staticmethod
    def summarize_text(text: str, max_tokens: int = 200) -> str:
        """Суммаризация текста до указанного лимита токенов"""
        current_tokens = estimate_tokens(text)
        
        if current_tokens <= max_tokens:
            return text
        
        # Простая суммаризация: берём начало и конец
        lines = text.split('\n')
        
        if len(lines) > 10:
            # Берём первые и последние строки
            start_lines = lines[:5]
            end_lines = lines[-3:]
            
            return '\n'.join(start_lines) + f'\n\n[... {len(lines) - 8} lines omitted ...]\n\n' + '\n'.join(end_lines)
        else:
            # Просто обрезаем
            ratio = max_tokens / current_tokens
            cut_point = int(len(text) * ratio * 0.8)  # 80% от расчётного
            return text[:cut_point] + '\n... [truncated]'


# ==================== МЕНЕДЖЕР КОНТЕКСТА ====================

class ContextManager:
    """
    Умный менеджер контекста для Neira.
    Управляет сборкой и оптимизацией контекста для LLM.
    """
    
    def __init__(
        self,
        max_tokens: int = DEFAULT_CONTEXT_MAX_TOKENS,
        model: str = "llama3",
        reserved_for_response: Optional[int] = None
    ):
        self.max_tokens = max(max_tokens, 1024)
        self.model = model
        self.compressor = ContextCompressor()
        fallback_reserved = DEFAULT_CONTEXT_RESERVED_TOKENS if reserved_for_response is None else reserved_for_response
        self.reserved_for_response = _clamp(fallback_reserved, 128, max(self.max_tokens - 256, 128))
        
        # Кэш для избежания повторной обработки
        self._cache: Dict[str, Tuple[str, int]] = {}

    def _context_limits(self) -> Dict[str, int]:
        available = max(self.max_tokens - self.reserved_for_response, 0)
        code_soft_limit = max(int(available * 0.35), min(1500, available))
        tool_soft_limit = max(int(available * 0.08), min(400, available))
        tool_summary_limit = max(int(available * 0.06), min(320, available))
        history_max_tokens = max(int(available * 0.25), min(1500, available))
        history_max_messages = _clamp(int(available / 800) if available else 6, 6, 20)
        code_max_lines = _clamp(int(code_soft_limit / 25) if code_soft_limit else 20, 20, 400)

        return {
            "code_soft_limit": code_soft_limit,
            "code_max_lines": code_max_lines,
            "tool_soft_limit": tool_soft_limit,
            "tool_summary_limit": tool_summary_limit,
            "history_max_tokens": history_max_tokens,
            "history_max_messages": history_max_messages,
        }
    
    def build_context(
        self,
        user_query: str,
        current_file: Optional[str] = None,
        current_code: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        related_files: Optional[List[str]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None
    ) -> ContextWindow:
        """
        Собрать оптимальный контекст для запроса.
        
        Args:
            user_query: Запрос пользователя
            current_file: Путь к текущему файлу
            current_code: Код из текущего файла/выделение
            chat_history: История чата
            related_files: Связанные файлы для контекста
            tool_results: Результаты выполнения инструментов
            system_prompt: Системный промпт
            
        Returns:
            ContextWindow с оптимизированным контекстом
        """
        window = ContextWindow(
            max_tokens=self.max_tokens,
            reserved_for_response=self.reserved_for_response
        )

        limits = self._context_limits()
        
        # 1. Системный промпт (CRITICAL)
        if system_prompt:
            window.add(ContextChunk(
                content=system_prompt,
                source='system',
                priority=ContextPriority.CRITICAL
            ))
        
        # 2. Текущий код (CRITICAL)
        if current_code:
            code_chunk = ContextChunk(
                content=current_code,
                source='file',
                priority=ContextPriority.CRITICAL,
                metadata={'file_path': current_file or 'selection'}
            )
            
            # Сжимаем если слишком большой
            if code_chunk.tokens > limits["code_soft_limit"]:
                code_chunk.content = self.compressor.compress_code(
                    current_code, 
                    max_lines=limits["code_max_lines"]
                )
                code_chunk.tokens = estimate_tokens(code_chunk.content)
            
            window.add(code_chunk)
        
        # 3. Запрос пользователя (CRITICAL)
        window.add(ContextChunk(
            content=user_query,
            source='chat',
            priority=ContextPriority.CRITICAL,
            metadata={'role': 'user'}
        ))
        
        # 4. Результаты инструментов (HIGH)
        if tool_results:
            for result in tool_results:
                tool_content = json.dumps(result, ensure_ascii=False, indent=2)
                
                # Сжимаем большие результаты
                if estimate_tokens(tool_content) > limits["tool_soft_limit"]:
                    tool_content = self.compressor.summarize_text(
                        tool_content, 
                        max_tokens=limits["tool_summary_limit"]
                    )
                
                if not window.add(ContextChunk(
                    content=f"Tool result:\n{tool_content}",
                    source='tool',
                    priority=ContextPriority.HIGH,
                    metadata={'tool': result.get('tool', 'unknown')}
                )):
                    break  # Больше нет места
        
        # 5. История чата (MEDIUM)
        if chat_history:
            compressed_history = self.compressor.compress_chat_history(
                chat_history,
                max_messages=limits["history_max_messages"],
                max_tokens=limits["history_max_tokens"]
            )
            
            for msg in compressed_history:
                if msg.get('role') == 'system':
                    continue  # Системный уже добавлен
                
                if not window.add(ContextChunk(
                    content=msg.get('content', ''),
                    source='chat',
                    priority=ContextPriority.MEDIUM,
                    metadata={'role': msg.get('role')}
                )):
                    break
        
        # 6. Связанные файлы (LOW)
        if related_files:
            for file_path in related_files:
                try:
                    content = Path(file_path).read_text(encoding='utf-8')
                    
                    # Сжимаем файлы
                    compressed = self.compressor.compress_code(
                        content, 
                        max_lines=30
                    )
                    
                    if not window.add(ContextChunk(
                        content=compressed,
                        source='file',
                        priority=ContextPriority.LOW,
                        metadata={'file_path': file_path}
                    )):
                        break
                except Exception:
                    continue
        
        return window
    
    def optimize_for_completion(
        self,
        code_before: str,
        code_after: str,
        file_path: str,
        language: str = "python"
    ) -> str:
        """
        Оптимизировать контекст для автодополнения.
        Минимальный контекст для быстрого ответа.
        """
        # Для completion берём только ближайший контекст
        lines_before = code_before.split('\n')
        lines_after = code_after.split('\n')
        
        # Берём последние 30 строк до курсора
        relevant_before = '\n'.join(lines_before[-30:])
        
        # И первые 10 строк после
        relevant_after = '\n'.join(lines_after[:10])
        
        return f"""```{language}
{relevant_before}
<|cursor|>
{relevant_after}
```"""
    
    def get_relevant_imports(self, code: str, language: str = "python") -> List[str]:
        """Извлечь релевантные импорты из кода"""
        imports = []
        
        if language == "python":
            # Python imports
            for match in re.finditer(r'^(?:from\s+(\S+)\s+)?import\s+(.+)$', code, re.MULTILINE):
                module = match.group(1) or match.group(2).split(',')[0].strip()
                imports.append(module)
        
        elif language in ("javascript", "typescript"):
            # JS/TS imports
            for match in re.finditer(r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]", code):
                imports.append(match.group(1))
        
        return list(set(imports))


# ==================== SLIDING WINDOW ====================

class SlidingWindowManager:
    """
    Управление скользящим окном для длинных диалогов.
    Сохраняет важные сообщения и суммаризирует старые.
    """
    
    def __init__(
        self,
        max_messages: int = 20,
        summary_threshold: int = 15
    ):
        self.max_messages = max_messages
        self.summary_threshold = summary_threshold
        self.messages: List[Dict[str, str]] = []
        self.summaries: List[str] = []
    
    def add_message(self, role: str, content: str) -> None:
        """Добавить сообщение в окно"""
        self.messages.append({
            'role': role,
            'content': content,
            'timestamp': import_time()
        })
        
        # Проверяем нужна ли суммаризация
        if len(self.messages) > self.summary_threshold:
            self._summarize_old_messages()
    
    def _summarize_old_messages(self) -> None:
        """Суммаризировать старые сообщения"""
        # Берём первые N сообщений для суммаризации
        to_summarize = self.messages[:self.summary_threshold // 2]
        
        # Создаём краткую сводку
        summary_parts = []
        for msg in to_summarize:
            role = msg.get('role', 'user')
            content = msg.get('content', '')[:100]
            summary_parts.append(f"- {role}: {content}...")
        
        summary = "Previous conversation summary:\n" + '\n'.join(summary_parts)
        self.summaries.append(summary)
        
        # Удаляем старые сообщения
        self.messages = self.messages[self.summary_threshold // 2:]
    
    def get_context_messages(self) -> List[Dict[str, str]]:
        """Получить сообщения для контекста"""
        result = []
        
        # Добавляем сводки старых диалогов
        if self.summaries:
            result.append({
                'role': 'system',
                'content': '\n\n'.join(self.summaries[-2:])  # Последние 2 сводки
            })
        
        # Добавляем текущие сообщения
        result.extend(self.messages[-self.max_messages:])
        
        return result
    
    def clear(self) -> None:
        """Очистить историю"""
        self.messages.clear()
        self.summaries.clear()


def import_time():
    """Импорт time для timestamp"""
    import time
    return time.time()


# ==================== ФАБРИКА ====================

_context_manager: Optional[ContextManager] = None

def get_context_manager(max_tokens: int = DEFAULT_CONTEXT_MAX_TOKENS) -> ContextManager:
    """Получить или создать Context Manager"""
    global _context_manager
    
    if _context_manager is None or _context_manager.max_tokens != max_tokens:
        _context_manager = ContextManager(max_tokens=max_tokens)
    
    return _context_manager


# ==================== УТИЛИТЫ ====================

def format_file_for_context(
    file_path: str,
    content: str,
    max_lines: int = 100
) -> str:
    """Форматировать файл для включения в контекст"""
    lines = content.split('\n')
    
    if len(lines) <= max_lines:
        return f"```{Path(file_path).suffix[1:] if Path(file_path).suffix else 'text'}\n# {file_path}\n{content}\n```"
    
    # Сжимаем
    compressed = ContextCompressor.compress_code(content, max_lines)
    return f"```{Path(file_path).suffix[1:]}\n# {file_path} (compressed)\n{compressed}\n```"


def calculate_optimal_context_size(
    model: str,
    task_type: str = "chat"
) -> int:
    """
    Рассчитать оптимальный размер контекста для модели и задачи.
    """
    if os.getenv("NEIRA_CONTEXT_MAX_TOKENS"):
        return DEFAULT_CONTEXT_MAX_TOKENS

    # Размеры контекстных окон разных моделей
    model_context_sizes = {
        'llama3': 8192,
        'llama3.1': 131072,
        'mistral': 8192,
        'mixtral': 32768,
        'codellama': 16384,
        'gemma2': 8192,
        'qwen2.5-coder': 32768,
        'deepseek-coder': 16384,
        'gpt-3.5-turbo': 16384,
        'gpt-4': 8192,
        'gpt-4-turbo': 128000,
        'claude-3': 200000,
    }
    
    # Находим подходящий размер
    base_size = 8192
    for name, size in model_context_sizes.items():
        if name in model.lower():
            base_size = size
            break
    
    # Корректируем по типу задачи
    task_ratios = {
        'chat': 0.6,           # Оставляем место для истории
        'completion': 0.3,     # Минимальный контекст
        'explain': 0.7,        # Больше кода
        'generate': 0.5,       # Баланс
        'refactor': 0.8,       # Максимум кода
    }
    
    ratio = task_ratios.get(task_type, 0.6)
    
    return int(base_size * ratio)


# ==================== ТЕСТИРОВАНИЕ ====================

if __name__ == "__main__":
    # Тест оценки токенов
    test_text = """
def hello_world():
    '''Simple hello world function'''
    print("Hello, World!")
    return True

class MyClass:
    def __init__(self):
        self.value = 42
    """
    
    print(f"Estimated tokens: {estimate_tokens(test_text)}")
    print(f"Precise tokens: {count_tokens_precise(test_text)}")
    
    # Тест сжатия
    long_code = "\n".join([f"line_{i} = {i}" for i in range(100)])
    compressed = ContextCompressor.compress_code(long_code, max_lines=20)
    print(f"\nOriginal lines: 100")
    print(f"Compressed lines: {len(compressed.split(chr(10)))}")
    
    # Тест ContextManager
    manager = get_context_manager()
    window = manager.build_context(
        user_query="Объясни этот код",
        current_code=test_text,
        current_file="test.py",
        system_prompt="Ты - AI ассистент по программированию."
    )
    
    print(f"\nContext window:")
    print(f"  Total tokens: {window.total_tokens}")
    print(f"  Available tokens: {window.available_tokens}")
    print(f"  Chunks: {len(window.chunks)}")
    
    # Тест optimal size
    print(f"\nOptimal context for llama3 chat: {calculate_optimal_context_size('llama3', 'chat')}")
    print(f"Optimal context for gpt-4-turbo explain: {calculate_optimal_context_size('gpt-4-turbo', 'explain')}")
