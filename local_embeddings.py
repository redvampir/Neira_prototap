"""
Local Embeddings — Локальные эмбеддинги.

DEPRECATED: Используйте neira.core.embeddings
Этот файл оставлен для обратной совместимости.
"""

# Реэкспорт из нового пакета
from neira.core.embeddings import (
    local_embeddings_enabled,
    get_local_embedding,
    cosine_similarity,
    find_similar,
    batch_embeddings,
    clear_embedding_cache,
    get_cache_stats,
    RUSSIAN_STOPWORDS,
    ENGLISH_STOPWORDS,
)

__all__ = [
    "local_embeddings_enabled",
    "get_local_embedding",
    "cosine_similarity",
    "find_similar",
    "batch_embeddings",
    "clear_embedding_cache",
    "get_cache_stats",
    "RUSSIAN_STOPWORDS",
    "ENGLISH_STOPWORDS",
]
