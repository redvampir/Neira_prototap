"""
Хранилище мозга Neira.

Отдельная точка входа позволяет изолировать путь к БД и постепенно
отделять новый мозг от устаревших зависимостей.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from neira_brain import NeiraBrain

logger = logging.getLogger(__name__)

ENV_BRAIN_DB = "NEIRA_BRAIN_DB"
DEFAULT_BRAIN_DB_PATH = Path("artifacts") / "neira_brain_v2.db"


def _resolve_db_path(explicit: str | Path | None = None) -> Path:
    """
    Вычисляет путь к БД с учётом аргумента и переменных окружения.
    """
    if explicit is not None:
        return Path(explicit)
    env_path = os.getenv(ENV_BRAIN_DB)
    if env_path:
        return Path(env_path)
    return DEFAULT_BRAIN_DB_PATH


def _ensure_parent_dir(path: Path) -> None:
    """Создаёт директорию для БД, если её ещё нет."""
    path.parent.mkdir(parents=True, exist_ok=True)


def get_brain_store(db_path: str | Path | None = None) -> NeiraBrain:
    """
    Возвращает экземпляр хранилища мозга с учётом выбранного пути к БД.
    """
    resolved = _resolve_db_path(db_path)
    _ensure_parent_dir(resolved)
    brain = NeiraBrain(resolved)
    if brain.db_path != resolved:
        logger.warning(
            "Запрошен путь БД %s, но используется %s",
            resolved,
            brain.db_path,
        )
    return brain


__all__ = ["get_brain_store"]
