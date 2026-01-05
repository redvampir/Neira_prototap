#!/usr/bin/env python3
"""
Тест функции create_organ_background без Telegram
Симулирует создание органа по описанию
"""

import sys
import asyncio
from cell_factory import CellFactory
from experience import ExperienceSystem

async def test_organ_creation():
    """Тестирует создание органа"""
    
    print("=" * 80)
    print("ТЕСТ СОЗДАНИЯ ОРГАНА БЕЗ TELEGRAM")
    print("=" * 80)
    
    # Симулируем разные описания
    test_cases = [
        {
            "description": "Орган для работы с PostgreSQL базой данных. Методы: connect, query, close",
            "expected_name": "database"
        },
        {
            "description": "Анализатор настроений для текстов на русском языке",
            "expected_name": "sentiment"
        },
        {
            "description": "Парсер JSON из REST API с валидацией схемы",
            "expected_name": "json"
        }
    ]
    
    exp_system = ExperienceSystem()
    factory = CellFactory(experience=exp_system)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"ТЕСТ {i}: {test['description']}")
        print('='*80)
        
        try:
            print("🧬 Создаю орган...")
            
            cell = factory.create_cell(
                pattern=test['description'],
                tasks=[{"description": test['description'], "status": "planned"}]
            )
            
            if cell:
                print(f"\n✅ УСПЕХ!")
                print(f"   Название: {cell.cell_name}")
                print(f"   Файл: {cell.file_path}")
                print(f"   Описание: {cell.description}")
                print(f"   ID: {cell.cell_id}")
                print(f"   Создан: {cell.created_at}")
                
                # Проверяем что файл существует
                import os
                if os.path.exists(cell.file_path):
                    print(f"\n📄 Файл создан и существует")
                    # Показываем первые 20 строк
                    with open(cell.file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[:20]
                        print("\n   Первые 20 строк кода:")
                        for j, line in enumerate(lines, 1):
                            print(f"   {j:2d} | {line.rstrip()}")
                else:
                    print(f"\n⚠️ Файл НЕ создан!")
            else:
                print(f"\n❌ ОШИБКА: Не удалось создать орган")
                
        except Exception as e:
            print(f"\n❌ ИСКЛЮЧЕНИЕ: {e}")
            import traceback
            traceback.print_exc()
        
        await asyncio.sleep(1)
    
    print("\n" + "="*80)
    print("ТЕСТЫ ЗАВЕРШЕНЫ")
    print("="*80)


async def simulate_telegram_flow():
    """Симулирует работу функции create_organ_background из telegram_bot.py"""
    
    print("\n" + "="*80)
    print("СИМУЛЯЦИЯ TELEGRAM ПОТОКА")
    print("="*80)
    
    # Симулируем Update объект
    class FakeMessage:
        async def reply_text(self, text):
            print(f"\n[BOT REPLY] {text}")
    
    class FakeUpdate:
        def __init__(self):
            self.message = FakeMessage()
    
    update = FakeUpdate()
    organ_description = "Орган для работы с Excel файлами. Методы: read_excel, write_excel, search_column"
    
    print(f"\n[USER] #создай_орган {organ_description}")
    
    # Это аналог функции create_organ_background из telegram_bot.py
    try:
        exp_system = ExperienceSystem()
        factory = CellFactory(experience=exp_system)
        
        await update.message.reply_text("🧠 Начинаю создавать новый орган...")
        
        cell = factory.create_cell(
            pattern=organ_description,
            tasks=[{"description": organ_description, "status": "planned"}]
        )
        
        if cell:
            await update.message.reply_text(
                f"✅ Орган создан успешно!\n\n"
                f"📝 Название: {cell.cell_name}\n"
                f"📄 Файл: {cell.file_path}\n"
                f"🎯 Назначение: {cell.description}\n\n"
                f"💡 Я научилась создавать код для себя!"
            )
        else:
            await update.message.reply_text(
                "⚠️ Не удалось создать орган. Попробуй описать задачу подробнее."
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при создании органа: {e}")
    
    print("\n[INFO] Симуляция завершена")


if __name__ == "__main__":
    # Windows event loop policy
    if sys.platform == "win32":
        try:
            from asyncio import WindowsSelectorEventLoopPolicy  # type: ignore
            asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())  # type: ignore
        except (AttributeError, ImportError):
            # Для старых версий Python используем ProactorEventLoopPolicy
            try:
                from asyncio import WindowsProactorEventLoopPolicy  # type: ignore
                asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())  # type: ignore
            except (AttributeError, ImportError):
                pass  # Используем дефолтную политику
    
    # Запускаем тесты
    asyncio.run(test_organ_creation())
    asyncio.run(simulate_telegram_flow())
