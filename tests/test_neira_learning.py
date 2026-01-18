"""
🧪 ТЕСТИРОВАНИЕ ОБУЧЕНИЯ NEIRA
Имитация взаимодействия через Telegram
"""

from main import Neira
import json
from datetime import datetime


import pytest

@pytest.mark.slow
def test_learning(mock_neira):
    print('🧠 ЗАПУСК ТЕСТОВОГО ОБУЧЕНИЯ НЕЙРЫ')
    print('=' * 70)
    
    # Инициализация
    neira = Neira(verbose=False)
    
    # ТЕСТ 1: Базовые знания
    print('\n📚 ТЕСТ 1: Базовые знания (как в Telegram /chat)')
    print('-' * 70)
    
    questions = [
        'Привет! Как тебя зовут?',
        'Кто твой создатель?',
        'Что ты умеешь делать?'
    ]
    
    for q in questions:
        print(f'\n👤 Пользователь: {q}')
        response = neira.process(q)
        display = response[:150] + '...' if len(response) > 150 else response
        print(f'🤖 Нейра: {display}')
    
    # ТЕСТ 2: Обучение новому факту
    print('\n\n📖 ТЕСТ 2: Обучение новому (как в Telegram /learn)')
    print('-' * 70)
    
    lessons = [
        'Запомни: моё любимое число - 42',
        'Важный факт: Python - лучший язык программирования',
        'Сегодня 14 декабря 2025 года'
    ]
    
    for lesson in lessons:
        print(f'\n👤 Учу: {lesson}')
        response = neira.process(lesson)
        print(f'🤖 Ответ: {response[:100]}...' if len(response) > 100 else f'🤖 Ответ: {response}')
    
    # ТЕСТ 3: Проверка усвоения
    print('\n\n✅ ТЕСТ 3: Проверка усвоения')
    print('-' * 70)
    
    checks = [
        'Какое моё любимое число?',
        'Что ты думаешь о Python?',
        'Какая сегодня дата?'
    ]
    
    for check in checks:
        print(f'\n👤 Вопрос: {check}')
        response = neira.process(check)
        print(f'🤖 Ответ: {response[:150]}...' if len(response) > 150 else f'🤖 Ответ: {response}')
    
    # ТЕСТ 4: Статистика памяти
    print('\n\n📊 ТЕСТ 4: Статистика памяти (как в Telegram /memory stats)')
    print('-' * 70)
    
    try:
        with open('neira_memory.json', encoding='utf-8') as f:
            mem = json.load(f)
        
        print(f'📦 Всего записей в памяти: {len(mem)}')
        
        # Анализ последних записей
        recent = mem[-10:] if len(mem) >= 10 else mem
        print(f'\n📝 Последние {len(recent)} записей:')
        for i, record in enumerate(recent, 1):
            content = record.get('content', 'N/A')[:60]
            timestamp = record.get('timestamp', 'N/A')
            print(f'  {i}. [{timestamp}] {content}...')
        
        # Проверка на дубликаты
        contents = [r.get('content', '') for r in mem]
        unique_contents = set(contents)
        duplicates = len(contents) - len(unique_contents)
        
        print(f'\n🔍 Анализ качества:')
        print(f'  ✅ Уникальных записей: {len(unique_contents)}')
        print(f'  ⚠️  Дубликатов: {duplicates}')
        
        if duplicates > 50:
            print(f'\n⚠️  ВНИМАНИЕ: Обнаружено {duplicates} дубликатов!')
            print('💡 Рекомендуется очистка памяти')
        
    except Exception as e:
        print(f'❌ Ошибка чтения памяти: {e}')
    
    print('\n\n✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!')
    print('=' * 70)

if __name__ == '__main__':
    test_learning()
