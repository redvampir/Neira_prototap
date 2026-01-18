#!/usr/bin/env python3
"""
Очистка дубликатов и зацикленных записей из памяти Neira
"""
import json
from datetime import datetime
from collections import defaultdict

def clean_memory():
    """Удаляет дубликаты и зацикленные записи"""
    
    # Загружаем память
    with open('neira_memory.json', 'r', encoding='utf-8') as f:
        memories = json.load(f)
    
    print(f"Всего записей до очистки: {len(memories)}\n")
    
    # 1. Находим точные дубликаты
    seen_texts = {}
    duplicates = []
    
    for i, entry in enumerate(memories):
        text_normalized = entry.get('text', '').strip().lower()
        
        if text_normalized in seen_texts:
            # Дубликат найден
            duplicates.append((i, seen_texts[text_normalized], text_normalized[:70]))
        else:
            seen_texts[text_normalized] = i
    
    print(f"🔍 Найдено точных дубликатов: {len(duplicates)}")
    
    # 2. Находим зацикливания (много похожих записей за короткий период)
    looped_entries = []
    time_buckets = defaultdict(list)  # timestamp_minute -> [indices]
    
    for i, entry in enumerate(memories):
        ts = entry.get('timestamp', '')
        # Группируем по минутам
        if ts:
            minute_key = ts[:16]  # YYYY-MM-DDTHH:MM
            time_buckets[minute_key].append(i)
    
    # Ищем минуты с аномально большим количеством записей (>5)
    for minute, indices in time_buckets.items():
        if len(indices) > 5:
            print(f"⚠️ Зацикливание обнаружено в {minute}: {len(indices)} записей")
            # Проверяем на похожесть
            texts_in_minute = [memories[i].get('text', '') for i in indices]
            
            # Если все про одно и то же - зацикливание
            keywords = ['telegram', 'c++', 'analyzer', 'logger', 'json', 'chatid']
            keyword_counts = {kw: sum(1 for t in texts_in_minute if kw in t.lower()) for kw in keywords}
            
            # Если >80% записей содержат одно ключевое слово - зацикливание
            for kw, count in keyword_counts.items():
                if count > len(indices) * 0.8:
                    print(f"   → Тема зацикливания: {kw} ({count}/{len(indices)} записей)")
                    # Оставляем только первую и последнюю запись
                    looped_entries.extend(indices[1:-1])
                    break
    
    print(f"🔍 Найдено зацикленных записей: {len(looped_entries)}\n")
    
    # 3. Создаем список записей для удаления
    to_remove = set()
    
    # Удаляем дубликаты (оставляем первое вхождение)
    for dup_idx, original_idx, text in duplicates:
        to_remove.add(dup_idx)
        if len(to_remove) <= 5:  # Показываем первые 5
            print(f"  Удаляем дубликат #{dup_idx}: {text}...")
    
    # Удаляем зацикленные записи
    to_remove.update(looped_entries)
    
    print(f"\n📊 Всего записей к удалению: {len(to_remove)}")
    
    # 4. Создаем очищенную память
    cleaned = [entry for i, entry in enumerate(memories) if i not in to_remove]
    
    print(f"✅ Записей после очистки: {len(cleaned)}")
    print(f"🗑️ Удалено записей: {len(memories) - len(cleaned)}\n")
    
    # 5. Создаем бэкап
    backup_name = f"neira_memory_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_name, 'w', encoding='utf-8') as f:
        json.dump(memories, f, ensure_ascii=False, indent=2)
    print(f"💾 Бэкап сохранен: {backup_name}")
    
    # 6. Сохраняем очищенную память
    with open('neira_memory.json', 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Память очищена и сохранена!")
    
    # 7. Показываем статистику последних записей
    print("\n" + "=" * 80)
    print("ПОСЛЕДНИЕ 10 ЗАПИСЕЙ ПОСЛЕ ОЧИСТКИ:")
    print("=" * 80)
    for i, entry in enumerate(cleaned[-10:], len(cleaned)-9):
        ts = entry.get('timestamp', 'нет')[:19]
        text = entry.get('text', '')[:70]
        print(f"{i}. {ts} - {text}")

if __name__ == "__main__":
    clean_memory()
