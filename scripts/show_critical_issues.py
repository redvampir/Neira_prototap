import json

with open('neira_memory.json', 'r', encoding='utf-8') as f:
    memories = json.load(f)

print("=" * 100)
print("КРИТИЧЕСКИЕ ПРОБЛЕМЫ ИЗ TELEGRAM ПЕРЕПИСКИ (записи 317-331)")
print("=" * 100)

for i in range(316, min(332, len(memories))):
    entry = memories[i]
    text = entry.get('text', '')
    timestamp = entry.get('timestamp', 'нет времени')
    
    print(f"\n[{i+1}] {timestamp}")
    print(text)
    print("-" * 100)
