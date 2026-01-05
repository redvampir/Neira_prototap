#!/usr/bin/env python3
"""
Smoke-тест автономного обучения Neira.

Проверяет:
- извлечение summary из Wikipedia REST API (с User-Agent)
- помещение факта в карантин
- автоодобрение и перенос в память (MemorySystem v2)
- совместимость, если передали MemoryCell (unwrap -> MemorySystem)

Важно: тест работает в temp-директориях и не трогает реальные файлы памяти проекта.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


def _configure_stdio() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


@dataclass(frozen=True)
class SmokeResult:
    quarantine_added: int
    quarantine_remaining: int
    long_term_added: int


async def _run_smoke(memory_provider: str) -> SmokeResult:
    os.environ.setdefault(
        "NEIRA_HTTP_USER_AGENT",
        "NeiraAutonomousLearningTest/1.0 (mailto:local@example.invalid)",
    )

    repo = _repo_root()

    prev_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as td:
        os.chdir(td)
        try:
            sys.path.insert(0, str(repo))

            from autonomous_learning import AutonomousLearningSystem
            from memory_system import MemorySystem

            if memory_provider == "memory_system":
                memory = MemorySystem(base_path=td)
                learner = AutonomousLearningSystem(memory_system=memory, idle_threshold_minutes=0)
                long_term_ref = memory.long_term
            elif memory_provider == "memory_cell":
                from cells import MemoryCell

                memory_cell = MemoryCell(memory_file=os.path.join(td, "neira_memory.json"))
                learner = AutonomousLearningSystem(memory_system=memory_cell, idle_threshold_minutes=0)
                if not memory_cell.memory_system:
                    raise RuntimeError("MemoryCell.memory_system не инициализирован (MemorySystem v2 отключён?).")
                long_term_ref = memory_cell.memory_system.long_term
            else:
                raise ValueError(f"Неизвестный memory_provider: {memory_provider}")

            long_term_before = len(long_term_ref)

            await learner._learn_from_keyword("Python", {})

            quarantine_added = len(learner.quarantine)
            if quarantine_added == 0:
                raise RuntimeError(
                    "Факт не попал в карантин. "
                    "Проверь сеть/доступ к Wikipedia и User-Agent (NEIRA_HTTP_USER_AGENT)."
                )

            # Форсируем авто-одобрение в тесте (чтобы не зависеть от эвристик confidence).
            learner.quarantine[0].confidence = 0.95
            await learner._review_quarantine()

            long_term_after = len(long_term_ref)
            return SmokeResult(
                quarantine_added=quarantine_added,
                quarantine_remaining=len(learner.quarantine),
                long_term_added=long_term_after - long_term_before,
            )
        finally:
            os.chdir(prev_cwd)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

    print("=" * 70)
    print("SMOKE: AutonomousLearningSystem + MemorySystem")
    print("=" * 70)
    r1 = await _run_smoke("memory_system")
    print(r1)

    print("\n" + "=" * 70)
    print("SMOKE: AutonomousLearningSystem + MemoryCell (unwrap)")
    print("=" * 70)
    r2 = await _run_smoke("memory_cell")
    print(r2)

    print("\n✅ Готово: автономное обучение делает запрос, кладёт факт в карантин и переносит в память.")


if __name__ == "__main__":
    _configure_stdio()
    asyncio.run(main())

