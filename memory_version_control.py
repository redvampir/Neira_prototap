"""
Система версионирования памяти для Neira (git-like snapshots)
Позволяет создавать снимки, откатываться, просматривать историю
"""

import json
import hashlib
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class Snapshot:
    """Снимок состояния памяти"""
    id: str
    timestamp: str
    message: str
    stats: Dict
    filepath: str
    
    def to_dict(self) -> dict:
        return asdict(self)


class MemoryVersionControl:
    """Git-like версионирование памяти"""
    
    def __init__(self, snapshots_dir: str = "./memory_snapshots"):
        """
        Args:
            snapshots_dir: Директория для хранения снимков
        """
        self.snapshots_dir = Path(snapshots_dir)
        self.snapshots_dir.mkdir(exist_ok=True)
        
        # Файл с историей снимков
        self.changelog_file = self.snapshots_dir / "CHANGELOG.json"
        
        # Инициализация лога
        if not self.changelog_file.exists():
            self._init_changelog()
    
    def _init_changelog(self):
        """Инициализирует файл истории"""
        changelog = {
            "created_at": datetime.now().isoformat(),
            "snapshots": []
        }
        
        with open(self.changelog_file, 'w', encoding='utf-8') as f:
            json.dump(changelog, f, ensure_ascii=False, indent=2)
    
    def create_snapshot(
        self,
        memory_data: List[dict],
        message: str = "",
        auto_cleanup: bool = True
    ) -> Snapshot:
        """
        Создаёт снимок текущего состояния памяти
        
        Args:
            memory_data: Данные памяти (список записей)
            message: Описание изменений
            auto_cleanup: Автоудаление старых снимков (>30 дней, оставить последние 10)
        
        Returns:
            Snapshot объект с информацией о снимке
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Генерируем уникальный ID
        snapshot_id = hashlib.md5(
            f"{timestamp}{message}{len(memory_data)}".encode()
        ).hexdigest()[:8]
        
        # Статистика
        stats = self._calculate_stats(memory_data)
        
        # Сохраняем снимок
        filename = f"snapshot_{timestamp}_{snapshot_id}.json"
        filepath = self.snapshots_dir / filename
        
        snapshot_content = {
            "id": snapshot_id,
            "timestamp": timestamp,
            "message": message,
            "stats": stats,
            "data": memory_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot_content, f, ensure_ascii=False, indent=2)
        
        # Обновляем changelog
        self._append_to_changelog(snapshot_id, message, timestamp, stats, str(filepath))
        
        # Автоочистка старых снимков
        if auto_cleanup:
            self._cleanup_old_snapshots()
        
        snapshot = Snapshot(
            id=snapshot_id,
            timestamp=timestamp,
            message=message,
            stats=stats,
            filepath=str(filepath)
        )
        
        print(f"📸 Снимок создан: {snapshot_id} ({len(memory_data)} записей)")
        
        return snapshot
    
    def restore_snapshot(self, snapshot_id: str) -> List[dict]:
        """
        Восстанавливает состояние из снимка
        
        Args:
            snapshot_id: ID снимка (полный или первые 4+ символа)
        
        Returns:
            Данные памяти из снимка
        """
        # Ищем файл снимка
        matching_files = list(self.snapshots_dir.glob(f"snapshot_*_{snapshot_id}*.json"))
        
        if not matching_files:
            raise ValueError(f"❌ Снимок {snapshot_id} не найден")
        
        if len(matching_files) > 1:
            raise ValueError(f"❌ Найдено несколько снимков с ID {snapshot_id}: {[f.name for f in matching_files]}")
        
        filepath = matching_files[0]
        
        with open(filepath, 'r', encoding='utf-8') as f:
            snapshot = json.load(f)
        
        print(f"♻️ Восстановлен снимок: {snapshot['id']}")
        print(f"   Дата: {snapshot['timestamp']}")
        print(f"   Сообщение: {snapshot['message']}")
        print(f"   Записей: {snapshot['stats']['total_memories']}")
        
        return snapshot["data"]
    
    def list_snapshots(self, limit: int = None) -> List[Snapshot]:
        """
        Список всех снимков (от новых к старым)
        
        Args:
            limit: Максимум снимков (None = все)
        
        Returns:
            Список Snapshot объектов
        """
        with open(self.changelog_file, 'r', encoding='utf-8') as f:
            changelog = json.load(f)
        
        snapshots_data = changelog.get("snapshots", [])
        
        # Сортируем по дате (новые первыми)
        snapshots_data.sort(key=lambda x: x["timestamp"], reverse=True)
        
        if limit:
            snapshots_data = snapshots_data[:limit]
        
        snapshots = [
            Snapshot(
                id=s["id"],
                timestamp=s["timestamp"],
                message=s.get("message", ""),
                stats=s.get("stats", {}),
                filepath=s.get("filepath", "")
            )
            for s in snapshots_data
        ]
        
        return snapshots
    
    def diff_snapshots(self, snapshot_id1: str, snapshot_id2: str) -> dict:
        """
        Сравнивает два снимка
        
        Args:
            snapshot_id1: ID первого снимка
            snapshot_id2: ID второго снимка
        
        Returns:
            Статистика различий
        """
        data1 = self.restore_snapshot(snapshot_id1)
        data2 = self.restore_snapshot(snapshot_id2)
        
        ids1 = {mem["id"] for mem in data1 if "id" in mem}
        ids2 = {mem["id"] for mem in data2 if "id" in mem}
        
        added = ids2 - ids1
        removed = ids1 - ids2
        common = ids1 & ids2
        
        # Проверяем изменённые
        modified = []
        for mem_id in common:
            mem1 = next(m for m in data1 if m.get("id") == mem_id)
            mem2 = next(m for m in data2 if m.get("id") == mem_id)
            
            if mem1.get("text") != mem2.get("text") or \
               mem1.get("confidence") != mem2.get("confidence"):
                modified.append(mem_id)
        
        diff = {
            "snapshot1": snapshot_id1,
            "snapshot2": snapshot_id2,
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
            "unchanged": len(common) - len(modified)
        }
        
        return diff
    
    def _calculate_stats(self, memory_data: List[dict]) -> dict:
        """Рассчитывает статистику памяти"""
        if not memory_data:
            return {
                "total_memories": 0,
                "avg_confidence": 0,
                "by_category": {},
                "by_validation": {}
            }
        
        # По категориям
        by_category = {}
        for mem in memory_data:
            category = mem.get("category", "unknown")
            by_category[category] = by_category.get(category, 0) + 1
        
        # По валидации
        by_validation = {}
        for mem in memory_data:
            validation = mem.get("validation_status", "unknown")
            by_validation[validation] = by_validation.get(validation, 0) + 1
        
        # Средняя уверенность
        confidences = [mem.get("confidence", 0) for mem in memory_data]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return {
            "total_memories": len(memory_data),
            "avg_confidence": round(avg_confidence, 3),
            "by_category": by_category,
            "by_validation": by_validation
        }
    
    def _append_to_changelog(
        self,
        snapshot_id: str,
        message: str,
        timestamp: str,
        stats: dict,
        filepath: str
    ):
        """Добавляет запись в changelog"""
        with open(self.changelog_file, 'r', encoding='utf-8') as f:
            changelog = json.load(f)
        
        changelog["snapshots"].append({
            "id": snapshot_id,
            "timestamp": timestamp,
            "message": message,
            "stats": stats,
            "filepath": filepath
        })
        
        with open(self.changelog_file, 'w', encoding='utf-8') as f:
            json.dump(changelog, f, ensure_ascii=False, indent=2)
    
    def _cleanup_old_snapshots(self, keep_last: int = 10, max_age_days: int = 30):
        """Удаляет старые снимки"""
        snapshots = self.list_snapshots()
        
        if len(snapshots) <= keep_last:
            return
        
        # Удаляем всё старше max_age_days, кроме последних keep_last
        now = datetime.now()
        to_delete = []
        
        for i, snapshot in enumerate(snapshots):
            if i < keep_last:
                continue  # Сохраняем последние N
            
            snapshot_date = datetime.strptime(snapshot.timestamp, "%Y%m%d_%H%M%S")
            age_days = (now - snapshot_date).days
            
            if age_days > max_age_days:
                to_delete.append(snapshot)
        
        # Удаляем файлы
        for snapshot in to_delete:
            try:
                Path(snapshot.filepath).unlink()
                print(f"🗑️ Удалён старый снимок: {snapshot.id}")
            except Exception as e:
                print(f"⚠️ Ошибка удаления {snapshot.id}: {e}")
        
        # Обновляем changelog
        if to_delete:
            with open(self.changelog_file, 'r', encoding='utf-8') as f:
                changelog = json.load(f)
            
            deleted_ids = {s.id for s in to_delete}
            changelog["snapshots"] = [
                s for s in changelog["snapshots"]
                if s["id"] not in deleted_ids
            ]
            
            with open(self.changelog_file, 'w', encoding='utf-8') as f:
                json.dump(changelog, f, ensure_ascii=False, indent=2)


# Утилита для работы с версиями
def snapshot_memory_file(
    memory_file: str,
    message: str = "",
    snapshots_dir: str = "./memory_snapshots"
) -> Snapshot:
    """
    Создаёт снимок файла памяти
    
    Args:
        memory_file: Путь к файлу памяти
        message: Описание изменений
        snapshots_dir: Директория для снимков
    
    Returns:
        Snapshot объект
    """
    # Загружаем память
    with open(memory_file, 'r', encoding='utf-8') as f:
        memory_data = json.load(f)
    
    # Создаём снимок
    vc = MemoryVersionControl(snapshots_dir)
    snapshot = vc.create_snapshot(memory_data, message)
    
    return snapshot


# Пример использования
if __name__ == "__main__":
    # Создаём систему версионирования
    vc = MemoryVersionControl(snapshots_dir="./test_snapshots")
    
    # Тестовые данные
    test_data = [
        {"id": "1", "text": "Запись 1", "confidence": 0.8, "category": "fact"},
        {"id": "2", "text": "Запись 2", "confidence": 0.6, "category": "preference"},
    ]
    
    # Создаём снимок
    print("📸 Создание снимка...")
    snapshot1 = vc.create_snapshot(test_data, "Initial state")
    
    # Изменяем данные
    test_data.append({"id": "3", "text": "Новая запись", "confidence": 0.9, "category": "fact"})
    
    # Создаём второй снимок
    print("\n📸 Создание второго снимка...")
    snapshot2 = vc.create_snapshot(test_data, "Added new record")
    
    # Список снимков
    print("\n📋 Список снимков:")
    snapshots = vc.list_snapshots()
    for s in snapshots:
        print(f"  {s.id} - {s.message} ({s.stats['total_memories']} записей)")
    
    # Сравнение снимков
    print("\n🔍 Сравнение снимков:")
    diff = vc.diff_snapshots(snapshot1.id, snapshot2.id)
    print(f"  Добавлено: {diff['added']}")
    print(f"  Удалено: {diff['removed']}")
    print(f"  Изменено: {diff['modified']}")
    
    # Восстановление
    print(f"\n♻️ Восстановление первого снимка...")
    restored = vc.restore_snapshot(snapshot1.id[:4])  # По первым 4 символам
    print(f"  Восстановлено записей: {len(restored)}")
