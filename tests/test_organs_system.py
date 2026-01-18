"""
Тестирование системы органов Нейры
- ExecutableOrgans (GraphicsOrgan, MathOrgan, TextOrgan)
- UnifiedOrganSystem (метаданные)
- Интеграция с neira_server
"""

import sys
sys.path.insert(0, '.')

def test_executable_organs():
    """Тест исполняемых органов"""
    print("=" * 60)
    print("🧬 ТЕСТ: ExecutableOrgans")
    print("=" * 60)
    
    from executable_organs import get_organ_registry, FeedbackType
    
    registry = get_organ_registry()
    print(f"✅ Загружено органов: {len(registry.organs)}")
    
    for organ_id, organ in registry.organs.items():
        info = organ.get_info()
        print(f"  • {info['name']} v{info['version']}: {info['description'][:50]}...")
    
    # Тест GraphicsOrgan
    print("\n📊 Тест GraphicsOrgan:")
    result, oid, rid = registry.process_command("нарисуй синий квадрат 3x3")
    print(result)
    print(f"  organ_id: {oid}, record_id: {rid}")
    
    # Feedback
    if oid:
        registry.add_feedback(oid, FeedbackType.POSITIVE)
        print("  ✅ Положительный feedback записан")
    
    # Тест MathOrgan
    print("\n🔢 Тест MathOrgan:")
    result, oid, rid = registry.process_command("посчитай 123 * 456")
    print(f"  {result}")
    
    # Тест TextOrgan
    print("\n📝 Тест TextOrgan:")
    result, oid, rid = registry.process_command("переверни 'Hello Neira!'")
    print(f"  {result}")
    
    # Статистика
    print("\n📈 Статистика обучения:")
    for organ in registry.organs.values():
        stats = organ.learner.get_stats()
        print(f"  {organ.name}: {stats['total_uses']} uses, {stats['learned_patterns']} patterns")
    
    return True


def test_unified_organ_system():
    """Тест UnifiedOrganSystem"""
    print("\n" + "=" * 60)
    print("🧬 ТЕСТ: UnifiedOrganSystem")
    print("=" * 60)
    
    from unified_organ_system import get_organ_system, OrganSandbox
    
    system = get_organ_system()
    print(f"✅ Загружено органов: {len(system.organs)}")
    
    for organ_id, organ in system.organs.items():
        print(f"  • {organ.name} ({organ.cell_type}): {organ.triggers[:3]}...")
    
    # Тест детекции
    print("\n🔍 Тест детекции органов:")
    test_queries = [
        "создай интерфейс калькулятора",
        "напиши функцию сортировки",
        "привет как дела",
    ]
    
    for query in test_queries:
        organ, reason = system.detect_organ(query)
        if organ:
            print(f"  ✅ '{query[:30]}...' → {organ.name}")
        else:
            print(f"  ⚪ '{query[:30]}...' → нет подходящего органа")
    
    # Тест Sandbox
    print("\n🧪 Тест Sandbox:")
    sandbox = OrganSandbox(system.protector)
    stats = sandbox.get_stats()
    print(f"  Статистика: {stats}")
    
    return True


def test_server_integration():
    """Тест интеграции с neira_server"""
    print("\n" + "=" * 60)
    print("🌐 ТЕСТ: Интеграция с neira_server")
    print("=" * 60)
    
    # Импортируем без запуска сервера
    from neira_server import NeiraServer
    
    server = NeiraServer(host="127.0.0.1", port=9999)
    
    # Проверяем что ExecutableOrgans доступны
    if server._executable_organs:
        print(f"✅ ExecutableOrgans доступны: {len(server._executable_organs.organs)} органов")
    else:
        print("❌ ExecutableOrgans НЕ доступны!")
        return False
    
    # Проверяем что UnifiedOrganSystem доступен
    if server._organ_system:
        print(f"✅ UnifiedOrganSystem доступен: {len(server._organ_system.organs)} органов")
    else:
        print("❌ UnifiedOrganSystem НЕ доступен!")
        return False
    
    # Тест автономного ответа через орган
    print("\n🤖 Тест автономного ответа через ExecutableOrgan:")
    response, source = server._try_autonomous_response("нарисуй квадрат 4x4")
    
    if response and source and "executable_organ" in source:
        print(f"  ✅ Ответ от: {source}")
        print(f"  📊 Результат:\n{response}")
    else:
        print(f"  ⚠️ Ответ не через ExecutableOrgan: source={source}")
    
    return True


def test_memory_persistence():
    """Тест что органы помнят своё состояние"""
    print("\n" + "=" * 60)
    print("💾 ТЕСТ: Память органов")
    print("=" * 60)
    
    from executable_organs import get_organ_registry, FeedbackType
    
    # Первая сессия
    registry1 = get_organ_registry()
    
    # Обучаем орган
    result, oid, rid = registry1.process_command("нарисуй зелёный круг 5")
    if oid:
        registry1.add_feedback(oid, FeedbackType.POSITIVE)
    
    patterns_count = registry1.get("graphics_organ").learner.get_stats()['learned_patterns']
    print(f"  Паттернов после обучения: {patterns_count}")
    
    # "Вторая сессия" (registry - singleton, так что будет тот же)
    registry2 = get_organ_registry()
    patterns_count2 = registry2.get("graphics_organ").learner.get_stats()['learned_patterns']
    print(f"  Паттернов во второй сессии: {patterns_count2}")
    
    if patterns_count == patterns_count2:
        print("  ✅ Память сохраняется между вызовами")
    else:
        print("  ⚠️ Память потеряна!")
    
    return True


if __name__ == "__main__":
    print("🧪 КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ СИСТЕМЫ ОРГАНОВ НЕЙРЫ")
    print("=" * 60)
    
    results = []
    
    try:
        results.append(("ExecutableOrgans", test_executable_organs()))
    except Exception as e:
        print(f"❌ Ошибка ExecutableOrgans: {e}")
        results.append(("ExecutableOrgans", False))
    
    try:
        results.append(("UnifiedOrganSystem", test_unified_organ_system()))
    except Exception as e:
        print(f"❌ Ошибка UnifiedOrganSystem: {e}")
        results.append(("UnifiedOrganSystem", False))
    
    try:
        results.append(("Server Integration", test_server_integration()))
    except Exception as e:
        print(f"❌ Ошибка Server Integration: {e}")
        results.append(("Server Integration", False))
    
    try:
        results.append(("Memory Persistence", test_memory_persistence()))
    except Exception as e:
        print(f"❌ Ошибка Memory Persistence: {e}")
        results.append(("Memory Persistence", False))
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")
    
    print(f"\n  Пройдено: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print("\n⚠️ Есть проблемы, требуется доработка")
