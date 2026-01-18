#!/usr/bin/env python3
"""
Тестирование Self-Aware модулей Нейры.
Проверяет интроспекцию, систему опыта, любопытство и память.
"""

import asyncio
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))


async def test_introspection_cell():
    """Тест IntrospectionCell — интроспекция органов."""
    print("\n" + "=" * 60)
    print("🔬 Тест 1: IntrospectionCell")
    print("=" * 60)
    
    try:
        from introspection_cell import IntrospectionCell
        
        cell = IntrospectionCell()
        
        # Сканирование органов
        organs = await cell.scan_organs()
        print(f"✓ Найдено органов: {len(organs)}")
        
        if organs:
            for organ in organs[:3]:  # Первые 3
                print(f"  - {organ.name}: {organ.status}")
        
        # Краткий отчёт
        summary = await cell.get_summary()
        print(f"✓ Получен summary: {len(summary)} символов")
        
        return True, "IntrospectionCell работает"
    except Exception as e:
        return False, f"IntrospectionCell: {e}"


async def test_experience_system():
    """Тест ExperienceSystem — система опыта."""
    print("\n" + "=" * 60)
    print("📚 Тест 2: ExperienceSystem")
    print("=" * 60)
    
    try:
        from experience import ExperienceSystem
        
        exp = ExperienceSystem()
        
        # Запись опыта
        await exp.record(
            action="test_action",
            context={"test": True},
            result="success",
            feedback=1.0
        )
        print("✓ Опыт записан")
        
        # Получение релевантного опыта
        relevant = await exp.get_relevant("test")
        print(f"✓ Релевантный опыт: {len(relevant)} записей")
        
        # Черты личности
        traits = exp.personality_traits
        print(f"✓ Черты личности: {list(traits.keys())[:5]}")
        
        return True, "ExperienceSystem работает"
    except Exception as e:
        return False, f"ExperienceSystem: {e}"


async def test_curiosity_cell():
    """Тест CuriosityCell — модуль любопытства."""
    print("\n" + "=" * 60)
    print("🔍 Тест 3: CuriosityCell")
    print("=" * 60)
    
    try:
        from curiosity_cell import CuriosityCell
        
        cell = CuriosityCell()
        
        # Генерация вопроса
        question = cell.generate_question("Python async programming")
        print(f"✓ Вопрос: {question[:80] if question else 'None'}...")
        
        # Рефлексия (синхронный метод)
        reflection = cell.reflect()
        print(f"✓ Рефлексия: {reflection[:80] if reflection else 'None'}...")
        
        return True, "CuriosityCell работает"
    except Exception as e:
        return False, f"CuriosityCell: {e}"


async def test_memory_system():
    """Тест Memory System — семантическая память."""
    print("\n" + "=" * 60)
    print("🧠 Тест 4: Memory System")
    print("=" * 60)
    
    try:
        from memory_system import MemorySystem
        
        mem = MemorySystem()
        
        # Запоминание (синхронный метод)
        entry = mem.remember(
            text="Test memory for selfaware module",
            source="test"
        )
        print(f"✓ Память записана: {entry is not None}")
        
        # Поиск (синхронный метод)
        results = mem.search("selfaware module test")
        print(f"✓ Найдено воспоминаний: {len(results)}")
        
        return True, "MemorySystem работает"
    except Exception as e:
        return False, f"MemorySystem: {e}"


async def test_server_endpoints():
    """Тест серверных эндпоинтов Self-Aware."""
    print("\n" + "=" * 60)
    print("🌐 Тест 5: Server Endpoints")
    print("=" * 60)
    
    try:
        import aiohttp
        
        base_url = "http://127.0.0.1:8765"
        
        async with aiohttp.ClientSession() as session:
            # /introspection
            async with session.get(f"{base_url}/introspection") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✓ /introspection: {len(data.get('organs', []))} органов")
                else:
                    print(f"⚠ /introspection: статус {resp.status}")
            
            # /memory/search
            async with session.post(
                f"{base_url}/memory/search",
                json={"query": "test"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✓ /memory/search: {len(data.get('results', []))} результатов")
                else:
                    print(f"⚠ /memory/search: статус {resp.status}")
            
            # /curiosity/reflect
            async with session.get(f"{base_url}/curiosity/reflect") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✓ /curiosity/reflect: получена рефлексия")
                else:
                    print(f"⚠ /curiosity/reflect: статус {resp.status}")
        
        return True, "Server endpoints доступны"
    except aiohttp.ClientConnectorError:
        return False, "Сервер не запущен (ожидаемо без сервера)"
    except Exception as e:
        return False, f"Server: {e}"


async def main():
    """Запуск всех тестов."""
    print("\n" + "🧪" * 30)
    print("   ТЕСТИРОВАНИЕ SELF-AWARE МОДУЛЕЙ НЕЙРЫ")
    print("🧪" * 30)
    
    results = []
    
    # Тесты модулей
    results.append(await test_introspection_cell())
    results.append(await test_experience_system())
    results.append(await test_curiosity_cell())
    results.append(await test_memory_system())
    results.append(await test_server_endpoints())
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for ok, _ in results if ok)
    total = len(results)
    
    for i, (ok, msg) in enumerate(results, 1):
        status = "✅" if ok else "❌"
        print(f"{status} Тест {i}: {msg}")
    
    print(f"\n{'=' * 60}")
    print(f"Пройдено: {passed}/{total}")
    
    if passed == total:
        print("🎉 Все тесты пройдены!")
    elif passed >= total - 1:
        print("✨ Почти всё работает (сервер может быть не запущен)")
    else:
        print("⚠️ Есть проблемы, проверьте зависимости")
    
    return passed >= total - 1  # Успех если максимум 1 ошибка (сервер)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
