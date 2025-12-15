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
import os
import time
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Импорты наших компонентов
from neural_pathways import NeuralPathwaySystem, PathwayMatch, PathwayTier
from response_synthesizer import ResponseSynthesizer, ResponseMode

# LLM fallback (опционально)
try:
    from llm_providers import LLMManager
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("⚠️ LLM providers не найдены - работаем в автономном режиме")


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
        self.llm_manager = None
        if use_llm and LLM_AVAILABLE:
            try:
                from llm_providers import create_default_manager
                self.llm_manager = create_default_manager()
                print("✅ LLM Consultant активирован (fallback)")
            except Exception as e:
                print(f"⚠️ LLM недоступен: {e}")
        
        # Статистика
        self.total_requests = 0
        self.strategy_stats = {s: 0 for s in ResponseStrategy}
        
        print("=" * 60)
        print("🧠 Neira Cortex v2.0 инициализирован")
        print("=" * 60)
        print(f"Neural Pathways: {len(self.pathways.pathways)}")
        print(f"Response Fragments: {len(self.synthesizer.fragments)}")
        print(f"Response Templates: {len(self.synthesizer.templates)}")
        print(f"LLM Consultant: {'✅ доступен' if self.llm_manager else '❌ недоступен'}")
        print("=" * 60)
    
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
        
        # 2. Ищем pathway
        pathway_match = self.pathways.match(user_input, user_id)
        
        # 3. Выбираем стратегию
        strategy = self.decision_router.route(
            intent,
            intent_confidence,
            pathway_match,
            has_llm=self.llm_manager is not None
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
                if self.llm_manager:
                    response = self._consult_llm(user_input, intent, context)
                    llm_used = True
                else:
                    # LLM недоступен - пытаемся собрать из фрагментов
                    response = self._assemble_from_fragments(intent, context)
                    
            elif strategy == ResponseStrategy.HYBRID:
                # Гибридная стратегия
                response = self._hybrid_response(user_input, intent, pathway_match, context)
            
        except Exception as e:
            print(f"⚠️ Ошибка генерации ответа: {e}")
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
            return best_fragment.apply_variables(**context)
        
        return "🤔 Интересный запрос! Дай мне секунду подумать..."
    
    def _consult_llm(
        self,
        user_input: str,
        intent: IntentType,
        context: Dict[str, Any]
    ) -> str:
        """Консультация с LLM"""
        try:
            system_prompt = (
                "Ты - Neira, живая программа с собственным интеллектом. "
                "Отвечай кратко, дружелюбно и по делу. "
                f"Тип запроса: {intent.value}"
            )
            
            if self.llm_manager:
                response = self.llm_manager.generate(
                    prompt=user_input,
                    system_prompt=system_prompt,
                    max_tokens=500,
                    temperature=0.7
                )
                
                if hasattr(response, 'content'):
                    return response.content
                elif isinstance(response, dict):
                    return response.get("text", str(response))
                else:
                    return str(response)
            else:
                return self._fallback_response(intent)
            
        except Exception as e:
            print(f"⚠️ LLM ошибка: {e}")
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
            except:
                pass
        
        # Пытаемся фрагменты
        return self._assemble_from_fragments(intent, context)
    
    def _fallback_response(self, intent: IntentType) -> str:
        """Fallback ответ если все стратегии провалились"""
        fallbacks = {
            IntentType.GREETING: "👋 Привет!",
            IntentType.GRATITUDE: "😊 Пожалуйста!",
            IntentType.QUESTION: "🤔 Интересный вопрос! Дай подумать...",
            IntentType.TASK: "Понял задачу, работаю над этим!",
            IntentType.CODE_REQUEST: "Сейчас напишу код для тебя.",
            IntentType.CHAT: "Всегда рада поболтать! 😊",
            IntentType.UNKNOWN: "Хм, интересно... Расскажи подробнее?"
        }
        return fallbacks.get(intent, "🤔 Дай подумать над этим...")
    
    def _reorganize_pathways(self):
        """Реорганизация pathways"""
        print("\n🔄 Запускаю реорганизацию Neural Pathways...")
        self.pathways.reorganize_all()
        self.pathways.save()
        print("✅ Реорганизация завершена\n")
    
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
        print("💾 Все компоненты сохранены")


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
    print("🧠 Neira Cortex v2.0 Test")
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
    
    print("📝 Обработка запросов:\n")
    
    for user_input, user_id in test_cases:
        result = cortex.process(user_input, user_id)
        
        print(f"👤 {user_id}: \"{user_input}\"")
        print(f"🤖 Neira: {result.response}")
        print(f"   📊 Strategy: {result.strategy.value} | "
              f"Intent: {result.intent.value} | "
              f"Latency: {result.latency_ms:.1f}ms" +
              (f" | Tier: {result.pathway_tier.value}" if result.pathway_tier else ""))
        print()
    
    # Статистика
    print("=" * 60)
    print("📊 Финальная статистика:")
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
    print(f"\n💾 Данные сохранены")
