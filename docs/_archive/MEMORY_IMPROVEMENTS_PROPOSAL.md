# 🧠 Предложения по улучшению системы памяти Neira

## 📊 Текущее состояние

**Что уже есть (memory_system.py v2.0):**
- ✅ Разделение на типы: Working/Short-Term/Long-Term/Episodic/Semantic
- ✅ Валидация перед записью
- ✅ Confidence score (уверенность 0-1)
- ✅ Защита от переполнения (лимиты: 1000/500/300)
- ✅ Автоочистка низкоуверенных записей
- ✅ Эмбеддинги для семантического поиска

**Проблемы после анализа:**
1. **Переполнение долгосрочной памяти** — 3.6 MB, 173 записи (после чистки 107)
2. **Зацикливания** — одинаковые записи за минуту (детектировано 12 случаев)
3. **Технические галлюцинации** — запоминает обсуждения про код, нейросети
4. **Нет шифрования** — память в plaintext JSON
5. **Нет версионирования** — невозможно откатиться на предыдущее состояние
6. **Нет приоритезации** — все записи равнозначны
7. **Медленный поиск** — линейный просмотр всех записей

---

## 🎯 Решение 1: Интеллектуальная консолидация памяти

### Проблема
Записи дублируются, зацикливаются, нет автоматического объединения похожих.

### Решение
**Memory Consolidation Engine** — автоматическое слияние и архивация

```python
class MemoryConsolidator:
    """Умное объединение записей памяти"""
    
    def consolidate_similar(self, memories: List[MemoryEntry], threshold=0.85):
        """
        Объединяет похожие записи (>85% схожести) в одну с повышенной уверенностью
        """
        clusters = []
        used = set()
        
        for i, mem1 in enumerate(memories):
            if i in used:
                continue
                
            cluster = [mem1]
            for j, mem2 in enumerate(memories[i+1:], i+1):
                if j in used:
                    continue
                    
                similarity = self._semantic_similarity(mem1.text, mem2.text)
                if similarity >= threshold:
                    cluster.append(mem2)
                    used.add(j)
            
            if len(cluster) > 1:
                # Объединяем в одну запись с повышенной уверенностью
                merged = self._merge_cluster(cluster)
                clusters.append(merged)
            else:
                clusters.append(mem1)
        
        return clusters
    
    def _merge_cluster(self, cluster: List[MemoryEntry]) -> MemoryEntry:
        """Объединяет кластер похожих записей"""
        # Берём самую свежую дату
        latest = max(cluster, key=lambda x: x.timestamp)
        
        # Повышаем уверенность (подтверждение через повторение)
        confidence_boost = min(1.0, latest.confidence + 0.1 * len(cluster))
        
        # Объединяем связи
        all_related = set()
        for mem in cluster:
            all_related.update(mem.related_ids)
        
        return MemoryEntry(
            id=latest.id,
            text=latest.text,
            memory_type=latest.memory_type,
            category=latest.category,
            timestamp=latest.timestamp,
            confidence=confidence_boost,
            validation_status="validated",  # Подтверждено повторением
            related_ids=list(all_related),
            access_count=sum(m.access_count for m in cluster)
        )
```

**Эффект:**
- Сжатие памяти на 30-50%
- Повышение качества (подтверждённые факты получают boost)
- Автоматическая валидация через повторение

---

## 🎯 Решение 2: Векторная БД для быстрого поиска

### Проблема
Линейный поиск по 173 записям медленный. При росте до 1000 будет критично.

### Решение
**ChromaDB** или **FAISS** для векторного поиска

```python
import chromadb
from chromadb.config import Settings

class VectorMemoryIndex:
    """Векторный индекс для быстрого семантического поиска"""
    
    def __init__(self, persist_directory="./memory_vectors"):
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_directory
        ))
        
        self.collection = self.client.get_or_create_collection(
            name="neira_memory",
            metadata={"description": "Long-term memory with embeddings"}
        )
    
    def add_memory(self, memory: MemoryEntry, embedding: List[float]):
        """Добавляет запись с эмбеддингом"""
        self.collection.add(
            ids=[memory.id],
            embeddings=[embedding],
            documents=[memory.text],
            metadatas=[{
                "category": memory.category,
                "confidence": memory.confidence,
                "timestamp": memory.timestamp
            }]
        )
    
    def search(self, query_embedding: List[float], top_k=5, min_confidence=0.3):
        """Быстрый поиск похожих записей"""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"confidence": {"$gte": min_confidence}}
        )
        
        return results['ids'][0], results['distances'][0]
```

**Эффект:**
- Поиск за O(log n) вместо O(n)
- Масштабируемость до миллионов записей
- Фильтрация по метаданным (категория, уверенность, дата)

---

## 🎯 Решение 3: Шифрование памяти

### Проблема
Память хранится в plaintext — уязвимость для доступа извне.

### Решение
**AES-256 шифрование** с ключом пользователя

```python
from cryptography.fernet import Fernet
import base64
import hashlib

class SecureMemoryStorage:
    """Шифрованное хранилище памяти"""
    
    def __init__(self, password: str):
        # Генерируем ключ из пароля
        key = hashlib.sha256(password.encode()).digest()
        self.cipher = Fernet(base64.urlsafe_b64encode(key))
    
    def save_encrypted(self, data: dict, filepath: str):
        """Сохраняет память в зашифрованном виде"""
        json_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
        encrypted = self.cipher.encrypt(json_bytes)
        
        with open(filepath, 'wb') as f:
            f.write(encrypted)
    
    def load_encrypted(self, filepath: str) -> dict:
        """Загружает зашифрованную память"""
        with open(filepath, 'rb') as f:
            encrypted = f.read()
        
        decrypted = self.cipher.decrypt(encrypted)
        return json.loads(decrypted.decode('utf-8'))
```

**Эффект:**
- Защита от несанкционированного доступа
- Конфиденциальность переписок
- Опциональное шифрование (можно отключить)

---

## 🎯 Решение 4: Приоритезация по важности

### Проблема
Все записи равнозначны — важные факты теряются среди мусора.

### Решение
**Scoring система** с автоматическим расчётом важности

```python
class MemoryScorer:
    """Оценка важности записей"""
    
    def calculate_importance(self, memory: MemoryEntry, context: dict) -> float:
        """
        Рассчитывает важность записи (0-1)
        
        Факторы:
        - Частота использования (access_count)
        - Свежесть (recency)
        - Подтверждение (validation_status)
        - Связанность (сколько других записей ссылаются)
        - Категория (FACT > CONVERSATION)
        """
        score = 0.0
        
        # 1. Частота использования (0-0.3)
        score += min(0.3, memory.access_count / 100)
        
        # 2. Свежесть (0-0.2)
        age_days = (datetime.now() - datetime.fromisoformat(memory.timestamp)).days
        recency_score = max(0, 0.2 - (age_days / 365) * 0.2)
        score += recency_score
        
        # 3. Валидация (0-0.3)
        validation_scores = {
            "user_confirmed": 0.3,
            "validated": 0.2,
            "pending": 0.1,
            "rejected": 0.0
        }
        score += validation_scores.get(memory.validation_status, 0.1)
        
        # 4. Связанность (0-0.1)
        score += min(0.1, len(memory.related_ids) / 50)
        
        # 5. Категория (0-0.1)
        category_scores = {
            "fact": 0.1,
            "instruction": 0.09,
            "preference": 0.08,
            "person": 0.07,
            "learned": 0.05,
            "conversation": 0.03,
            "event": 0.02
        }
        score += category_scores.get(memory.category, 0.05)
        
        return min(1.0, score)
    
    def prioritize_memories(self, memories: List[MemoryEntry]) -> List[MemoryEntry]:
        """Сортирует записи по важности"""
        scored = [
            (mem, self.calculate_importance(mem, {}))
            for mem in memories
        ]
        
        sorted_mems = sorted(scored, key=lambda x: x[1], reverse=True)
        
        # Обновляем поле importance
        for mem, score in sorted_mems:
            mem.importance = score
        
        return [m[0] for m in sorted_mems]
```

**Эффект:**
- Важные факты всегда в топе
- Автоматическая архивация редкоиспользуемых
- Оптимизация контекста для LLM (только топ-20)

---

## 🎯 Решение 5: Git-like версионирование

### Проблема
Невозможно откатиться после ошибочной очистки или повреждения.

### Решение
**Snapshot система** с diff'ами

```python
class MemoryVersionControl:
    """Git-like версионирование памяти"""
    
    def __init__(self, snapshots_dir="./memory_snapshots"):
        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def create_snapshot(self, memory_data: dict, message: str = ""):
        """Создаёт снимок текущего состояния"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_id = hashlib.md5(f"{timestamp}{message}".encode()).hexdigest()[:8]
        
        snapshot = {
            "id": snapshot_id,
            "timestamp": timestamp,
            "message": message,
            "data": memory_data,
            "stats": {
                "total_memories": len(memory_data),
                "avg_confidence": sum(m.get("confidence", 0) for m in memory_data) / len(memory_data)
            }
        }
        
        filepath = self.snapshots_dir / f"snapshot_{timestamp}_{snapshot_id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        
        # Лог изменений
        self._append_to_changelog(snapshot_id, message, timestamp)
        
        return snapshot_id
    
    def restore_snapshot(self, snapshot_id: str) -> dict:
        """Восстанавливает состояние из снимка"""
        snapshots = list(self.snapshots_dir.glob(f"snapshot_*_{snapshot_id}.json"))
        
        if not snapshots:
            raise ValueError(f"Snapshot {snapshot_id} не найден")
        
        with open(snapshots[0], 'r', encoding='utf-8') as f:
            snapshot = json.load(f)
        
        return snapshot["data"]
    
    def list_snapshots(self) -> List[dict]:
        """Список всех снимков"""
        snapshots = []
        for filepath in sorted(self.snapshots_dir.glob("snapshot_*.json")):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                snapshots.append({
                    "id": data["id"],
                    "timestamp": data["timestamp"],
                    "message": data.get("message", ""),
                    "stats": data.get("stats", {})
                })
        return snapshots
```

**Эффект:**
- Безопасное экспериментирование (можно откатить)
- История изменений памяти
- Восстановление после сбоев

---

## 🎯 Решение 6: Детектор аномалий в реальном времени

### Проблема
Технические галлюцинации и зацикливания детектируются только постфактум.

### Решение
**Anomaly Detector** перед записью

```python
class MemoryAnomalyDetector:
    """Детектор аномальных записей перед сохранением"""
    
    def __init__(self):
        # Паттерны технического мусора
        self.technical_patterns = [
            r"import\s+\w+",
            r"class\s+\w+:",
            r"def\s+\w+\(",
            r"async\s+def",
            r"нейронн(ая|ые|ых|ой)\s+сет",
            r"трансформер",
            r"градиентн(ый|ого)\s+спуск",
            r"биохимическ(ий|ого|ом)",
        ]
        
        # История последних N записей для детекта зацикливания
        self.recent_window = []
        self.window_size = 10
    
    def is_anomaly(self, text: str, timestamp: str) -> Tuple[bool, str]:
        """
        Проверяет, является ли запись аномалией
        
        Returns:
            (is_anomaly, reason)
        """
        # 1. Технический код/жаргон
        for pattern in self.technical_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True, "technical_jargon"
        
        # 2. Зацикливание (3+ одинаковых за минуту)
        minute_key = timestamp[:16]  # YYYY-MM-DDTHH:MM
        same_minute = [
            (t, txt) for t, txt in self.recent_window
            if t[:16] == minute_key
        ]
        
        if len(same_minute) >= 3:
            # Проверяем схожесть
            similarities = [
                self._text_similarity(text, txt)
                for _, txt in same_minute
            ]
            if max(similarities, default=0) > 0.7:
                return True, "looping"
        
        # 3. Слишком длинный текст (>2000 символов)
        if len(text) > 2000:
            return True, "too_long"
        
        # 4. Подозрительные фразы
        suspicious = [
            "я не знаю", "не уверен", "возможно", "может быть",
            "согласно моим данным", "в моей базе", "как языковая модель"
        ]
        
        lower_text = text.lower()
        suspicion_count = sum(1 for phrase in suspicious if phrase in lower_text)
        
        if suspicion_count >= 3:
            return True, "uncertain_language"
        
        # Обновляем окно
        self.recent_window.append((timestamp, text))
        if len(self.recent_window) > self.window_size:
            self.recent_window.pop(0)
        
        return False, ""
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Jaccard similarity"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        return len(words1 & words2) / len(words1 | words2) if words1 | words2 else 0
```

**Эффект:**
- Блокировка мусора до записи
- Предотвращение зацикливаний
- Чистая память с первого дня

---

## 📦 Итоговая архитектура v3.0

```
MemorySystem v3.0
├── Core
│   ├── VectorMemoryIndex (ChromaDB) — быстрый поиск
│   ├── SecureMemoryStorage (AES-256) — шифрование
│   └── MemoryVersionControl (Snapshots) — версионирование
│
├── Intelligence
│   ├── MemoryConsolidator — объединение похожих
│   ├── MemoryScorer — приоритезация
│   └── MemoryAnomalyDetector — защита от мусора
│
└── Policies
    ├── Auto-cleanup (по importance score)
    ├── Auto-consolidation (раз в сутки)
    └── Auto-snapshot (перед очисткой)
```

---

## 🚀 План внедрения (поэтапно)

### Фаза 1: Защита (1-2 дня)
1. ✅ Anomaly Detector — блокировка мусора
2. ✅ Auto-cleanup — лимиты и очистка
3. ✅ Snapshots — версионирование

### Фаза 2: Оптимизация (2-3 дня)
4. ⏳ VectorIndex — ChromaDB интеграция
5. ⏳ Consolidation — объединение похожих
6. ⏳ Scoring — приоритезация

### Фаза 3: Безопасность (1 день)
7. ⏳ Encryption — опциональное шифрование
8. ⏳ Access control — права доступа

---

## 💡 Рекомендации

**Сейчас:**
1. Внедрить `MemoryAnomalyDetector` — остановит рост мусора
2. Включить `auto_consolidation` — сожмёт текущие 107 записей
3. Создать snapshot перед любыми изменениями

**Через неделю:**
4. Мигрировать на ChromaDB — ускорит в 10-100x
5. Добавить scoring — важные факты всегда доступны

**Опционально:**
6. Шифрование — если важна конфиденциальность
7. Веб-интерфейс — визуализация памяти

---

## 📊 Метрики успеха

**До улучшений:**
- Памяти: 3.6 MB → 2.2 MB (после ручной чистки)
- Записей: 173 → 107
- Зацикливаний: 12 случаев
- Поиск: O(n) линейный

**После v3.0 (прогноз):**
- Памяти: ~1 MB (консолидация + scoring)
- Записей: ~80 высококачественных
- Зацикливаний: 0 (детектор)
- Поиск: O(log n) векторный
- Защита: AES-256 + snapshots
- Скорость: +90% быстрее

---

**Какое решение хочешь внедрить первым?**
