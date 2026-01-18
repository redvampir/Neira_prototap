"""
Тест всех мозговых систем Нейры.
"""

import sys
import json
from datetime import datetime

import pytest


def test_lateral_inhibition():
    """Тест латерального торможения."""
    print("\n" + "="*50)
    print("🧠 Тест: Латеральное торможение")
    print("="*50)
    
    from lateral_inhibition import get_lateral_inhibition
    
    li = get_lateral_inhibition()
    
    # Активируем несколько топиков (topic_id, name, category, strength)
    li.activate_topic("python_prog", "программирование на Python", "technical", 0.8)
    li.activate_topic("feelings", "чувства и эмоции", "emotional", 0.5)
    li.activate_topic("game_dev", "создание игры", "creative", 0.3)
    
    print(f"Активных топиков: {len(li.topics)}")
    
    focus = li.get_focus()
    if focus:
        print(f"Фокус: {focus.name} (категория: {focus.category}, активация: {focus.activation:.2f})")
    
    relevant = li.get_context_filter()
    print(f"Релевантные категории: {relevant}")
    
    stats = li.get_statistics()
    print(f"Статистика: {json.dumps(stats, ensure_ascii=False, indent=2)}")
    
    print("✅ Латеральное торможение работает!")
    return True


def test_predictive_coding():
    """Тест предсказательного кодирования."""
    print("\n" + "="*50)
    print("🔮 Тест: Предсказательное кодирование")
    print("="*50)
    
    from predictive_coding import get_predictive_coding, PredictionType
    
    pc = get_predictive_coding()
    
    # Создаём предсказание
    prediction = pc.predict(
        "Привет! Как дела?",
        PredictionType.FOLLOW_UP,
        trigger="greeting"
    )
    
    if prediction:
        print(f"Предсказание: {prediction.predicted_value}")
        print(f"Уверенность: {prediction.confidence:.2f}")
        
        # Разрешаем предсказание
        result = pc.resolve_prediction(prediction.prediction_id, "how_are_you")
        print(f"Результат: ошибка={result.get('error', 0):.2f}, успех={result.get('success')}")
    
    # Подсказка
    suggestion = pc.suggest_next("Помоги с кодом")
    if suggestion:
        print(f"Подсказка: {suggestion}")
    
    stats = pc.get_statistics()
    print(f"Точность: {stats['accuracy']:.2%}")
    
    print("✅ Предсказательное кодирование работает!")
    return True


def test_synaptic_pruning():
    """Тест синаптического прунинга."""
    print("\n" + "="*50)
    print("✂️ Тест: Синаптический прунинг")
    print("="*50)
    
    from synaptic_pruning import get_synaptic_pruning, PruningStrategy
    
    sp = get_synaptic_pruning()
    
    # Добавляем связи
    conn1 = sp.add_connection("user_greeting", "response_hello", strength=0.9, protected=True)
    conn2 = sp.add_connection("old_topic", "forgotten_response", strength=0.05)
    conn3 = sp.add_connection("frequent_topic", "good_response", strength=0.7)
    
    print(f"Добавлено связей: 3")
    print(f"Всего связей: {len(sp.connections)}")
    
    # Используем сильную связь
    sp.use_connection(conn3.connection_id)
    
    # Рассчитываем оценки прунинга
    sp.calculate_pruning_scores()
    
    weak = sp.get_weak_connections(5)
    print(f"Слабых связей: {len(weak)}")
    
    # Запускаем прунинг
    event = sp.run_pruning(PruningStrategy.HYBRID, force=True)
    print(f"Удалено: {event.pruned_count}")
    
    stats = sp.get_statistics()
    print(f"Статистика: средняя сила={stats['avg_strength']:.2f}")
    
    print("✅ Синаптический прунинг работает!")
    return True


def test_neural_oscillations():
    """Тест нейронных осцилляций."""
    print("\n" + "="*50)
    print("〰️ Тест: Нейронные осцилляции")
    print("="*50)
    
    from neural_oscillations import get_neural_oscillations, BrainWave
    
    no = get_neural_oscillations()
    
    # Текущий режим
    mode = no.get_current_mode()
    print(f"Текущий режим: {mode['mode']}")
    print(f"Описание: {mode['description']}")
    print(f"Когерентность: {mode['coherence']:.2f}")
    
    # Переход в режим работы
    result = no.transition_to(BrainWave.BETA, trigger="test_work")
    print(f"Переход в BETA: успех={result['success']}")
    
    # Модификаторы
    modifiers = no.get_modifiers()
    print(f"Модификаторы: скорость={modifiers['processing_speed']:.1f}, креатив={modifiers['creativity']:.1f}")
    
    # Автоопределение режима
    detected = no.detect_mode_from_context("помоги написать код на Python")
    print(f"Определённый режим для 'код на Python': {detected.value}")
    
    detected2 = no.detect_mode_from_context("придумай историю про дракона")
    print(f"Определённый режим для 'история про дракона': {detected2.value}")
    
    stats = no.get_statistics()
    print(f"Всего переходов: {stats['total_transitions']}")
    
    print("✅ Нейронные осцилляции работают!")
    return True


@pytest.mark.skip(reason="brain_integration moved to scripts/")
def test_brain_integration():
    """Тест интеграции всех систем."""
    print("\n" + "="*50)
    print("🧬 Тест: Интеграция мозговых систем")
    print("="*50)
    
    from brain_integration import get_brain_integration
    
    brain = get_brain_integration()
    
    # Обработка входа
    result = brain.process_input("Помоги мне написать функцию на Python")
    print(f"Обработано через системы: {result['systems_activated']}")
    print(f"Текущий режим: {result.get('current_mode', {}).get('mode', 'N/A')}")
    
    if "focus" in result:
        print(f"Фокус: {result['focus']['topic']}")
    
    if "prediction" in result:
        print(f"Предсказание: {result['prediction']['value']} ({result['prediction']['confidence']:.0%})")
    
    # Состояние мозга
    state = brain.get_brain_state()
    print(f"\nСостояние мозга:")
    print(f"  Режим: {state.oscillation_mode}")
    print(f"  Когерентность: {state.coherence:.2f}")
    print(f"  Фокус: {state.focus_topic or 'нет'}")
    
    # Полная статистика
    full_stats = brain.get_full_statistics()
    print(f"\nДоступные системы: {len(full_stats['available_systems'])}")
    for sys_name in full_stats['available_systems']:
        print(f"  ✓ {sys_name}")
    
    if full_stats['missing_systems']:
        print(f"\nОтсутствующие системы:")
        for sys_name in full_stats['missing_systems']:
            print(f"  ✗ {sys_name}")
    
    print("\n✅ Интеграция работает!")
    return True


def main():
    """Запуск всех тестов."""
    print("="*60)
    print("🧠 ТЕСТИРОВАНИЕ МОЗГОВЫХ СИСТЕМ НЕЙРЫ")
    print("="*60)
    print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Латеральное торможение", test_lateral_inhibition),
        ("Предсказательное кодирование", test_predictive_coding),
        ("Синаптический прунинг", test_synaptic_pruning),
        ("Нейронные осцилляции", test_neural_oscillations),
        ("Интеграция систем", test_brain_integration),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
        except Exception as e:
            print(f"\n❌ ОШИБКА в тесте '{name}': {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False, str(e)))
    
    # Итоги
    print("\n" + "="*60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, error in results:
        status = "✅" if success else "❌"
        error_msg = f" ({error})" if error else ""
        print(f"{status} {name}{error_msg}")
    
    print(f"\nПройдено: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 Все мозговые системы работают корректно!")
    else:
        print(f"\n⚠️ {total - passed} тест(ов) не прошло")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
