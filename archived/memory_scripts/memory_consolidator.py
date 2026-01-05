"""
Консолидатор памяти для Neira
Объединяет похожие записи, повышает качество через подтверждение
"""

import json
from typing import List, Dict, Set, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import asdict


class MemoryConsolidator:
    """Умное объединение записей памяти"""
    
    def __init__(self, similarity_threshold: float = 0.85):
        """
        Args:
            similarity_threshold: Порог схожести для объединения (0-1)
        """
        self.similarity_threshold = similarity_threshold
    
    def consolidate_similar(self, memories: List[dict]) -> Tuple[List[dict], dict]:
        """
        Объединяет похожие записи (>threshold схожести) в одну с повышенной уверенностью
        
        Args:
            memories: Список записей памяти
        
        Returns:
            (consolidated_memories, stats)
        """
        if not memories:
            return [], {"clusters": 0, "merged": 0, "kept": 0}
        
        # Кластеризация похожих записей
        clusters = self._cluster_similar(memories)
        
        consolidated = []
        merged_count = 0
        
        for cluster in clusters:
            if len(cluster) > 1:
                # Объединяем кластер в одну запись
                merged = self._merge_cluster(cluster)
                consolidated.append(merged)
                merged_count += len(cluster) - 1
            else:
                # Одиночная запись - оставляем как есть
                consolidated.append(cluster[0])
        
        stats = {
            "original_count": len(memories),
            "consolidated_count": len(consolidated),
            "clusters": len(clusters),
            "merged": merged_count,
            "reduction_percent": round((1 - len(consolidated) / len(memories)) * 100, 1) if memories else 0
        }
        
        return consolidated, stats
    
    def _cluster_similar(self, memories: List[dict]) -> List[List[dict]]:
        """Кластеризует похожие записи"""
        clusters = []
        used_indices = set()
        
        for i, mem1 in enumerate(memories):
            if i in used_indices:
                continue
            
            cluster = [mem1]
            used_indices.add(i)
            
            for j, mem2 in enumerate(memories[i+1:], i+1):
                if j in used_indices:
                    continue
                
                similarity = self._semantic_similarity(
                    mem1.get("text", ""),
                    mem2.get("text", "")
                )
                
                if similarity >= self.similarity_threshold:
                    cluster.append(mem2)
                    used_indices.add(j)
            
            clusters.append(cluster)
        
        return clusters
    
    def _merge_cluster(self, cluster: List[dict]) -> dict:
        """
        Объединяет кластер похожих записей в одну
        
        Стратегия:
        - Текст: самая свежая запись
        - Confidence: базовая + бонус за подтверждение
        - Related: объединение всех связей
        - Access count: сумма обращений
        - Validation: если хоть одна user_confirmed → confirmed
        """
        # Сортируем по дате (самая свежая первой)
        sorted_cluster = sorted(
            cluster,
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
        
        latest = sorted_cluster[0]
        
        # Повышаем уверенность за подтверждение через повторение
        base_confidence = latest.get("confidence", 0.5)
        confirmation_boost = min(0.3, 0.05 * len(cluster))  # +0.05 за каждую похожую
        new_confidence = min(1.0, base_confidence + confirmation_boost)
        
        # Объединяем связи
        all_related = set()
        for mem in cluster:
            related = mem.get("related_ids", [])
            if isinstance(related, list):
                all_related.update(related)
        
        # Суммируем обращения
        total_access = sum(mem.get("access_count", 0) for mem in cluster)
        
        # Валидация: если хоть одна подтверждена пользователем
        validation_priority = {
            "user_confirmed": 4,
            "validated": 3,
            "pending": 2,
            "rejected": 1
        }
        
        best_validation = max(
            cluster,
            key=lambda x: validation_priority.get(x.get("validation_status", "pending"), 0)
        ).get("validation_status", "validated")
        
        # Создаём объединённую запись
        merged = latest.copy()
        merged.update({
            "confidence": new_confidence,
            "validation_status": best_validation,
            "related_ids": list(all_related),
            "access_count": total_access,
            "consolidation_info": {
                "merged_count": len(cluster),
                "merged_at": datetime.now().isoformat(),
                "source_ids": [mem.get("id", "") for mem in cluster if mem.get("id")]
            }
        })
        
        return merged
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Семантическая схожесть текстов (Jaccard + n-grams)
        
        Комбинирует:
        1. Jaccard similarity слов (50%)
        2. Character n-gram similarity (50%)
        """
        if not text1 or not text2:
            return 0.0
        
        # 1. Jaccard similarity слов
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if words1 and words2:
            jaccard = len(words1 & words2) / len(words1 | words2)
        else:
            jaccard = 0.0
        
        # 2. Character n-gram similarity (n=3)
        ngrams1 = self._get_ngrams(text1.lower(), n=3)
        ngrams2 = self._get_ngrams(text2.lower(), n=3)
        
        if ngrams1 and ngrams2:
            ngram_sim = len(ngrams1 & ngrams2) / len(ngrams1 | ngrams2)
        else:
            ngram_sim = 0.0
        
        # Комбинируем (50/50)
        return (jaccard + ngram_sim) / 2
    
    def _get_ngrams(self, text: str, n: int = 3) -> Set[str]:
        """Генерирует character n-grams"""
        text = text.replace(" ", "")  # Убираем пробелы
        return {text[i:i+n] for i in range(len(text) - n + 1)}
    
    def consolidate_by_category(self, memories: List[dict]) -> Tuple[List[dict], dict]:
        """
        Консолидация с группировкой по категориям
        
        Сначала группирует по категориям, потом консолидирует внутри каждой
        """
        if not memories:
            return [], {}
        
        # Группируем по категориям
        by_category = {}
        for mem in memories:
            category = mem.get("category", "conversation")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(mem)
        
        # Консолидируем каждую категорию отдельно
        consolidated = []
        total_stats = {
            "original_count": len(memories),
            "by_category": {}
        }
        
        for category, cat_memories in by_category.items():
            cat_consolidated, cat_stats = self.consolidate_similar(cat_memories)
            consolidated.extend(cat_consolidated)
            total_stats["by_category"][category] = cat_stats
        
        total_stats["consolidated_count"] = len(consolidated)
        total_stats["reduction_percent"] = round(
            (1 - len(consolidated) / len(memories)) * 100, 1
        ) if memories else 0
        
        return consolidated, total_stats


# Утилита для консолидации файла памяти
def consolidate_memory_file(
    input_file: str,
    output_file: str = None,
    threshold: float = 0.85,
    by_category: bool = True
) -> dict:
    """
    Консолидирует файл памяти
    
    Args:
        input_file: Путь к исходному файлу
        output_file: Путь для сохранения (если None - перезапишет исходный)
        threshold: Порог схожести (0-1)
        by_category: Группировать по категориям перед консолидацией
    
    Returns:
        Статистика консолидации
    """
    # Загружаем память
    with open(input_file, 'r', encoding='utf-8') as f:
        memories = json.load(f)
    
    if not isinstance(memories, list):
        raise ValueError("Файл должен содержать список записей")
    
    print(f"📂 Загружено записей: {len(memories)}")
    
    # Консолидируем
    consolidator = MemoryConsolidator(similarity_threshold=threshold)
    
    if by_category:
        consolidated, stats = consolidator.consolidate_by_category(memories)
    else:
        consolidated, stats = consolidator.consolidate_similar(memories)
    
    # Сохраняем
    if output_file is None:
        output_file = input_file
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(consolidated, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Сохранено записей: {len(consolidated)}")
    print(f"📉 Сжатие: {stats['reduction_percent']}%")
    
    if "by_category" in stats:
        print("\n📊 По категориям:")
        for category, cat_stats in stats["by_category"].items():
            print(f"  {category}: {cat_stats['original_count']} → {cat_stats['consolidated_count']} "
                  f"(-{cat_stats['reduction_percent']}%)")
    
    return stats


# Пример использования
if __name__ == "__main__":
    # Тестовые данные
    test_memories = [
        {
            "id": "1",
            "text": "Люблю гулять в парке по утрам",
            "category": "preference",
            "confidence": 0.7,
            "validation_status": "pending",
            "timestamp": "2025-12-15T08:00:00",
            "access_count": 5,
            "related_ids": []
        },
        {
            "id": "2",
            "text": "Обожаю утренние прогулки в парке",
            "category": "preference",
            "confidence": 0.6,
            "validation_status": "validated",
            "timestamp": "2025-12-15T09:00:00",
            "access_count": 3,
            "related_ids": []
        },
        {
            "id": "3",
            "text": "Мой любимый цвет - синий",
            "category": "preference",
            "confidence": 0.8,
            "validation_status": "user_confirmed",
            "timestamp": "2025-12-14T10:00:00",
            "access_count": 10,
            "related_ids": []
        }
    ]
    
    consolidator = MemoryConsolidator(similarity_threshold=0.80)
    
    print("🧪 Тест консолидации:")
    print(f"Исходных записей: {len(test_memories)}\n")
    
    consolidated, stats = consolidator.consolidate_similar(test_memories)
    
    print(f"✅ Результат:")
    print(f"  Записей после: {len(consolidated)}")
    print(f"  Кластеров: {stats['clusters']}")
    print(f"  Объединено: {stats['merged']}")
    print(f"  Сжатие: {stats['reduction_percent']}%")
    
    print(f"\n📋 Консолидированные записи:")
    for mem in consolidated:
        print(f"\n  [{mem['id']}] {mem['text'][:50]}...")
        print(f"    Confidence: {mem['confidence']:.2f}")
        print(f"    Validation: {mem['validation_status']}")
        if "consolidation_info" in mem:
            info = mem["consolidation_info"]
            print(f"    Merged: {info['merged_count']} записей")
            print(f"    Sources: {info['source_ids']}")
