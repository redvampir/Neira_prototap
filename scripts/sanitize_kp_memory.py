"""
Цель: убрать из сохранённой памяти ошибочную расшифровку «КП» как «Командное письмо».
Инварианты: правим только записи, где есть "Командного Письма"; остальные данные не трогаем.
Риски: потеря части истории; по умолчанию делается backup перед записью.
Проверка: `python scripts/sanitize_kp_memory.py --write`
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


_NEEDLE = "Командного Письма"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Не удалось прочитать JSON: {path}: {exc}") from exc


def _write_json(path: Path, data: Any) -> None:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Не удалось записать JSON: {path}: {exc}") from exc


def _backup_file(path: Path) -> Path:
    backup_path = path.with_suffix(path.suffix + ".bak")
    try:
        backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"Не удалось создать backup: {backup_path}: {exc}") from exc
    return backup_path


def _contains_needle(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return _NEEDLE in value


def _filter_records(records: Any, *, field_name: str) -> tuple[Any, int]:
    """
    Удаляет элементы списка-словарей, где `field_name` содержит needle.

    Returns:
        (records_without_bad, removed_count)
    """
    if not isinstance(records, list):
        return records, 0

    kept: list[Any] = []
    removed = 0
    for item in records:
        if isinstance(item, dict) and _contains_needle(item.get(field_name)):
            removed += 1
            continue
        kept.append(item)
    return kept, removed


def sanitize_emotional_memory(data: Any) -> tuple[Any, int]:
    removed = 0
    if not isinstance(data, dict):
        return data, removed

    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        return data, removed

    for _user_id, profile in profiles.items():
        if not isinstance(profile, dict):
            continue

        # Актуальная структура: профиль хранит список "emotional_moments"
        emotional_moments = profile.get("emotional_moments")
        filtered, removed_here = _filter_records(emotional_moments, field_name="my_response")
        if removed_here:
            profile["emotional_moments"] = filtered
            removed += removed_here

    return data, removed


def sanitize_emotional_state(data: Any) -> tuple[Any, int]:
    removed = 0
    if not isinstance(data, dict):
        return data, removed

    history = data.get("history")
    filtered, removed = _filter_records(history, field_name="details")
    if removed:
        data["history"] = filtered
    return data, removed


def sanitize_chat_contexts(data: Any) -> tuple[Any, int]:
    removed = 0
    if not isinstance(data, dict):
        return data, removed

    for _chat_id, ctx in data.items():
        if not isinstance(ctx, dict):
            continue
        history = ctx.get("context_history")
        if not isinstance(history, list):
            continue

        kept: list[Any] = []
        for msg in history:
            if isinstance(msg, dict) and msg.get("role") == "assistant" and _contains_needle(msg.get("content")):
                removed += 1
                continue
            kept.append(msg)
        ctx["context_history"] = kept

    return data, removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="Записать изменения в файлы (иначе dry-run).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    targets: list[tuple[Path, str]] = [
        (repo_root / "data" / "emotional_memory.json", "emotional_memory"),
        (repo_root / "data" / "emotional_state.json", "emotional_state"),
        (repo_root / "neira_chat_contexts.json", "chat_contexts"),
    ]

    total_removed = 0
    for path, kind in targets:
        if not path.exists():
            print(f"- Пропускаю (нет файла): {path}")
            continue

        original = _read_json(path)

        if kind == "emotional_memory":
            updated, removed = sanitize_emotional_memory(original)
        elif kind == "emotional_state":
            updated, removed = sanitize_emotional_state(original)
        elif kind == "chat_contexts":
            updated, removed = sanitize_chat_contexts(original)
        else:
            raise RuntimeError(f"Неизвестный тип: {kind}")

        total_removed += removed
        print(f"- {path}: удалено записей = {removed}")

        if args.write and removed:
            _backup_file(path)
            _write_json(path, updated)

    print(f"Итого удалено записей: {total_removed}")
    if not args.write:
        print("Dry-run: добавь `--write`, чтобы применить изменения.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
