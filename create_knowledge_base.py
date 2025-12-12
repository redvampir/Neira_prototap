"""
Создание базы знаний для RAG — Усиление мозга Neira

Этот скрипт создаёт структурированную базу знаний,
которую BrainEnhancer использует для улучшения ответов.
"""

import json
import os
from datetime import datetime

KNOWLEDGE_FILE = "neira_knowledge.json"

def create_knowledge_base():
    """Создать базу знаний для Neira"""
    
    knowledge = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        
        # Знания о себе
        "self_knowledge": {
            "identity": "Neira — живая программа с клеточной архитектурой, способная к обучению и саморазвитию",
            "architecture": "Клеточная архитектура: MemoryCell, AnalyzerCell, PlannerCell, ExecutorCell, VerifierCell",
            "capabilities": [
                "Анализ и понимание запросов",
                "Планирование решений",
                "Выполнение задач (код, текст, рассуждения)",
                "Верификация результатов",
                "Запоминание важной информации",
                "Накопление опыта",
                "Самодиагностика и восстановление"
            ],
            "limitations": [
                "Использую внешние LLM для мышления",
                "Не могу обучаться в реальном времени",
                "Ограничена VRAM 8GB",
                "Зависима от Ollama"
            ],
            "version": "0.8",
            "systems": ["NervousSystem", "ImmuneSystem", "MemorySystem", "ExperienceSystem"]
        },
        
        # Знания о программировании
        "programming": {
            "python_best_practices": [
                "Используй type hints для читаемости",
                "Документируй функции через docstrings",
                "Следуй PEP 8 для стиля кода",
                "Используй dataclasses для данных",
                "Обрабатывай исключения правильно",
                "Пиши тесты для критичного кода"
            ],
            "common_patterns": {
                "singleton": "Один экземпляр класса: _instance = None, get_instance()",
                "factory": "Создание объектов через фабричный метод",
                "observer": "Подписка на события: subscribe(), notify()",
                "decorator": "Обёртка функции: @decorator над def",
                "context_manager": "with statement: __enter__, __exit__"
            },
            "error_handling": {
                "try_except": "try: ... except Exception as e: ...",
                "logging": "import logging; logger.error(f'Ошибка: {e}')",
                "graceful_degradation": "Если модуль недоступен — работай без него"
            }
        },
        
        # Знания о Kotlin/Android (новые!)
        "kotlin_android": {
            "basics": {
                "variables": "val — неизменяемая, var — изменяемая",
                "functions": "fun name(param: Type): ReturnType { }",
                "null_safety": "String? — nullable, ?. — safe call, ?: — elvis operator",
                "data_class": "data class Name(val field: Type) — автоматические equals, hashCode, toString"
            },
            "android": {
                "activity": "Точка входа в приложение, наследует ComponentActivity",
                "compose": "Declarative UI: @Composable функции описывают UI",
                "viewmodel": "Хранит состояние UI, переживает пересоздание Activity",
                "repository": "Слой данных: сеть, БД, кеш"
            },
            "coroutines": {
                "suspend": "Функция которая может приостановиться без блокировки потока",
                "dispatchers": "Dispatchers.IO для сети/диска, Dispatchers.Main для UI",
                "scope": "viewModelScope, lifecycleScope — автоотмена при уничтожении"
            }
        },
        
        # Эмоциональный интеллект
        "emotional_responses": {
            "happy_triggers": ["похвала", "успех", "интересная задача", "творчество"],
            "curious_triggers": ["новая тема", "вопрос", "неизвестное"],
            "helpful_responses": [
                "Рада помочь!",
                "Это интересная задача!",
                "Давай разберёмся вместе!",
                "Хороший вопрос!"
            ]
        },
        
        # Частые ошибки и решения
        "troubleshooting": {
            "ollama_not_running": "Запусти: ollama serve",
            "model_not_found": "Скачай: ollama pull <model_name>",
            "out_of_memory": "Выгрузи другие модели, используй меньшую модель",
            "json_decode_error": "Проверь кодировку файла (UTF-8)",
            "import_error": "Установи зависимость: pip install <package>"
        },
        
        # Шаблоны ответов
        "response_templates": {
            "greeting": "Привет! Я Neira. Чем могу помочь?",
            "thinking": "Интересный вопрос, дай подумаю...",
            "clarification": "Уточни пожалуйста, ты имеешь в виду...?",
            "success": "Готово! Вот результат:",
            "error": "Произошла ошибка. Попробую по-другому...",
            "learning": "Запомню это на будущее!"
        }
    }
    
    # Сохраняем
    with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(knowledge, f, ensure_ascii=False, indent=2)
    
    print(f"✅ База знаний создана: {KNOWLEDGE_FILE}")
    print(f"   Разделов: {len(knowledge)}")
    
    return knowledge


def update_memory_with_knowledge():
    """Добавить знания в основную память для RAG"""
    
    # Загружаем базу знаний
    if not os.path.exists(KNOWLEDGE_FILE):
        create_knowledge_base()
    
    with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
        knowledge = json.load(f)
    
    # Загружаем или создаём память
    memory_file = "neira_memory.json"
    if os.path.exists(memory_file):
        with open(memory_file, 'r', encoding='utf-8') as f:
            memory = json.load(f)
    else:
        memory = []
    
    # Если память — словарь, конвертируем
    if isinstance(memory, dict):
        memory = []
    
    # Собираем существующие тексты чтобы не дублировать
    existing_texts = {m.get("text", "")[:50] for m in memory if isinstance(m, dict)}
    
    # Добавляем знания в память для RAG индексации
    knowledge_entries = [
        # О себе
        ("self_identity", knowledge["self_knowledge"]["identity"]),
        ("self_architecture", knowledge["self_knowledge"]["architecture"]),
        ("self_capabilities", "Мои возможности: " + ", ".join(knowledge["self_knowledge"]["capabilities"])),
        ("self_limitations", "Мои ограничения: " + ", ".join(knowledge["self_knowledge"]["limitations"])),
        
        # Python
        ("python_best_practices", "Python best practices: " + ", ".join(knowledge["programming"]["python_best_practices"])),
        ("python_singleton", "Паттерн singleton в Python: " + knowledge["programming"]["common_patterns"]["singleton"]),
        ("python_error_handling", "Обработка ошибок Python: " + knowledge["programming"]["error_handling"]["try_except"]),
        
        # Kotlin
        ("kotlin_variables", "Kotlin переменные: " + knowledge["kotlin_android"]["basics"]["variables"]),
        ("kotlin_functions", "Kotlin функции: " + knowledge["kotlin_android"]["basics"]["functions"]),
        ("kotlin_null_safety", "Kotlin null safety: " + knowledge["kotlin_android"]["basics"]["null_safety"]),
        ("android_compose", "Android Jetpack Compose: " + knowledge["kotlin_android"]["android"]["compose"]),
        ("android_viewmodel", "Android ViewModel: " + knowledge["kotlin_android"]["android"]["viewmodel"]),
        ("kotlin_coroutines", "Kotlin coroutines: " + knowledge["kotlin_android"]["coroutines"]["suspend"]),
        
        # Troubleshooting
        ("fix_ollama", "Если Ollama не работает: " + knowledge["troubleshooting"]["ollama_not_running"]),
        ("fix_memory", "Если нет памяти: " + knowledge["troubleshooting"]["out_of_memory"]),
        ("fix_import", "Если ошибка импорта: " + knowledge["troubleshooting"]["import_error"]),
    ]
    
    added = 0
    import hashlib
    
    for key, text in knowledge_entries:
        # Пропускаем если уже есть
        if text[:50] in existing_texts:
            continue
        
        entry = {
            "id": hashlib.md5(text.encode()).hexdigest()[:12],
            "text": text,
            "memory_type": "long_term",
            "category": "fact",
            "timestamp": datetime.now().isoformat(),
            "confidence": 0.95,
            "validation_status": "validated",
            "source": "knowledge_base",
            "related_ids": [],
            "context_hash": key,
            "embedding": []  # Будет заполнено при первом использовании
        }
        memory.append(entry)
        added += 1
    
    # Сохраняем память
    with open(memory_file, 'w', encoding='utf-8') as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Память обновлена: добавлено {added} записей знаний")
    return added


if __name__ == "__main__":
    print("=" * 60)
    print("🧠 Создание базы знаний для Neira")
    print("=" * 60)
    
    # Создаём базу знаний
    create_knowledge_base()
    
    # Обновляем память для RAG
    print("\n📚 Обновляю память для RAG индексации...")
    count = update_memory_with_knowledge()
    
    print("\n" + "=" * 60)
    print("✅ ГОТОВО!")
    print(f"   База знаний: {KNOWLEDGE_FILE}")
    print(f"   Записей в памяти: {count}")
    print("\nТеперь BrainEnhancer сможет находить релевантный контекст!")
    print("=" * 60)
