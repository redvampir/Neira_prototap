"""
🧠 Единый модуль управления памятью Neira

Объединяет функционал:
- memory_cleanup.py
- aggressive_memory_cleanup.py  
- clean_memory_duplicates.py
- memory_consolidator.py

Использование:
    from neira.utils.memory_manager import MemoryManager
    
    manager = MemoryManager()
    manager.full_cleanup()
    manager.find_duplicates()
    manager.consolidate()
"""

import json
import logging
import shutil
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from neira.config import (
    MEMORY_MAX_LONG_TERM,
    MEMORY_MAX_SHORT_TERM,
    MEMORY_CLEANUP_AGE_DAYS,
    MEMORY_MIN_CONFIDENCE,
)

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Менеджер памяти Neira.
    
    Обеспечивает:
    - Очистку устаревших записей
    - Удаление дубликатов
    - Консолидацию памяти
    - Бэкапы
    """
    
    def __init__(
        self,
        memory_file: str = "neira_memory.json",
        backup_dir: str = "memory_backups"
    ):
        """
        Инициализация менеджера памяти.
        
        Args:
            memory_file: Путь к файлу памяти
            backup_dir: Директория для бэкапов
        """
        self.memory_file = Path(memory_file)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
    
    def load(self) -> list[dict[str, Any]]:
        """Загружает память из файла."""
        if not self.memory_file.exists():
            logger.warning(f"Файл памяти не найден: {self.memory_file}")
            return []
        
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка чтения памяти: {e}")
            return []
    
    def save(self, memories: list[dict[str, Any]]) -> None:
        """Сохраняет память в файл."""
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(memories, f, ensure_ascii=False, indent=2)
        logger.info(f"Сохранено {len(memories)} записей")
    
    def create_backup(self) -> Path:
        """
        Создаёт бэкап памяти.
        
        Returns:
            Путь к файлу бэкапа
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"memory_backup_{timestamp}.json"
        
        if self.memory_file.exists():
            shutil.copy(self.memory_file, backup_path)
            logger.info(f"Бэкап создан: {backup_path}")
        
        return backup_path
    
    def find_duplicates(self) -> list[tuple[int, str]]:
        """
        Находит дубликаты в памяти.
        
        Returns:
            Список (индекс, текст) дубликатов
        """
        memories = self.load()
        seen_texts: dict[str, int] = {}
        duplicates: list[tuple[int, str]] = []
        
        for i, entry in enumerate(memories):
            text = entry.get('text', '').strip().lower()
            
            if text in seen_texts:
                duplicates.append((i, text[:70]))
            else:
                seen_texts[text] = i
        
        logger.info(f"Найдено дубликатов: {len(duplicates)}")
        return duplicates
    
    def find_loops(self, threshold: int = 5) -> list[tuple[str, int]]:
        """
        Находит зацикливания (много записей за короткий период).
        
        Args:
            threshold: Порог записей в минуту для детекции
            
        Returns:
            Список (timestamp, количество) зацикливаний
        """
        memories = self.load()
        time_buckets: dict[str, list[int]] = defaultdict(list)
        
        for i, entry in enumerate(memories):
            ts = entry.get('timestamp', '')
            if ts:
                minute_key = ts[:16]  # YYYY-MM-DDTHH:MM
                time_buckets[minute_key].append(i)
        
        loops = [
            (minute, len(indices))
            for minute, indices in time_buckets.items()
            if len(indices) > threshold
        ]
        
        logger.info(f"Найдено зацикливаний: {len(loops)}")
        return loops
    
    def cleanup_old(self, keep_days: int = MEMORY_CLEANUP_AGE_DAYS) -> int:
        """
        Удаляет записи старше указанного периода.
        
        Args:
            keep_days: Сколько дней хранить
            
        Returns:
            Количество удалённых записей
        """
        memories = self.load()
        cutoff = datetime.now() - timedelta(days=keep_days)
        
        original_count = len(memories)
        filtered = []
        
        for entry in memories:
            ts_str = entry.get('timestamp', '')
            try:
                ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                if ts.replace(tzinfo=None) > cutoff:
                    filtered.append(entry)
            except (ValueError, AttributeError):
                # Если нет timestamp — оставляем
                filtered.append(entry)
        
        removed = original_count - len(filtered)
        
        if removed > 0:
            self.save(filtered)
            logger.info(f"Удалено старых записей: {removed}")
        
        return removed
    
    def cleanup_low_confidence(
        self, 
        min_confidence: float = MEMORY_MIN_CONFIDENCE
    ) -> int:
        """
        Удаляет записи с низкой уверенностью.
        
        Args:
            min_confidence: Минимальный порог уверенности
            
        Returns:
            Количество удалённых записей
        """
        memories = self.load()
        original_count = len(memories)
        
        filtered = [
            m for m in memories
            if m.get('confidence', 1.0) >= min_confidence
        ]
        
        removed = original_count - len(filtered)
        
        if removed > 0:
            self.save(filtered)
            logger.info(f"Удалено записей с низкой уверенностью: {removed}")
        
        return removed
    
    def remove_duplicates(self) -> int:
        """
        Удаляет дубликаты из памяти.
        
        Returns:
            Количество удалённых дубликатов
        """
        memories = self.load()
        seen_texts: set[str] = set()
        unique: list[dict[str, Any]] = []
        
        for entry in memories:
            text = entry.get('text', '').strip().lower()
            
            if text not in seen_texts:
                seen_texts.add(text)
                unique.append(entry)
        
        removed = len(memories) - len(unique)
        
        if removed > 0:
            self.save(unique)
            logger.info(f"Удалено дубликатов: {removed}")
        
        return removed
    
    def consolidate(
        self,
        max_long_term: int = MEMORY_MAX_LONG_TERM,
        max_short_term: int = MEMORY_MAX_SHORT_TERM
    ) -> dict[str, int]:
        """
        Консолидирует память до заданных лимитов.
        
        Args:
            max_long_term: Максимум долгосрочных записей
            max_short_term: Максимум краткосрочных записей
            
        Returns:
            Статистика консолидации
        """
        memories = self.load()
        
        # Разделяем по типу
        long_term = [m for m in memories if m.get('memory_type') == 'long_term']
        short_term = [m for m in memories if m.get('memory_type') == 'short_term']
        other = [m for m in memories if m.get('memory_type') not in ('long_term', 'short_term')]
        
        # Сортируем по важности/времени и обрезаем
        long_term.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        short_term.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        stats = {
            'long_term_removed': max(0, len(long_term) - max_long_term),
            'short_term_removed': max(0, len(short_term) - max_short_term),
        }
        
        consolidated = (
            long_term[:max_long_term] + 
            short_term[:max_short_term] + 
            other
        )
        
        self.save(consolidated)
        logger.info(f"Консолидация: {stats}")
        
        return stats
    
    def full_cleanup(self, create_backup: bool = True) -> dict[str, int]:
        """
        Полная очистка памяти.
        
        Выполняет:
        1. Бэкап
        2. Удаление старых записей
        3. Удаление дубликатов
        4. Удаление низкой уверенности
        5. Консолидацию
        
        Args:
            create_backup: Создавать ли бэкап перед очисткой
            
        Returns:
            Статистика очистки
        """
        logger.info("=" * 50)
        logger.info("🧹 ПОЛНАЯ ОЧИСТКА ПАМЯТИ")
        logger.info("=" * 50)
        
        if create_backup:
            self.create_backup()
        
        stats = {
            'old_removed': self.cleanup_old(),
            'duplicates_removed': self.remove_duplicates(),
            'low_confidence_removed': self.cleanup_low_confidence(),
        }
        
        consolidate_stats = self.consolidate()
        stats.update(consolidate_stats)
        
        logger.info(f"Очистка завершена: {stats}")
        return stats
    
    def get_stats(self) -> dict[str, Any]:
        """
        Возвращает статистику памяти.
        
        Returns:
            Словарь со статистикой
        """
        memories = self.load()
        
        by_type: dict[str, int] = defaultdict(int)
        for m in memories:
            by_type[m.get('memory_type', 'unknown')] += 1
        
        return {
            'total_records': len(memories),
            'by_type': dict(by_type),
            'duplicates': len(self.find_duplicates()),
            'loops': len(self.find_loops()),
            'file_size_kb': (
                self.memory_file.stat().st_size / 1024 
                if self.memory_file.exists() 
                else 0
            ),
        }


# CLI для запуска из командной строки
def main():
    """CLI для управления памятью."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Управление памятью Neira')
    parser.add_argument(
        '--action', 
        choices=['cleanup', 'stats', 'duplicates', 'backup'],
        default='stats',
        help='Действие'
    )
    parser.add_argument(
        '--memory-file',
        default='neira_memory.json',
        help='Путь к файлу памяти'
    )
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    manager = MemoryManager(args.memory_file)
    
    if args.action == 'cleanup':
        stats = manager.full_cleanup()
        print(f"Очистка завершена: {stats}")
    elif args.action == 'stats':
        stats = manager.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    elif args.action == 'duplicates':
        dups = manager.find_duplicates()
        print(f"Найдено дубликатов: {len(dups)}")
    elif args.action == 'backup':
        path = manager.create_backup()
        print(f"Бэкап создан: {path}")


if __name__ == '__main__':
    main()
