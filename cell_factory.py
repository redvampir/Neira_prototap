"""
Neira Cell Factory v0.8 — Улучшенная фабрика органов

НОВЫЕ ВОЗМОЖНОСТИ:
1. Обнаружение повторяющихся паттернов задач
2. Генерация кода новой клетки по шаблону
3. ✨ Проверка безопасности через OrganGuardian
4. Автоматическое тестирование клетки
5. Сохранение в generated/ для динамической загрузки
6. Версионирование и управление жизненным циклом
7. 🆕 Интерактивный режим создания органов
8. 🆕 Проверка на дубликаты и полезность
9. 🆕 Режимы: auto, interactive, manual
"""

import os
import json
import subprocess
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
import requests

from cells import (
    DEFAULT_MAX_RESPONSE_TOKENS,
    OLLAMA_NUM_CTX,
    OLLAMA_URL,
    MODEL_CODE,
    MODEL_REASON,
    TIMEOUT,
    _MODEL_LAYERS,
    _merge_system_prompt,
)
from experience import ExperienceSystem
from organ_guardian import OrganGuardian, ThreatLevel  # ✨ НОВОЕ
from llm_providers import LLMManager, create_default_manager  # ✨ Универсальный LLM провайдер

logger = logging.getLogger("neira-cell-factory")


# Конфигурация
GENERATED_CELLS_DIR = "generated"
CELL_REGISTRY_FILE = "neira_cell_registry.json"
MIN_PATTERN_OCCURRENCES = 3  # Минимум повторений для генерации клетки
ORGAN_SPEC_MODEL = os.getenv("NEIRA_ORGAN_SPEC_MODEL", MODEL_REASON)

# 🆕 Режимы создания органов
class CreationMode:
    AUTO = "auto"          # Полностью автоматическое (только по явным командам)
    INTERACTIVE = "interactive"  # Обсуждение с пользователем
    MANUAL = "manual"      # Только по запросу администратора

# Глобальный LLM Manager для универсального доступа к LLM (Ollama/LMStudio/OpenAI/etc)
_LLM_MANAGER: Optional[LLMManager] = None

def _get_llm_manager() -> LLMManager:
    """Ленивая инициализация LLM Manager"""
    global _LLM_MANAGER
    if _LLM_MANAGER is None:
        _LLM_MANAGER = create_default_manager()
    return _LLM_MANAGER


# 🆕 Менеджер режимов создания органов
class OrganCreationManager:
    """Управляет режимами создания органов и интерактивным процессом"""
    
    def __init__(self):
        self.creation_mode = os.getenv("NEIRA_ORGAN_CREATION_MODE", CreationMode.INTERACTIVE)
        self.pending_organs = {}  # organ_id -> spec
        self.user_sessions = {}   # user_id -> session_data
        
    def set_creation_mode(self, mode: str) -> bool:
        """Установить режим создания органов"""
        if mode not in [CreationMode.AUTO, CreationMode.INTERACTIVE, CreationMode.MANUAL]:
            return False
        self.creation_mode = mode
        logger.info(f"🆕 Режим создания органов изменён на: {mode}")
        return True
    
    def should_create_automatically(self, user_input: str, user_id: str) -> Tuple[bool, str]:
        """
        Определить, нужно ли автоматически создать орган
        
        Returns: (should_create, reason)
        """
        if self.creation_mode == CreationMode.MANUAL:
            return False, "Режим: только ручное создание"
        
        # Проверяем явные команды
        explicit_commands = [
            "#создай_орган", "#grow_organ", "#create_organ", "#новый_орган",
            "/grow", "вырасти орган", "создай орган"
        ]
        
        has_explicit_command = any(cmd in user_input.lower() for cmd in explicit_commands)
        
        if has_explicit_command:
            if self.creation_mode == CreationMode.AUTO:
                return True, "Явная команда в авто-режиме"
            else:  # INTERACTIVE
                return False, "Явная команда — перейдём к интерактивному обсуждению"
        
        # Для неявных запросов — только в интерактивном режиме
        if self.creation_mode == CreationMode.INTERACTIVE:
            # Проверяем паттерны, указывающие на желание создать орган
            growth_indicators = [
                "научись", "добавь возможность", "создай функцию",
                "мне нужен орган", "вырасти", "развивайся"
            ]
            
            has_growth_indicator = any(indicator in user_input.lower() for indicator in growth_indicators)
            
            if has_growth_indicator:
                return False, "Обнаружен индикатор роста — обсудим создание"
        
        return False, "Не подходит для авто-создания"
    
    def start_interactive_session(self, user_id: str, initial_description: str) -> Dict[str, Any]:
        """Начать интерактивную сессию создания органа"""
        session_id = f"session_{user_id}_{int(datetime.now().timestamp())}"
        
        self.user_sessions[user_id] = {
            "session_id": session_id,
            "step": "initial_proposal",
            "description": initial_description,
            "proposed_spec": None,
            "user_feedback": [],
            "created_at": datetime.now().isoformat()
        }
        
        return {
            "session_id": session_id,
            "message": f"🧬 Начинаем создавать орган для: '{initial_description}'\n\n"
                      "Я предложу спецификацию, а вы сможете её скорректировать.\n"
                      "Готовы начать? (да/нет/отмена)"
        }
    
    def process_interactive_step(self, user_id: str, user_response: str) -> Dict[str, Any]:
        """Обработать шаг интерактивной сессии"""
        if user_id not in self.user_sessions:
            return {"error": "Сессия не найдена"}
        
        session = self.user_sessions[user_id]
        step = session["step"]
        
        if step == "initial_proposal":
            if user_response.lower() in ["да", "yes", "готов", "start"]:
                # Генерируем спецификацию
                from cell_factory import CellFactory
                factory = CellFactory()
                
                # Создаём временную спецификацию для обсуждения
                spec = factory.generate_cell_spec(session["description"], [])
                
                if spec:
                    session["proposed_spec"] = spec
                    session["step"] = "review_spec"
                    
                    return {
                        "message": f"📋 Предлагаю спецификацию органа:\n\n"
                                  f"🏷️ **Имя:** {spec.cell_name}\n"
                                  f"📝 **Описание:** {spec.description}\n"
                                  f"🎯 **Назначение:** {spec.purpose}\n"
                                  f"🔍 **Паттерн:** {spec.task_pattern}\n\n"
                                  "Что думаете? (ок/изменить/отмена)\n"
                                  "_Если 'изменить' — опишите, что исправить_",
                        "spec": spec
                    }
                else:
                    return {"error": "Не удалось сгенерировать спецификацию"}
            
            elif user_response.lower() in ["нет", "no", "отмена", "cancel"]:
                del self.user_sessions[user_id]
                return {"message": "🛑 Создание органа отменено"}
            
            else:
                return {"message": "Пожалуйста, ответьте 'да' или 'нет'"}
        
        elif step == "review_spec":
            if user_response.lower() in ["ок", "ok", "хорошо", "good"]:
                # Переходим к созданию
                session["step"] = "create_organ"
                return {
                    "message": "✅ Отлично! Создаю орган...\n"
                              "Это займёт несколько секунд.",
                    "action": "create",
                    "spec": session["proposed_spec"]
                }
            
            elif "изменить" in user_response.lower() or "change" in user_response.lower():
                # Просим уточнения
                session["step"] = "modify_spec"
                return {
                    "message": "📝 Что именно изменить в спецификации?\n"
                              "Опишите желаемые изменения:"
                }
            
            elif user_response.lower() in ["отмена", "cancel"]:
                del self.user_sessions[user_id]
                return {"message": "🛑 Создание органа отменено"}
            
            else:
                return {"message": "Пожалуйста, скажите 'ок', 'изменить' или 'отмена'"}
        
        elif step == "modify_spec":
            # Сохраняем feedback и просим подтверждения
            session["user_feedback"].append(user_response)
            session["step"] = "confirm_modification"
            
            return {
                "message": f"📝 Записал изменения: '{user_response}'\n\n"
                          "Учитывать эти изменения при создании? (да/нет)"
            }
        
        elif step == "confirm_modification":
            if user_response.lower() in ["да", "yes"]:
                session["step"] = "create_organ"
                return {
                    "message": "✅ Создаю орган с учётом ваших изменений...",
                    "action": "create_with_modifications",
                    "spec": session["proposed_spec"],
                    "modifications": session["user_feedback"]
                }
            else:
                session["step"] = "review_spec"
                return {
                    "message": "📋 Возвращаемся к спецификации.\n"
                              "Что думаете? (ок/изменить/отмена)"
                }
    
    def end_session(self, user_id: str):
        """Завершить сессию"""
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]


# Глобальный менеджер создания органов
_organ_creation_manager = OrganCreationManager()

def get_organ_creation_manager() -> OrganCreationManager:
    """Получить глобальный менеджер создания органов"""
    return _organ_creation_manager


def _build_ollama_options(temperature: float, max_tokens: int, model_name: str = MODEL_REASON) -> Dict[str, Any]:
    options: Dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
    if OLLAMA_NUM_CTX:
        options["num_ctx"] = OLLAMA_NUM_CTX
    if _MODEL_LAYERS is not None:
        adapter = _MODEL_LAYERS.get_active_adapter(model_name)
        if adapter:
            options["adapter"] = adapter
    return options


def _merge_layer_system_prompt(system_prompt: str, model_name: str = MODEL_REASON) -> str:
    if _MODEL_LAYERS is None:
        return system_prompt
    layer_prompt = _MODEL_LAYERS.get_active_prompt(model_name)
    return _merge_system_prompt(system_prompt, layer_prompt)


def _extract_json_block(text: str) -> Optional[str]:
    """
    Извлекает JSON из текста, учитывая:
    - Markdown блоки ```json ... ```
    - Чистый JSON объект
    - JSON с текстом вокруг
    """
    if not text:
        return None
    
    # 1. Пробуем извлечь из markdown блока ```json ... ```
    md_patterns = [
        r'```json\s*\n?([\s\S]*?)\n?```',
        r'```\s*\n?([\s\S]*?)\n?```',
    ]
    for pattern in md_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate.startswith('{') and candidate.endswith('}'):
                return candidate
    
    # 2. Ищем JSON объект напрямую
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    
    # Проверяем баланс скобок
    candidate = text[start:end + 1]
    depth = 0
    in_string = False
    escape = False
    for ch in candidate:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
        if not in_string:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
    
    if depth == 0:
        return candidate
    
    # Если баланс не сходится, пробуем найти первый валидный JSON
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == '"' and (i == 0 or text[i-1] != '\\'):
            in_string = not in_string
        if not in_string:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    
    return text[start:end + 1]


def _sanitize_json_text(text: str) -> str:
    """Экранирует управляющие символы внутри строк JSON."""
    in_string = False
    escape = False
    out: List[str] = []
    for ch in text:
        if in_string:
            if escape:
                out.append(ch)
                escape = False
                continue
            if ch == "\\":
                out.append(ch)
                escape = True
                continue
            if ch == '"':
                in_string = False
                out.append(ch)
                continue
            code = ord(ch)
            if code < 32:
                if ch == "\n":
                    out.append("\\n")
                elif ch == "\r":
                    out.append("\\r")
                elif ch == "\t":
                    out.append("\\t")
                else:
                    out.append(f"\\u{code:04x}")
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)
    return "".join(out)


def _normalize_json_text(text: str) -> str:
    """Нормализует JSON с типичными ошибками (контрольные символы, запятые, кавычки)."""
    normalized = _sanitize_json_text(text)
    normalized = re.sub(r",\s*([}\]])", r"\1", normalized)
    normalized = re.sub(r"(?<!\\\\)'([^'\\\\]*(?:\\\\.[^'\\\\]*)*)'(\s*:)", r'"\1"\2', normalized)
    normalized = re.sub(r":\s*'([^'\\\\]*(?:\\\\.[^'\\\\]*)*)'", r': "\1"', normalized)
    return normalized


@dataclass
class CellSpec:
    """Спецификация новой клетки"""
    cell_name: str
    description: str
    purpose: str
    system_prompt: str
    methods: List[str]
    task_pattern: str  # Паттерн задач для которых создана


@dataclass
class GeneratedCell:
    """Метаданные сгенерированной клетки"""
    cell_id: str
    cell_name: str
    file_path: str
    created_at: str
    task_pattern: str
    description: str

    # Метрики
    uses_count: int = 0
    avg_score: float = 0.0
    active: bool = False

    # Командные подсказки для безопасного вызова органа (например: "/run_math_helper", "#math_helper")
    command_triggers: List[str] = field(default_factory=list)
    # Версионирование
    version: int = 1
    parent_cell: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "GeneratedCell":
        return GeneratedCell(**d)


class CellFactory:
    """Фабрика клеток с проверкой безопасности"""

    def __init__(self, experience: ExperienceSystem):
        self.experience = experience
        self.registry: List[GeneratedCell] = []
        os.makedirs(GENERATED_CELLS_DIR, exist_ok=True)
        self.load_registry()
        
        # ✨ НОВОЕ: Система защиты органов
        self.guardian = OrganGuardian()

        # Шаблон клетки
        self.cell_template = '''"""
{description}
Автоматически сгенерированная клетка v{version}
Создана: {created_at}
"""

from typing import Optional
from cells import Cell, CellResult, MemoryCell


class {class_name}(Cell):
    """
    {purpose}
    """

    name = "{cell_name}"
    system_prompt = """{system_prompt}"""

    def __init__(self, memory: Optional[MemoryCell] = None):
        super().__init__(memory)

    def process(self, input_data: str) -> CellResult:
        """Основной метод обработки"""
        result = self.call_llm(input_data)

        return CellResult(
            content=result,
            confidence=0.7,
            cell_name=self.name,
            metadata={{"generated": True, "version": {version}}}
        )


# Экспорт для динамического импорта
__all__ = ["{class_name}"]
'''

    def load_registry(self):
        """Загрузить реестр сгенерированных клеток"""
        if os.path.exists(CELL_REGISTRY_FILE):
            try:
                with open(CELL_REGISTRY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.registry = [GeneratedCell.from_dict(c) for c in data]
                print(f"🏭 Загружено сгенерированных клеток: {len(self.registry)}")
            except Exception as e:
                logger.exception(f"⚠️ Ошибка загрузки реестра: {e}")

    def save_registry(self):
        """Сохранить реестр"""
        try:
            with open(CELL_REGISTRY_FILE, "w", encoding="utf-8") as f:
                json.dump([c.to_dict() for c in self.registry], f,
                         ensure_ascii=False, indent=2)
        except Exception as e:
            logger.exception(f"⚠️ Ошибка сохранения реестра: {e}")

    def _check_for_duplicates(self, new_pattern: str) -> Dict[str, Any]:
        """
        Проверить на дубликаты среди существующих органов
        
        Returns:
            {
                "is_duplicate": bool,
                "existing_organ": str | None,
                "similarity": float,
                "reason": str
            }
        """
        from difflib import SequenceMatcher
        
        best_match = None
        best_similarity = 0.0
        
        for cell in self.registry:
            # Сравниваем паттерны
            pattern_similarity = SequenceMatcher(None, 
                                               new_pattern.lower(), 
                                               cell.task_pattern.lower()).ratio()
            
            # Сравниваем описания
            desc_similarity = SequenceMatcher(None,
                                            new_pattern.lower(),
                                            cell.description.lower()).ratio()
            
            # Берем максимальную схожесть
            similarity = max(pattern_similarity, desc_similarity)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = cell
        
        # Порог схожести для дубликата
        DUPLICATE_THRESHOLD = 0.7
        
        if best_match and best_similarity >= DUPLICATE_THRESHOLD:
            return {
                "is_duplicate": True,
                "existing_organ": best_match.cell_name,
                "similarity": best_similarity * 100,
                "reason": f"Похожий орган '{best_match.cell_name}' уже существует"
            }
        
        return {
            "is_duplicate": False,
            "existing_organ": None,
            "similarity": best_similarity * 100,
            "reason": "Дубликатов не найдено"
        }

    def detect_task_patterns(self) -> Dict[str, List]:
        """Обнаружить повторяющиеся паттерны задач"""

        # Группируем задачи по ключевым словам
        patterns = {}

        for exp in self.experience.experiences:
            # Извлекаем ключевые слова из запроса
            words = exp.user_input.lower().split()

            # Ищем паттерны (упрощенно: первые 2-3 слова)
            if len(words) >= 2:
                pattern = " ".join(words[:2])

                if pattern not in patterns:
                    patterns[pattern] = []

                patterns[pattern].append(exp)

        # Фильтруем паттерны с достаточным количеством повторений
        significant_patterns = {
            pattern: tasks
            for pattern, tasks in patterns.items()
            if len(tasks) >= MIN_PATTERN_OCCURRENCES
        }

        return significant_patterns

    def should_create_cell(self) -> Optional[Tuple[str, List]]:
        """Определить нужно ли создавать новую клетку"""

        patterns = self.detect_task_patterns()

        if not patterns:
            return None

        # Проверяем есть ли паттерн для которого нет специализированной клетки
        for pattern, tasks in patterns.items():
            # Проверяем нет ли уже клетки для этого паттерна
            exists = any(c.task_pattern == pattern for c in self.registry)

            if not exists:
                print(f"🎯 Обнаружен новый паттерн: '{pattern}' ({len(tasks)} задач)")
                return pattern, tasks

        return None

    def generate_cell_spec(self, pattern: str, tasks: List, max_retries: int = 2) -> Optional[CellSpec]:
        """
        Генерировать спецификацию клетки с retry логикой.
        
        Args:
            pattern: Паттерн задач
            tasks: Список примеров задач
            max_retries: Максимум попыток при ошибке JSON
        """

        # Анализируем задачи
        task_examples = "\n".join([
            f"- {t.get('description', str(t))[:100]}" if isinstance(t, dict) else f"- {str(t)[:100]}"
            for t in tasks[:5]
        ])

        # Улучшенный промпт с few-shot примером
        prompt = f"""Создай спецификацию новой клетки для Neira.

ПАТТЕРН ЗАДАЧ: {pattern}

ПРИМЕРЫ ЗАПРОСОВ:
{task_examples}

ВЫВЕДИ ТОЛЬКО JSON БЕЗ ПОЯСНЕНИЙ:

ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА:
{{
  "cell_name": "math_helper",
  "description": "Решает математические задачи и уравнения",
  "purpose": "Помогает с вычислениями, алгеброй и геометрией. Объясняет решения пошагово.",
  "system_prompt": "Ты — математический помощник. Решай задачи пошагово, объясняя каждое действие."
}}

ТЕПЕРЬ СОЗДАЙ JSON ДЛЯ ПАТТЕРНА \"{pattern}\":"""

        model_name = ORGAN_SPEC_MODEL.strip() or MODEL_REASON
        system_prompt = _merge_layer_system_prompt(
            "Ты генерируешь JSON спецификации. Отвечай ТОЛЬКО валидным JSON объектом без markdown, без пояснений.",
            model_name=model_name,
        )
        
        # Получаем LLM Manager для универсального доступа к любому LLM
        llm = _get_llm_manager()
        
        for attempt in range(max_retries):
            try:
                # Увеличиваем temperature при retry для разнообразия
                temperature = 0.3 + (attempt * 0.2)
                max_tokens = min(DEFAULT_MAX_RESPONSE_TOKENS, 2048)
                
                logger.info(f"🧬 Генерация спецификации органа (попытка {attempt + 1}/{max_retries})...")
                
                # Используем LLMManager вместо прямого запроса к Ollama
                llm_response = llm.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                if not llm_response.success:
                    logger.warning(f"⚠️ Ошибка LLM: {llm_response.error} (попытка {attempt + 1})")
                    continue

                result = llm_response.content
                
                # Логируем сырой ответ для отладки
                if not result:
                    logger.warning(f"⚠️ Пустой ответ от модели (попытка {attempt + 1})")
                    continue

                # Парсим JSON с улучшенным извлечением
                spec_text = _extract_json_block(result)
                if not spec_text:
                    logger.warning(f"⚠️ Ответ модели не содержит JSON (попытка {attempt + 1}). Ответ: {result[:200]}...")
                    continue

                # Многоуровневый парсинг JSON
                spec_data = None
                parse_methods = [
                    ("direct", lambda t: json.loads(t)),
                    ("sanitized", lambda t: json.loads(_sanitize_json_text(t))),
                    ("normalized", lambda t: json.loads(_normalize_json_text(t))),
                ]
                
                for method_name, parse_func in parse_methods:
                    try:
                        spec_data = parse_func(spec_text)
                        logger.debug(f"✅ JSON распарсен методом: {method_name}")
                        break
                    except json.JSONDecodeError:
                        continue
                
                if spec_data is None:
                    logger.warning(f"⚠️ Не удалось распарсить JSON (попытка {attempt + 1}). Текст: {spec_text[:200]}...")
                    continue

                # Проверяем обязательные поля
                required_keys = ("cell_name", "description", "purpose", "system_prompt")
                missing_keys = [k for k in required_keys if k not in spec_data]
                if missing_keys:
                    logger.warning(f"⚠️ Отсутствуют поля: {missing_keys} (попытка {attempt + 1})")
                    continue

                logger.info(f"✅ Спецификация органа '{spec_data['cell_name']}' создана успешно")
                
                return CellSpec(
                    cell_name=spec_data["cell_name"],
                    description=spec_data["description"],
                    purpose=spec_data["purpose"],
                    system_prompt=spec_data["system_prompt"],
                    methods=["process"],  # Базовый набор
                    task_pattern=pattern
                )

            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Таймаут запроса к модели (попытка {attempt + 1})")
            except requests.exceptions.RequestException as e:
                logger.error(f"⚠️ Ошибка сети: {e} (попытка {attempt + 1})")
            except Exception as e:
                logger.exception(f"⚠️ Неожиданная ошибка: {e} (попытка {attempt + 1})")
        
        logger.error(f"❌ Не удалось создать спецификацию органа после {max_retries} попыток")
        return None

    def create_cell_file(self, spec: CellSpec) -> str:
        """Создать файл клетки"""

        class_name = "".join(word.capitalize() for word in spec.cell_name.split("_")) + "Cell"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{spec.cell_name}_{timestamp}.py"
        filepath = os.path.join(GENERATED_CELLS_DIR, filename)

        code = self.cell_template.format(
            description=spec.description,
            version=1,
            created_at=datetime.now().isoformat(),
            class_name=class_name,
            cell_name=spec.cell_name,
            purpose=spec.purpose,
            system_prompt=spec.system_prompt
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        print(f"📝 Создан файл: {filepath}")
        return filepath

    def validate_cell(self, filepath: str) -> Tuple[bool, str]:
        """Валидация клетки (синтаксис + базовая проверка)"""

        try:
            # Проверка синтаксиса
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()

            compile(code, filepath, "exec")

            # Пробуем импортировать
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_cell", filepath)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            return True, "Валидация пройдена"

        except SyntaxError as e:
            return False, f"Синтаксическая ошибка: {e}"
        except Exception as e:
            return False, f"Ошибка импорта: {e}"

    def create_cell(self, pattern: str, tasks: List, author_id: int = 0) -> Dict[str, Any]:
        """
        Создать новую клетку с проверкой безопасности
        
        Returns:
            {
                "success": bool,
                "cell": GeneratedCell | None,
                "threat_level": str,
                "report": str,
                "quarantined": bool,
                "organ_id": str | None
            }
        """

        print("\n" + "="*60)
        print("🏭 СОЗДАНИЕ НОВОЙ КЛЕТКИ")
        print("="*60)

        # 🆕 Проверяем на дубликаты
        duplicate_check = self._check_for_duplicates(pattern)
        if duplicate_check["is_duplicate"]:
            print(f"⚠️  ОБНАРУЖЕН ДУБЛИКАТ!")
            print(f"   Существующий орган: {duplicate_check['existing_organ']}")
            print(f"   Схожесть: {duplicate_check['similarity']:.1f}%")
            
            return {
                "success": False,
                "error": f"Орган уже существует: {duplicate_check['existing_organ']} "
                        f"(схожесть {duplicate_check['similarity']:.1f}%)",
                "threat_level": "duplicate",
                "duplicate_info": duplicate_check
            }

        # Генерируем спецификацию
        spec = self.generate_cell_spec(pattern, tasks)

        if not spec:
            logger.error("❌ Не удалось создать спецификацию")
            return {
                "success": False,
                "error": "Не удалось создать спецификацию органа",
                "threat_level": "unknown"
            }

        print(f"\n📋 СПЕЦИФИКАЦИЯ:")
        print(f"   Имя: {spec.cell_name}")
        print(f"   Описание: {spec.description}")
        print(f"   Паттерн: {spec.task_pattern}")

        # ✨ НОВОЕ: Генерируем код
        code = self.cell_template.format(
            description=spec.description,
            version=1,
            created_at=datetime.now().isoformat(),
            class_name=spec.cell_name.title().replace("_", ""),
            cell_name=spec.cell_name,
            purpose=spec.purpose,
            system_prompt=spec.system_prompt
        )
        
        # ✨ НОВОЕ: ПРОВЕРКА БЕЗОПАСНОСТИ
        print(f"\n🔍 ПРОВЕРКА БЕЗОПАСНОСТИ...")
        scan_result = self.guardian.scan_organ_code(code, spec.cell_name)
        safety_report = self.guardian.generate_safety_report(scan_result, spec.cell_name)
        
        print(safety_report)
        
        # Обработка по уровню угрозы
        if scan_result.threat_level == ThreatLevel.CRITICAL:
            logger.error("\n🚨 ОРГАН ЗАБЛОКИРОВАН - критическая угроза!")
            return {
                "success": False,
                "threat_level": "critical",
                "report": safety_report,
                "error": "Орган содержит критически опасный код и был заблокирован"
            }
        
        elif scan_result.threat_level == ThreatLevel.DANGEROUS:
            logger.warning("\n⚠️ ОРГАН ТРЕБУЕТ ОДОБРЕНИЯ АДМИНИСТРАТОРА")
            quarantined_organ = self.guardian.quarantine_organ(
                name=spec.cell_name,
                description=spec.description,
                code=code,
                author_id=author_id,
                scan_result=scan_result
            )
            return {
                "success": False,
                "threat_level": "dangerous",
                "report": safety_report,
                "quarantined": True,
                "organ_id": quarantined_organ.organ_id,
                "message": "Орган помещён в карантин. Ожидайте одобрения администратора."
            }
        
        elif scan_result.threat_level == ThreatLevel.SUSPICIOUS:
            print("\n🔍 ОРГАН ПОМЕЩЁН В 24-ЧАСОВОЙ КАРАНТИН")
            quarantined_organ = self.guardian.quarantine_organ(
                name=spec.cell_name,
                description=spec.description,
                code=code,
                author_id=author_id,
                scan_result=scan_result,
                quarantine_hours=24
            )
            return {
                "success": False,
                "threat_level": "suspicious",
                "report": safety_report,
                "quarantined": True,
                "organ_id": quarantined_organ.organ_id,
                "message": "Орган помещён в 24-часовой карантин для мониторинга."
            }
        
        # ✅ БЕЗОПАСЕН - создаём файл
        print(f"\n✅ ОРГАН БЕЗОПАСЕН - создаём файл")
        filepath = os.path.join(GENERATED_CELLS_DIR, f"{spec.cell_name}.py")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)

        print(f"📝 Создан файл: {filepath}")

        # Валидация
        valid, validation_msg = self.validate_cell(filepath)

        if not valid:
            logger.error(f"❌ Валидация провалена: {validation_msg}")
            os.remove(filepath)
            return {
                "success": False,
                "threat_level": "safe",
                "error": f"Синтаксическая ошибка: {validation_msg}"
            }

        print(f"✅ Валидация пройдена")

        # Регистрируем
        cell_id = f"{spec.cell_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Генерируем безопасные текстовые команды для вызова органа
        # Обязательно одна из команд — улучшение органа (русский триггер)
        commands = [
            f"/run_{spec.cell_name}",
            f"#{spec.cell_name}",
            f"/улучшение_{spec.cell_name}"
        ]

        generated_cell = GeneratedCell(
            cell_id=cell_id,
            cell_name=spec.cell_name,
            file_path=filepath,
            created_at=datetime.now().isoformat(),
            task_pattern=pattern,
            description=spec.description,
            active=True,  # ✨ Безопасный орган активен сразу
            command_triggers=commands
        )

        self.registry.append(generated_cell)
        self.save_registry()

        # Emit event so running bot can hot-register commands
        try:
            from neira.utils.event_bus import event_bus
            event_bus.emit("organ_created", generated_cell.to_dict())
        except Exception:
            logger.exception("Не удалось эмитировать событие organ_created")

        print(f"\n🎉 КЛЕТКА СОЗДАНА: {cell_id}")
        print(f"   Файл: {filepath}")
        print(f"   Статус: Активна и готова к использованию")
        # Подсказки команд
        print(f"   Команды: {', '.join(commands)}")
        
        return {
            "success": True,
            "cell": generated_cell,
            "threat_level": "safe",
            "report": safety_report,
            "message": "✅ Орган создан и готов к использованию!",
            "commands": commands
        }

        if not valid:
            logger.error(f"❌ Валидация провалена: {validation_msg}")
            os.remove(filepath)
            return None

        print(f"✅ Валидация пройдена")

        # Регистрируем
        cell_id = f"{spec.cell_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        generated_cell = GeneratedCell(
            cell_id=cell_id,
            cell_name=spec.cell_name,
            file_path=filepath,
            created_at=datetime.now().isoformat(),
            task_pattern=pattern,
            description=spec.description,
            active=False  # Требуется тестирование перед активацией
        )

        self.registry.append(generated_cell)
        self.save_registry()

        print(f"\n🎉 КЛЕТКА СОЗДАНА: {cell_id}")
        print(f"   Файл: {filepath}")
        print(f"   Статус: требуется тестирование")
        print(f"   Используй /load-cell {spec.cell_name} для активации")

        return generated_cell

    def auto_creation_cycle(self) -> List[GeneratedCell]:
        """Автоматический цикл создания клеток"""

        print("\n" + "="*60)
        print("🏭 АВТОМАТИЧЕСКОЕ СОЗДАНИЕ КЛЕТОК")
        print("="*60)

        created = []

        # Обнаруживаем паттерны
        patterns = self.detect_task_patterns()

        print(f"\nОбнаружено паттернов: {len(patterns)}")

        for pattern, tasks in patterns.items():
            # Проверяем нет ли уже клетки
            exists = any(c.task_pattern == pattern for c in self.registry)

            if not exists:
                print(f"\n🎯 Новый паттерн: '{pattern}' ({len(tasks)} задач)")

                cell = self.create_cell(pattern, tasks)

                if cell:
                    created.append(cell)
            else:
                print(f"\n✅ Паттерн '{pattern}': клетка уже существует")

        if not created:
            print("\n✅ Новых клеток не требуется")

        return created

    def activate_cell(self, cell_name: str):
        """Активировать клетку"""
        for cell in self.registry:
            if cell.cell_name == cell_name:
                cell.active = True
                self.save_registry()
                print(f"✅ Клетка активирована: {cell_name}")
                print(f"   Файл: {cell.file_path}")
                print(f"   Перезапусти Neira для загрузки клетки")
                return

        logger.warning(f"⚠️ Клетка не найдена: {cell_name}")

    def get_active_cells(self) -> List[GeneratedCell]:
        """Получить список активных клеток"""
        return [c for c in self.registry if c.active]

    def get_stats(self) -> Dict:
        """Статистика фабрики"""
        return {
            "total_cells": len(self.registry),
            "active_cells": len(self.get_active_cells()),
            "total_uses": sum(c.uses_count for c in self.registry),
            "patterns_covered": len(set(c.task_pattern for c in self.registry))
        }

    def show_registry(self) -> str:
        """Показать реестр клеток"""
        if not self.registry:
            return "🏭 Реестр клеток пуст"

        output = "🏭 РЕЕСТР СГЕНЕРИРОВАННЫХ КЛЕТОК:\n\n"

        for i, cell in enumerate(self.registry, 1):
            status = "🟢 ACTIVE" if cell.active else "⏸️  INACTIVE"

            output += f"{i}. {cell.cell_name} {status}\n"
            output += f"   ID: {cell.cell_id}\n"
            output += f"   Описание: {cell.description}\n"
            output += f"   Паттерн: {cell.task_pattern}\n"
            output += f"   Создана: {cell.created_at[:19]}\n"
            output += f"   Файл: {cell.file_path}\n"
            # Показываем доступные команды для безопасного вызова органа
            if getattr(cell, 'command_triggers', None):
                output += f"   Команды: {', '.join(cell.command_triggers)}\n"

            if cell.uses_count > 0:
                output += f"   Использований: {cell.uses_count}\n"
                output += f"   Средний score: {cell.avg_score:.1f}/10\n"

            output += "\n"

        stats = self.get_stats()
        output += f"📊 СТАТИСТИКА:\n"
        output += f"   Всего клеток: {stats['total_cells']}\n"
        output += f"   Активных: {stats['active_cells']}\n"
        output += f"   Паттернов покрыто: {stats['patterns_covered']}\n"

        return output


# === ТЕСТ ===
if __name__ == "__main__":
    print("=" * 60)
    print("Тест CellFactory")
    print("=" * 60)

    from experience import ExperienceSystem

    exp = ExperienceSystem()
    factory = CellFactory(exp)

    print(f"\n{factory.show_registry()}")

    # Обнаружение паттернов
    patterns = factory.detect_task_patterns()
    print(f"\nОбнаружено паттернов: {len(patterns)}")

    for pattern, tasks in list(patterns.items())[:3]:
        print(f"  '{pattern}': {len(tasks)} задач")
