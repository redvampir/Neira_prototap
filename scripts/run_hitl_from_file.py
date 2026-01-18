"""
Запуск HITL-сценария из файла вопросов.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from neira_cortex import NeiraCortex
from training_orchestrator import TrainingOrchestrator

logger = logging.getLogger(__name__)

DEFAULT_NAME = "HITL: Русский язык"
DEFAULT_DESCRIPTION = "HITL-сценарий для оценки ответов."
DEFAULT_CATEGORY = "general"
MIN_HITL_QUESTIONS = 50
SUPPORTED_EXTENSIONS = {".json", ".jsonl"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Запуск HITL-сценария из файла вопросов."
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Путь к JSON/JSONL файлу с вопросами.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Автоматический режим без HITL-оценок.",
    )
    return parser.parse_args()


def _extract_metadata(data: Dict[str, Any]) -> Tuple[str, str, str]:
    name = str(data.get("name", DEFAULT_NAME)).strip() or DEFAULT_NAME
    description = str(data.get("description", DEFAULT_DESCRIPTION)).strip() or DEFAULT_DESCRIPTION
    category = str(data.get("category", DEFAULT_CATEGORY)).strip() or DEFAULT_CATEGORY
    return name, description, category


def _load_json_questions(path: Path) -> Tuple[List[str], Tuple[str, str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        questions = data.get("questions", [])
        name, description, category = _extract_metadata(data)
    elif isinstance(data, list):
        questions = data
        name, description, category = DEFAULT_NAME, DEFAULT_DESCRIPTION, DEFAULT_CATEGORY
    else:
        return [], (DEFAULT_NAME, DEFAULT_DESCRIPTION, DEFAULT_CATEGORY)
    normalized = [str(q).strip() for q in questions if str(q).strip()]
    return normalized, (name, description, category)


def _load_jsonl_questions(path: Path) -> List[str]:
    questions: List[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("JSONL ошибка %s:%s", path, line_number)
                continue
            if isinstance(payload, dict) and "question" in payload:
                questions.append(str(payload["question"]).strip())
            elif isinstance(payload, str):
                questions.append(payload.strip())
    return [q for q in questions if q]


def _dedupe_questions(questions: List[str]) -> List[str]:
    unique: List[str] = []
    seen = set()
    for question in questions:
        if question in seen:
            continue
        seen.add(question)
        unique.append(question)
    return unique


def _load_questions(path: Path) -> Tuple[List[str], Tuple[str, str, str]]:
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        logger.error("Неподдерживаемый формат: %s", path.suffix)
        return [], (DEFAULT_NAME, DEFAULT_DESCRIPTION, DEFAULT_CATEGORY)
    try:
        if path.suffix.lower() == ".json":
            questions, meta = _load_json_questions(path)
        else:
            questions = _load_jsonl_questions(path)
            meta = (DEFAULT_NAME, DEFAULT_DESCRIPTION, DEFAULT_CATEGORY)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Ошибка загрузки %s: %s", path, exc)
        return [], (DEFAULT_NAME, DEFAULT_DESCRIPTION, DEFAULT_CATEGORY)
    return _dedupe_questions(questions), meta


def main() -> int:
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    path = Path(args.file)
    if not path.exists():
        logger.error("Файл не найден: %s", path)
        return 1
    questions, meta = _load_questions(path)
    if len(questions) < MIN_HITL_QUESTIONS:
        logger.error("Нужно минимум %s вопросов, найдено %s.", MIN_HITL_QUESTIONS, len(questions))
        return 1

    name, description, category = meta
    cortex = NeiraCortex(use_llm=True)
    orchestrator = TrainingOrchestrator(cortex.pathways)
    scenario = orchestrator.create_scenario(
        name=name,
        description=description,
        questions=questions,
        category=category,
    )
    orchestrator.run_scenario(scenario.id, cortex, auto_mode=args.auto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
