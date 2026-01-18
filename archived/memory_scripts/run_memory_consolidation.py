"""
Скрипт для консолидации текущей памяти Neira
Использует MemoryConsolidator для объединения похожих записей
"""

import json
from pathlib import Path
from memory_consolidator import consolidate_memory_file
from memory_version_control import snapshot_memory_file


def main():
    """Консолидирует основные файлы памяти"""
    
    memory_files = {
        "neira_memory.json": "Долгосрочная память",
        "neira_short_term.json": "Краткосрочная память",
        "neira_semantic.json": "Семантическая память",
        "neira_episodic.json": "Эпизодическая память"
    }
    
    print("=" * 60)
    print("🧠 КОНСОЛИДАЦИЯ ПАМЯТИ NEIRA v3.0")
    print("=" * 60)
    
    total_stats = {
        "before": 0,
        "after": 0,
        "merged": 0
    }
    
    for filename, description in memory_files.items():
        filepath = Path(filename)
        
        if not filepath.exists():
            print(f"\n⏭️ Пропускаем {filename} (файл не найден)")
            continue
        
        print(f"\n{'='*60}")
        print(f"📂 {description} ({filename})")
        print(f"{'='*60}")
        
        # Создаём snapshot перед консолидацией
        print(f"📸 Создание snapshot...")
        try:
            snapshot = snapshot_memory_file(
                str(filepath),
                message=f"Before consolidation: {description}",
                snapshots_dir="./memory_snapshots"
            )
            print(f"   ✅ Snapshot создан: {snapshot.id}")
        except Exception as e:
            print(f"   ⚠️ Ошибка создания snapshot: {e}")
        
        # Консолидируем
        try:
            stats = consolidate_memory_file(
                str(filepath),
                output_file=None,  # Перезаписать исходный файл
                threshold=0.85,
                by_category=True
            )
            
            total_stats["before"] += stats["original_count"]
            total_stats["after"] += stats["consolidated_count"]
            total_stats["merged"] += stats.get("merged", 0)
            
        except Exception as e:
            print(f"❌ Ошибка консолидации {filename}: {e}")
    
    # Итоги
    print(f"\n{'='*60}")
    print("📊 ИТОГОВАЯ СТАТИСТИКА")
    print(f"{'='*60}")
    print(f"Записей до:     {total_stats['before']}")
    print(f"Записей после:  {total_stats['after']}")
    print(f"Объединено:     {total_stats['merged']}")
    
    if total_stats['before'] > 0:
        reduction = (1 - total_stats['after'] / total_stats['before']) * 100
        print(f"Сжатие:         {reduction:.1f}%")
    
    print("\n✅ Консолидация завершена!")
    print("\n💡 Подсказка: Используйте memory_version_control для восстановления,")
    print("   если результат не устроил:")
    print("   python -c \"from memory_version_control import MemoryVersionControl; vc = MemoryVersionControl(); print([s.id + ' - ' + s.message for s in vc.list_snapshots()])\"")


if __name__ == "__main__":
    main()
