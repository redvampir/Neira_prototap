"""
Local Embeddings v2.0 — Улучшенные локальные эмбеддинги

Работает полностью offline без зависимостей от внешних сервисов.
Включает:
- N-gram хэширование (базовый метод)
- Семантические фичи (ключевые слова, категории)
- Стоп-слова для русского и английского
- Кэширование для производительности
- TF-подобное взвешивание
"""

import hashlib
import math
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple


_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off"}


# ============== Стоп-слова ==============

RUSSIAN_STOPWORDS = {
    'и', 'в', 'во', 'не', 'на', 'с', 'со', 'к', 'по', 'за', 'из', 'о', 'об', 'а',
    'но', 'да', 'то', 'как', 'что', 'это', 'все', 'он', 'она', 'они', 'мы', 'вы',
    'я', 'ты', 'ее', 'его', 'их', 'бы', 'же', 'ли', 'у', 'для', 'до', 'от', 'при',
    'так', 'был', 'была', 'были', 'быть', 'есть', 'будет', 'будут', 'который',
    'которая', 'которые', 'этот', 'эта', 'эти', 'тот', 'та', 'те', 'только',
    'уже', 'еще', 'ещё', 'когда', 'где', 'там', 'здесь', 'тут', 'очень', 'можно',
    'нужно', 'надо', 'чтобы', 'если', 'тогда', 'потом', 'вот', 'или', 'ну',
    'ведь', 'даже', 'тоже', 'также', 'какой', 'какая', 'какие', 'каждый', 'свой',
    'своя', 'свое', 'свои', 'весь', 'вся', 'всё', 'всем', 'всех', 'мой', 'моя',
    'мое', 'наш', 'наша', 'наше', 'ваш', 'ваша', 'ваше', 'через', 'между', 'под',
    'над', 'после', 'перед', 'без', 'около', 'вокруг', 'кроме', 'кто', 'куда',
    'откуда', 'почему', 'зачем', 'сколько', 'пока', 'чем', 'никто', 'ничто',
    'никогда', 'нигде', 'себя', 'сам', 'сама', 'само', 'сами', 'меня', 'тебя',
    'нас', 'вас', 'ему', 'ей', 'им', 'мне', 'тебе', 'нам', 'вам', 'него', 'нее',
    'них', 'нему', 'ней', 'ним', 'собой', 'другой', 'другая', 'другие',
}

ENGLISH_STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'if', 'then', 'else', 'when', 'where',
    'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is',
    'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having',
    'do', 'does', 'did', 'doing', 'will', 'would', 'could', 'should', 'may',
    'might', 'must', 'shall', 'can', 'for', 'of', 'to', 'from', 'in', 'out', 'on',
    'off', 'over', 'under', 'up', 'down', 'with', 'at', 'by', 'about', 'into',
    'through', 'during', 'before', 'after', 'above', 'below', 'between', 'because',
    'as', 'until', 'while', 'each', 'all', 'both', 'most', 'other', 'some', 'such',
    'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
    'also', 'now', 'how', 'why', 'any', 'here', 'there', 'it', 'its', 'i', 'me',
    'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours',
    'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers',
    'herself', 'they', 'them', 'their', 'theirs', 'themselves', 'more', 'few',
}

ALL_STOPWORDS = RUSSIAN_STOPWORDS | ENGLISH_STOPWORDS


# ============== Семантические категории ==============
# Ключевые слова для определения темы запроса

SEMANTIC_CATEGORIES = {
    'code': {
        'keywords': ['код', 'функция', 'класс', 'программ', 'скрипт', 'python', 'javascript',
                     'code', 'function', 'class', 'script', 'variable', 'переменн', 'метод',
                     'method', 'import', 'return', 'def ', 'async', 'await', 'loop', 'цикл',
                     'массив', 'array', 'list', 'dict', 'json', 'api', 'http', 'request'],
        'weight': 2.0
    },
    'ui': {
        'keywords': ['интерфейс', 'ui', 'кнопк', 'форм', 'html', 'css', 'дизайн', 'layout',
                     'button', 'input', 'canvas', 'игр', 'game', 'визуализ', 'chart', 'график',
                     'dashboard', 'дашборд', 'калькулятор', 'calculator', 'анимац', 'animation'],
        'weight': 2.0
    },
    'analysis': {
        'keywords': ['анализ', 'проверь', 'найди ошибк', 'оптимиз', 'ревью', 'review',
                     'analyze', 'check', 'debug', 'исправ', 'fix', 'bug', 'баг', 'проблем',
                     'error', 'ошибк', 'exception', 'рефактор', 'refactor'],
        'weight': 1.8
    },
    'memory': {
        'keywords': ['запомни', 'помни', 'вспомни', 'память', 'remember', 'memory', 'forget',
                     'забудь', 'знаешь', 'знал', 'узнал', 'learned', 'учил', 'выучил'],
        'weight': 2.0
    },
    'creative': {
        'keywords': ['создай', 'придумай', 'напиши', 'сгенерируй', 'generate', 'create',
                     'make', 'build', 'история', 'story', 'сказк', 'стих', 'poem'],
        'weight': 1.5
    },
    'question': {
        'keywords': ['что', 'как', 'почему', 'зачем', 'когда', 'где', 'кто', 'какой',
                     'what', 'how', 'why', 'when', 'where', 'who', 'which', 'explain',
                     'объясни', 'расскажи', 'tell'],
        'weight': 1.3
    },
    'action': {
        'keywords': ['сделай', 'выполни', 'запусти', 'останови', 'удали', 'добавь',
                     'измени', 'обнови', 'do', 'run', 'execute', 'stop', 'delete', 'add',
                     'change', 'update', 'install', 'установи'],
        'weight': 1.7
    }
}


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
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return default


def _env_tri_state(name: str) -> Optional[bool]:
    raw = os.getenv(name)
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return None


_LOCAL_EMBED_DIM = _env_int("NEIRA_LOCAL_EMBED_DIM", 384, min_value=32, max_value=4096)
_LOCAL_MIN_NGRAM = _env_int("NEIRA_LOCAL_EMBED_MIN_NGRAM", 3, min_value=1, max_value=8)
_LOCAL_MAX_NGRAM = _env_int("NEIRA_LOCAL_EMBED_MAX_NGRAM", 5, min_value=1, max_value=10)
_LOCAL_MAX_NGRAMS = _env_int("NEIRA_LOCAL_EMBED_MAX_NGRAMS", 8000, min_value=128, max_value=200000)
_LOCAL_MAX_TEXT_CHARS = _env_int("NEIRA_LOCAL_EMBED_MAX_TEXT_CHARS", 20000, min_value=256, max_value=200000)

if _LOCAL_MAX_NGRAM < _LOCAL_MIN_NGRAM:
    _LOCAL_MAX_NGRAM = _LOCAL_MIN_NGRAM

# Включить семантические фичи (по умолчанию да)
_USE_SEMANTIC_FEATURES = _env_bool("NEIRA_LOCAL_EMBED_SEMANTIC", True)

# Размер LRU кэша для эмбеддингов
_EMBED_CACHE_SIZE = _env_int("NEIRA_LOCAL_EMBED_CACHE_SIZE", 1000, min_value=100, max_value=10000)


def local_embeddings_enabled() -> bool:
    tri_state = _env_tri_state("NEIRA_LOCAL_EMBEDDINGS")
    if tri_state is not None:
        return tri_state
    return _env_bool("NEIRA_DISABLE_OLLAMA", False)


# ============== Text Processing ==============

def _normalize_text(text: str) -> str:
    """Нормализовать текст: lowercase, убрать лишние пробелы"""
    text = text.strip().lower()
    if not text:
        return ""
    return " ".join(text.split())


def _tokenize(text: str) -> List[str]:
    """Разбить текст на токены"""
    # Разбиваем по не-буквенным символам, сохраняя кириллицу и латиницу
    tokens = re.findall(r'[a-zA-Zа-яА-ЯёЁ0-9]+', text.lower())
    return tokens


def _remove_stopwords(tokens: List[str]) -> List[str]:
    """Удалить стоп-слова"""
    return [t for t in tokens if t not in ALL_STOPWORDS and len(t) > 1]


def _simple_stem_russian(word: str) -> str:
    """
    Простое стемминг для русского языка
    Удаляет распространённые окончания
    """
    if len(word) < 4:
        return word
    
    # Распространённые окончания
    endings = [
        'ость', 'ение', 'ание', 'ться', 'ают', 'ует', 'ить', 'ать', 'ять',
        'ого', 'его', 'ому', 'ему', 'ым', 'им', 'ой', 'ей', 'ую', 'юю',
        'ые', 'ие', 'ых', 'их', 'ая', 'яя', 'ое', 'ее',
        'ов', 'ев', 'ам', 'ям', 'ах', 'ях', 'ми',
        'ся', 'сь', 'ет', 'ит', 'ут', 'ют', 'ла', 'ло', 'ли',
    ]
    
    for ending in endings:
        if word.endswith(ending) and len(word) - len(ending) >= 2:
            return word[:-len(ending)]
    
    return word


def _simple_stem_english(word: str) -> str:
    """
    Простой стемминг для английского
    Porter-подобный, но упрощённый
    """
    if len(word) < 4:
        return word
    
    # Распространённые окончания
    endings = [
        'ment', 'ness', 'tion', 'sion', 'able', 'ible', 'ful', 'less',
        'ive', 'ous', 'ity', 'ing', 'ed', 'er', 'es', 'ly', 's'
    ]
    
    for ending in endings:
        if word.endswith(ending) and len(word) - len(ending) >= 2:
            return word[:-len(ending)]
    
    return word


def _stem_word(word: str) -> str:
    """Стемминг слова (автоопределение языка)"""
    # Определяем язык по первым буквам
    if re.match(r'[а-яё]', word):
        return _simple_stem_russian(word)
    else:
        return _simple_stem_english(word)


def _extract_keywords(text: str) -> List[str]:
    """Извлечь ключевые слова из текста"""
    tokens = _tokenize(text)
    tokens = _remove_stopwords(tokens)
    stems = [_stem_word(t) for t in tokens]
    return stems


# ============== Semantic Features ==============

def _detect_categories(text: str) -> Dict[str, float]:
    """
    Определить семантические категории текста
    
    Returns:
        Словарь {категория: score}
    """
    text_lower = text.lower()
    detected = {}
    
    for category, data in SEMANTIC_CATEGORIES.items():
        score = 0.0
        for keyword in data['keywords']:
            if keyword in text_lower:
                score += data['weight']
        if score > 0:
            detected[category] = score
    
    return detected


def _category_to_vector(categories: Dict[str, float], dim: int) -> List[float]:
    """
    Преобразовать категории в вектор фиксированной размерности
    """
    vector = [0.0] * dim
    
    if not categories:
        return vector
    
    # Используем хэширование имён категорий для получения индексов
    for category, score in categories.items():
        digest = hashlib.blake2b(category.encode('utf-8'), digest_size=8).digest()
        # Используем несколько индексов для каждой категории (distributed representation)
        for i in range(4):
            offset = i * 2
            index = int.from_bytes(digest[offset:offset+2], 'little') % dim
            sign = 1.0 if (digest[offset] & 1) == 0 else -1.0
            vector[index] += sign * score
    
    return vector


# ============== Main Embedding Function ==============

@lru_cache(maxsize=_EMBED_CACHE_SIZE)
def _get_embedding_cached(text: str) -> Optional[Tuple[float, ...]]:
    """Кэшированная версия (возвращает tuple для hashable)"""
    result = _compute_embedding(text)
    return tuple(result) if result else None


def _compute_embedding(text: str) -> Optional[List[float]]:
    """
    Вычислить эмбеддинг текста
    
    Комбинирует:
    1. N-gram хэши (базовый метод)
    2. Семантические категории
    3. TF-подобное взвешивание
    """
    normalized = _normalize_text(text)
    if not normalized:
        return None
    
    if len(normalized) > _LOCAL_MAX_TEXT_CHARS:
        normalized = normalized[:_LOCAL_MAX_TEXT_CHARS]
    
    dim = _LOCAL_EMBED_DIM
    
    # Часть 1: N-gram хэши (70% вектора)
    ngram_dim = int(dim * 0.7)
    ngram_vector = _compute_ngram_vector(normalized, ngram_dim)
    
    if _USE_SEMANTIC_FEATURES:
        # Часть 2: Семантические категории (15% вектора)
        category_dim = int(dim * 0.15)
        categories = _detect_categories(text)
        category_vector = _category_to_vector(categories, category_dim)
        
        # Часть 3: Keyword stems (15% вектора)
        keyword_dim = dim - ngram_dim - category_dim
        keywords = _extract_keywords(text)
        keyword_vector = _compute_keyword_vector(keywords, keyword_dim)
        
        # Объединяем
        vector = ngram_vector + category_vector + keyword_vector
    else:
        # Только n-gram
        vector = ngram_vector + [0.0] * (dim - ngram_dim)
    
    # Нормализуем
    norm = math.sqrt(sum(v * v for v in vector))
    if norm <= 1e-12:
        return None
    
    return [v / norm for v in vector]


def _compute_ngram_vector(text: str, dim: int) -> List[float]:
    """Вычислить n-gram вектор"""
    vector = [0.0] * dim
    count = 0
    length = len(text)
    min_n = _LOCAL_MIN_NGRAM
    max_n = _LOCAL_MAX_NGRAM
    max_ngrams = _LOCAL_MAX_NGRAMS
    
    for i in range(length):
        for n in range(min_n, max_n + 1):
            end = i + n
            if end > length:
                break
            ngram = text[i:end]
            digest = hashlib.blake2b(ngram.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            
            # TF-подобное взвешивание: короткие n-gram менее важны
            weight = math.log(n + 1)
            vector[index] += sign * weight
            
            count += 1
            if count >= max_ngrams:
                break
        if count >= max_ngrams:
            break
    
    return vector


def _compute_keyword_vector(keywords: List[str], dim: int) -> List[float]:
    """Вычислить вектор на основе ключевых слов"""
    vector = [0.0] * dim
    
    if not keywords:
        return vector
    
    # Подсчитываем частоту
    keyword_counts: Dict[str, int] = {}
    for kw in keywords:
        keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
    
    # Хэшируем каждое ключевое слово
    for keyword, count in keyword_counts.items():
        digest = hashlib.blake2b(keyword.encode('utf-8'), digest_size=8).digest()
        index = int.from_bytes(digest[:4], 'little') % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        
        # TF-подобное взвешивание
        weight = 1 + math.log(count)
        vector[index] += sign * weight
    
    return vector


def get_local_embedding(text: str) -> Optional[List[float]]:
    """
    Получить локальный эмбеддинг текста
    
    Использует кэширование для производительности
    """
    if not local_embeddings_enabled():
        return None
    if not isinstance(text, str):
        return None
    
    # Используем кэшированную версию
    cached = _get_embedding_cached(text)
    return list(cached) if cached else None


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Вычислить косинусное сходство между двумя векторами
    
    Оба вектора должны быть нормализованы (норма = 1)
    """
    if len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    return dot_product


def find_similar(
    query: str,
    candidates: List[Tuple[str, List[float]]],
    top_k: int = 5,
    threshold: float = 0.3
) -> List[Tuple[str, float]]:
    """
    Найти похожие тексты
    
    Args:
        query: Текст запроса
        candidates: Список (текст, эмбеддинг)
        top_k: Максимальное количество результатов
        threshold: Минимальный порог сходства
    
    Returns:
        Список (текст, score) отсортированный по убыванию score
    """
    query_emb = get_local_embedding(query)
    if not query_emb:
        return []
    
    results = []
    for text, emb in candidates:
        if emb:
            score = cosine_similarity(query_emb, emb)
            if score >= threshold:
                results.append((text, score))
    
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def batch_embeddings(texts: List[str]) -> List[Optional[List[float]]]:
    """
    Получить эмбеддинги для нескольких текстов
    """
    return [get_local_embedding(t) for t in texts]


def clear_embedding_cache():
    """Очистить кэш эмбеддингов"""
    _get_embedding_cached.cache_clear()


def get_cache_stats() -> Dict[str, Any]:
    """Получить статистику кэша"""
    info = _get_embedding_cached.cache_info()
    return {
        'hits': info.hits,
        'misses': info.misses,
        'size': info.currsize,
        'maxsize': info.maxsize
    }


# ============== Test ==============

if __name__ == "__main__":
    # Включаем локальные эмбеддинги для теста
    os.environ["NEIRA_LOCAL_EMBEDDINGS"] = "true"
    
    print("🧪 Тест Local Embeddings v2.0")
    print("=" * 50)
    
    test_texts = [
        "Создай интерфейс для игры",
        "Напиши функцию сортировки массива",
        "Привет, как дела?",
        "Проанализируй этот код на ошибки",
        "Запомни что меня зовут Алексей",
    ]
    
    embeddings = []
    for text in test_texts:
        emb = get_local_embedding(text)
        if emb:
            embeddings.append((text, emb))
            print(f"✅ '{text[:30]}...' → dim={len(emb)}")
        else:
            print(f"❌ Не удалось создать эмбеддинг для '{text}'")
    
    print("\n" + "=" * 50)
    print("Сравнение сходства:")
    
    query = "Сделай интерфейс игры"
    print(f"\nЗапрос: '{query}'")
    
    similar = find_similar(query, embeddings, top_k=3)
    for text, score in similar:
        print(f"  {score:.3f}: {text}")
    
    print("\n" + "=" * 50)
    print("Категории:")
    
    for text in test_texts[:3]:
        cats = _detect_categories(text)
        print(f"'{text[:30]}...' → {cats}")
    
    print("\n" + "=" * 50)
    print(f"Статистика кэша: {get_cache_stats()}")
    print("\n🎉 Тесты завершены!")
