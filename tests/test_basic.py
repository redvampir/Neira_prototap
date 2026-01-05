"""
Базовые тесты — проверка что проект импортируется и запускается.

Запуск: pytest tests/test_basic.py -v
"""
import pytest


class TestImports:
    """Тесты импортов основных модулей."""
    
    def test_import_cells(self):
        """Проверяем что cells.py импортируется."""
        from cells import Cell, MemoryCell, AnalyzerCell
        assert Cell is not None
        assert MemoryCell is not None
    
    def test_import_memory_system(self):
        """Проверяем что memory_system импортируется."""
        from memory_system import MemorySystem, MemoryEntry, MemoryType
        assert MemorySystem is not None
    
    def test_import_llm_providers(self):
        """Проверяем что llm_providers импортируется."""
        from llm_providers import LLMManager, ProviderType
        assert LLMManager is not None
    
    def test_import_organ_system(self):
        """Проверяем что система органов импортируется."""
        from unified_organ_system import UnifiedOrganSystem, OrganDefinition
        from executable_organs import ExecutableOrgan, get_organ_registry
        assert UnifiedOrganSystem is not None
        assert get_organ_registry is not None
    
    def test_import_cortex(self):
        """Проверяем что cortex импортируется."""
        from neira_cortex import NeiraCortex, IntentType
        assert NeiraCortex is not None
    
    def test_import_rate_limiter(self):
        """Проверяем что rate_limiter импортируется."""
        from rate_limiter import RateLimiter, RateLimitConfig
        assert RateLimiter is not None


class TestBasicFunctionality:
    """Базовые тесты функциональности."""
    
    def test_memory_cell_creation(self):
        """Создание MemoryCell."""
        from cells import MemoryCell
        memory = MemoryCell()
        assert memory is not None
        assert hasattr(memory, 'remember')
        assert hasattr(memory, 'recall')
    
    def test_organ_registry_singleton(self):
        """Реестр органов — singleton."""
        from executable_organs import get_organ_registry
        r1 = get_organ_registry()
        r2 = get_organ_registry()
        assert r1 is r2
    
    def test_intent_recognition(self):
        """Распознавание намерений."""
        from neira_cortex import IntentRecognizer, IntentType
        recognizer = IntentRecognizer()
        
        # Приветствие
        intent, conf = recognizer.recognize("привет!")
        assert intent == IntentType.GREETING
        
        # Вопрос (без слов-триггеров кода)
        intent, conf = recognizer.recognize("где находится Москва?")
        assert intent == IntentType.QUESTION
    
    @pytest.mark.slow
    def test_llm_manager_creation(self):
        """Создание LLM менеджера."""
        from llm_providers import create_default_manager
        manager = create_default_manager()
        # Может не быть провайдеров — это OK
        assert manager is not None


class TestTypeHints:
    """Проверка что type hints корректны."""
    
    def test_optional_parameters(self):
        """Проверка Optional параметров."""
        from unified_organ_system import UnifiedOrganSystem
        system = UnifiedOrganSystem()
        
        # Должно работать без ошибок
        result = system.find_similar_organ("test", triggers=None)
        assert result is None or hasattr(result, 'name')

class TestRateLimiter:
    """Тесты Rate Limiter."""
    
    def test_basic_limiting(self):
        """Базовый rate limiting."""
        from rate_limiter import RateLimiter, RateLimitConfig
        
        config = RateLimitConfig(
            requests_per_minute=3,
            burst_limit=10,
            min_interval_seconds=0.0
        )
        limiter = RateLimiter(config)
        
        # Первые 3 запроса должны пройти
        for i in range(3):
            allowed, _ = limiter.check("test")
            assert allowed, f"Запрос {i+1} должен быть разрешён"
            limiter.record("test")
        
        # 4-й должен быть заблокирован
        allowed, reason = limiter.check("test")
        assert not allowed
        assert "Лимит" in reason
    
    def test_separate_users(self):
        """Разные пользователи — разные лимиты."""
        from rate_limiter import RateLimiter, RateLimitConfig
        
        config = RateLimitConfig(requests_per_minute=2)
        limiter = RateLimiter(config)
        
        # Заполняем лимит user1
        limiter.record("user1")
        limiter.record("user1")
        
        # user2 ещё не исчерпал лимит
        allowed, _ = limiter.check("user2")
        assert allowed