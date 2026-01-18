"""
Ремонт JSON-файла памяти, если он был повреждён при записи.

По умолчанию чинит `neira_memory.json` в корне репозитория.
Создаёт бэкап рядом: `<file>.bak.<timestamp>`.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


def _salvage_json_array(raw: str) -> list[Any]:
    decoder = json.JSONDecoder()
    i = 0
    n = len(raw)
    while i < n and raw[i].isspace():
        i += 1
    if i >= n or raw[i] != "[":
        raise ValueError("JSON не начинается с '['")
    i += 1

    items: list[Any] = []
    while i < n:
        while i < n and raw[i].isspace():
            i += 1
        if i >= n or raw[i] == "]":
            break
        if raw[i] == ",":
            i += 1
            continue
        item, next_i = decoder.raw_decode(raw, i)
        items.append(item)
        i = next_i
    return items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="neira_memory.json", help="Путь к JSON-файлу памяти")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"Файл не найден: {path}")

    raw = path.read_text(encoding="utf-8")
    try:
        json.loads(raw)
        print(f"OK: {path} (уже валиден)")
        return 0
    except json.JSONDecodeError as exc:
        print(f"Повреждён JSON, пробую восстановить: {exc}")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.bak.{ts}")
    shutil.copy2(path, backup)
    print(f"Backup: {backup}")

    items = _salvage_json_array(raw)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Repaired: {path} (items={len(items)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

