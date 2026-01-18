#!/usr/bin/env python3
"""Анализ памяти Нейры для выявления галлюцинаций"""
import json
from datetime import datetime

# Загружаем память
with open('neira_memory.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"=" * 80)
print(f"АНАЛИЗ ПАМЯТИ НЕЙРЫ")
print(f"=" * 80)
print(f"Всего записей: {len(data)}")
print()

# Показываем последние 100 записей
print("ПОСЛЕДНИЕ 100 ЗАПИСЕЙ:")
print("-" * 80)
for i, m in enumerate(data[-100:], len(data) - 99):
    ts = m.get("timestamp", "?")[:19] if m.get("timestamp") else "?"
    cat = m.get("category", "?")
    src = m.get("source", "?")
    text = m.get("text", "")[:150].replace("\n", " ")
    print(f"{i:4}. [{ts}] {cat:12} | {src:15} | {text}...")
    
print()
print("=" * 80)
print("СТАТИСТИКА ПО КАТЕГОРИЯМ:")
print("-" * 80)
categories = {}
sources = {}
for m in data:
    cat = m.get("category", "unknown")
    src = m.get("source", "unknown")
    categories[cat] = categories.get(cat, 0) + 1
    sources[src] = sources.get(src, 0) + 1

for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {count}")

print()
print("СТАТИСТИКА ПО ИСТОЧНИКАМ:")
print("-" * 80)
for src, count in sorted(sources.items(), key=lambda x: -x[1]):
    print(f"  {src}: {count}")

# Анализ последних записей на предмет галлюцинаций
print()
print("=" * 80)
print("ПОТЕНЦИАЛЬНЫЕ ГАЛЛЮЦИНАЦИИ (странные записи):")
print("-" * 80)
keywords = ["Кость", "прибыль", "продаж", "вычислит", "нейрон", "модел", "$", "час", "мощност"]
for i, m in enumerate(data[-100:], len(data) - 99):
    text = m.get("text", "")
    # Ищем странные паттерны
    if any(kw in text for kw in keywords):
        ts = m.get("timestamp", "?")[:19] if m.get("timestamp") else "?"
        print(f"{i:4}. [{ts}] {text[:200]}...")
