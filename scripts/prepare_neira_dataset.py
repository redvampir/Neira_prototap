"""
Подготовка JSONL-датасета для обучения Neira.

Скрипт читает .json/.jsonl файлы и приводит примеры к формату
{"prompt": "...", "completion": "..."}.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_INPUT_PATH = Path("training_scenarios")
DEFAULT_OUTPUT_PATH = Path("training_data/neira_training.jsonl")
SUPPORTED_EXTENSIONS = {".json", ".jsonl"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Подготовка JSONL-датасета для обучения Neira."
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="Путь к файлу или папке с .json/.jsonl.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Куда сохранить JSONL-датасет.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Перезаписать выходной файл, если он существует.",
    )
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="Удалять дубликаты по паре prompt/completion.",
    )
    return parser.parse_args()


def _collect_input_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if source.is_dir():
        return sorted(
            path
            for path in source.rglob("*")
            if path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
    return []


def _load_json_records(path: Path) -> list[dict[str, object]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        logger.warning("Не удалось прочитать %s: %s", path, exc)
        return []
    except json.JSONDecodeError as exc:
        logger.warning("Некорректный JSON в %s: %s", path, exc)
        return []

    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    logger.warning("Неподдерживаемый формат JSON в %s", path)
    return []


def _load_jsonl_records(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    logger.warning("JSONL ошибка %s:%s: %s", path, line_number, exc)
                    continue
                if isinstance(payload, dict):
                    records.append(payload)
                else:
                    logger.warning("Строка %s:%s не объект JSON", path, line_number)
    except OSError as exc:
        logger.warning("Не удалось прочитать %s: %s", path, exc)
    return records


def _normalize_example(raw: dict[str, object]) -> dict[str, str] | None:
    if "prompt" in raw and "completion" in raw:
        prompt = str(raw["prompt"]).strip()
        completion = str(raw["completion"]).strip()
    elif all(key in raw for key in ("instruction", "input", "output")):
        instruction = str(raw["instruction"]).strip()
        input_text = str(raw["input"]).strip()
        output = str(raw["output"]).strip()
        prompt_parts = [instruction, input_text] if input_text else [instruction]
        prompt = "\n\n".join(part for part in prompt_parts if part)
        completion = output
    elif "question" in raw and ("response" in raw or "corrected_response" in raw):
        prompt = str(raw.get("question", "")).strip()
        corrected = str(raw.get("corrected_response") or "").strip()
        response = str(raw.get("response") or "").strip()
        rating = raw.get("rating")
        if corrected:
            completion = corrected
        elif isinstance(rating, (int, float)) and rating <= 2:
            return None
        else:
            completion = response
    else:
        return None

    if not prompt or not completion:
        return None
    return {"prompt": prompt, "completion": completion}


def _dedupe_examples(examples: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for example in examples:
        key = (example["prompt"], example["completion"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(example)
    return unique


def _write_jsonl(
    examples: list[dict[str, str]],
    output_path: Path,
    overwrite: bool,
) -> bool:
    if output_path.exists() and not overwrite:
        logger.error("Файл %s уже существует. Используйте --overwrite.", output_path)
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("w", encoding="utf-8") as handle:
            for example in examples:
                handle.write(json.dumps(example, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.error("Не удалось записать %s: %s", output_path, exc)
        return False
    logger.info("Готово: %s примеров -> %s", len(examples), output_path)
    return True


def main() -> int:
    args = _parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    input_path = Path(args.input)
    output_path = Path(args.output)

    input_files = _collect_input_files(input_path)
    if not input_files:
        logger.error("Нет подходящих файлов в %s", input_path)
        return 1

    examples: list[dict[str, str]] = []
    for path in input_files:
        records = _load_jsonl_records(path) if path.suffix.lower() == ".jsonl" else _load_json_records(path)
        for record in records:
            normalized = _normalize_example(record)
            if normalized is None:
                logger.warning("Пропуск записи без нужных ключей в %s", path)
                continue
            examples.append(normalized)

    if not examples:
        logger.error("Не удалось собрать ни одного примера.")
        return 1

    if args.dedupe:
        examples = _dedupe_examples(examples)

    if not _write_jsonl(examples, output_path, args.overwrite):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
