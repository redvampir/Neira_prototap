import builtins
import pytest
from datetime import datetime

import sys
from pathlib import Path

# Pytest иногда выбирает rootdir на уровень выше `prototype/` (тогда import main ломается).
# Делаем импорт стабильным: добавляем корень проекта в sys.path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import main as main_mod


class SimpleResult:
    def __init__(self, content: str, metadata: dict | None = None):
        self.content = content
        self.metadata = metadata or {}


class StubMemory:
    def __init__(self, *args, **kwargs):
        self._session = []
        self.memories = []

    def add_to_session(self, text: str):
        self._session.append(text)

    def recall_text(self, query: str, top_k: int = 3):
        return []

    def remember(self, text: str, importance: float = 0.5, category: str = 'general', source: str = 'test'):
        entry = {
            'text': text,
            'importance': importance,
            'category': category,
            'source': source,
            'timestamp': datetime.now().isoformat()
        }
        self.memories.append(entry)

    def get_stats(self):
        return {'total': len(self.memories), 'conversation': len(self.memories), 'web': 0, 'code': 0}


class StubCell:
    def __init__(self, memory=None, *args, **kwargs):
        self.memory = memory

    def process(self, *args, **kwargs):
        return SimpleResult("Привет! Меня зовут Нейра.")


class StubPlanner(StubCell):
    def process(self, user_input, analysis_content=None):
        return SimpleResult("Ответь кратко и по делу.")


class StubExecutor(StubCell):
    def process(self, user_input, plan_content, full_extra_context, problems=""):
        if "Как тебя зовут" in user_input or "Как тебя зовут" in plan_content:
            return SimpleResult("Привет! Меня зовут Нейра.")
        if "Расскажи о себе" in user_input:
            return SimpleResult("Я — Нейра, живая AI программа.")
        return SimpleResult("Я могу помогать с разными задачами.")


class StubVerifier(StubCell):
    def process(self, *args, **kwargs):
        return SimpleResult("ПРИНЯТ")


class StubFactExtractor(StubCell):
    def process(self, *args, **kwargs):
        # Возвращаем список фактов (словари) — соответствие ожидаемому интерфейсу
        return [
            {"text": "пример факта", "importance": 0.6, "category": "general", "source": "test"}
        ]


class StubExperience:
    def get_personality_prompt(self):
        return ""

    def get_relevant_experience(self, task_type):
        return []

    def record_experience(self, *args, **kwargs):
        return None


@pytest.fixture()
def mock_neira(monkeypatch):
    """Fixture that stubs heavy Neira subsystems for fast integration tests."""
    monkeypatch.setattr(main_mod, 'MemoryCell', StubMemory, raising=False)
    monkeypatch.setattr(main_mod, 'AnalyzerCell', StubCell, raising=False)
    monkeypatch.setattr(main_mod, 'PlannerCell', StubPlanner, raising=False)
    monkeypatch.setattr(main_mod, 'ExecutorCell', StubExecutor, raising=False)
    monkeypatch.setattr(main_mod, 'VerifierCell', StubVerifier, raising=False)
    monkeypatch.setattr(main_mod, 'FactExtractorCell', StubFactExtractor, raising=False)
    monkeypatch.setattr(main_mod, 'ExperienceSystem', StubExperience, raising=False)

    # Reduce retries to speed tests
    try:
        monkeypatch.setattr(main_mod, 'MAX_RETRIES', 0, raising=False)
    except Exception:
        pass

    # Mock input to immediately exit interactive loop
    monkeypatch.setattr(builtins, 'input', lambda prompt='': 'выход')

    yield
"""
Pytest конфигурация для тестов Neira.

Настраивает пути импорта и общие фикстуры.
"""
import sys
from pathlib import Path

import pytest

# Добавляем корень проекта в PYTHONPATH
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture
def project_root() -> Path:
    """Путь к корню проекта."""
    return ROOT_DIR


@pytest.fixture
def memory_system():
    """Фикстура для тестирования памяти."""
    from memory_system import MemorySystem
    ms = MemorySystem(".")
    yield ms
    # Cleanup после теста
    ms.clear_working_memory()


@pytest.fixture
def organ_registry():
    """Фикстура для реестра органов."""
    from executable_organs import get_organ_registry
    return get_organ_registry()


@pytest.fixture
def llm_manager():
    """Фикстура для LLM менеджера (если доступен)."""
    try:
        from llm_providers import create_default_manager
        manager = create_default_manager()
        if manager and manager.providers:
            return manager
    except Exception:
        pass
    pytest.skip("LLM Manager недоступен")
