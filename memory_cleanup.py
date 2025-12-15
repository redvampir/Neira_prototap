"""
🧹 ПОЛНАЯ ОЧИСТКА И ЗАЩИТА ПАМЯТИ NEIRA
Система контроля роста данных без квантования
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

class MemoryProtection:
    """Защита от переполнения памяти"""
    
    # Лимиты памяти
    MAX_TOTAL_RECORDS = 1000  # Максимум записей
    MAX_SHORT_TERM = 100      # Краткосрочная память
    MAX_LONG_TERM = 500       # Долгосрочная память
    MIN_CONFIDENCE = 0.3      # Минимальная уверенность для сохранения
    
    def __init__(self, memory_file: str = "neira_memory.json"):
        self.memory_file = memory_file
        self.backup_dir = Path("memory_backups")
        self.backup_dir.mkdir(exist_ok=True)
    
    def full_cleanup(self, keep_important: bool = True):
        """Полная очистка памяти с опциональным сохранением важного"""
        
        print("=" * 70)
        print("🧹 ПОЛНАЯ ОЧИСТКА ПАМЯТИ")
        print("=" * 70)
        
        # Создаем бэкап
        backup_path = self._create_backup()
        print(f"✅ Бэкап создан: {backup_path}")
        
        if not Path(self.memory_file).exists():
            print("⚠️  Файл памяти не существует, создаем новый")
            self._save_memory([])
            return
        
        with open(self.memory_file, 'r', encoding='utf-8') as f:
            memory = json.load(f)
        
        print(f"📊 Записей до очистки: {len(memory)}")
        
        if keep_important:
            # Оставляем только важные записи (высокая уверенность)
            important = [
                m for m in memory 
                if m.get('confidence', 0) >= 0.8 or 
                   m.get('type') == 'core_knowledge'
            ]
            
            # Ограничиваем до 50 самых важных
            important = sorted(
                important, 
                key=lambda x: x.get('confidence', 0), 
                reverse=True
            )[:50]
            
            print(f"💎 Сохранено важных записей: {len(important)}")
            self._save_memory(important)
        else:
            # Полная очистка
            print("🔥 Выполняется полная очистка...")
            self._save_memory([])
        
        print("✅ Очистка завершена!")
        return backup_path
    
    def apply_limits(self):
        """Применить лимиты к существующей памяти"""
        
        print("\n" + "=" * 70)
        print("⚙️  ПРИМЕНЕНИЕ ЛИМИТОВ ПАМЯТИ")
        print("=" * 70)
        
        if not Path(self.memory_file).exists():
            print("⚠️  Файл памяти не существует")
            return
        
        with open(self.memory_file, 'r', encoding='utf-8') as f:
            memory = json.load(f)
        
        original_count = len(memory)
        print(f"📊 Записей до оптимизации: {original_count}")
        
        # 1. Удаляем дубликаты
        unique_memory = self._remove_duplicates(memory)
        print(f"🔍 После удаления дубликатов: {len(unique_memory)}")
        
        # 2. Фильтруем по уверенности
        filtered = [
            m for m in unique_memory 
            if m.get('confidence', 0.5) >= self.MIN_CONFIDENCE
        ]
        print(f"⚖️  После фильтрации по уверенности: {len(filtered)}")
        
        # 3. Применяем лимит
        if len(filtered) > self.MAX_TOTAL_RECORDS:
            # Сортируем по важности
            sorted_memory = sorted(
                filtered,
                key=lambda x: (
                    x.get('confidence', 0),
                    x.get('timestamp', '')
                ),
                reverse=True
            )
            
            limited = sorted_memory[:self.MAX_TOTAL_RECORDS]
            print(f"✂️  После применения лимита: {len(limited)}")
        else:
            limited = filtered
        
        # 4. Распределяем по типам
        optimized = self._optimize_by_type(limited)
        
        # Сохраняем
        self._save_memory(optimized)
        
        saved = len(optimized)
        removed = original_count - saved
        print(f"\n📈 Результат:")
        print(f"   ✅ Сохранено: {saved}")
        print(f"   🗑️  Удалено: {removed}")
        print(f"   💾 Экономия: {removed / original_count * 100:.1f}%")
    
    def _remove_duplicates(self, memory: list) -> list:
        """Удаление дубликатов"""
        seen = set()
        unique = []
        
        for record in memory:
            content = record.get('content', '')
            if content and content not in seen:
                seen.add(content)
                unique.append(record)
        
        return unique
    
    def _optimize_by_type(self, memory: list) -> list:
        """Оптимизация по типам памяти"""
        
        by_type = {
            'long_term': [],
            'short_term': [],
            'conversation': [],
            'other': []
        }
        
        for record in memory:
            mem_type = record.get('type', 'other')
            if mem_type not in by_type:
                by_type['other'].append(record)
            else:
                by_type[mem_type].append(record)
        
        # Применяем лимиты по типам
        optimized = []
        
        # Долгосрочная память - самые важные
        long_term = sorted(
            by_type['long_term'],
            key=lambda x: x.get('confidence', 0),
            reverse=True
        )[:self.MAX_LONG_TERM]
        optimized.extend(long_term)
        
        # Краткосрочная память - самые свежие
        short_term = sorted(
            by_type['short_term'],
            key=lambda x: x.get('timestamp', ''),
            reverse=True
        )[:self.MAX_SHORT_TERM]
        optimized.extend(short_term)
        
        # Диалоги - последние N
        conversations = sorted(
            by_type['conversation'],
            key=lambda x: x.get('timestamp', ''),
            reverse=True
        )[:200]
        optimized.extend(conversations)
        
        # Остальное - топ по уверенности
        other = sorted(
            by_type['other'],
            key=lambda x: x.get('confidence', 0),
            reverse=True
        )[:150]
        optimized.extend(other)
        
        return optimized
    
    def _create_backup(self) -> Path:
        """Создание бэкапа"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"neira_memory_backup_{timestamp}.json"
        
        if Path(self.memory_file).exists():
            shutil.copy2(self.memory_file, backup_path)
        
        return backup_path
    
    def _save_memory(self, memory: list):
        """Сохранение памяти"""
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    
    def get_stats(self) -> dict:
        """Получить статистику памяти"""
        
        if not Path(self.memory_file).exists():
            return {'total': 0, 'by_type': {}}
        
        with open(self.memory_file, 'r', encoding='utf-8') as f:
            memory = json.load(f)
        
        stats = {
            'total': len(memory),
            'by_type': {},
            'by_confidence': {
                'high': 0,      # > 0.8
                'medium': 0,    # 0.5 - 0.8
                'low': 0        # < 0.5
            }
        }
        
        for record in memory:
            # По типу
            mem_type = record.get('type', 'unknown')
            stats['by_type'][mem_type] = stats['by_type'].get(mem_type, 0) + 1
            
            # По уверенности
            conf = record.get('confidence', 0.5)
            if conf > 0.8:
                stats['by_confidence']['high'] += 1
            elif conf >= 0.5:
                stats['by_confidence']['medium'] += 1
            else:
                stats['by_confidence']['low'] += 1
        
        return stats


def main():
    """Главная функция очистки"""
    
    protection = MemoryProtection()
    
    # Показываем текущую статистику
    print("\n📊 ТЕКУЩАЯ СТАТИСТИКА:")
    print("-" * 70)
    stats = protection.get_stats()
    print(f"Всего записей: {stats['total']}")
    print(f"\nПо типам:")
    for mem_type, count in stats['by_type'].items():
        print(f"  {mem_type}: {count}")
    print(f"\nПо уверенности:")
    print(f"  Высокая (>0.8): {stats['by_confidence']['high']}")
    print(f"  Средняя (0.5-0.8): {stats['by_confidence']['medium']}")
    print(f"  Низкая (<0.5): {stats['by_confidence']['low']}")
    
    # Выбор действия
    print("\n" + "=" * 70)
    print("ВЫБЕРИТЕ ДЕЙСТВИЕ:")
    print("=" * 70)
    print("1. Полная очистка (сохранить важное)")
    print("2. Полная очистка (удалить всё)")
    print("3. Применить лимиты (оптимизация)")
    print("4. Только статистика")
    
    choice = input("\nВаш выбор (1-4): ").strip()
    
    if choice == '1':
        protection.full_cleanup(keep_important=True)
    elif choice == '2':
        protection.full_cleanup(keep_important=False)
    elif choice == '3':
        protection.apply_limits()
    elif choice == '4':
        print("\n✅ Статистика показана выше")
    else:
        print("❌ Неверный выбор")
    
    # Показываем финальную статистику
    print("\n📊 ФИНАЛЬНАЯ СТАТИСТИКА:")
    print("-" * 70)
    final_stats = protection.get_stats()
    print(f"Всего записей: {final_stats['total']}")
    print(f"\nЛимиты:")
    print(f"  Максимум: {protection.MAX_TOTAL_RECORDS}")
    print(f"  Использовано: {final_stats['total'] / protection.MAX_TOTAL_RECORDS * 100:.1f}%")


if __name__ == '__main__':
    main()
