import json

m = json.load(open('neira_memory.json', encoding='utf-8'))

print("=" * 80)
print("ПОСЛЕДНИЕ 15 ЗАПИСЕЙ С ВРЕМЕННЫМИ МЕТКАМИ")
print("=" * 80)

for i, e in enumerate(m[-15:], len(m)-14):
    ts = e.get('timestamp', 'нет')[:19]
    text = e.get('text', '')[:70]
    print(f"{i}. {ts} - {text}")

# Проверяем зацикливание
print("\n" + "=" * 80)
print("АНАЛИЗ ЗАЦИКЛИВАНИЯ")
print("=" * 80)

last_50 = m[-50:]
telegram_mentions = sum(1 for e in last_50 if 'telegram' in e.get('text', '').lower())
cpp_mentions = sum(1 for e in last_50 if 'c++' in e.get('text', '').lower())
json_mentions = sum(1 for e in last_50 if 'json' in e.get('text', '').lower())

print(f"Из последних 50 записей:")
print(f"  Telegram: {telegram_mentions} упоминаний ({telegram_mentions*2}%)")
print(f"  C++:      {cpp_mentions} упоминаний ({cpp_mentions*2}%)")
print(f"  JSON:     {json_mentions} упоминаний ({json_mentions*2}%)")

if telegram_mentions > 40:
    print("\n🚨 ЗАЦИКЛИВАНИЕ ОБНАРУЖЕНО!")
    print(f"   Neira застряла на теме Telegram/C++")
    
    # Находим когда началось зацикливание
    for i in range(len(m)-100, len(m)):
        text = m[i].get('text', '').lower()
        if 'telegram' in text and 'c++' in text:
            print(f"\n   Зацикливание началось примерно с записи #{i+1}")
            print(f"   Время: {m[i].get('timestamp', 'нет')[:19]}")
            break
