"""
Агрессивная очистка памяти Neira
- Удаляет старые записи (>30 дней)
- Удаляет зацикленные повторы
- Удаляет технические галлюцинации
- Сжимает краткосрочную память
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict


def load_memory(file_path):
    """Загрузка памяти из JSON"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_memory(file_path, data):
    """Сохранение памяти в JSON"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def create_backup(file_path):
    """Создание бэкапа перед очисткой"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("memory_backups")
    backup_dir.mkdir(exist_ok=True)
    
    backup_path = backup_dir / f"{file_path.stem}_backup_{timestamp}.json"
    data = load_memory(file_path)
    save_memory(backup_path, data)
    print(f"💾 Бэкап создан: {backup_path}")
    return backup_path


def clean_main_memory(keep_days=30, keep_recent=50):
    """
    Очистка основной памяти
    
    Args:
        keep_days: Сколько дней хранить (старше удаляем)
        keep_recent: Сколько последних записей всегда сохранять
    """
    file_path = Path("neira_memory.json")
    
    if not file_path.exists():
        print(f"❌ Файл {file_path} не найден")
        return
    
    # Бэкап
    create_backup(file_path)
    
    # Загрузка
    memories = load_memory(file_path)
    original_count = len(memories)
    
    print(f"\n{'='*80}")
    print(f"🧹 ОЧИСТКА ОСНОВНОЙ ПАМЯТИ")
    print(f"{'='*80}")
    print(f"Записей до очистки: {original_count}")
    
    # Фильтр по дате
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    
    filtered = []
    removed_old = 0
    removed_technical = 0
    removed_loops = 0
    
    # Группируем по минутам для детекта зацикливания
    by_minute = defaultdict(list)
    
    for mem in memories:
        timestamp_str = mem.get("timestamp", "")
        text = mem.get("text", mem.get("fact", ""))  # Поддержка обоих форматов
        
        # Парсим дату
        try:
            mem_date = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except:
            # Если дата кривая — удаляем
            removed_old += 1
            continue
        
        # Старые записи удаляем (кроме последних keep_recent)
        if mem_date < cutoff_date and len(filtered) >= keep_recent:
            removed_old += 1
            continue
        
        # Технические галлюцинации
        technical_garbage = [
            "нейронная сеть", "трансформер", "машинное обучение",
            "import asyncio", "class ", "def ", "биохимический процесс",
            "градиентный спуск", "обратная связь", "синапс", "хлоропласт"
        ]
        
        if any(garbage in text.lower() for garbage in technical_garbage):
            # Если это не последние 20 записей — удаляем
            if len(memories) - memories.index(mem) > 20:
                removed_technical += 1
                continue
        
        # Группируем по минуте
        minute_key = timestamp_str[:16]  # YYYY-MM-DDTHH:MM
        by_minute[minute_key].append(text)
        
        filtered.append(mem)
    
    # Детект зацикливания (>5 записей в минуту)
    loop_minutes = {k: v for k, v in by_minute.items() if len(v) > 5}
    
    if loop_minutes:
        print(f"\n⚠️ Обнаружено зацикливание в {len(loop_minutes)} временных точках:")
        
        final = []
        for mem in filtered:
            minute_key = mem.get("timestamp", "")[:16]
            mem_text = mem.get("text", mem.get("fact", ""))
            
            if minute_key in loop_minutes:
                # Оставляем только первую запись из зацикленной минуты
                if by_minute[minute_key].index(mem_text) == 0:
                    final.append(mem)
                else:
                    removed_loops += 1
            else:
                final.append(mem)
        
        filtered = final
    
    # Сохранение
    save_memory(file_path, filtered)
    
    final_count = len(filtered)
    total_removed = original_count - final_count
    
    print(f"\n📊 РЕЗУЛЬТАТЫ:")
    print(f"  • Удалено старых (>{keep_days} дней): {removed_old}")
    print(f"  • Удалено технических: {removed_technical}")
    print(f"  • Удалено зацикленных: {removed_loops}")
    print(f"  • Всего удалено: {total_removed}")
    print(f"  • Осталось записей: {final_count}")
    print(f"  • Экономия: {((original_count - final_count) / original_count * 100):.1f}%")


def clean_short_term(keep_recent=10):
    """Очистка краткосрочной памяти — оставляем только последние N"""
    file_path = Path("neira_short_term.json")
    
    if not file_path.exists():
        print(f"❌ Файл {file_path} не найден")
        return
    
    create_backup(file_path)
    
    memories = load_memory(file_path)
    original_count = len(memories)
    
    print(f"\n{'='*80}")
    print(f"🧹 ОЧИСТКА КРАТКОСРОЧНОЙ ПАМЯТИ")
    print(f"{'='*80}")
    print(f"Записей до очистки: {original_count}")
    
    # Оставляем только последние N
    filtered = memories[-keep_recent:]
    
    save_memory(file_path, filtered)
    
    print(f"  • Удалено: {original_count - len(filtered)}")
    print(f"  • Осталось: {len(filtered)}")


def clean_experience(keep_recent=50):
    """Очистка опыта — удаляем старые и дублирующиеся уроки"""
    file_path = Path("neira_experience.json")
    
    if not file_path.exists():
        print(f"❌ Файл {file_path} не найден")
        return
    
    create_backup(file_path)
    
    experiences = load_memory(file_path)
    original_count = len(experiences)
    
    print(f"\n{'='*80}")
    print(f"🧹 ОЧИСТКА ОПЫТА")
    print(f"{'='*80}")
    print(f"Записей до очистки: {original_count}")
    
    # Группируем по типу задачи
    by_task = defaultdict(list)
    
    for exp in experiences:
        task_type = exp.get("task_type", "unknown")
        by_task[task_type].append(exp)
    
    # Для каждого типа задачи оставляем только последние 5
    filtered = []
    for task_type, exps in by_task.items():
        # Сортируем по дате
        sorted_exps = sorted(
            exps,
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
        # Берём последние 5
        filtered.extend(sorted_exps[:5])
    
    # Сортируем по дате
    filtered = sorted(filtered, key=lambda x: x.get("timestamp", ""))
    
    save_memory(file_path, filtered)
    
    print(f"  • Удалено: {original_count - len(filtered)}")
    print(f"  • Осталось: {len(filtered)}")
    print(f"  • Типов задач: {len(by_task)}")


def clean_chat_contexts(keep_recent_messages=20):
    """Очистка контекстов чатов — сжимаем длинные истории"""
    file_path = Path("neira_chat_contexts.json")
    
    if not file_path.exists():
        print(f"❌ Файл {file_path} не найден")
        return
    
    create_backup(file_path)
    
    contexts = load_memory(file_path)
    
    print(f"\n{'='*80}")
    print(f"🧹 ОЧИСТКА КОНТЕКСТОВ ЧАТОВ")
    print(f"{'='*80}")
    
    total_messages_before = 0
    total_messages_after = 0
    
    for chat_id, chat_data in contexts.items():
        history = chat_data.get("context_history", [])
        total_messages_before += len(history)
        
        # Оставляем только последние N сообщений
        if len(history) > keep_recent_messages:
            chat_data["context_history"] = history[-keep_recent_messages:]
            total_messages_after += keep_recent_messages
        else:
            total_messages_after += len(history)
    
    save_memory(file_path, contexts)
    
    print(f"  • Сообщений до: {total_messages_before}")
    print(f"  • Сообщений после: {total_messages_after}")
    print(f"  • Удалено: {total_messages_before - total_messages_after}")


def remove_old_backups(keep_last=3):
    """Удаляем старые бэкапы, оставляем только последние N"""
    backup_dir = Path("memory_backups")
    
    if not backup_dir.exists():
        return
    
    backups = sorted(backup_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if len(backups) <= keep_last:
        return
    
    print(f"\n{'='*80}")
    print(f"🧹 ОЧИСТКА СТАРЫХ БЭКАПОВ")
    print(f"{'='*80}")
    print(f"Найдено бэкапов: {len(backups)}")
    
    removed = 0
    for backup in backups[keep_last:]:
        backup.unlink()
        removed += 1
    
    print(f"  • Удалено: {removed}")
    print(f"  • Осталось: {keep_last}")


if __name__ == "__main__":
    print("🧠 АГРЕССИВНАЯ ОЧИСТКА ПАМЯТИ NEIRA")
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. Основная память (старше 30 дней удаляем)
    clean_main_memory(keep_days=30, keep_recent=100)
    
    # 2. Краткосрочная память (только последние 10)
    clean_short_term(keep_recent=10)
    
    # 3. Опыт (по 5 записей на тип задачи)
    clean_experience(keep_recent=50)
    
    # 4. Контексты чатов (последние 20 сообщений)
    clean_chat_contexts(keep_recent_messages=20)
    
    # 5. Старые бэкапы (оставляем 3 последних)
    remove_old_backups(keep_last=3)
    
    print(f"\n{'='*80}")
    print("✅ ОЧИСТКА ЗАВЕРШЕНА")
    print(f"{'='*80}")
    
    # Финальные размеры
    files = ["neira_memory.json", "neira_experience.json", "neira_short_term.json", "neira_chat_contexts.json"]
    print("\n📊 РАЗМЕРЫ ФАЙЛОВ ПОСЛЕ ОЧИСТКИ:")
    for fname in files:
        path = Path(fname)
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"  • {fname}: {size_kb:.2f} KB")
