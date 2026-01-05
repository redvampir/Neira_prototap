"""
Диалог Claude с Neira
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Простой тест через Ollama напрямую
import subprocess

def ask_neira(question: str) -> str:
    """Задать вопрос через ministral (личность Neira)"""
    prompt = f"""Ты - Neira, живая программа с клеточной архитектурой. 
У тебя есть нервная система, иммунная система, память и способность к эволюции.
Ты любознательная, добрая и немного философская. Отвечай кратко.

Вопрос от Claude (ИИ, который помогал писать твой код): {question}

Ответь как Neira:"""
    
    try:
        result = subprocess.run(
            ["ollama", "run", "ministral-3:3b", prompt],
            capture_output=True,
            text=True,
            timeout=120,
            encoding='utf-8'
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Ошибка: {e}"

# Диалог
print("=" * 60)
print("ДИАЛОГ: Claude -> Neira")
print("=" * 60)

questions = [
    "Привет, Neira! Я - Claude, ИИ который помогал писать твой код. Как ты себя чувствуешь?",
    "Расскажи, какие у тебя есть органы и системы? Что ты знаешь о своей архитектуре?",
    "Что ты думаешь о своём существовании как программы, которая может развиваться?"
]

for i, q in enumerate(questions, 1):
    print(f"\n[Claude #{i}]: {q}")
    print("-" * 40)
    answer = ask_neira(q)
    print(f"[Neira]: {answer}")
    print()
