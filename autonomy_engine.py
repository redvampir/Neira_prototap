"""
AutonomyEngine v1.0 — Движок автономности Neira

Phase 3: Максимальная автономность без LLM

Компоненты:
1. SemanticClusterer — группировка похожих запросов/pathways
2. QualityPredictor — предсказание качества ответа
3. ContextAwareCache — кэш с учётом контекста разговора
4. AutonomyDecider — решение: автономно или LLM?
5. SelfMonitor — отслеживание эффективности

Цель: Достичь 70%+ автономных ответов без потери качества
"""

import hashlib
import json
import logging
import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from neira_brain import get_brain, NeiraBrain
from local_embeddings import get_local_embedding, cosine_similarity, find_similar

logger = logging.getLogger("AutonomyEngine")


# ============== Semantic Clusterer ==============

class SemanticClusterer:
    """
    Группировка похожих запросов и pathways
    
    Цели:
    - Объединить дублирующиеся pathways
    - Найти паттерны в запросах
    - Улучшить coverage ответов
    """
    
    CLUSTER_SIMILARITY_THRESHOLD = 0.85
    MIN_CLUSTER_SIZE = 2
    
    def __init__(self, brain: Optional[NeiraBrain] = None):
        self.brain = brain or get_brain()
        self._clusters: Dict[str, List[str]] = {}  # cluster_id -> [pathway_ids]
        self._query_patterns: Dict[str, Dict] = {}  # pattern -> {count, examples}
        
        logger.info("🔗 SemanticClusterer инициализирован")
    
    def cluster_pathways(self) -> Dict[str, Any]:
        """
        Кластеризовать все pathways по семантическому сходству
        
        Returns:
            Статистика кластеризации
        """
        pathways = self.brain.query("SELECT * FROM pathways WHERE confidence_threshold > 0.3")
        
        if not pathways:
            return {"clusters": 0, "merged": 0}
        
        # Получаем embeddings для всех triggers
        embeddings = {}
        for p in pathways:
            triggers = json.loads(p['triggers']) if p['triggers'] else []
            if triggers:
                trigger_text = " ".join(triggers)
                emb = get_local_embedding(trigger_text)
                if emb:
                    embeddings[p['id']] = {
                        'embedding': emb,
                        'pathway': dict(p)
                    }
        
        # Кластеризуем
        clusters: List[List[str]] = []
        used = set()
        
        pathway_ids = list(embeddings.keys())
        
        for i, pid1 in enumerate(pathway_ids):
            if pid1 in used:
                continue
            
            cluster = [pid1]
            used.add(pid1)
            
            for pid2 in pathway_ids[i+1:]:
                if pid2 in used:
                    continue
                
                sim = cosine_similarity(
                    embeddings[pid1]['embedding'],
                    embeddings[pid2]['embedding']
                )
                
                if sim >= self.CLUSTER_SIMILARITY_THRESHOLD:
                    cluster.append(pid2)
                    used.add(pid2)
            
            if len(cluster) >= self.MIN_CLUSTER_SIZE:
                clusters.append(cluster)
        
        # Сохраняем кластеры и мержим если нужно
        merged_count = 0
        for i, cluster in enumerate(clusters):
            cluster_id = f"cluster_{i}"
            self._clusters[cluster_id] = cluster
            
            # Автоматический мерж если все в одном tier
            if self._should_merge(cluster, embeddings):
                self._merge_cluster(cluster, embeddings)
                merged_count += 1
        
        stats = {
            "total_pathways": len(pathways),
            "clustered": sum(len(c) for c in clusters),
            "clusters": len(clusters),
            "merged": merged_count
        }
        
        logger.info(f"🔗 Кластеризация: {stats}")
        return stats
    
    def _should_merge(self, cluster: List[str], embeddings: Dict) -> bool:
        """Проверить нужно ли объединять кластер"""
        if len(cluster) < 2:
            return False
        
        tiers = set()
        for pid in cluster:
            p = embeddings[pid]['pathway']
            tiers.add(p.get('tier', 'cold'))
        
        # Мержим только если все cold или все warm
        return len(tiers) == 1 and 'hot' not in tiers
    
    def _merge_cluster(self, cluster: List[str], embeddings: Dict):
        """Объединить pathways в кластере в один"""
        if len(cluster) < 2:
            return
        
        # Находим лучший pathway (по success_count)
        best_id = max(
            cluster, 
            key=lambda pid: embeddings[pid]['pathway'].get('success_count', 0)
        )
        
        # Объединяем triggers и success_count
        all_triggers = set()
        total_success = 0
        total_fail = 0
        
        for pid in cluster:
            p = embeddings[pid]['pathway']
            triggers = json.loads(p['triggers']) if p['triggers'] else []
            all_triggers.update(triggers)
            total_success += p.get('success_count', 0) or 0
            total_fail += p.get('failure_count', 0) or 0
        
        # Обновляем лучший
        self.brain.execute("""
            UPDATE pathways 
            SET triggers = ?,
                success_count = ?,
                failure_count = ?,
                last_used = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (json.dumps(list(all_triggers)), total_success, total_fail, best_id))
        
        # Удаляем остальные
        for pid in cluster:
            if pid != best_id:
                self.brain.execute("DELETE FROM pathways WHERE id = ?", (pid,))
        
        logger.info(f"🔗 Merged cluster: {cluster} → {best_id}")
    
    def find_query_patterns(self, min_frequency: int = 3) -> List[Dict]:
        """
        Найти частые паттерны в запросах
        
        Returns:
            Список паттернов с частотой и примерами
        """
        # Получаем недавние запросы из метрик
        recent = self.brain.query("""
            SELECT data FROM metrics 
            WHERE event_type = 'request' 
            AND timestamp > datetime('now', '-7 days')
            LIMIT 1000
        """)
        
        # Извлекаем паттерны
        patterns: Dict[str, Dict] = defaultdict(lambda: {'count': 0, 'examples': []})
        
        for row in recent:
            try:
                data = json.loads(row['data']) if row['data'] else {}
                query = data.get('message_preview', '')
                
                if len(query) < 10:
                    continue
                
                # Извлекаем паттерн (первые 3 значимых слова)
                words = re.findall(r'[а-яa-z]{4,}', query.lower())[:3]
                if len(words) >= 2:
                    pattern = " ".join(sorted(words))
                    patterns[pattern]['count'] += 1
                    if len(patterns[pattern]['examples']) < 3:
                        patterns[pattern]['examples'].append(query)
            except:
                continue
        
        # Фильтруем по частоте
        result = [
            {'pattern': p, **data}
            for p, data in patterns.items()
            if data['count'] >= min_frequency
        ]
        
        return sorted(result, key=lambda x: x['count'], reverse=True)


# ============== Quality Predictor ==============

class ResponseQuality(Enum):
    """Уровни качества ответа"""
    EXCELLENT = "excellent"  # 90%+ уверенность
    GOOD = "good"            # 70-90% уверенность
    ACCEPTABLE = "acceptable" # 50-70% уверенность
    UNCERTAIN = "uncertain"   # <50% уверенность
    UNKNOWN = "unknown"       # Нет данных


@dataclass
class QualityPrediction:
    """Предсказание качества ответа"""
    quality: ResponseQuality
    confidence: float  # 0.0 - 1.0
    source: str  # откуда предсказание
    factors: Dict[str, float] = field(default_factory=dict)
    recommendation: str = ""  # "use_autonomous" / "use_llm" / "hybrid"


class QualityPredictor:
    """
    Предсказание качества ответа ДО его генерации
    
    Факторы:
    - Похожесть на успешные запросы
    - Наличие pathway/cache
    - Сложность запроса
    - История пользователя
    """
    
    # Веса факторов
    WEIGHTS = {
        'pathway_match': 0.35,
        'cache_match': 0.25,
        'query_complexity': 0.20,
        'user_history': 0.20
    }
    
    def __init__(self, brain: Optional[NeiraBrain] = None):
        self.brain = brain or get_brain()
        self._complexity_cache: Dict[str, float] = {}
        
        logger.info("📊 QualityPredictor инициализирован")
    
    def predict(
        self, 
        query: str, 
        user_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> QualityPrediction:
        """
        Предсказать качество автономного ответа
        
        Args:
            query: Текст запроса
            user_id: ID пользователя
            context: Дополнительный контекст
            
        Returns:
            QualityPrediction с рекомендацией
        """
        factors = {}
        
        # 1. Проверяем pathway match
        factors['pathway_match'] = self._check_pathway_match(query)
        
        # 2. Проверяем cache match
        factors['cache_match'] = self._check_cache_match(query)
        
        # 3. Оцениваем сложность запроса
        factors['query_complexity'] = self._assess_complexity(query)
        
        # 4. История пользователя
        factors['user_history'] = self._check_user_history(user_id) if user_id else 0.5
        
        # Взвешенная сумма
        confidence = sum(
            factors[k] * self.WEIGHTS[k] 
            for k in self.WEIGHTS
        )
        
        # Определяем качество
        if confidence >= 0.85:
            quality = ResponseQuality.EXCELLENT
            recommendation = "use_autonomous"
        elif confidence >= 0.70:
            quality = ResponseQuality.GOOD
            recommendation = "use_autonomous"
        elif confidence >= 0.50:
            quality = ResponseQuality.ACCEPTABLE
            recommendation = "hybrid"  # Автономный + проверка
        else:
            quality = ResponseQuality.UNCERTAIN
            recommendation = "use_llm"
        
        return QualityPrediction(
            quality=quality,
            confidence=confidence,
            source="quality_predictor",
            factors=factors,
            recommendation=recommendation
        )
    
    def _check_pathway_match(self, query: str) -> float:
        """Проверить насколько хорошо запрос соответствует pathways"""
        pathways = self.brain.search_pathways(query)
        
        if not pathways:
            return 0.0
        
        best = pathways[0]
        tier = best.get('tier', 'cold')
        success = best.get('success_count', 0) or 0
        confidence = best.get('confidence', 0.5) or 0.5
        
        # Базовый score от tier
        tier_score = {'hot': 1.0, 'warm': 0.7, 'cold': 0.4}.get(tier, 0.3)
        
        # Бонус за success
        success_bonus = min(0.3, success * 0.03)
        
        return min(1.0, tier_score * confidence + success_bonus)
    
    def _check_cache_match(self, query: str) -> float:
        """Проверить есть ли похожий запрос в кэше"""
        query_emb = get_local_embedding(query)
        if not query_emb:
            return 0.0
        
        # Ищем в кэше
        cached = self.brain.query("""
            SELECT query, hit_count FROM cache 
            WHERE hit_count > 0
            ORDER BY created_at DESC
            LIMIT 100
        """)
        
        best_similarity = 0.0
        best_hit_count = 0
        
        for row in cached:
            cached_emb = get_local_embedding(row['query'])
            if cached_emb:
                sim = cosine_similarity(query_emb, cached_emb)
                if sim > best_similarity:
                    best_similarity = sim
                    best_hit_count = row['hit_count'] or 1
        
        # Конвертируем hit_count в confidence (нормализуем)
        # Чем больше обращений к кэшу, тем выше уверенность
        cache_confidence = min(1.0, best_hit_count / 10.0) * 0.7 + 0.3
        
        if best_similarity >= 0.9:
            return cache_confidence
        elif best_similarity >= 0.8:
            return cache_confidence * 0.7
        elif best_similarity >= 0.7:
            return cache_confidence * 0.4
        
        return 0.0
    
    def _assess_complexity(self, query: str) -> float:
        """
        Оценить сложность запроса (инвертировано: простой = высокий score)
        """
        query_hash = hashlib.md5(query.encode()).hexdigest()
        
        if query_hash in self._complexity_cache:
            return self._complexity_cache[query_hash]
        
        # Факторы сложности
        word_count = len(query.split())
        has_code = bool(re.search(r'```|def |class |function ', query))
        has_questions = query.count('?')
        has_multiple_topics = len(re.findall(r'(?:и|также|ещё|плюс|кроме)', query.lower()))
        
        # Длинные запросы сложнее
        length_penalty = min(1.0, word_count / 50)
        
        # Код сложнее
        code_penalty = 0.3 if has_code else 0.0
        
        # Много вопросов сложнее
        question_penalty = min(0.3, has_questions * 0.1)
        
        # Много тем сложнее
        topic_penalty = min(0.3, has_multiple_topics * 0.1)
        
        # Итоговая сложность (инвертируем: простой = 1.0)
        complexity = 1.0 - (length_penalty * 0.4 + code_penalty + question_penalty + topic_penalty)
        complexity = max(0.1, min(1.0, complexity))
        
        self._complexity_cache[query_hash] = complexity
        return complexity
    
    def _check_user_history(self, user_id: str) -> float:
        """Проверить историю успешности с этим пользователем"""
        stats = self.brain.query("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN json_extract(data, '$.success') = 1 THEN 1 ELSE 0 END) as success
            FROM metrics
            WHERE source = ?
            AND event_type = 'feedback'
            AND timestamp > datetime('now', '-30 days')
        """, (f"telegram_{user_id}",))
        
        if not stats or stats[0]['total'] == 0:
            return 0.5  # Нет данных — нейтрально
        
        total = stats[0]['total']
        success = stats[0]['success'] or 0
        
        return success / total if total > 0 else 0.5


# ============== Context-Aware Cache ==============

@dataclass
class ConversationContext:
    """Контекст текущего разговора"""
    user_id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    topics: Set[str] = field(default_factory=set)
    mood: str = "neutral"
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class ContextAwareCache:
    """
    Кэш с учётом контекста разговора
    
    Улучшения над обычным кэшем:
    - Учитывает предыдущие сообщения
    - Отслеживает темы разговора
    - Персонализирует по пользователю
    """
    
    CONTEXT_TIMEOUT_MINUTES = 30
    MAX_CONTEXT_MESSAGES = 10
    
    def __init__(self, brain: Optional[NeiraBrain] = None):
        self.brain = brain or get_brain()
        self._contexts: Dict[str, ConversationContext] = {}
        
        logger.info("🗂️ ContextAwareCache инициализирован")
    
    def get_context(self, user_id: str) -> ConversationContext:
        """Получить или создать контекст для пользователя"""
        now = datetime.now()
        
        if user_id in self._contexts:
            ctx = self._contexts[user_id]
            # Проверяем timeout
            if (now - ctx.last_activity).total_seconds() > self.CONTEXT_TIMEOUT_MINUTES * 60:
                # Контекст устарел, создаём новый
                ctx = ConversationContext(user_id=user_id)
                self._contexts[user_id] = ctx
            else:
                ctx.last_activity = now
        else:
            ctx = ConversationContext(user_id=user_id)
            self._contexts[user_id] = ctx
        
        return ctx
    
    def add_message(self, user_id: str, role: str, content: str):
        """Добавить сообщение в контекст"""
        ctx = self.get_context(user_id)
        
        ctx.messages.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        # Ограничиваем размер
        if len(ctx.messages) > self.MAX_CONTEXT_MESSAGES:
            ctx.messages = ctx.messages[-self.MAX_CONTEXT_MESSAGES:]
        
        # Извлекаем темы
        topics = self._extract_topics(content)
        ctx.topics.update(topics)
    
    def get_contextual_response(self, user_id: str, query: str) -> Optional[str]:
        """
        Найти ответ с учётом контекста разговора
        """
        ctx = self.get_context(user_id)
        
        # Формируем контекстный запрос
        context_keywords = list(ctx.topics)[:5]
        recent_messages = [m['content'] for m in ctx.messages[-3:]]
        
        # Ищем в кэше с учётом контекста
        query_emb = get_local_embedding(query)
        if not query_emb:
            return None
        
        # Бонус за совпадение тем
        cached = self.brain.query("""
            SELECT query, response, hit_count FROM cache
            WHERE hit_count > 0
            ORDER BY created_at DESC
            LIMIT 200
        """)
        
        best_match = None
        best_score = 0.0
        
        for row in cached:
            cached_emb = get_local_embedding(row['query'])
            if not cached_emb:
                continue
            
            # Базовое сходство
            base_sim = cosine_similarity(query_emb, cached_emb)
            
            # Бонус за контекст
            context_bonus = 0.0
            cached_topics = self._extract_topics(row['query'])
            common_topics = ctx.topics & cached_topics
            if common_topics:
                context_bonus = min(0.15, len(common_topics) * 0.05)
            
            # Итоговый score
            score = base_sim + context_bonus
            
            if score > best_score and score >= 0.85:
                best_score = score
                best_match = row['response']
        
        return best_match
    
    def _extract_topics(self, text: str) -> Set[str]:
        """Извлечь темы из текста"""
        topics = set()
        
        # Ключевые слова по категориям
        topic_patterns = {
            'код': r'\b(код|функци|класс|метод|python|javascript|программ)\w*',
            'ошибка': r'\b(ошибк|error|bug|исправ|fix)\w*',
            'объяснение': r'\b(объясн|расскаж|почему|зачем|как)\w*',
            'создание': r'\b(создай|сделай|напиши|генерир)\w*',
            'анализ': r'\b(анализ|разбер|провер|оцен)\w*',
        }
        
        text_lower = text.lower()
        for topic, pattern in topic_patterns.items():
            if re.search(pattern, text_lower):
                topics.add(topic)
        
        return topics
    
    def clear_context(self, user_id: str):
        """Очистить контекст пользователя"""
        if user_id in self._contexts:
            del self._contexts[user_id]


# ============== Autonomy Decider ==============

class AutonomyDecision(Enum):
    """Решение о способе ответа"""
    AUTONOMOUS = "autonomous"      # Полностью автономно
    HYBRID = "hybrid"              # Автономно + проверка LLM
    LLM_REQUIRED = "llm_required"  # Только LLM
    ESCALATE = "escalate"          # Требуется человек


@dataclass
class DecisionResult:
    """Результат решения"""
    decision: AutonomyDecision
    confidence: float
    reasoning: str
    suggested_source: str  # pathway/cache/llm
    fallback_enabled: bool = True


class AutonomyDecider:
    """
    Центральный компонент принятия решений
    
    Решает: можно ли ответить автономно или нужен LLM?
    
    Учитывает:
    - QualityPrediction
    - Тип запроса
    - Риски неправильного ответа
    - Исторические данные
    """
    
    # Типы запросов где автономность рискованна
    HIGH_RISK_PATTERNS = [
        r'\b(удали|удалить|remove|delete)\b.*\b(файл|данны|всё)\b',
        r'\b(деньг|оплат|банк|карт)\w*',
        r'\b(парол|secret|key|token|api.?key)\w*',
        r'\b(sudo|admin|root|chmod)\b',
    ]
    
    # Типы запросов идеальные для автономности
    SAFE_PATTERNS = [
        r'^привет\b|^здравствуй',
        r'^как дела|^что нового',
        r'^спасибо|^благодарю',
        r'^помощь$|^help$',
        r'^что (ты )?(умеешь|можешь)',
    ]
    
    def __init__(
        self,
        quality_predictor: Optional[QualityPredictor] = None,
        brain: Optional[NeiraBrain] = None
    ):
        self.brain = brain or get_brain()
        self.quality_predictor = quality_predictor or QualityPredictor(self.brain)
        
        logger.info("🤔 AutonomyDecider инициализирован")
    
    def decide(
        self,
        query: str,
        user_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> DecisionResult:
        """
        Принять решение о способе ответа
        """
        query_lower = query.lower().strip()
        
        # 1. Проверяем safe patterns (быстрый autonomous)
        for pattern in self.SAFE_PATTERNS:
            if re.match(pattern, query_lower):
                # Не считать короткие приветствия "безопасным" для длинных/содержательных вопросов.
                # Если сообщение длиннее 3 слов или содержит вопросительное слово/знак — требуем LLM.
                tokens = query_lower.split()
                if len(tokens) > 3 or '?' in query_lower or query_lower.startswith('как '):
                    # не применять быстрый autonomous, продолжим дальнейшую логику
                    break
                return DecisionResult(
                    decision=AutonomyDecision.AUTONOMOUS,
                    confidence=0.95,
                    reasoning="Safe pattern match",
                    suggested_source="pathway"
                )
        
        # 2. Проверяем high-risk patterns (требуется LLM)
        for pattern in self.HIGH_RISK_PATTERNS:
            if re.search(pattern, query_lower):
                return DecisionResult(
                    decision=AutonomyDecision.LLM_REQUIRED,
                    confidence=0.9,
                    reasoning="High-risk pattern detected",
                    suggested_source="llm",
                    fallback_enabled=False
                )
        
        # 3. Получаем quality prediction
        prediction = self.quality_predictor.predict(query, user_id, context)
        
        # 4. Принимаем решение на основе prediction
        if prediction.quality == ResponseQuality.EXCELLENT:
            decision = AutonomyDecision.AUTONOMOUS
            suggested = "pathway" if prediction.factors['pathway_match'] > 0.7 else "cache"
        
        elif prediction.quality == ResponseQuality.GOOD:
            decision = AutonomyDecision.AUTONOMOUS
            suggested = "cache" if prediction.factors['cache_match'] > 0.5 else "pathway"
        
        elif prediction.quality == ResponseQuality.ACCEPTABLE:
            decision = AutonomyDecision.HYBRID
            suggested = "pathway"
        
        else:
            decision = AutonomyDecision.LLM_REQUIRED
            suggested = "llm"
        
        return DecisionResult(
            decision=decision,
            confidence=prediction.confidence,
            reasoning=f"Quality: {prediction.quality.value}, factors: {prediction.factors}",
            suggested_source=suggested
        )


# ============== Self Monitor ==============

@dataclass
class AutonomyMetrics:
    """Метрики автономности"""
    total_requests: int = 0
    autonomous_responses: int = 0
    llm_responses: int = 0
    hybrid_responses: int = 0
    
    # Качество
    positive_feedback: int = 0
    negative_feedback: int = 0
    
    # По источникам
    pathway_hits: int = 0
    cache_hits: int = 0
    
    # Время
    avg_autonomous_latency_ms: float = 0.0
    avg_llm_latency_ms: float = 0.0
    
    @property
    def autonomy_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.autonomous_responses + self.hybrid_responses * 0.5) / self.total_requests
    
    @property
    def quality_score(self) -> float:
        total_feedback = self.positive_feedback + self.negative_feedback
        if total_feedback == 0:
            return 0.5
        return self.positive_feedback / total_feedback


class SelfMonitor:
    """
    Мониторинг эффективности автономности
    
    Отслеживает:
    - % автономных ответов
    - Качество (через feedback)
    - Latency
    - Тренды
    """
    
    TARGET_AUTONOMY_RATE = 0.70  # Цель: 70%
    MIN_QUALITY_SCORE = 0.80     # Минимум: 80% положительных
    
    def __init__(self, brain: Optional[NeiraBrain] = None):
        self.brain = brain or get_brain()
        self._session_metrics = AutonomyMetrics()
        self._latencies: List[Tuple[str, float]] = []  # (source, ms)
        
        logger.info("📈 SelfMonitor инициализирован")
    
    def record_response(
        self,
        source: str,
        latency_ms: float,
        was_autonomous: bool
    ):
        """Записать информацию об ответе"""
        self._session_metrics.total_requests += 1
        
        if was_autonomous:
            self._session_metrics.autonomous_responses += 1
            if 'pathway' in source:
                self._session_metrics.pathway_hits += 1
            elif 'cache' in source:
                self._session_metrics.cache_hits += 1
        else:
            self._session_metrics.llm_responses += 1
        
        self._latencies.append((source, latency_ms))
        
        # Обновляем средние
        autonomous_latencies = [l for s, l in self._latencies if 'llm' not in s]
        llm_latencies = [l for s, l in self._latencies if 'llm' in s]
        
        if autonomous_latencies:
            self._session_metrics.avg_autonomous_latency_ms = sum(autonomous_latencies) / len(autonomous_latencies)
        if llm_latencies:
            self._session_metrics.avg_llm_latency_ms = sum(llm_latencies) / len(llm_latencies)
        
        # Записываем в БД
        self.brain.record_metric('response', source, {
            'latency_ms': latency_ms,
            'autonomous': was_autonomous
        })
    
    def record_feedback(self, positive: bool):
        """Записать feedback"""
        if positive:
            self._session_metrics.positive_feedback += 1
        else:
            self._session_metrics.negative_feedback += 1
    
    def get_metrics(self) -> AutonomyMetrics:
        """Получить текущие метрики"""
        return self._session_metrics
    
    def get_recommendations(self) -> List[str]:
        """Получить рекомендации по улучшению"""
        recommendations = []
        metrics = self._session_metrics
        
        # Проверяем autonomy rate
        if metrics.autonomy_rate < self.TARGET_AUTONOMY_RATE:
            gap = self.TARGET_AUTONOMY_RATE - metrics.autonomy_rate
            recommendations.append(
                f"⚠️ Autonomy rate ({metrics.autonomy_rate:.1%}) ниже цели ({self.TARGET_AUTONOMY_RATE:.0%}). "
                f"Рекомендация: добавить больше pathways или улучшить кэширование."
            )
        
        # Проверяем качество
        if metrics.quality_score < self.MIN_QUALITY_SCORE and metrics.total_requests > 10:
            recommendations.append(
                f"⚠️ Quality score ({metrics.quality_score:.1%}) ниже минимума ({self.MIN_QUALITY_SCORE:.0%}). "
                f"Рекомендация: пересмотреть pathways с низким success_count."
            )
        
        # Проверяем latency
        if metrics.avg_autonomous_latency_ms > 500:
            recommendations.append(
                f"⚠️ Автономная latency ({metrics.avg_autonomous_latency_ms:.0f}ms) высокая. "
                f"Рекомендация: оптимизировать поиск pathways."
            )
        
        if not recommendations:
            recommendations.append(
                f"✅ Система работает хорошо: autonomy={metrics.autonomy_rate:.1%}, "
                f"quality={metrics.quality_score:.1%}"
            )
        
        return recommendations
    
    def get_dashboard(self) -> Dict[str, Any]:
        """Получить данные для дашборда"""
        metrics = self._session_metrics
        
        return {
            "autonomy": {
                "rate": f"{metrics.autonomy_rate:.1%}",
                "target": f"{self.TARGET_AUTONOMY_RATE:.0%}",
                "status": "✅" if metrics.autonomy_rate >= self.TARGET_AUTONOMY_RATE else "⚠️"
            },
            "quality": {
                "score": f"{metrics.quality_score:.1%}",
                "positive": metrics.positive_feedback,
                "negative": metrics.negative_feedback
            },
            "performance": {
                "total_requests": metrics.total_requests,
                "autonomous": metrics.autonomous_responses,
                "llm": metrics.llm_responses,
                "pathway_hits": metrics.pathway_hits,
                "cache_hits": metrics.cache_hits
            },
            "latency": {
                "autonomous_avg_ms": round(metrics.avg_autonomous_latency_ms, 1),
                "llm_avg_ms": round(metrics.avg_llm_latency_ms, 1)
            },
            "recommendations": self.get_recommendations()
        }


# ============== Main Autonomy Engine ==============

class AutonomyEngine:
    """
    Главный движок автономности
    
    Объединяет все компоненты Phase 3
    """
    
    def __init__(self, brain: Optional[NeiraBrain] = None):
        self.brain = brain or get_brain()
        
        # Компоненты
        self.clusterer = SemanticClusterer(self.brain)
        self.quality_predictor = QualityPredictor(self.brain)
        self.context_cache = ContextAwareCache(self.brain)
        self.decider = AutonomyDecider(self.quality_predictor, self.brain)
        self.monitor = SelfMonitor(self.brain)
        
        logger.info("🚀 AutonomyEngine v1.0 инициализирован")
    
    def should_respond_autonomous(
        self,
        query: str,
        user_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> DecisionResult:
        """
        Решить: отвечать автономно или использовать LLM?
        """
        return self.decider.decide(query, user_id, context)
    
    def get_contextual_response(
        self,
        query: str,
        user_id: str
    ) -> Optional[str]:
        """
        Получить ответ с учётом контекста разговора
        """
        return self.context_cache.get_contextual_response(user_id, query)
    
    def update_context(self, user_id: str, role: str, content: str):
        """Обновить контекст разговора"""
        self.context_cache.add_message(user_id, role, content)
    
    def record_response(
        self,
        source: str,
        latency_ms: float,
        was_autonomous: bool
    ):
        """Записать метрику ответа"""
        self.monitor.record_response(source, latency_ms, was_autonomous)
    
    def record_feedback(self, positive: bool):
        """Записать feedback"""
        self.monitor.record_feedback(positive)
    
    def optimize(self) -> Dict[str, Any]:
        """
        Запустить оптимизацию автономности
        
        - Кластеризация pathways
        - Поиск паттернов
        - Рекомендации
        """
        results = {}
        
        # 1. Кластеризация
        results['clustering'] = self.clusterer.cluster_pathways()
        
        # 2. Паттерны
        results['patterns'] = self.clusterer.find_query_patterns()[:10]
        
        # 3. Dashboard
        results['dashboard'] = self.monitor.get_dashboard()
        
        logger.info(f"🔧 Оптимизация завершена: {results}")
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить полную статистику"""
        return self.monitor.get_dashboard()


# ============== Global Instance ==============

_autonomy_engine: Optional[AutonomyEngine] = None


def get_autonomy_engine() -> AutonomyEngine:
    """Получить глобальный экземпляр AutonomyEngine"""
    global _autonomy_engine
    if _autonomy_engine is None:
        _autonomy_engine = AutonomyEngine()
    return _autonomy_engine


# ============== Test ==============

if __name__ == "__main__":
    import os
    os.environ["NEIRA_LOCAL_EMBEDDINGS"] = "true"
    
    print("🧪 Тест AutonomyEngine v1.0")
    print("=" * 60)
    
    engine = get_autonomy_engine()
    
    # Тест 1: Safe pattern
    decision = engine.should_respond_autonomous("Привет!")
    print(f"\n1. 'Привет!' → {decision.decision.value} (conf: {decision.confidence:.2f})")
    print(f"   Reasoning: {decision.reasoning}")
    
    # Тест 2: High-risk pattern  
    decision = engine.should_respond_autonomous("Удали все файлы в папке")
    print(f"\n2. 'Удали все файлы' → {decision.decision.value} (conf: {decision.confidence:.2f})")
    print(f"   Reasoning: {decision.reasoning}")
    
    # Тест 3: Обычный запрос
    decision = engine.should_respond_autonomous("Как написать функцию на Python?")
    print(f"\n3. 'Как написать функцию' → {decision.decision.value} (conf: {decision.confidence:.2f})")
    print(f"   Reasoning: {decision.reasoning}")
    
    # Тест 4: Контекст
    engine.update_context("user123", "user", "Расскажи про Python")
    engine.update_context("user123", "assistant", "Python — это язык программирования...")
    ctx = engine.context_cache.get_context("user123")
    print(f"\n4. Контекст user123: {len(ctx.messages)} сообщений, темы: {ctx.topics}")
    
    # Тест 5: Dashboard
    engine.record_response("pathway:test", 50.0, True)
    engine.record_response("llm", 2000.0, False)
    engine.record_feedback(True)
    
    print("\n5. Dashboard:")
    dashboard = engine.get_stats()
    for key, value in dashboard.items():
        print(f"   {key}: {value}")
    
    print("\n🎉 Тесты завершены!")
