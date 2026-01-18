#!/usr/bin/env python3
"""Train Neira: English starter script

Usage:
  python -m scripts.train_english [--dry-run] [--confirm]

--dry-run: extract and summarize sources without writing to memory
--confirm: actually write to memory (creates MemorySystem)
"""
import argparse
import asyncio
from pathlib import Path
import glob
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from content_extractor import LearningManager


async def run(sources, confirm: bool, summarize: bool):
    # If confirm, try to create MemorySystem (lazy import to avoid heavy init)
    memory = None
    if confirm:
        try:
            from memory_system import MemorySystem
            memory = MemorySystem()
        except Exception as e:
            logger.error(f"Не удалось инициализировать MemorySystem: {e}")
            logger.info("Продолжаем в режиме dry-run.")
            memory = None

    manager = LearningManager(memory_system=memory)

    logger.info(f"Запускаю обучение для {len(sources)} источников (confirm={confirm})")
    result = await manager.learn_batch(sources, category='english')

    # Сохраняем краткий отчёт
    report = {
        'sources': sources,
        'result': result
    }
    Path('artifacts').mkdir(exist_ok=True)
    out = Path('artifacts/train_english_report.json')
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    logger.info(f"Готово: {result.get('success')}/{result.get('total')} sources, words={result.get('total_words')}")
    logger.info(f"Отчёт записан в {out}")


def find_sources(data_dir: Path):
    patterns = ['*.txt', '*.md']
    files = []
    for p in patterns:
        files.extend(sorted([str(x) for x in data_dir.glob(p)]))
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Do not write to memory')
    parser.add_argument('--confirm', action='store_true', help='Write to memory (overrides dry-run)')
    parser.add_argument('--data-dir', default='training_data/english', help='Directory with training sources')
    parser.add_argument('--summarize', action='store_true', help='Create summaries for long texts')
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error(f"Data dir not found: {data_dir}")
        return

    sources = find_sources(data_dir)
    if not sources:
        logger.error(f"No sources found in {data_dir}")
        return

    # If confirm not set and dry-run false, default to dry-run
    confirm = args.confirm and not args.dry_run

    asyncio.run(run(sources, confirm=confirm, summarize=args.summarize))


if __name__ == '__main__':
    main()
