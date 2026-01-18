"""
ResponseEngine v1.0 — Движок автономных ответов

Включает:
- ResponseCache: Кэширование ответов LLM
- PathwayAutoGenerator: Автоматическое создание pathways из частых запросов
- ResponseVariator: Вариации ответов без LLM

Цель: Максимальная автономность — минимум обращений к LLM
"""

import hashlib
import json
import logging
import random
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from neira_brain import get_brain, NeiraBrain
from local_embeddings import get_local_embedding, cosine_similarity, find_similar

logger = logging.getLogger("ResponseEngine")


# ============== Response Cache ==============

class ResponseCache:
    """
    Кэширование ответов LLM
    
    - Семантический поиск по похожим запросам
    - TTL для устаревших записей
    - Адаптивный TTL на основе качества ответа
    """
    
    DEFAULT_TTL_HOURS = 24 * 7  # 1 неделя по умолчанию
    MIN_SIMILARITY = 0.85  # Минимальное сходство для использования кэша
    
    def __init__(self, brain: Optional[NeiraBrain] = None):
        self.brain = brain or get_brain()
        self._embedding_cache: Dict[str, Tuple[str, List[float]]] = {}  # query_hash -> (query, embedding)
        
        # Загружаем embeddings для существующих записей кэша
        self._load_embeddings()
        
        logger.info(f"📦 ResponseCache инициализирован: {len(self._embedding_cache)} записей")
    
    def _load_embeddings(self):
        """Загрузить embeddings для кэшированных запросов"""
        # Получаем все записи кэша из БД
        cache_entries = self.brain.cache_search("")  # Пустой поиск = все записи
        
        for entry in cache_entries:
            query = entry.get('query', '')
            if query:
                emb = get_local_embedding(query)
                if emb:
                    query_hash = self._hash_query(query)
                    self._embedding_cache[query_hash] = (query, emb)
    
    def _hash_query(self, query: str) -> str:
        """Хэш запроса"""
        normalized = ' '.join(query.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def get(self, query: str) -> Optional[str]:
        """
        Получить ответ из кэша
        
        Использует семантический поиск для нахождения похожих запросов
        """
        query_emb = get_local_embedding(query)
        if not query_emb:
            return None
        
        # Ищем похожие запросы
        candidates = list(self._embedding_cache.values())
        if not candidates:
            return None
        
        similar = find_similar(query, candidates, top_k=1, threshold=self.MIN_SIMILARITY)
        
        if similar:
            matched_query, score = similar[0]
            
            # Проверяем TTL
            entry = self.brain.cache_get(matched_query)
            if entry:
                # Проверяем не истёк ли TTL
                created_at = datetime.fromisoformat(entry['created_at'])
                ttl_hours = entry.get('ttl_hours', self.DEFAULT_TTL_HOURS)
                
                if datetime.now() - created_at < timedelta(hours=ttl_hours):
                    # Обновляем статистику
                    self.brain.record_metric('cache_hit', 'system', {
                        'query': query[:100],
                        'matched': matched_query[:100],
                        'similarity': score
                    })
                    
                    return entry['response']
        
        return None
    
    def store(
        self,
        query: str,
        response: str,
        category: str = "general",
        quality_score: float = 0.7,
        ttl_hours: Optional[int] = None
    ):
        """
        Сохранить ответ в кэш
        
        Args:
            query: Запрос пользователя
            response: Ответ LLM
            category: Категория запроса
            quality_score: Оценка качества (0-1), влияет на TTL
            ttl_hours: Явный TTL или адаптивный на основе quality
        """
        # Адаптивный TTL: качественные ответы живут дольше
        if ttl_hours is None:
            ttl_hours = int(self.DEFAULT_TTL_HOURS * (0.5 + quality_score))
        
        # Сохраняем в БД
        self.brain.cache_store(
            query=query,
            response=response,
            category=category,
            ttl_hours=ttl_hours,
            metadata={'quality_score': quality_score}
        )
        
        # Обновляем embedding cache
        emb = get_local_embedding(query)
        if emb:
            query_hash = self._hash_query(query)
            self._embedding_cache[query_hash] = (query, emb)
        
        logger.debug(f"💾 Cached: '{query[:50]}...' (TTL: {ttl_hours}h)")
    
    def invalidate(self, query: str):
        """Инвалидировать запись кэша"""
        query_hash = self._hash_query(query)
        if query_hash in self._embedding_cache:
            del self._embedding_cache[query_hash]
        
        # TODO: Удалить из БД когда будет метод
        logger.debug(f"🗑️ Invalidated: '{query[:50]}...'")
    
    def get_stats(self) -> Dict[str, Any]:
        """Статистика кэша"""
        return {
            'entries': len(self._embedding_cache),
            'memory_mb': len(str(self._embedding_cache)) / 1024 / 1024
        }


# ============== Pathway Auto Generator ==============

class PathwayAutoGenerator:
    """
    Автоматическое создание pathways из частых запросов
    
    Логика:
    1. Отслеживаем все запросы
    2. Группируем похожие
    3. Если группа достигает порога — создаём pathway
    4. Pathway с шаблоном ответа на основе успешных ответов группы
    """
    
    MIN_GROUP_SIZE = 3  # Минимум запросов для создания pathway
    SIMILARITY_THRESHOLD = 0.8  # Порог сходства для группировки
    
    def __init__(self, brain: Optional[NeiraBrain] = None):
        self.brain = brain or get_brain()
        self._pending_queries: List[Dict[str, Any]] = []  # Ожидающие группировки
        
        logger.info("🔧 PathwayAutoGenerator инициализирован")
    
    def track_query(self, query: str, response: str, success: bool = True):
        """
        Отслеживать запрос для автоматического создания pathway
        """
        if not success or len(query) < 10 or len(response) < 20:
            return
        
        emb = get_local_embedding(query)
        if not emb:
            return
        
        self._pending_queries.append({
            'query': query,
            'response': response,
            'embedding': emb,
            'timestamp': datetime.now().isoformat()
        })
        
        # Периодически проверяем на создание pathways
        if len(self._pending_queries) >= self.MIN_GROUP_SIZE * 2:
            self._try_generate_pathways()
    
    def _try_generate_pathways(self):
        """Попытаться сгенерировать pathways из накопленных запросов"""
        if len(self._pending_queries) < self.MIN_GROUP_SIZE:
            return
        
        # Группируем похожие запросы
        groups: List[List[Dict]] = []
        used = set()
        
        for i, q1 in enumerate(self._pending_queries):
            if i in used:
                continue
            
            group = [q1]
            used.add(i)
            
            for j, q2 in enumerate(self._pending_queries[i+1:], start=i+1):
                if j in used:
                    continue
                
                similarity = cosine_similarity(q1['embedding'], q2['embedding'])
                if similarity >= self.SIMILARITY_THRESHOLD:
                    group.append(q2)
                    used.add(j)
            
            if len(group) >= self.MIN_GROUP_SIZE:
                groups.append(group)
        
        # Создаём pathways из групп
        for group in groups:
            self._create_pathway_from_group(group)
        
        # Очищаем обработанные
        self._pending_queries = [q for i, q in enumerate(self._pending_queries) if i not in used]
        
        logger.info(f"🔧 Создано {len(groups)} pathways, осталось pending: {len(self._pending_queries)}")
    
    def _create_pathway_from_group(self, group: List[Dict]):
        """Создать pathway из группы похожих запросов"""
        if not group:
            return
        
        # Извлекаем ключевые слова из всех запросов группы
        all_words: Dict[str, int] = defaultdict(int)
        for item in group:
            words = re.findall(r'[а-яa-z]{3,}', item['query'].lower())
            for word in words:
                all_words[word] += 1
        
        # Берём самые частые как триггеры
        common_words = sorted(all_words.items(), key=lambda x: x[1], reverse=True)[:5]
        triggers = [w for w, _ in common_words if _ >= 2]
        
        if len(triggers) < 2:
            return
        
        # Берём самый подходящий ответ как шаблон
        # (пока просто первый, в будущем — на основе оценок)
        template_response = group[0]['response']
        
        # Генерируем ID
        pathway_id = f"auto_{hashlib.sha256('_'.join(triggers).encode()).hexdigest()[:8]}"
        
        # Проверяем что такой pathway ещё не существует
        existing = self.brain.get_pathway(pathway_id)
        if existing:
            return
        
        # Создаём
        pathway = {
            'id': pathway_id,
            'triggers': triggers,
            'response_template': template_response,
            'category': 'auto_generated',
            'tier': 'warm',
            'success_count': len(group),
            'fail_count': 0,
            'metadata': {
                'source_queries': [g['query'][:100] for g in group[:3]],
                'auto_generated': True,
                'created_at': datetime.now().isoformat()
            }
        }
        
        self.brain.save_pathway(pathway)
        
        logger.info(f"✨ Auto-pathway создан: {pathway_id} (triggers: {triggers})")
    
    def force_generate(self):
        """Принудительная генерация pathways"""
        self._try_generate_pathways()
    
    def find_matching_pathway(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Найти pathway, соответствующий запросу
        
        Args:
            query: Текст запроса
            
        Returns:
            Словарь pathway или None
        """
        query_lower = query.lower()
        query_words = set(re.findall(r'[а-яa-z]{3,}', query_lower))
        
        if not query_words:
            return None
        
        # Получаем все pathways из БД
        pathways = self.brain.query(
            "SELECT * FROM pathways WHERE confidence > 0.1"
        )
        
        best_match = None
        best_score = 0.0
        
        for row in pathways:
            try:
                triggers = json.loads(row['triggers']) if row['triggers'] else []
                if not triggers:
                    continue
                
                # Считаем сколько триггеров совпадает
                triggers_set = set(t.lower() for t in triggers)
                matches = len(query_words & triggers_set)
                
                if matches == 0:
                    continue
                
                # Score на основе процента совпадений
                score = matches / len(triggers_set)
                
                # Бонус за tier
                tier = row.get('tier', 'cold')
                tier_bonus = {'hot': 0.3, 'warm': 0.15, 'cold': 0.0}.get(tier, 0.0)
                score += tier_bonus
                
                # Бонус за success_count
                success = row.get('success_count', 0) or 0
                if success > 0:
                    score += min(0.2, success * 0.02)
                
                if score > best_score:
                    best_score = score
                    best_match = dict(row)
                    
            except Exception as e:
                logger.warning(f"Ошибка парсинга pathway: {e}")
                continue
        
        if best_match and best_score >= 0.5:
            logger.debug(f"🎯 Найден pathway '{best_match.get('id')}' (score: {best_score:.2f})")
            return best_match
        
        return None
    
    def maybe_create_pathway(
        self, 
        query: str, 
        response: str, 
        success: bool = True
    ) -> Optional[str]:
        """
        Создать pathway если запрос достаточно специфичный
        
        Args:
            query: Текст запроса
            response: Текст ответа
            success: Был ли ответ успешным
            
        Returns:
            ID созданного pathway или None
        """
        if not success or len(query) < 15 or len(response) < 30:
            return None
        
        # Извлекаем ключевые слова
        words = re.findall(r'[а-яa-z]{4,}', query.lower())
        if len(words) < 2:
            return None
        
        # Считаем частоту слов
        word_freq: Dict[str, int] = defaultdict(int)
        for w in words:
            word_freq[w] += 1
        
        # Берём уникальные слова как триггеры
        triggers = [w for w in words if word_freq[w] <= 2][:5]
        
        if len(triggers) < 2:
            return None
        
        # Проверяем что похожего pathway нет
        existing = self.find_matching_pathway(query)
        if existing:
            return None
        
        # Создаём новый pathway
        pathway_id = f"user_{hashlib.sha256(query[:50].encode()).hexdigest()[:8]}"
        
        pathway = {
            'id': pathway_id,
            'triggers': triggers,
            'response_template': response,
            'category': 'user_generated',
            'tier': 'cold',  # Новые pathways начинают с cold
            'success_count': 1,
            'fail_count': 0,
            'confidence': 0.6,
            'metadata': {
                'source_query': query[:200],
                'created_at': datetime.now().isoformat(),
                'source': 'positive_feedback'
            }
        }
        
        self.brain.save_pathway(pathway)
        logger.info(f"✨ User-pathway создан: {pathway_id} (triggers: {triggers[:3]}...)")
        
        return pathway_id


# ============== Pathway Tier Manager ==============

class PathwayTierManager:
    """
    Управление тирами pathways (hot/warm/cold)
    
    Логика продвижения:
    - cold → warm: success_count >= 3 И confidence >= 0.6
    - warm → hot: success_count >= 10 И confidence >= 0.8 И fail_count < success_count/5
    - hot → warm: fail_count > success_count/3 ИЛИ confidence < 0.7
    - warm → cold: fail_count > success_count/2 ИЛИ confidence < 0.5
    
    Hot pathways используются первыми (быстрейший ответ)
    """
    
    # Пороги для продвижения
    COLD_TO_WARM_SUCCESS = 3
    COLD_TO_WARM_CONFIDENCE = 0.6
    
    WARM_TO_HOT_SUCCESS = 10
    WARM_TO_HOT_CONFIDENCE = 0.8
    WARM_TO_HOT_FAIL_RATIO = 0.2  # fail_count < success * ratio
    
    # Пороги для понижения
    HOT_TO_WARM_FAIL_RATIO = 0.33
    HOT_TO_WARM_MIN_CONFIDENCE = 0.7
    
    WARM_TO_COLD_FAIL_RATIO = 0.5
    WARM_TO_COLD_MIN_CONFIDENCE = 0.5
    
    def __init__(self, brain: Optional[NeiraBrain] = None):
        self.brain = brain or get_brain()
        logger.info("📊 PathwayTierManager инициализирован")
    
    def evaluate_pathway(self, pathway_id: str) -> Optional[str]:
        """
        Оценить pathway и определить нужно ли изменить tier
        
        Returns:
            Новый tier ('hot', 'warm', 'cold') или None если изменений не нужно
        """
        pathway = self.brain.get_pathway(pathway_id)
        if not pathway:
            return None
        
        current_tier = pathway.get('tier', 'cold')
        success = pathway.get('success_count', 0) or 0
        fail = pathway.get('fail_count', 0) or 0
        confidence = pathway.get('confidence', 0.5) or 0.5
        
        new_tier = self._calculate_new_tier(current_tier, success, fail, confidence)
        
        if new_tier != current_tier:
            self._update_tier(pathway_id, new_tier)
            return new_tier
        
        return None
    
    def _calculate_new_tier(
        self, 
        current: str, 
        success: int, 
        fail: int, 
        confidence: float
    ) -> str:
        """Вычислить новый tier на основе метрик"""
        
        # Проверяем понижение сначала (приоритет безопасности)
        if current == 'hot':
            # Hot → Warm: слишком много ошибок или низкая confidence
            if success > 0 and fail > success * self.HOT_TO_WARM_FAIL_RATIO:
                return 'warm'
            if confidence < self.HOT_TO_WARM_MIN_CONFIDENCE:
                return 'warm'
        
        if current == 'warm':
            # Warm → Cold: очень много ошибок или очень низкая confidence
            if success > 0 and fail > success * self.WARM_TO_COLD_FAIL_RATIO:
                return 'cold'
            if confidence < self.WARM_TO_COLD_MIN_CONFIDENCE:
                return 'cold'
        
        # Проверяем повышение
        if current == 'cold':
            # Cold → Warm
            if success >= self.COLD_TO_WARM_SUCCESS and confidence >= self.COLD_TO_WARM_CONFIDENCE:
                return 'warm'
        
        if current == 'warm':
            # Warm → Hot
            can_promote = (
                success >= self.WARM_TO_HOT_SUCCESS and
                confidence >= self.WARM_TO_HOT_CONFIDENCE and
                (fail == 0 or fail < success * self.WARM_TO_HOT_FAIL_RATIO)
            )
            if can_promote:
                return 'hot'
        
        return current
    
    def _update_tier(self, pathway_id: str, new_tier: str):
        """Обновить tier в БД"""
        self.brain.execute("""
            UPDATE pathways 
            SET tier = ?, last_used = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_tier, pathway_id))
        
        logger.info(f"🎚️ Pathway '{pathway_id}' → tier: {new_tier}")
    
    def evaluate_all(self) -> Dict[str, int]:
        """
        Оценить все pathways и обновить тиры
        
        Returns:
            Статистика изменений {promoted: N, demoted: M}
        """
        stats = {'promoted': 0, 'demoted': 0, 'unchanged': 0}
        
        pathways = self.brain.query("SELECT id, tier FROM pathways")
        
        for row in pathways:
            old_tier = row['tier']
            new_tier = self.evaluate_pathway(row['id'])
            
            if new_tier is None:
                stats['unchanged'] += 1
            elif self._tier_rank(new_tier) > self._tier_rank(old_tier):
                stats['promoted'] += 1
            else:
                stats['demoted'] += 1
        
        logger.info(
            f"📊 Tier evaluation: promoted={stats['promoted']}, "
            f"demoted={stats['demoted']}, unchanged={stats['unchanged']}"
        )
        
        return stats
    
    def _tier_rank(self, tier: str) -> int:
        """Числовой ранг тира для сравнения"""
        return {'cold': 0, 'warm': 1, 'hot': 2}.get(tier, 0)
    
    def get_tier_stats(self) -> Dict[str, int]:
        """Получить статистику по тирам"""
        result = self.brain.query("""
            SELECT tier, COUNT(*) as count 
            FROM pathways 
            GROUP BY tier
        """)
        
        stats = {'hot': 0, 'warm': 0, 'cold': 0}
        for row in result:
            tier = row['tier'] or 'cold'
            stats[tier] = row['count']
        
        return stats


# ============== Response Variator ==============

class ResponseVariator:
    """
    Вариации ответов без обращения к LLM
    
    Использует:
    - Синонимы приветствий/прощаний
    - Вариации структуры предложений
    - Эмоциональные маркеры
    - Персонализацию
    """
    
    # Синонимы для вариаций
    GREETING_VARIANTS = [
        "Привет!", "Здравствуй!", "Приветствую!", "Добрый день!",
        "Хэй!", "Рада тебя видеть!", "👋 Привет!"
    ]
    
    POSITIVE_MARKERS = [
        "✨", "🎉", "👍", "💫", "🌟", "😊", "🙂"
    ]
    
    THINKING_PHRASES = [
        "Хм, интересно...", "Дай подумать...", "Так, давай разберёмся...",
        "Смотри...", "Вот что я думаю..."
    ]
    
    CONFIRMATION_PHRASES = [
        "Готово!", "Сделано!", "Вот, держи!", "Пожалуйста!",
        "Вот что получилось:", "Готово! 🎉"
    ]
    
    TRANSITIONS = [
        "Кстати,", "К слову,", "Между прочим,", "А ещё"
    ]
    
    # Шаблоны с переменными
    VARIABLE_PATTERNS = {
        '{user_name}': lambda ctx: ctx.get('user_name', 'друг'),
        '{time_greeting}': lambda ctx: ResponseVariator._time_greeting(),
        '{random_emoji}': lambda ctx: random.choice(['😊', '🙂', '👋', '✨', '💫']),
        '{random_positive}': lambda ctx: random.choice(ResponseVariator.POSITIVE_MARKERS),
    }
    
    @staticmethod
    def _time_greeting() -> str:
        """Приветствие в зависимости от времени суток"""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "Доброе утро"
        elif 12 <= hour < 17:
            return "Добрый день"
        elif 17 <= hour < 22:
            return "Добрый вечер"
        else:
            return "Доброй ночи"
    
    @classmethod
    def variate(cls, response: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Добавить вариации к ответу
        
        Args:
            response: Исходный ответ
            context: Контекст (user_name, etc)
        
        Returns:
            Вариированный ответ
        """
        if not response:
            return response
        
        context = context or {}
        result = response
        
        # Заменяем переменные
        for pattern, replacer in cls.VARIABLE_PATTERNS.items():
            if pattern in result:
                result = result.replace(pattern, replacer(context))
        
        return result
    
    @classmethod
    def generate_greeting(cls, user_name: Optional[str] = None) -> str:
        """Сгенерировать приветствие"""
        greeting = random.choice(cls.GREETING_VARIANTS)
        time_part = cls._time_greeting()
        
        if user_name:
            templates = [
                f"{greeting} {user_name}!",
                f"{time_part}, {user_name}!",
                f"👋 {user_name}! {greeting}"
            ]
        else:
            templates = [
                greeting,
                f"{time_part}!",
                f"👋 {greeting}"
            ]
        
        return random.choice(templates)
    
    @classmethod
    def add_personality(cls, response: str, mood: str = "neutral") -> str:
        """
        Добавить личность к ответу
        
        Args:
            response: Ответ
            mood: neutral, happy, curious, helpful
        """
        if mood == "happy":
            if not any(e in response for e in cls.POSITIVE_MARKERS):
                response = f"{random.choice(cls.POSITIVE_MARKERS)} {response}"
        
        elif mood == "curious":
            if random.random() > 0.7:
                response = f"{random.choice(cls.THINKING_PHRASES)} {response}"
        
        elif mood == "helpful":
            if random.random() > 0.5 and not response.endswith(('!', '?')):
                response = f"{response} {random.choice(cls.CONFIRMATION_PHRASES)}"
        
        return response


# ============== Response Engine (Main Interface) ==============

class ResponseEngine:
    """
    Главный движок для автономных ответов
    
    Объединяет: Cache + AutoGenerator + Variator + TierManager + Pathways
    """
    
    def __init__(self, brain: Optional[NeiraBrain] = None):
        self.brain = brain or get_brain()
        self.cache = ResponseCache(self.brain)
        self.auto_gen = PathwayAutoGenerator(self.brain)
        self.tier_manager = PathwayTierManager(self.brain)
        self.variator = ResponseVariator()
        
        # Алиас для доступа извне
        self.pathway_generator = self.auto_gen
        
        logger.info("🚀 ResponseEngine инициализирован")
    
    def try_respond_autonomous(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[str], str]:
        """
        Попытаться ответить автономно (без LLM)
        
        Returns:
            (ответ или None, источник ответа)
        """
        user_context = user_context or {}
        
        # 1. Проверяем pathways (hot tier — моментальный ответ)
        pathways = self.brain.search_pathways(query)
        for p in pathways:
            if p.get('tier') == 'hot' and p.get('success_count', 0) > 5:
                response = self.variator.variate(p['response_template'], user_context)
                
                # Записываем использование
                self.brain.record_metric('pathway_hit', 'system', {
                    'pathway_id': p['id'],
                    'query': query[:100]
                })
                
                return response, f"pathway:{p['id']}"
        
        # 2. Проверяем кэш
        cached = self.cache.get(query)
        if cached:
            response = self.variator.variate(cached, user_context)
            return response, "cache"
        
        # 3. Проверяем warm pathways
        for p in pathways:
            if p.get('tier') == 'warm' and p.get('success_count', 0) > 2:
                response = self.variator.variate(p['response_template'], user_context)
                return response, f"pathway:{p['id']}"
        
        # 4. Не смогли ответить автономно
        return None, "need_llm"
    
    def store_llm_response(
        self,
        query: str,
        response: str,
        success: bool = True,
        quality_score: float = 0.7
    ):
        """
        Сохранить ответ LLM для будущего использования
        """
        # Сохраняем в кэш
        self.cache.store(query, response, quality_score=quality_score)
        
        # Отслеживаем для автоматического создания pathways
        self.auto_gen.track_query(query, response, success)
        
        # Записываем метрику
        self.brain.record_metric('llm_response_stored', 'system', {
            'query': query[:100],
            'success': success,
            'quality': quality_score
        })
    
    def process_feedback(self, pathway_id: str, positive: bool = True):
        """
        Обработать feedback и обновить tier если нужно
        
        Args:
            pathway_id: ID pathway
            positive: Положительный или отрицательный feedback
        """
        # Обновляем success/fail count уже делается в handle_pathway_feedback
        # Здесь проверяем нужно ли изменить tier
        new_tier = self.tier_manager.evaluate_pathway(pathway_id)
        if new_tier:
            logger.info(f"🎚️ Pathway '{pathway_id}' promoted/demoted to: {new_tier}")
    
    def get_autonomy_stats(self) -> Dict[str, Any]:
        """Статистика автономности"""
        metrics = self.brain.get_metrics_summary(hours=24 * 7)  # 7 дней
        tier_stats = self.tier_manager.get_tier_stats()

        autonomy_rate = metrics.get('autonomy_rate_strict', metrics.get('autonomy_rate', 0))
        autonomy_rate_weighted = metrics.get('autonomy_rate_weighted', 0)

        return {
            'cache': self.cache.get_stats(),
            'tiers': tier_stats,
            'autonomy_rate_percent': round(float(autonomy_rate), 1),
            'autonomy_rate_weighted_percent': round(float(autonomy_rate_weighted), 1),
            'definition': {
                'autonomy_strict': 'autonomous_responses / total_requests',
                'autonomy_weighted': '(autonomous_responses + hybrid_responses * 0.5) / total_requests',
                'autonomous_responses': 'Ответы без LLM/веба (cortex/органы/кэш/pathways).',
                'hybrid_responses': 'Ответы с частичным участием LLM.',
                'llm_calls': 'Количество обращений к LLM.'
            },
            'metrics': metrics,
        }
    
    def evaluate_all_pathways(self) -> Dict[str, int]:
        """Оценить все pathways и обновить тиры"""
        return self.tier_manager.evaluate_all()


# ============== Global Instance ==============

_response_engine: Optional[ResponseEngine] = None


def get_response_engine() -> ResponseEngine:
    """Получить глобальный экземпляр ResponseEngine"""
    global _response_engine
    if _response_engine is None:
        _response_engine = ResponseEngine()
    return _response_engine


# ============== Test ==============

if __name__ == "__main__":
    import os
    os.environ["NEIRA_LOCAL_EMBEDDINGS"] = "true"
    
    print("🧪 Тест ResponseEngine")
    print("=" * 50)
    
    engine = get_response_engine()
    
    # Тест автономного ответа (пока пусто)
    response, source = engine.try_respond_autonomous("Привет, как дела?", {'user_name': 'Тест'})
    print(f"Автономный ответ: {response} (источник: {source})")
    
    # Симулируем сохранение LLM ответа
    engine.store_llm_response(
        query="Как написать функцию на Python?",
        response="Для написания функции используйте ключевое слово def...",
        success=True
    )
    print("✅ LLM ответ сохранён в кэш")
    
    # Тест вариатора
    print("\n" + "=" * 50)
    print("Тест ResponseVariator:")
    
    for _ in range(3):
        greeting = ResponseVariator.generate_greeting("Алексей")
        print(f"  {greeting}")
    
    test_response = "Вот твой код: print('hello')"
    varied = ResponseVariator.add_personality(test_response, mood="happy")
    print(f"\nС настроением: {varied}")
    
    # Тест с переменными
    template = "👋 {time_greeting}, {user_name}! {random_emoji}"
    result = ResponseVariator.variate(template, {'user_name': 'Друг'})
    print(f"Шаблон с переменными: {result}")
    
    print("\n🎉 Тесты завершены!")
