import json

with open('neira_memory.json', 'r', encoding='utf-8') as f:
    memories = json.load(f)

print(f"Всего записей в памяти: {len(memories)}\n")
print("=" * 80)
print("ПОСЛЕДНИЕ 15 ЗАПИСЕЙ:")
print("=" * 80)

for i, entry in enumerate(memories[-15:], start=len(memories)-14):
    text = entry.get('text', '')
    timestamp = entry.get('timestamp', 'нет времени')
    print(f"\n[{i}] {timestamp}")
    print(text[:1000])
    print("-" * 80)
