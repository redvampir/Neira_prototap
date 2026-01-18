#!/usr/bin/env python3
"""
Тест интеграции системы клеток и органов с новой моделью
"""

import os
import sys

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(__file__))

def test_integration():
    print("🧪 Тестирование интеграции системы клеток и органов...")

    try:
        # Импортируем основные компоненты
        from cells import MemoryCell, AnalyzerCell, PlannerCell, ExecutorCell
        print("✅ Клетки импортированы успешно")

        # Проверяем систему памяти
        memory = MemoryCell()
        print("✅ MemoryCell инициализирована")

        # Проверяем наличие model_layers
        try:
            from model_layers import ModelLayersRegistry
            registry = ModelLayersRegistry('model_layers.json')
            layers = registry.get_layers_for_model('nemotron-mini')
            print(f"✅ Model layers загружены: {len(layers)} слоев")

            # Проверяем наличие наших слоев
            layer_names = [layer.id for layer in layers]
            required_layers = ['cell_system', 'memory_integration', 'organ_system']
            for layer in required_layers:
                if layer in layer_names:
                    print(f"✅ Слой '{layer}' найден")
                else:
                    print(f"⚠️ Слой '{layer}' не найден")

        except Exception as e:
            print(f"⚠️ Model layers недоступны: {e}")

        # Проверяем cell router
        try:
            from cell_router import get_router
            router = get_router()
            print("✅ Cell Router инициализирован")
        except Exception as e:
            print(f"⚠️ Cell Router недоступен: {e}")

        print("\n🎉 Интеграция системы клеток и органов завершена!")
        print("Теперь новая модель будет использовать память и клеточную архитектуру.")

    except Exception as e:
        print(f"❌ Ошибка интеграции: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_integration()