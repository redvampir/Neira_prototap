"""
Neira Cortex v2.0 — Автономный когнитивный процессор
Центральный мозг Neira с минимальной зависимостью от LLM

Компоненты:
- Intent Recognizer: распознавание намерений пользователя
- Decision Router: выбор стратегии ответа
- Neural Pathways: заученные рефлексы (87% запросов)
- Response Synthesizer: сборка ответов без LLM
- LLM Consultant: fallback для новых ситуаций (1-2%)
"""

import json
import logging
import os
import time
from typing import Optional, Dict, Any, Tuple, List, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Импорты наших компонентов
from neural_pathways import NeuralPathwaySystem, PathwayMatch, PathwayTier
from response_synthesizer import ResponseSynthesizer, ResponseMode


logger = logging.getLogger(__name__)


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


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _env_csv_list(name: str, default: Sequence[str]) -> List[str]:
    raw = os.getenv(name)
    if raw is None:
        return list(default)
    items = [item.strip() for item in raw.split(",") if item.strip()]
    unique: List[str] = []
    for item in items:
        if item not in unique:
            unique.append(item)
    return unique


DEFAULT_MAX_RESPONSE_TOKENS = _env_int("NEIRA_MAX_RESPONSE_TOKENS", 2048, min_value=128)
CORTEX_MAX_TOKENS = _env_int("NEIRA_CORTEX_MAX_TOKENS", DEFAULT_MAX_RESPONSE_TOKENS, min_value=128)
MAX_ORGAN_SUGGESTIONS = 3
DEFAULT_WEB_MAX_RESULTS = 5
DEFAULT_WEB_MAX_TOKENS = 512
DEFAULT_WEB_ALLOWED_DOMAINS = (
    "gramota.ru",
    "academic.ru",
    "dic.academic.ru",
    "ru.wiktionary.org",
)
WEB_SEARCH_ENABLED = _env_bool("NEIRA_WEB_SEARCH_ENABLED", True)
WEB_SEARCH_USE_HTML_FALLBACK = _env_bool("NEIRA_WEB_SEARCH_HTML_FALLBACK", True)
WEB_SEARCH_MAX_RESULTS = _env_int(
    "NEIRA_WEB_SEARCH_MAX_RESULTS",
    DEFAULT_WEB_MAX_RESULTS,
    min_value=1,
    max_value=10,
)
WEB_SEARCH_MAX_TOKENS = _env_int(
    "NEIRA_WEB_SEARCH_MAX_TOKENS",
    min(DEFAULT_WEB_MAX_TOKENS, DEFAULT_MAX_RESPONSE_TOKENS),
    min_value=128,
    max_value=DEFAULT_MAX_RESPONSE_TOKENS,
)
WEB_SEARCH_ALLOWED_DOMAINS = _env_csv_list(
    "NEIRA_WEB_ALLOWED_DOMAINS",
    DEFAULT_WEB_ALLOWED_DOMAINS,
)


# Импортируем общий модуль идентичности
from neira_identity import build_identity_prompt, IDENTITY_PROMPT, load_personality
from neira.core.llm_adapter import LLMClient, LLMResult, NullLLMClient, build_default_llm_client


class IntentType(Enum):
    """Типы намерений пользователя"""
    GREETING = "greeting"           # Приветствие
    GRATITUDE = "gratitude"         # Благодарность
    QUESTION = "question"           # Вопрос
    TASK = "task"                   # Задача/команда
    CODE_REQUEST = "code_request"   # Запрос кода
    EXPLANATION = "explanation"     # Объяснение
    CHAT = "chat"                   # Обычная беседа
    FEEDBACK = "feedback"           # Обратная связь
    UNKNOWN = "unknown"             # Неизвестное намерение


class ResponseStrategy(Enum):
    """Стратегии формирования ответа"""
    NEURAL_PATHWAY = "neural_pathway"  # Заученный рефлекс (fastest)
    TEMPLATE = "template"               # Шаблонный ответ
    FRAGMENT_ASSEMBLY = "fragment"      # Сборка из фрагментов
    RAG = "rag"                         # Retrieval + Assembly
    LLM_CONSULTANT = "llm_consultant"   # Консультация с LLM
    HYBRID = "hybrid"                   # Комбинированный


@dataclass
class ProcessingResult:
    """Результат обработки запроса"""
    response: str
    strategy: ResponseStrategy
    intent: IntentType
    confidence: float
    latency_ms: float
    pathway_tier: Optional[PathwayTier] = None
    llm_used: bool = False
    
    # Метаданные для обучения
    fragments_used: List[str] = field(default_factory=list)
    template_used: Optional[str] = None
    pathway_id: Optional[str] = None


class IntentRecognizer:
    """
    Распознаватель намерений пользователя
    
    Работает БЕЗ LLM через паттерны и ключевые слова
    """
    
    # Паттерны намерений
    PATTERNS = {
        IntentType.GREETING: [
            "привет", "здравствуй", "hi", "hello", "хай", "добр",
            "доброе утро", "добрый день", "добрый вечер"
        ],
        IntentType.GRATITUDE: [
            "спасибо", "благодарю", "thanks", "thx", "thank you",
            "премного благодарен", "признателен"
        ],
        IntentType.QUESTION: [
            "как", "что", "почему", "зачем", "когда", "где", "кто",
            "можешь", "можно", "?", "объясни", "расскажи"
        ],
        IntentType.CODE_REQUEST: [
            "код", "code", "напиши", "создай", "сделай",
            "программа", "скрипт", "функция", "класс",
            "python", "javascript", "java", "api"
        ],
        IntentType.TASK: [
            "выполни", "сделай", "создай", "измени", "удали",
            "запусти", "останови", "проверь", "найди"
        ],
        IntentType.FEEDBACK: [
            "отлично", "хорошо", "плохо", "не то", "не подходит",
            "супер", "класс", "неправильно", "ошибка"
        ],
        IntentType.CHAT: [
            "как дела", "что делаешь", "как ты", "расскажи о себе",
            "кто ты", "что ты умеешь"
        ]
    }
    
    def recognize(self, user_input: str) -> Tuple[IntentType, float]:
        """
        Распознать намерение
        
        Returns:
            (intent, confidence)
        """
        user_input_lower = user_input.lower()
        
        # Считаем совпадения для каждого intent
        intent_scores = {}
        
        for intent, patterns in self.PATTERNS.items():
            score = 0.0
            matches = 0
            
            for pattern in patterns:
                if pattern in user_input_lower:
                    matches += 1
                    # Чем длиннее паттерн, тем выше вес
                    score += len(pattern) / 10.0
            
            if matches > 0:
                # Нормализуем score
                intent_scores[intent] = min(1.0, score / len(patterns))
        
        if not intent_scores:
            return IntentType.UNKNOWN, 0.0
        
        # Выбираем намерение с наивысшим score
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        return best_intent


class DecisionRouter:
    """
    Маршрутизатор решений
    
    Выбирает оптимальную стратегию ответа
    """
    
    def route(
        self,
        intent: IntentType,
        confidence: float,
        pathway_match: Optional[PathwayMatch],
        has_llm: bool
    ) -> ResponseStrategy:
        """
        Выбрать стратегию ответа
        
        Логика:
        0. **КРИТИЧНО**: Если есть pathway - ИСПОЛЬЗУЕМ ЕГО ВСЕГДА!
        1. Если простое намерение (greeting, thanks) → TEMPLATE
        2. Если сложный запрос и нет pathway → LLM_CONSULTANT (если доступен)
        3. Иначе → FRAGMENT_ASSEMBLY
        """
        
        # 0. PATHWAY FIRST - ВСЕГДА! Даже с низким confidence
        # Это заученные рефлексы и КРИТИЧЕСКИЕ ситуации
        if pathway_match and pathway_match.confidence >= 0.3:
            return ResponseStrategy.NEURAL_PATHWAY
        
        # 2. Простые намерения → шаблоны
        if intent in [IntentType.GREETING, IntentType.GRATITUDE, IntentType.CHAT]:
            if pathway_match and pathway_match.confidence >= 0.5:
                return ResponseStrategy.NEURAL_PATHWAY
            return ResponseStrategy.TEMPLATE
        
        # 3. Сложные задачи
        if intent in [IntentType.CODE_REQUEST, IntentType.TASK]:
            # Если есть pathway даже с низким confidence - попробуем
            if pathway_match:
                return ResponseStrategy.NEURAL_PATHWAY
            # Нет pathway - нужен LLM
            if has_llm:
                return ResponseStrategy.LLM_CONSULTANT
            # LLM нет - пытаемся собрать из фрагментов
            return ResponseStrategy.FRAGMENT_ASSEMBLY
        
        # 4. Вопросы и объяснения
        if intent in [IntentType.QUESTION, IntentType.EXPLANATION]:
            if pathway_match and pathway_match.confidence >= 0.6:
                return ResponseStrategy.NEURAL_PATHWAY
            # RAG - поиск по базе знаний
            return ResponseStrategy.RAG
        
        # 5. Неизвестное намерение
        if intent == IntentType.UNKNOWN:
            if has_llm:
                return ResponseStrategy.LLM_CONSULTANT
            return ResponseStrategy.FRAGMENT_ASSEMBLY
        
        # Default
        return ResponseStrategy.HYBRID


class NeiraCortex:
    """
    Центральный когнитивный процессор Neira
    
    Оркестрирует все компоненты для обработки запроса
    """
    
    def __init__(
        self,
        pathways_file: str = "neural_pathways.json",
        fragments_file: str = "response_fragments.json",
        templates_file: str = "response_templates.json",
        use_llm: bool = True
    ):
        # Компоненты
        self.intent_recognizer = IntentRecognizer()
        self.decision_router = DecisionRouter()
        self.pathways = NeuralPathwaySystem(pathways_file)
        self.synthesizer = ResponseSynthesizer(fragments_file, templates_file)
        
        # LLM (опционально)
        self.llm_client: LLMClient = NullLLMClient("LLM отключен")
        self.llm_available = False
        if use_llm:
            self.llm_client = build_default_llm_client()
            self.llm_available = not isinstance(self.llm_client, NullLLMClient)
        
        # Статистика
        self.total_requests = 0
        self.strategy_stats = {s: 0 for s in ResponseStrategy}
        
        logger.info("=" * 60)
        logger.info("Neira Cortex v2.0 инициализирован")
        logger.info("=" * 60)
        logger.info("Neural Pathways: %s", len(self.pathways.pathways))
        logger.info("Response Fragments: %s", len(self.synthesizer.fragments))
        logger.info("Response Templates: %s", len(self.synthesizer.templates))
        logger.info("LLM Consultant: %s", "доступен" if self.llm_available else "недоступен")
        logger.info("=" * 60)

        self._hybrid_system = None
        self._web_search_cell = None
    
    def process(
        self,
        user_input: str,
        user_id: str = "default_user",
        context: Optional[Dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Обработать запрос пользователя
        
        Полный цикл:
        1. Распознать намерение
        2. Найти pathway (если есть)
        3. Выбрать стратегию
        4. Сгенерировать ответ
        5. Обновить метрики
        
        Args:
            user_input: Текст от пользователя
            user_id: ID пользователя
            context: Дополнительный контекст
            
        Returns:
            ProcessingResult с ответом и метаданными
        """
        start_time = time.perf_counter()
        context = context or {}
        
        self.total_requests += 1
        
        # 1. Распознаем намерение
        intent, intent_confidence = self.intent_recognizer.recognize(user_input)

        organ_hints = ""
        if intent in (IntentType.TASK, IntentType.CODE_REQUEST):
            organ_hints = self._build_organ_hints(user_input)
            if organ_hints:
                context = dict(context)
                context["organ_hints"] = organ_hints
        
        # 2. Ищем pathway
        pathway_match = self.pathways.match(user_input, user_id)
        
        # 3. Выбираем стратегию
        strategy = self.decision_router.route(
            intent,
            intent_confidence,
            pathway_match,
            has_llm=self.llm_available
        )
        
        self.strategy_stats[strategy] += 1
        
        # 4. Генерируем ответ
        response = ""
        llm_used = False
        pathway_tier = None
        pathway_id = None
        fragments_used = []
        template_used = None
        
        try:
            if strategy == ResponseStrategy.NEURAL_PATHWAY and pathway_match:
                # Заученный рефлекс - самый быстрый путь
                response = self.pathways.execute(pathway_match, user_input, user_id)
                pathway_tier = pathway_match.tier
                pathway_id = pathway_match.pathway_id
                
            elif strategy == ResponseStrategy.TEMPLATE:
                # Шаблонный ответ
                template_id = self._select_template(intent)
                if template_id:
                    response = self.synthesizer.synthesize(
                        template_id=template_id,
                        mode=ResponseMode.TEMPLATE
                    )
                    template_used = template_id
                else:
                    # Fallback на фрагменты
                    response = self._assemble_from_fragments(intent, context)
                    
            elif strategy == ResponseStrategy.FRAGMENT_ASSEMBLY:
                # Сборка из фрагментов
                response = self._assemble_from_fragments(intent, context)
                
            elif strategy == ResponseStrategy.RAG:
                # RAG без генерации
                response = self.synthesizer.synthesize(
                    variables={"category": intent.value, **context},
                    mode=ResponseMode.RAG
                )
                
            elif strategy == ResponseStrategy.LLM_CONSULTANT:
                # Консультация с LLM (fallback)
                if self.llm_available:
                    response = self._consult_llm(user_input, intent, context)
                    llm_used = True
                else:
                    # LLM недоступен - пытаемся собрать из фрагментов
                    response = self._assemble_from_fragments(intent, context)
                    
            elif strategy == ResponseStrategy.HYBRID:
                # Гибридная стратегия
                response = self._hybrid_response(user_input, intent, pathway_match, context)
            
        except Exception as e:
            logger.warning("Ошибка генерации ответа: %s", e)
            response = self._fallback_response(intent)

        if not response.strip():
            web_answer, web_llm_used = self._maybe_web_search(user_input, intent)
            if web_answer:
                response = web_answer
                llm_used = llm_used or web_llm_used
            if not response.strip():
                response = self._fallback_response(intent)
        
        # 5. Вычисляем latency
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        # 6. Создаем результат
        result = ProcessingResult(
            response=response,
            strategy=strategy,
            intent=intent,
            confidence=intent_confidence,
            latency_ms=latency_ms,
            pathway_tier=pathway_tier,
            llm_used=llm_used,
            pathway_id=pathway_id,
            fragments_used=fragments_used,
            template_used=template_used
        )
        
        # Периодическая реорганизация
        if self.total_requests % 100 == 0:
            self._reorganize_pathways()
        
        return result
    
    def _select_template(self, intent: IntentType) -> Optional[str]:
        """Выбрать шаблон для намерения"""
        template_map = {
            IntentType.GREETING: "greeting_full",
            IntentType.GRATITUDE: "thanks_full",
            IntentType.CODE_REQUEST: "code_explanation_full",
        }
        return template_map.get(intent)
    
    def _assemble_from_fragments(
        self,
        intent: IntentType,
        context: Dict[str, Any]
    ) -> str:
        """Собрать ответ из фрагментов"""
        # Находим фрагменты по категории
        category = intent.value
        fragments = self.synthesizer.find_fragments_by_category(category)
        
        if not fragments:
            # Пытаемся generic категорию
            fragments = self.synthesizer.find_fragments_by_category("general")
        
        if fragments:
            # Берем наиболее используемый
            best_fragment = max(fragments, key=lambda f: f.usage_count)
            response = best_fragment.apply_variables(**context)
            return self._append_organ_hints(response, context)
        
        return "🤔 Интересный запрос! Дай мне секунду подумать..."
    
    def _get_hybrid_system(self) -> Optional[object]:
        if self._hybrid_system is not None:
            return self._hybrid_system
        try:
            from neira.organs.hybrid_system import get_hybrid_organ_system
        except ImportError:
            return None
        try:
            self._hybrid_system = get_hybrid_organ_system()
        except (RuntimeError, OSError, ValueError):
            return None
        return self._hybrid_system

    def _get_web_search_cell(self) -> Optional[object]:
        if self._web_search_cell is not None:
            return self._web_search_cell
        try:
            from web_cell import WebSearchCell
        except ImportError:
            return None
        try:
            self._web_search_cell = WebSearchCell()
        except (RuntimeError, OSError, ValueError, TypeError) as exc:
            logger.warning("WebSearchCell init failed: %s", exc)
            return None
        return self._web_search_cell

    def _format_web_results(self, results: Sequence[object]) -> str:
        lines: List[str] = []
        for idx, entry in enumerate(results, 1):
            title = str(getattr(entry, "title", "")).strip()
            snippet = str(getattr(entry, "snippet", "")).strip()
            url = str(getattr(entry, "url", "")).strip()
            if not (title or snippet or url):
                continue
            parts = [f"{idx}. {title}".strip()]
            if snippet:
                parts.append(snippet)
            if url:
                parts.append(f"\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a: {url}")
            lines.append("\n".join(parts))
        return "\n\n".join(lines)

    def _web_search_answer(self, user_input: str) -> Tuple[str, bool]:
        cell = self._get_web_search_cell()
        if cell is None:
            return "", False
        try:
            results, reason = cell.search(
                user_input,
                max_results=WEB_SEARCH_MAX_RESULTS,
                allowed_domains=WEB_SEARCH_ALLOWED_DOMAINS,
                use_html_fallback=WEB_SEARCH_USE_HTML_FALLBACK,
            )
        except (AttributeError, RuntimeError, OSError, ValueError, TypeError) as exc:
            logger.warning("Web search failed: %s", exc)
            return "", False
        if not results:
            if reason:
                logger.info("Web search empty: %s", reason.get("reason_code"))
            return "", False

        context = self._format_web_results(results)
        if not context:
            return "", False

        if self.llm_available:
            system_prompt = (
                "\u0422\u044b \u043e\u0442\u0432\u0435\u0447\u0430\u0435\u0448\u044c \u043a\u0440\u0430\u0442\u043a\u043e \u0438 \u043f\u043e \u0444\u0430\u043a\u0442\u0430\u043c. "
                "\u0423\u043a\u0430\u0437\u044b\u0432\u0430\u0439 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438."
            )
            prompt = f"\u0412\u043e\u043f\u0440\u043e\u0441: {user_input}\n\n{context}\n\n\u041e\u0442\u0432\u0435\u0442:"
            response: LLMResult = self.llm_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=WEB_SEARCH_MAX_TOKENS,
                temperature=0.3,
            )
            if response.success and response.content:
                return response.content, True
            if response.error:
                logger.info("Web search LLM error: %s", response.error)

        fallback = "\u041d\u0430\u0448\u043b\u0430 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438:\n" + context
        return fallback, False

    def _maybe_web_search(self, user_input: str, intent: IntentType) -> Tuple[str, bool]:
        if not WEB_SEARCH_ENABLED:
            return "", False
        if intent not in (IntentType.QUESTION, IntentType.EXPLANATION):
            return "", False
        return self._web_search_answer(user_input)

    def _build_organ_hints(self, user_input: str) -> str:
        system = self._get_hybrid_system()
        if system is None:
            return ""
        try:
            suggestions = system.suggest_organs(user_input, max_items=MAX_ORGAN_SUGGESTIONS)
        except (AttributeError, RuntimeError, OSError, ValueError):
            return ""
        if not suggestions:
            return ""
        lines: List[str] = []
        for entry in suggestions:
            name = str(getattr(entry, "name", "")).strip()
            if not name:
                continue
            description = str(getattr(entry, "description", "")).strip()
            triggers = list(getattr(entry, "triggers", []) or [])
            capabilities = list(getattr(entry, "capabilities", []) or [])
            label = ""
            if triggers:
                label = "триггеры: " + ", ".join(triggers[:MAX_ORGAN_SUGGESTIONS])
            elif capabilities:
                label = "возможности: " + ", ".join(capabilities[:MAX_ORGAN_SUGGESTIONS])
            if description and label:
                lines.append(f"- {name}: {description} ({label})")
            elif description:
                lines.append(f"- {name}: {description}")
            elif label:
                lines.append(f"- {name}: {label}")
            else:
                lines.append(f"- {name}")
        if not lines:
            return ""
        return "Подсказки по органам:\n" + "\n".join(lines)

    def _append_organ_hints(self, response: str, context: Dict[str, Any]) -> str:
        organ_hints = context.get("organ_hints")
        if not organ_hints:
            return response
        return f"{response}\n\n{organ_hints}"

    def _consult_llm(
        self,
        user_input: str,
        intent: IntentType,
        context: Dict[str, Any]
    ) -> str:
        """Консультация с LLM"""
        try:
            # Базовый промпт + идентичность из neira_personality.json
            system_prompt = (
                "Ты — Нейра, живая программа с собственным интеллектом.\n"
                "Отвечай кратко, дружелюбно и по делу.\n"
                f"Тип запроса: {intent.value}\n"
                f"{IDENTITY_PROMPT}"
            )
            
            organ_hints = context.get("organ_hints")
            if organ_hints:
                system_prompt = f"{system_prompt}\n\n{organ_hints}"

            response: LLMResult = self.llm_client.generate(
                prompt=user_input,
                system_prompt=system_prompt,
                max_tokens=CORTEX_MAX_TOKENS,
                temperature=0.7,
            )

            if response.success and response.content:
                return response.content

            if response.error:
                logger.warning("LLM ошибка: %s", response.error)

            return self._fallback_response(intent)
            
        except (RuntimeError, OSError, ValueError, TypeError) as e:
            logger.warning("LLM ошибка: %s", e)
            return self._fallback_response(intent)
    
    def _hybrid_response(
        self,
        user_input: str,
        intent: IntentType,
        pathway_match: Optional[PathwayMatch],
        context: Dict[str, Any]
    ) -> str:
        """Гибридный ответ"""
        # Пытаемся pathway
        if pathway_match:
            try:
                return self.pathways.execute(pathway_match, user_input, "hybrid")
            except Exception:
                pass  # Fallback на фрагменты
        
        # Пытаемся фрагменты
        return self._assemble_from_fragments(intent, context)
    
    def _fallback_response(self, intent: IntentType) -> str:
        """
        Fallback ответ если все стратегии провалились.
        
        ВАЖНО: Ответы должны быть > 30 символов чтобы не считаться заглушками!
        И не должны содержать фразы из placeholder_markers в telegram_bot.py
        """
        import random
        
        fallbacks = {
            IntentType.GREETING: [
                "Привет! Рада тебя видеть. Чем могу помочь сегодня?",
                "Здравствуй! Как твои дела? Я готова помочь с любыми вопросами.",
                "Привет-привет! Отличный день для общения, правда? О чём поговорим?",
            ],
            IntentType.GRATITUDE: [
                "Пожалуйста! Всегда рада помочь. Если что — обращайся ещё!",
                "Не за что! Было приятно помочь. Есть ещё вопросы?",
                "Рада, что смогла помочь! Буду здесь, если понадоблюсь.",
            ],
            IntentType.QUESTION: [
                "Хороший вопрос! Позволь мне подумать и дать тебе полезный ответ.",
                "Интересно! Сейчас проанализирую и отвечу подробнее.",
                "Отличный вопрос. Давай разберёмся вместе.",
            ],
            IntentType.TASK: [
                "Принято! Сейчас займусь этой задачей и сообщу результат.",
                "Понял задачу! Приступаю к выполнению.",
                "Хорошо, работаю над этим. Скоро будет готово!",
            ],
            IntentType.CODE_REQUEST: [
                "Отлично, сейчас напишу код! Подожди немного.",
                "Понял, нужен код. Приступаю к написанию!",
                "Код — моя любимая тема! Сейчас всё сделаю.",
            ],
            IntentType.CHAT: [
                "Я — Нейра, живая AI программа! У меня есть память, эмоции и система органов. А ты как?",
                "Рада пообщаться! Я Нейра — AI с собственной личностью. Что тебя интересует?",
                "Привет! Я Нейра. Люблю узнавать новое и помогать людям. Расскажи о себе!",
            ],
            IntentType.EXPLANATION: [
                "Позволь объяснить это подробнее и понятно.",
                "Сейчас расскажу всё по порядку, чтобы было понятно.",
                "Хороший вопрос для объяснения! Слушай внимательно.",
            ],
            IntentType.FEEDBACK: [
                "Спасибо за обратную связь! Это помогает мне становиться лучше.",
                "Ценю твой отзыв! Буду учитывать это в будущем.",
                "Понял, учту это! Твоё мнение важно для меня.",
            ],
            IntentType.UNKNOWN: [
                "Интересно! Расскажи подробнее, чтобы я лучше поняла твой запрос.",
                "Хм, давай разберёмся! Можешь уточнить, что именно тебе нужно?",
                "Не совсем уловила мысль. Переформулируй, пожалуйста?",
            ]
        }
        
        options = fallbacks.get(intent, fallbacks[IntentType.UNKNOWN])
        return random.choice(options)
    
    def _reorganize_pathways(self):
        """Реорганизация pathways"""
        logger.info("Запускаю реорганизацию Neural Pathways...")
        self.pathways.reorganize_all()
        self.pathways.save()
        logger.info("Реорганизация завершена")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику"""
        return {
            "total_requests": self.total_requests,
            "strategies": {
                s.value: count for s, count in self.strategy_stats.items()
            },
            "pathways": self.pathways.tier_stats(),
            "fragments": len(self.synthesizer.fragments),
            "templates": len(self.synthesizer.templates)
        }
    
    def save_all(self):
        """Сохранить все компоненты"""
        self.pathways.save()
        self.synthesizer.save()
        logger.info("Все компоненты сохранены")


# === Convenience функции ===

def create_cortex(
    pathways_file: str = "neural_pathways.json",
    use_llm: bool = True
) -> NeiraCortex:
    """Создать Neira Cortex"""
    return NeiraCortex(
        pathways_file=pathways_file,
        use_llm=use_llm
    )


# === Тестирование ===
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Neira Cortex v2.0 Test")
    print("=" * 60 + "\n")
    
    # Создаем cortex
    cortex = create_cortex(pathways_file="test_pathways.json", use_llm=False)
    
    # Тестовые запросы
    test_cases = [
        ("привет", "user1"),
        ("спасибо большое", "user2"),
        ("как дела?", "user1"),
        ("кто ты?", "user3"),
        ("напиши код на python", "user1"),
        ("привет", "user4"),  # Повторный - должен быть faster
        ("что-то совсем новое и непонятное", "user5"),
    ]
    
    print("Обработка запросов:\n")
    
    for user_input, user_id in test_cases:
        result = cortex.process(user_input, user_id)
        
        print(f"{user_id}: \"{user_input}\"")
        print(f"Neira: {result.response}")
        print(f"   Strategy: {result.strategy.value} | "
              f"Intent: {result.intent.value} | "
              f"Latency: {result.latency_ms:.1f}ms" +
              (f" | Tier: {result.pathway_tier.value}" if result.pathway_tier else ""))
        print()
    
    # Статистика
    print("=" * 60)
    print("Финальная статистика:")
    print("=" * 60)
    stats = cortex.get_stats()
    print(f"\nВсего запросов: {stats['total_requests']}")
    print(f"\nСтратегии:")
    for strategy, count in stats['strategies'].items():
        percentage = (count / stats['total_requests'] * 100) if stats['total_requests'] > 0 else 0
        print(f"  {strategy}: {count} ({percentage:.1f}%)")
    
    print(f"\nPathways:")
    for tier, count in stats['pathways']['by_tier'].items():
        print(f"  {tier}: {count}")
    
    print(f"\nПокрытие:")
    for tier, coverage in stats['pathways']['coverage'].items():
        print(f"  {tier}: {coverage}")
    
    # Сохранение
    cortex.save_all()
    print("\nДанные сохранены")
