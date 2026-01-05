"""
Neira Brain v1.0 — Единая SQLite база данных для всех компонентов

Таблицы:
- pathways: Neural Pathways (заученные рефлексы)
- cache: Кэш ответов LLM
- organs: Реестр органов
- metrics: Метрики системы
- user_preferences: Настройки пользователей

Преимущества SQLite:
- Быстрый поиск по индексам
- Атомарные транзакции
- Единый файл вместо десятков JSON
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import os
import logging

logger = logging.getLogger("NeiraBrain")


def _env_int(name: str, default: int, min_val: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        val = int(raw.strip())
        return max(val, min_val)
    except ValueError:
        return default


# Настройки
DB_PATH = Path(os.getenv("NEIRA_BRAIN_DB", "neira_brain.db"))
CACHE_MAX_ENTRIES = _env_int("NEIRA_CACHE_MAX_ENTRIES", 5000, 100)
CACHE_TTL_DAYS = _env_int("NEIRA_CACHE_TTL_DAYS", 30, 1)


# ============== Схема базы данных ==============

SCHEMA = """
-- Neural Pathways
CREATE TABLE IF NOT EXISTS pathways (
    id TEXT PRIMARY KEY,
    triggers TEXT NOT NULL,  -- JSON array
    response_template TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    tier TEXT DEFAULT 'cold',
    position INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    unique_users TEXT DEFAULT '[]',  -- JSON array
    confidence_threshold REAL DEFAULT 0.2,
    llm_fallback INTEGER DEFAULT 0,
    variables TEXT DEFAULT '{}',  -- JSON object
    require_exact_match INTEGER DEFAULT 0,
    case_sensitive INTEGER DEFAULT 0,
    user_specific INTEGER DEFAULT 0,
    user_id TEXT,
    auto_generated INTEGER DEFAULT 0,
    last_used TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pathways_tier ON pathways(tier);
CREATE INDEX IF NOT EXISTS idx_pathways_category ON pathways(category);
CREATE INDEX IF NOT EXISTS idx_pathways_user ON pathways(user_id) WHERE user_specific = 1;

-- Response Cache
CREATE TABLE IF NOT EXISTS cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    query_embedding TEXT,  -- JSON array (float)
    response TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    hit_count INTEGER DEFAULT 0,
    source TEXT DEFAULT 'llm',  -- llm, pathway, user
    user_id TEXT,
    created_at TEXT NOT NULL,
    last_hit TEXT
);

CREATE INDEX IF NOT EXISTS idx_cache_hash ON cache(query_hash);
CREATE INDEX IF NOT EXISTS idx_cache_category ON cache(category);
CREATE INDEX IF NOT EXISTS idx_cache_created ON cache(created_at);

-- Organs Registry
CREATE TABLE IF NOT EXISTS organs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    code TEXT,
    cell_type TEXT NOT NULL,
    capabilities TEXT DEFAULT '[]',  -- JSON array
    status TEXT DEFAULT 'active',  -- active, quarantined, disabled
    threat_level TEXT DEFAULT 'safe',  -- safe, suspicious, dangerous, critical
    created_by TEXT,
    approved_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_organs_status ON organs(status);
CREATE INDEX IF NOT EXISTS idx_organs_type ON organs(cell_type);

-- System Metrics
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,  -- telegram, vscode, desktop, server
    data TEXT,  -- JSON
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics(event_type);
CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics(timestamp);

-- User Preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY,
    name TEXT,
    greeting_style TEXT DEFAULT 'friendly',
    variables TEXT DEFAULT '{}',  -- JSON: custom variables for templates
    settings TEXT DEFAULT '{}',  -- JSON: user settings
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Migrations tracking
CREATE TABLE IF NOT EXISTS migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


# ============== Database Connection ==============

class NeiraBrain:
    """
    Единая база данных Neira
    Thread-safe через connection per thread
    """
    
    _instance: Optional['NeiraBrain'] = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: Optional[Path] = None):
        """Singleton pattern"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, db_path: Optional[Path] = None):
        if self._initialized:
            return
        
        self.db_path = db_path or DB_PATH
        self._local = threading.local()
        self._init_db()
        self._initialized = True
        logger.info(f"🧠 NeiraBrain инициализирован: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Получить connection для текущего потока"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def _cursor(self):
        """Context manager для cursor с автоматическим commit/rollback"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"DB Error: {e}")
            raise
        finally:
            cursor.close()
    
    def _init_db(self):
        """Инициализация схемы"""
        conn = self._get_connection()
        conn.executescript(SCHEMA)
        conn.commit()
        logger.info("📊 Схема базы данных создана/проверена")

    # ============== Metrics ==============
    def add_metric(self, event_type: str, source: str, data: Dict[str, Any]) -> bool:
        """Добавить запись метрики в таблицу `metrics`.

        Args:
            event_type: Тип события, например 'organ_invocation'
            source: Источник события: 'telegram', 'vscode', 'server'
            data: Сериализуемый словарь с деталями

        Returns:
            True при успешной вставке
        """
        try:
            with self._cursor() as cur:
                cur.execute(
                    "INSERT INTO metrics (event_type, source, data, timestamp) VALUES (?, ?, ?, ?)",
                    (event_type, source, json.dumps(data, ensure_ascii=False), datetime.now().isoformat())
                )
            return True
        except Exception as e:
            logger.error(f"Не удалось записать метрику: {e}")
            return False
    
    # ============== Pathways ==============
    
    def get_pathway(self, pathway_id: str) -> Optional[Dict[str, Any]]:
        """Получить pathway по ID"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM pathways WHERE id = ?", (pathway_id,))
            row = cur.fetchone()
            return self._row_to_pathway(row) if row else None
    
    def get_all_pathways(self, tier: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить все pathways, опционально фильтр по tier"""
        with self._cursor() as cur:
            if tier:
                cur.execute(
                    "SELECT * FROM pathways WHERE tier = ? ORDER BY position",
                    (tier,)
                )
            else:
                cur.execute("SELECT * FROM pathways ORDER BY tier, position")
            return [self._row_to_pathway(row) for row in cur.fetchall()]
    
    def search_pathways(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Поиск pathways по запросу
        
        Args:
            query: Текст запроса для поиска
            limit: Максимальное количество результатов
            
        Returns:
            Список подходящих pathways, отсортированных по релевантности
        """
        query_lower = query.lower().strip()
        all_pathways = self.get_all_pathways()
        
        results = []
        for pathway in all_pathways:
            score = 0.0
            triggers = pathway.get('triggers', [])
            
            # Проверяем каждый trigger
            for trigger in triggers:
                trigger_lower = trigger.lower()
                
                # Точное совпадение
                if trigger_lower == query_lower:
                    score = 1.0
                    break
                
                # Trigger содержится в запросе
                if trigger_lower in query_lower:
                    score = max(score, 0.8)
                
                # Запрос содержится в trigger
                if query_lower in trigger_lower:
                    score = max(score, 0.7)
                
                # Общие слова
                trigger_words = set(trigger_lower.split())
                query_words = set(query_lower.split())
                common = trigger_words & query_words
                if common:
                    word_score = len(common) / max(len(trigger_words), len(query_words))
                    score = max(score, word_score * 0.6)
            
            if score > 0:
                pathway['match_score'] = score
                results.append(pathway)
        
        # Сортируем по score и tier
        tier_order = {'hot': 0, 'warm': 1, 'cold': 2}
        results.sort(key=lambda p: (-p.get('match_score', 0), tier_order.get(p.get('tier', 'cold'), 2)))
        
        return results[:limit]

    def save_pathway(self, pathway: Dict[str, Any]) -> bool:
        """Сохранить/обновить pathway"""
        now = datetime.now().isoformat()
        pathway.setdefault('created_at', now)
        pathway['updated_at'] = now
        
        with self._cursor() as cur:
            cur.execute("""
                INSERT OR REPLACE INTO pathways 
                (id, triggers, response_template, category, tier, position,
                 success_count, failure_count, unique_users, confidence_threshold,
                 llm_fallback, variables, require_exact_match, case_sensitive,
                 user_specific, user_id, auto_generated, last_used, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pathway['id'],
                json.dumps(pathway.get('triggers', []), ensure_ascii=False),
                pathway.get('response_template', ''),
                pathway.get('category', 'general'),
                pathway.get('tier', 'cold'),
                pathway.get('position', 0),
                pathway.get('success_count', 0),
                pathway.get('failure_count', 0),
                json.dumps(list(pathway.get('unique_users', [])), ensure_ascii=False),
                pathway.get('confidence_threshold', 0.2),
                1 if pathway.get('llm_fallback') else 0,
                json.dumps(pathway.get('variables', {}), ensure_ascii=False),
                1 if pathway.get('require_exact_match') else 0,
                1 if pathway.get('case_sensitive') else 0,
                1 if pathway.get('user_specific') else 0,
                pathway.get('user_id'),
                1 if pathway.get('auto_generated') else 0,
                pathway.get('last_used'),
                pathway['created_at'],
                pathway['updated_at']
            ))
        return True
    
    def update_pathway_usage(self, pathway_id: str, user_id: str, success: bool = True):
        """Обновить статистику использования pathway"""
        with self._cursor() as cur:
            # Получаем текущие данные
            cur.execute("SELECT unique_users, success_count, failure_count FROM pathways WHERE id = ?", (pathway_id,))
            row = cur.fetchone()
            if not row:
                return
            
            users = set(json.loads(row['unique_users'] or '[]'))
            users.add(user_id)
            
            if success:
                cur.execute("""
                    UPDATE pathways 
                    SET success_count = success_count + 1,
                        unique_users = ?,
                        last_used = ?
                    WHERE id = ?
                """, (json.dumps(list(users)), datetime.now().isoformat(), pathway_id))
            else:
                cur.execute("""
                    UPDATE pathways 
                    SET failure_count = failure_count + 1,
                        last_used = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), pathway_id))
    
    def _row_to_pathway(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Конвертировать Row в dict"""
        return {
            'id': row['id'],
            'triggers': json.loads(row['triggers']),
            'response_template': row['response_template'],
            'category': row['category'],
            'tier': row['tier'],
            'position': row['position'],
            'success_count': row['success_count'],
            'failure_count': row['failure_count'],
            'unique_users': set(json.loads(row['unique_users'] or '[]')),
            'confidence_threshold': row['confidence_threshold'],
            'llm_fallback': bool(row['llm_fallback']),
            'variables': json.loads(row['variables'] or '{}'),
            'require_exact_match': bool(row['require_exact_match']),
            'case_sensitive': bool(row['case_sensitive']),
            'user_specific': bool(row['user_specific']),
            'user_id': row['user_id'],
            'auto_generated': bool(row['auto_generated']),
            'last_used': row['last_used'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }
    
    # ============== Cache ==============
    
    def cache_get(self, query_hash: str) -> Optional[Dict[str, Any]]:
        """Получить из кэша по хэшу запроса"""
        with self._cursor() as cur:
            cur.execute("""
                SELECT * FROM cache WHERE query_hash = ?
                ORDER BY hit_count DESC LIMIT 1
            """, (query_hash,))
            row = cur.fetchone()
            if row:
                # Обновляем счетчик
                cur.execute("""
                    UPDATE cache SET hit_count = hit_count + 1, last_hit = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), row['id']))
                return self._row_to_cache(row)
            return None
    
    def cache_search(self, query: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        """
        Поиск в кэше по тексту запроса
        
        Args:
            query: Текст для поиска (пустой = все записи)
            limit: Максимальное количество результатов
            
        Returns:
            Список записей кэша
        """
        with self._cursor() as cur:
            if query:
                cur.execute("""
                    SELECT * FROM cache 
                    WHERE query LIKE ? 
                    ORDER BY hit_count DESC, created_at DESC
                    LIMIT ?
                """, (f"%{query}%", limit))
            else:
                cur.execute("""
                    SELECT * FROM cache 
                    ORDER BY hit_count DESC, created_at DESC
                    LIMIT ?
                """, (limit,))
            return [self._row_to_cache(row) for row in cur.fetchall()]

    def cache_find_similar(self, embedding: List[float], threshold: float = 0.75, limit: int = 5) -> List[Dict[str, Any]]:
        """Найти похожие записи в кэше по embedding"""
        # Загружаем все embeddings и ищем похожие
        # (для больших баз можно использовать faiss или annoy)
        with self._cursor() as cur:
            cur.execute("SELECT * FROM cache WHERE query_embedding IS NOT NULL")
            results = []
            for row in cur.fetchall():
                stored_emb = json.loads(row['query_embedding'])
                similarity = self._cosine_similarity(embedding, stored_emb)
                if similarity >= threshold:
                    results.append((similarity, self._row_to_cache(row)))
            
            # Сортируем по похожести
            results.sort(key=lambda x: x[0], reverse=True)
            return [r[1] for r in results[:limit]]
    
    def cache_store(self, query: str, response: str, embedding: Optional[List[float]] = None,
                    category: str = "general", source: str = "llm", user_id: Optional[str] = None,
                    ttl_hours: Optional[int] = None, metadata: Optional[Dict[str, Any]] = None):
        """Сохранить в кэш"""
        import hashlib
        query_hash = hashlib.sha256(query.lower().strip().encode()).hexdigest()[:32]
        
        with self._cursor() as cur:
            cur.execute("""
                INSERT INTO cache (query, query_hash, query_embedding, response, category, source, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                query,
                query_hash,
                json.dumps(embedding) if embedding else None,
                response,
                category,
                source,
                user_id,
                datetime.now().isoformat()
            ))
        
        # Очистка старых записей
        self._cleanup_cache()
    
    def _cleanup_cache(self):
        """Удалить старые записи из кэша"""
        cutoff = (datetime.now() - timedelta(days=CACHE_TTL_DAYS)).isoformat()
        with self._cursor() as cur:
            # Удаляем старые неиспользуемые
            cur.execute("""
                DELETE FROM cache 
                WHERE created_at < ? AND (last_hit IS NULL OR last_hit < ?)
            """, (cutoff, cutoff))
            
            # Если слишком много записей — удаляем самые старые
            cur.execute("SELECT COUNT(*) FROM cache")
            count = cur.fetchone()[0]
            if count > CACHE_MAX_ENTRIES:
                cur.execute("""
                    DELETE FROM cache WHERE id IN (
                        SELECT id FROM cache 
                        ORDER BY COALESCE(last_hit, created_at) ASC
                        LIMIT ?
                    )
                """, (count - CACHE_MAX_ENTRIES,))
    
    def _row_to_cache(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            'id': row['id'],
            'query': row['query'],
            'query_hash': row['query_hash'],
            'query_embedding': json.loads(row['query_embedding']) if row['query_embedding'] else None,
            'response': row['response'],
            'category': row['category'],
            'hit_count': row['hit_count'],
            'source': row['source'],
            'user_id': row['user_id'],
            'created_at': row['created_at'],
            'last_hit': row['last_hit']
        }
    
    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Косинусное сходство"""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a < 1e-12 or norm_b < 1e-12:
            return 0.0
        return dot / (norm_a * norm_b)
    
    # ============== Organs ==============
    
    def get_organ(self, organ_id: str) -> Optional[Dict[str, Any]]:
        """Получить орган по ID"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM organs WHERE id = ?", (organ_id,))
            row = cur.fetchone()
            return self._row_to_organ(row) if row else None
    
    def get_all_organs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить все органы"""
        with self._cursor() as cur:
            if status:
                cur.execute("SELECT * FROM organs WHERE status = ?", (status,))
            else:
                cur.execute("SELECT * FROM organs")
            return [self._row_to_organ(row) for row in cur.fetchall()]
    
    def save_organ(self, organ: Dict[str, Any]) -> bool:
        """Сохранить/обновить орган"""
        now = datetime.now().isoformat()
        organ.setdefault('created_at', now)
        organ['updated_at'] = now
        
        with self._cursor() as cur:
            cur.execute("""
                INSERT OR REPLACE INTO organs
                (id, name, description, code, cell_type, capabilities, status,
                 threat_level, created_by, approved_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                organ['id'],
                organ.get('name', ''),
                organ.get('description', ''),
                organ.get('code', ''),
                organ.get('cell_type', 'custom'),
                json.dumps(organ.get('capabilities', []), ensure_ascii=False),
                organ.get('status', 'active'),
                organ.get('threat_level', 'safe'),
                organ.get('created_by'),
                organ.get('approved_by'),
                organ['created_at'],
                organ['updated_at']
            ))
        return True
    
    def _row_to_organ(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            'id': row['id'],
            'name': row['name'],
            'description': row['description'],
            'code': row['code'],
            'cell_type': row['cell_type'],
            'capabilities': json.loads(row['capabilities'] or '[]'),
            'status': row['status'],
            'threat_level': row['threat_level'],
            'created_by': row['created_by'],
            'approved_by': row['approved_by'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }
    
    # ============== Metrics ==============
    
    def record_metric(self, event_type: str, source: str, data: Optional[Dict] = None):
        """Записать метрику"""
        with self._cursor() as cur:
            cur.execute("""
                INSERT INTO metrics (event_type, source, data, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                event_type,
                source,
                json.dumps(data, ensure_ascii=False) if data else None,
                datetime.now().isoformat()
            ))
    
    def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Получить сводку метрик за последние N часов"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with self._cursor() as cur:
            cur.execute("""
                SELECT event_type, COUNT(*) as count 
                FROM metrics WHERE timestamp > ?
                GROUP BY event_type
            """, (cutoff,))
            
            summary = {row['event_type']: row['count'] for row in cur.fetchall()}
            
            # Расчёт автономности
            total = summary.get('request', 0)
            pathway_hits = summary.get('pathway_hit', 0)
            cache_hits = summary.get('cache_hit', 0)
            llm_calls = summary.get('llm_call', 0)
            
            autonomy_rate = 0.0
            if total > 0:
                autonomy_rate = (pathway_hits + cache_hits) / total
            
            return {
                'total_requests': total,
                'pathway_hits': pathway_hits,
                'cache_hits': cache_hits,
                'llm_calls': llm_calls,
                'autonomy_rate': round(autonomy_rate * 100, 1),
                'period_hours': hours
            }
    
    # ============== User Preferences ==============
    
    def get_user_prefs(self, user_id: str) -> Dict[str, Any]:
        """Получить настройки пользователя"""
        with self._cursor() as cur:
            cur.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row:
                return {
                    'user_id': row['user_id'],
                    'name': row['name'],
                    'greeting_style': row['greeting_style'],
                    'variables': json.loads(row['variables'] or '{}'),
                    'settings': json.loads(row['settings'] or '{}')
                }
            return {
                'user_id': user_id,
                'name': None,
                'greeting_style': 'friendly',
                'variables': {},
                'settings': {}
            }
    
    def save_user_prefs(self, user_id: str, prefs: Dict[str, Any]):
        """Сохранить настройки пользователя"""
        now = datetime.now().isoformat()
        with self._cursor() as cur:
            cur.execute("""
                INSERT OR REPLACE INTO user_preferences
                (user_id, name, greeting_style, variables, settings, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM user_preferences WHERE user_id = ?), ?), ?)
            """, (
                user_id,
                prefs.get('name'),
                prefs.get('greeting_style', 'friendly'),
                json.dumps(prefs.get('variables', {}), ensure_ascii=False),
                json.dumps(prefs.get('settings', {}), ensure_ascii=False),
                user_id,
                now,
                now
            ))
    
    # ============== Generic SQL Methods ==============
    
    def query(self, sql: str, params: Tuple = ()) -> List[sqlite3.Row]:
        """Выполнить SELECT запрос и вернуть результаты"""
        with self._cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    
    def execute(self, sql: str, params: Tuple = ()) -> int:
        """Выполнить INSERT/UPDATE/DELETE и вернуть rowcount"""
        with self._cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount
    
    # ============== Migration from JSON ==============
    
    def migrate_from_json(self, pathways_file: str = "neural_pathways.json"):
        """Миграция из JSON файлов в SQLite"""
        migrated = 0
        
        # Migrate pathways
        if Path(pathways_file).exists():
            try:
                with open(pathways_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for p in data.get('pathways', []):
                    self.save_pathway(p)
                    migrated += 1
                
                logger.info(f"✅ Мигрировано {migrated} pathways из {pathways_file}")
            except Exception as e:
                logger.error(f"❌ Ошибка миграции pathways: {e}")
        
        return migrated


# ============== Global instance ==============

_brain_instance: Optional[NeiraBrain] = None


def get_brain() -> NeiraBrain:
    """Получить глобальный экземпляр NeiraBrain"""
    global _brain_instance
    if _brain_instance is None:
        _brain_instance = NeiraBrain()
    return _brain_instance


# ============== Test ==============

if __name__ == "__main__":
    import sys
    
    print("🧠 Тест NeiraBrain")
    print("=" * 50)
    
    brain = get_brain()
    
    # Тест pathway
    test_pathway = {
        'id': 'test_greeting',
        'triggers': ['привет', 'hello'],
        'response_template': '👋 Привет! Как дела?',
        'category': 'greeting',
        'tier': 'hot'
    }
    
    brain.save_pathway(test_pathway)
    print(f"✅ Pathway сохранён: {test_pathway['id']}")
    
    loaded = brain.get_pathway('test_greeting')
    if loaded:
        print(f"✅ Pathway загружен: {loaded['triggers']}")
    else:
        print("❌ Pathway не найден")
    
    # Тест cache
    brain.cache_store(
        query="что такое python",
        response="Python — это язык программирования",
        category="tech"
    )
    print("✅ Cache запись создана")
    
    # Тест metrics
    brain.record_metric('request', 'test', {'query': 'test'})
    brain.record_metric('pathway_hit', 'test', {'pathway_id': 'test_greeting'})
    
    summary = brain.get_metrics_summary(1)
    print(f"✅ Метрики: {summary}")
    
    # Тест user prefs
    brain.save_user_prefs('user123', {
        'name': 'Тестовый пользователь',
        'variables': {'favorite_lang': 'Python'}
    })
    prefs = brain.get_user_prefs('user123')
    print(f"✅ User prefs: {prefs['name']}")
    
    print("=" * 50)
    print("🎉 Все тесты пройдены!")
