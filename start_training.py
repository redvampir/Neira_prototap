"""
🎓 Интерактивное обучение Neira
Реализация концепции из training-interface-improvements.md
"""

from training_orchestrator import TrainingOrchestrator, TrainingScenario
from neira_cortex import NeiraCortex


def main():
    """Главное меню обучения"""
    
    print("""
╔═══════════════════════════════════════════════════════════╗
║           🎓 СИСТЕМА ОБУЧЕНИЯ NEIRA 🎓                   ║
║                                                           ║
║  Адаптация training-interface-improvements.md            ║
║  для Python прототипа                                    ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Инициализация
    print("🔧 Инициализация системы...")
    cortex = NeiraCortex()
    orchestrator = TrainingOrchestrator(cortex.pathways)
    
    while True:
        print(f"\n{'=' * 70}")
        print("📋 ГЛАВНОЕ МЕНЮ")
        print(f"{'=' * 70}")
        print("1. Создать новый сценарий обучения")
        print("2. Запустить сценарий")
        print("3. Показать метрики")
        print("4. Просмотреть сценарии")
        print("5. Проверить сегменты, требующие внимания")
        print("6. Быстрый старт (демо сценарий)")
        print("0. Выход")
        
        choice = input("\nВыбор: ").strip()
        
        if choice == "1":
            create_scenario_interactive(orchestrator)
        elif choice == "2":
            run_scenario_interactive(orchestrator, cortex)
        elif choice == "3":
            orchestrator.show_metrics()
        elif choice == "4":
            show_scenarios(orchestrator)
        elif choice == "5":
            orchestrator.review_pending_segments()
        elif choice == "6":
            quick_start(orchestrator, cortex)
        elif choice == "0":
            print("\n👋 До встречи! Продолжай обучать Neira!")
            break
        else:
            print("⚠️ Неверный выбор")


def create_scenario_interactive(orchestrator: TrainingOrchestrator):
    """Создать сценарий интерактивно"""
    
    print(f"\n{'=' * 70}")
    print("✨ СОЗДАНИЕ НОВОГО СЦЕНАРИЯ")
    print(f"{'=' * 70}")
    
    name = input("Название сценария: ").strip()
    if not name:
        print("❌ Название обязательно")
        return
    
    description = input("Описание: ").strip()
    category = input("Категория (general/greeting/support/crisis/fun): ").strip() or "general"
    
    print("\nВведите вопросы (по одному на строку, пустая строка для завершения):")
    questions = []
    i = 1
    while True:
        q = input(f"{i}. ").strip()
        if not q:
            break
        questions.append(q)
        i += 1
    
    if not questions:
        print("❌ Нужен хотя бы один вопрос")
        return
    
    scenario = orchestrator.create_scenario(
        name=name,
        description=description,
        questions=questions,
        category=category
    )
    
    print(f"\n✅ Сценарий создан: {scenario.id}")


def run_scenario_interactive(orchestrator: TrainingOrchestrator, cortex: NeiraCortex):
    """Запустить сценарий интерактивно"""
    
    if not orchestrator.scenarios:
        print("❌ Нет доступных сценариев. Создайте новый.")
        return
    
    print(f"\n{'=' * 70}")
    print("▶️  ЗАПУСК СЦЕНАРИЯ")
    print(f"{'=' * 70}")
    
    # Показываем список
    scenarios = list(orchestrator.scenarios.values())
    for i, scenario in enumerate(scenarios, 1):
        status_emoji = {
            "idle": "⏸️",
            "running": "▶️",
            "paused": "⏸️",
            "completed": "✅",
            "failed": "❌"
        }.get(scenario.status.value, "❓")
        
        print(f"{i}. {status_emoji} {scenario.name}")
        print(f"   {scenario.description}")
        print(f"   Сегментов: {len(scenario.segments)}, Прогресс: {scenario.progress_percentage():.1f}%")
    
    choice = input("\nВыберите сценарий (номер): ").strip()
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(scenarios):
            scenario = scenarios[idx]
            
            print(f"\n🎯 Запуск: {scenario.name}")
            auto = input("Автоматический режим без HITL? (y/n): ").strip().lower()
            
            orchestrator.run_scenario(
                scenario.id,
                cortex,
                auto_mode=(auto == 'y')
            )
        else:
            print("❌ Неверный номер")
    except ValueError:
        print("❌ Введите число")


def show_scenarios(orchestrator: TrainingOrchestrator):
    """Показать все сценарии"""
    
    if not orchestrator.scenarios:
        print("❌ Нет сценариев")
        return
    
    print(f"\n{'=' * 70}")
    print("📚 СЦЕНАРИИ ОБУЧЕНИЯ")
    print(f"{'=' * 70}")
    
    for scenario in orchestrator.scenarios.values():
        print(f"\n📖 {scenario.name}")
        print(f"   ID: {scenario.id}")
        print(f"   Описание: {scenario.description}")
        print(f"   Категория: {scenario.category}")
        print(f"   Статус: {scenario.status.value}")
        print(f"   Сегментов: {len(scenario.segments)}")
        print(f"   Прогресс: {scenario.progress_percentage():.1f}%")
        print(f"   Успехов: {scenario.successes}")
        print(f"   Неудач: {scenario.failures}")


def quick_start(orchestrator: TrainingOrchestrator, cortex: NeiraCortex):
    """Быстрый старт с демо сценарием"""
    
    print(f"\n{'=' * 70}")
    print("🚀 БЫСТРЫЙ СТАРТ")
    print(f"{'=' * 70}")
    print("\nСоздаю демонстрационный сценарий...")
    
    scenario = orchestrator.create_scenario(
        name="Демо: Базовое общение",
        description="Тестирование простых приветствий и прощаний",
        questions=[
            "Привет, Neira!",
            "Как у тебя дела?",
            "Что ты умеешь делать?",
            "Спасибо за помощь!",
            "До встречи!"
        ],
        category="demo"
    )
    
    print(f"\n▶️ Запускаю сценарий...\n")
    
    orchestrator.run_scenario(
        scenario.id,
        cortex,
        auto_mode=False  # С HITL оценкой
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Обучение прервано. До встречи!")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
