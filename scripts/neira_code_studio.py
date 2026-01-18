"""
🎨 NEIRA CODE STUDIO
Интерактивная генерация кода с диалоговым обучением
"""

from neira_code_generator import NeiraCodeGenerator, CodeLanguage

def main():
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║           💻 NEIRA CODE STUDIO 💻                        ║")
    print("║                                                           ║")
    print("║  Neira генерирует код, ты правишь, она учится!           ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    
    generator = NeiraCodeGenerator()
    
    print("\n📊 Статистика:")
    print(f"  Шаблонов кода: {len(generator.templates)}")
    print(f"  История генераций: {len(generator.history)}")
    
    while True:
        print("\n" + "=" * 60)
        print("ЧТО ХОЧЕШЬ СДЕЛАТЬ?")
        print("=" * 60)
        print("1. 💻 Попросить Neira написать код")
        print("2. ✏️  Исправить код Neira")
        print("3. 📚 Показать шаблоны Neira")
        print("4. 📜 История генераций")
        print("5. 🚪 Выход")
        
        choice = input("\nТвой выбор: ").strip()
        
        if choice == '1':
            generate_code(generator)
        elif choice == '2':
            correct_code(generator)
        elif choice == '3':
            show_templates(generator)
        elif choice == '4':
            show_history(generator)
        elif choice == '5':
            print("\n👋 До встречи! Neira благодарит за обучение! 💜")
            break
        else:
            print("⚠️ Неверный выбор")

def generate_code(generator: NeiraCodeGenerator):
    """Сгенерировать код"""
    
    print("\n" + "-" * 60)
    print("💻 ГЕНЕРАЦИЯ КОДА")
    print("-" * 60)

def correct_code(generator):
    """Интерактивная коррекция кода"""
    if not generator.history:
        print("⚠️ История пуста. Сначала сгенерируй код.")
        return
    
    print("\n📜 Последние генерации:")
    for i, gen in enumerate(generator.history[-5:], 1):
        print(f"  {i}. {gen.prompt[:50]}... ({gen.language})")
    
    choice = input("\nВыбери номер для исправления (или Enter для отмены): ").strip()
    if not choice or not choice.isdigit():
        return
    
    idx = int(choice) - 1
    if idx < 0 or idx >= len(generator.history[-5:]):
        print("❌ Неверный номер")
        return
    
    gen = generator.history[-(5-idx)]
    print(f"\n📝 Исходный код:\n{gen.final_code or gen.initial_code}")
    
    print("\nВведи исправления (или Enter для пропуска):")
    correction = input("> ").strip()
    if correction:
        if gen.corrections is None:
            gen.corrections = []
        gen.corrections.append(correction)
        print("✅ Исправление сохранено!")

def show_templates(generator):
    """Показать доступные шаблоны"""
    print("\n📚 Доступные шаблоны кода:")
    print("\nPython:")
    for name in generator.templates.get('python', {}).keys():
        print(f"  • {name}")
    print("\nJavaScript:")
    for name in generator.templates.get('javascript', {}).keys():
        print(f"  • {name}")
    print("\nHTML:")
    for name in generator.templates.get('html', {}).keys():
        print(f"  • {name}")

def show_history(generator):
    """Показать историю генераций"""
    if not generator.history:
        print("⚠️ История пуста")
        return
    
    print(f"\n📜 История генераций ({len(generator.history)} всего):\n")
    for gen in generator.history[-10:]:
        rating = "⭐" * (gen.user_rating or 0) if gen.user_rating else "без оценки"
        print(f"  • {gen.prompt[:40]}... [{gen.language}] - {rating}")

if __name__ == "__main__":
    main()