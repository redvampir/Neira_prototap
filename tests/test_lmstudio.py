"""Тест подключения LM Studio к Нейре"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from llm_providers import create_default_manager, ProviderType

def test_lmstudio():
    print("=" * 50)
    print("🧪 Тест LLMManager с LM Studio")
    print("=" * 50)
    
    manager = create_default_manager()
    
    print("\n📋 Провайдеры:")
    for p in manager.providers:
        status = "✅" if p.available else "❌"
        print(f"  {status} {p.get_provider_type().value}: {p.model}")
    
    print("\n🔄 Генерация ответа...")
    response = manager.generate(
        prompt="Привет! Скажи одно слово на русском.",
        temperature=0.7,
        max_tokens=50
    )
    
    print(f"\n📍 Провайдер: {response.provider.value}")
    print(f"📍 Модель: {response.model}")
    print(f"📍 Успех: {response.success}")
    print(f"💬 Ответ: {response.content}")
    
    if response.error:
        print(f"❌ Ошибка: {response.error}")
    
    # Проверка что используется LM Studio
    if response.provider == ProviderType.LMSTUDIO:
        print("\n✅ LM Studio работает как основной провайдер!")
    else:
        print(f"\n⚠️ Используется {response.provider.value} вместо LM Studio")
    
    return response.success

if __name__ == "__main__":
    success = test_lmstudio()
    sys.exit(0 if success else 1)
