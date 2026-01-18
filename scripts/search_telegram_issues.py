import json

with open('neira_memory.json', 'r', encoding='utf-8') as f:
    memories = json.load(f)

print(f"Всего записей: {len(memories)}\n")

# Ищем записи связанные с Telegram или проблемами
keywords = ['telegram', 'телеграм', 'ошибка', 'проблема', 'не работает', 'баг', 'error']

print("=" * 80)
print("ЗАПИСИ, СВЯЗАННЫЕ С TELEGRAM И ПРОБЛЕМАМИ:")
print("=" * 80)

found_count = 0
for i, entry in enumerate(memories[-100:], start=len(memories)-99):
    text = entry.get('text', '').lower()
    timestamp = entry.get('timestamp', 'нет времени')
    
    if any(keyword in text for keyword in keywords):
        found_count += 1
        print(f"\n[{i}] {timestamp}")
        print(entry.get('text', '')[:800])
        print("-" * 80)

print(f"\n\nНайдено записей: {found_count}")
