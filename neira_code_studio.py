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