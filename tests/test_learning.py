import asyncio
import tempfile
from pathlib import Path
import json

import pytest

from content_extractor import LearningManager


def test_learn_from_file(monkeypatch, tmp_path: Path):
    # Создаём временный текстовый файл
    sample = tmp_path / "sample.txt"
    sample.write_text("Hello world. This is a test.\nAnother line.", encoding='utf-8')

    # Подменяем сохранение истории чтобы не менять реальный файл
    monkeypatch.setattr(LearningManager, "_save_history", lambda self: None)

    manager = LearningManager(memory_system=None)

    # Запускаем async вызов
    result = asyncio.run(manager.learn_from_source(str(sample), category="test", summarize=False))

    assert isinstance(result, dict)
    assert result.get("success") is True
    assert result.get("word_count") > 0
