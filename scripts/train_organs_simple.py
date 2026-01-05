"""
Простое обучение Нейры созданию органов
Добавляет записи напрямую в JSON файлы без импорта telegram_bot
"""

import json
import os
from datetime import datetime

EXPERIENCE_FILE = "neira_experience.json"
PERSONALITY_FILE = "neira_personality.json"

def train():
    print("🧬 Обучение Нейры созданию органов")
    print("=" * 50)
    
    # Загружаем текущий опыт
    experiences = []
    if os.path.exists(EXPERIENCE_FILE):
        with open(EXPERIENCE_FILE, 'r', encoding='utf-8') as f:
            experiences = json.load(f)
        print(f"📚 Загружено записей: {len(experiences)}")

    # Уроки по созданию органов
    lessons = [
        {
            "task_type": "organ_creation",
            "user_input": "Как создать новый орган?",
            "lesson": "Структура органа: файл название_cell.py в generated/, класс от Cell, поля name и system_prompt, метод process(), возврат CellResult"
        },
        {
            "task_type": "organ_creation", 
            "user_input": "JSON спецификация органа",
            "lesson": 'JSON формат: cell_name (snake_case), description (что делает), purpose (зачем), system_prompt (инструкции для LLM). Только чистый JSON без markdown!'
        },
        {
            "task_type": "organ_creation",
            "user_input": "Безопасность органов",
            "lesson": "ЗАПРЕЩЕНО: eval, exec, __import__, os.system, работа с файлами без проверки. OrganGuardian сканирует все органы перед активацией"
        },
        {
            "task_type": "organ_creation",
            "user_input": "Триггеры органа", 
            "lesson": "Триггеры - ключевые слова для активации органа. CellRouter выбирает орган с максимальным совпадением триггеров с запросом пользователя"
        },
        {
            "task_type": "organ_creation",
            "user_input": "Команда создания органа",
            "lesson": "В Telegram используй #создай_орган <описание>. Пример: #создай_орган помощник по математике который решает уравнения"
        },
        {
            "task_type": "organ_creation",
            "user_input": "Жизненный цикл органа",
            "lesson": "Цикл: генерация спецификации -> код -> проверка OrganGuardian -> smoke-test -> активация. Опасные органы в карантин"
        },
        {
            "task_type": "organ_creation",
            "user_input": "Пример органа",
            "lesson": "Пример MathHelperCell: name='math_helper', system_prompt='Ты математический помощник', triggers=['посчитай','вычисли'], метод process() вызывает LLM"
        },
        {
            "task_type": "organ_creation",
            "user_input": "Типы органов",
            "lesson": "Типы: ui_code (интерфейсы), code (Python), analysis (анализ), web (поиск), memory (память), custom (любой)"
        },
    ]

    # Добавляем уроки
    added = 0
    for lesson in lessons:
        # Проверяем нет ли такого
        exists = any(
            e.get("task_type") == "organ_creation" and 
            lesson["user_input"] == e.get("user_input")
            for e in experiences
        )
        if not exists:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "task_type": lesson["task_type"],
                "user_input": lesson["user_input"],
                "verdict": "ПРИНЯТ",
                "score": 10,
                "problems": "",
                "lesson": lesson["lesson"]
            }
            experiences.append(entry)
            added += 1
            print(f"✅ Добавлен: {lesson['user_input']}")
        else:
            print(f"⏭️ Уже есть: {lesson['user_input']}")

    # Сохраняем опыт
    with open(EXPERIENCE_FILE, 'w', encoding='utf-8') as f:
        json.dump(experiences, f, ensure_ascii=False, indent=2)
    print(f"\n📚 Сохранено всего записей: {len(experiences)}")

    # Загружаем личность
    personality = {}
    if os.path.exists(PERSONALITY_FILE):
        with open(PERSONALITY_FILE, 'r', encoding='utf-8') as f:
            personality = json.load(f)

    # Добавляем инсайты об органах
    insights = personality.get("insights", [])
    new_insights = [
        "Я могу создавать новые органы для расширения возможностей",
        "Каждый орган проходит проверку безопасности OrganGuardian",
        "Хорошая JSON спецификация = хороший орган",
        "Органы активируются по триггерам - ключевым словам в запросе",
        "Перед активацией орган проходит smoke-test",
    ]
    
    for ins in new_insights:
        if ins not in insights:
            insights.append(ins)
            print(f"💡 Инсайт: {ins[:50]}...")
    
    personality["insights"] = insights
    
    # Добавляем знание о командах
    if "known_commands" not in personality:
        personality["known_commands"] = []
    
    if "#создай_орган" not in personality["known_commands"]:
        personality["known_commands"].append("#создай_орган")
        print("💡 Добавлена команда: #создай_орган")

    with open(PERSONALITY_FILE, 'w', encoding='utf-8') as f:
        json.dump(personality, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print(f"🎉 Обучение завершено!")
    print(f"   Добавлено уроков: {added}")
    print(f"   Инсайтов: {len(insights)}")
    print("=" * 50)

if __name__ == "__main__":
    train()
