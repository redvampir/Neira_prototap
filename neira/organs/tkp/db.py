"""
Цель: SQLite-база ТКП (нормализованные параметры, связь модель → каталог).
Инварианты: Путь БД в artifacts/, никаких данных "из головы".
Проверка: python -m py_compile neira/organs/tkp/db.py
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from neira.config import TKP_DB_PATH

if TYPE_CHECKING:
    from neira.organs.tkp.parser import ParsedCatalog

logger = logging.getLogger(__name__)


def store_parsed_catalog(parsed: ParsedCatalog, db_path: Path | None = None) -> None:
    """
    Сохранить распарсенный каталог в SQLite.
    """
    db_path = db_path or TKP_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        _ensure_schema(conn)
        model_id = _upsert_model(conn, parsed.model_name, parsed.catalog_path)
        _upsert_parameters(conn, model_id, parsed.parameters)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tkp_models (
            id INTEGER PRIMARY KEY,
            model_name TEXT NOT NULL,
            model_normalized TEXT NOT NULL,
            catalog_path TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(model_normalized, catalog_path)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tkp_parameters (
            id INTEGER PRIMARY KEY,
            model_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            name_normalized TEXT NOT NULL,
            value TEXT,
            unit TEXT,
            source_page INTEGER,
            source_text TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(model_id, name_normalized),
            FOREIGN KEY(model_id) REFERENCES tkp_models(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tkp_params_name ON tkp_parameters(name_normalized)"
    )


def _upsert_model(
    conn: sqlite3.Connection,
    model_name: str,
    catalog_path: str,
) -> int:
    normalized = _normalize_text(model_name)
    now = datetime.now().isoformat()
    conn.execute(
        """
        INSERT INTO tkp_models (model_name, model_normalized, catalog_path, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(model_normalized, catalog_path) DO UPDATE SET
            model_name=excluded.model_name,
            updated_at=excluded.updated_at
        """,
        (model_name, normalized, catalog_path, now),
    )
    row = conn.execute(
        """
        SELECT id FROM tkp_models
        WHERE model_normalized = ? AND catalog_path = ?
        """,
        (normalized, catalog_path),
    ).fetchone()
    if row is None:
        raise sqlite3.Error("Не удалось сохранить модель в БД.")
    return int(row[0])


def _upsert_parameters(
    conn: sqlite3.Connection,
    model_id: int,
    parameters,
) -> None:
    now = datetime.now().isoformat()
    for param in parameters:
        normalized = _normalize_text(param.name)
        if not normalized:
            continue
        conn.execute(
            """
            INSERT INTO tkp_parameters (
                model_id,
                name,
                name_normalized,
                value,
                unit,
                source_page,
                source_text,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(model_id, name_normalized) DO UPDATE SET
                name=excluded.name,
                value=excluded.value,
                unit=excluded.unit,
                source_page=excluded.source_page,
                source_text=excluded.source_text,
                updated_at=excluded.updated_at
            """,
            (
                model_id,
                param.name,
                normalized,
                param.value,
                param.unit,
                param.source_page,
                param.source_text,
                now,
            ),
        )


def _normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"\\s+", " ", lowered)
    lowered = re.sub(r"[^a-z0-9а-яё _-]+", "", lowered)
    return lowered.strip()
