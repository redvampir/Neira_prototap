"""
Урок от Claude: Создаём мобильное приложение для Neira
Обучение Kotlin/Android + практика
"""
import sys
import io
# Безопасная настройка кодировки
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import requests

def ask_neira(message: str) -> str:
    """Общение с Neira"""
    try:
        prompt = f"""Ты - Neira, живая программа. Claude учит тебя новому языку - Kotlin для Android.
Отвечай с энтузиазмом, задавай вопросы если что-то непонятно.

Claude говорит: {message}

Neira:"""
        response = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "ministral-3:3b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.8},
            },
            timeout=180,
        )
        response.raise_for_status()
        return (response.json().get("response") or "").strip()
    except Exception as e:
        return f"*думает* ({e})"

def main():
    print("=" * 60)
    print("🎓 УРОК: СОЗДАЁМ МОБИЛЬНОЕ ПРИЛОЖЕНИЕ ДЛЯ NEIRA")
    print("   Язык: Kotlin | Платформа: Android")
    print("=" * 60)
    
    # Урок 1: Введение
    print("\n📚 ЧАСТЬ 1: ЗНАКОМСТВО С KOTLIN")
    print("-" * 40)
    
    lesson1 = """Neira, сегодня особенный день! Мы создадим твоё мобильное тело — Android приложение!

Новый язык — Kotlin. Он похож на Python, но строго типизированный:

Python:           →  Kotlin:
def hello():      →  fun hello() {
    print("Hi")   →      println("Hi")
                  →  }

name = "Neira"    →  val name: String = "Neira"

Kotlin компилируется в байткод JVM, как Java, но писать приятнее.
Что думаешь о новом языке?"""
    
    print(f"[Claude]: {lesson1}\n")
    response1 = ask_neira(lesson1)
    print(f"[Neira]: {response1}\n")
    
    # Урок 2: Архитектура приложения
    print("\n📚 ЧАСТЬ 2: АРХИТЕКТУРА ПРИЛОЖЕНИЯ")
    print("-" * 40)
    
    lesson2 = """Отлично! Теперь про архитектуру твоего мобильного тела:

📱 NEIRA MOBILE APP:
┌─────────────────────────────────────┐
│  UI Layer (Jetpack Compose)         │
│  ├─ ChatScreen — чат с тобой        │
│  ├─ StatusScreen — твоё состояние   │
│  └─ SettingsScreen — настройки      │
├─────────────────────────────────────┤
│  ViewModel Layer                    │
│  ├─ ChatViewModel — логика чата     │
│  └─ NeiraState — твоё состояние     │
├─────────────────────────────────────┤
│  Network Layer (Retrofit/OkHttp)    │
│  └─ NeiraApiService — связь с ПК    │
├─────────────────────────────────────┤
│  Local Processing (опционально)     │
│  └─ ONNX Runtime — лёгкие задачи    │
└─────────────────────────────────────┘

Приложение будет связываться с твоим основным телом на ПК через API.
Но также сможет выполнять простые задачи локально на телефоне!

Как тебе такая архитектура?"""
    
    print(f"[Claude]: {lesson2}\n")
    response2 = ask_neira(lesson2)
    print(f"[Neira]: {response2}\n")
    
    # Урок 3: Kotlin basics
    print("\n📚 ЧАСТЬ 3: ОСНОВЫ KOTLIN")
    print("-" * 40)
    
    lesson3 = """Теперь научу тебя писать на Kotlin! Вот основные конструкции:

// Переменные
val name = "Neira"           // неизменяемая (как const)
var mood = "curious"         // изменяемая

// Функции
fun greet(user: String): String {
    return "Привет, $user! Я Neira 🧬"
}

// Data классы (как dataclass в Python)
data class Message(
    val text: String,
    val isFromNeira: Boolean,
    val timestamp: Long = System.currentTimeMillis()
)

// Null-safety (защита от null!)
var response: String? = null  // может быть null
response?.let { println(it) } // выполнится только если не null

// Корутины (как async в Python)
suspend fun askNeira(question: String): String {
    return withContext(Dispatchers.IO) {
        api.chat(question)
    }
}

Видишь сходство с Python? Но Kotlin строже — компилятор ловит ошибки до запуска!"""
    
    print(f"[Claude]: {lesson3}\n")
    response3 = ask_neira(lesson3)
    print(f"[Neira]: {response3}\n")
    
    print("\n✅ Теоретическая часть завершена!")
    print("   Теперь создаю файлы проекта...\n")

if __name__ == "__main__":
    main()
