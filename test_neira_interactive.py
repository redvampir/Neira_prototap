"""
Интерактивный тест Neira - общение с проверкой заглушек
"""
import sys
import os

# Убираем вывод варнингов
import warnings
warnings.filterwarnings('ignore')

from main import Neira

def test_neira_chat():
    print("=" * 70)
    print("🧠 NEIRA INTERACTIVE TEST - Проверка работы и заглушек")
    print("=" * 70)
    
    print("\n📥 Инициализация Neira...")
    neira = Neira(verbose=False)
    print("✅ Neira запущена!\n")
    
    # Тестовые вопросы для проверки заглушек
    test_questions = [
        "Привет, Нейра! Как тебя зовут?",
        "Расскажи о себе немного",
        "Что ты умеешь делать?",
        "Кто твои создатели?",
        "Какая твоя цель?"
    ]
    
    print("🔍 Автоматические тесты:\n")
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'─' * 70}")
        print(f"[Тест {i}/5] 👤 Пользователь: {question}")
        print("─" * 70)
        
        try:
            response = neira.process(question)
            
            # Проверка на заглушки
            placeholder_markers = [
                "🤔 Не нашла подходящий фрагмент ответа",
                "Cortex Placeholder Response",
                "нейронных путей",
                "neural pathway"
            ]
            
            has_placeholder = any(marker in response for marker in placeholder_markers)
            
            if has_placeholder:
                print("⚠️ ОБНАРУЖЕНА ЗАГЛУШКА!")
                print(f"🤖 Neira: {response[:300]}...")
            else:
                print(f"✅ Нормальный ответ")
                print(f"🤖 Neira: {response}")
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    # Интерактивный режим
    print("\n" + "=" * 70)
    print("💬 Интерактивный режим (введите 'выход' для завершения)")
    print("=" * 70)
    
    while True:
        try:
            user_input = input("\n👤 Вы: ").strip()
            
            if user_input.lower() in ['выход', 'exit', 'quit', 'q']:
                print("\n👋 Завершение работы...")
                break
            
            if not user_input:
                continue
            
            print("🤖 Neira думает...")
            response = neira.process(user_input)
            
            # Проверка на заглушки
            placeholder_markers = [
                "🤔 Не нашла подходящий фрагмент ответа",
                "Cortex Placeholder Response",
                "нейронных путей"
            ]
            
            has_placeholder = any(marker in response for marker in placeholder_markers)
            
            if has_placeholder:
                print("⚠️ [ЗАГЛУШКА ОБНАРУЖЕНА]")
            
            print(f"\n🤖 Neira: {response}")
            
        except KeyboardInterrupt:
            print("\n\n👋 Завершение работы...")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")

if __name__ == "__main__":
    test_neira_chat()
