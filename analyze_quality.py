#!/usr/bin/env python3
"""Анализ качества памяти Нейры"""
import json

with open('neira_memory.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=' * 70)
print('КАЧЕСТВЕННЫЙ АНАЛИЗ ПАМЯТИ НЕЙРЫ (без галлюцинаций)')
print('=' * 70)

# Категоризация по качеству
excellent = []  # Точные факты, полезные
good = []       # Нормальные, но общие
mediocre = []   # Слишком абстрактные/размытые

for m in data:
    text = m.get('text', '')
    
    # Эвристика качества
    if any(x in text.lower() for x in ['павел', 'нейра', 'разработчик', 'партнёр', 'создател']):
        excellent.append(m)
    elif any(x in text.lower() for x in ['должн', 'нужн', 'требует', 'важно', 'помочь', 'анализ']):
        good.append(m)
    elif len(text) < 50:
        mediocre.append(m)
    else:
        good.append(m)

print(f'\n📊 РАСПРЕДЕЛЕНИЕ ПО КАЧЕСТВУ:')
print(f'   🌟 Отличные (конкретные факты): {len(excellent)}')
print(f'   ✅ Хорошие (полезные): {len(good)}')
print(f'   ⚠️ Посредственные (размытые): {len(mediocre)}')

print(f'\n🌟 ПРИМЕРЫ ОТЛИЧНЫХ ЗАПИСЕЙ:')
for m in excellent[:10]:
    text = m.get('text', '')[:90]
    print(f'   • {text}...')

print(f'\n✅ ПРИМЕРЫ ХОРОШИХ ЗАПИСЕЙ:')
for m in good[:10]:
    text = m.get('text', '')[:90]
    print(f'   • {text}...')

print(f'\n⚠️ ПРИМЕРЫ ПОСРЕДСТВЕННЫХ:')
for m in mediocre[:5]:
    text = m.get('text', '')[:90]
    print(f'   • {text}...')

# Уникальность
texts = [m.get('text', '') for m in data]
unique = len(set(texts))
print(f'\n📈 МЕТРИКИ:')
print(f'   Всего записей: {len(data)}')
print(f'   Уникальных: {unique}')
print(f'   Дубликатов: {len(data) - unique}')
print(f'   Средняя длина: {sum(len(t) for t in texts) // len(texts)} символов')

# Категории
categories = {}
for m in data:
    cat = m.get('category', 'unknown')
    categories[cat] = categories.get(cat, 0) + 1

print(f'\n📂 ПО КАТЕГОРИЯМ:')
for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
    pct = count * 100 // len(data)
    print(f'   {cat}: {count} ({pct}%)')

# Оценка качества для модели 7B
print(f'\n' + '=' * 70)
print('💡 ОЦЕНКА ДЛЯ МОДЕЛИ 7B:')
print('=' * 70)
quality_score = (len(excellent) * 3 + len(good) * 2 + len(mediocre) * 0.5) / len(data)
print(f'   Индекс качества: {quality_score:.2f}/3.0')

if quality_score > 2.0:
    verdict = "ОТЛИЧНО - модель работает выше ожиданий"
elif quality_score > 1.5:
    verdict = "ХОРОШО - приемлемое качество для 7B"
elif quality_score > 1.0:
    verdict = "СРЕДНЕ - есть проблемы с абстракцией"
else:
    verdict = "ПЛОХО - нужна доработка или смена модели"

print(f'   Вердикт: {verdict}')
