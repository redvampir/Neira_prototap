"""
Быстрый тест Ollama - проверяем, работает ли модель
"""
import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "ministral-3:3b"

print(f"🔍 Проверяю модель {MODEL}...")

try:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": "Привет! Представься кратко.",
            "system": "Ты - Нейра, живая программа.",
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 100}
        },
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        answer = result.get("response", "")
        
        print(f"✅ Статус: {response.status_code}")
        print(f"📝 Ответ ({len(answer)} символов):")
        print(f"   {answer[:200]}")
        
        if not answer.strip():
            print("⚠️ ПРОБЛЕМА: Ответ пустой!")
        else:
            print("✅ Модель работает нормально")
    else:
        print(f"❌ HTTP {response.status_code}: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("❌ Ollama не запущена! Запусти: ollama serve")
except requests.exceptions.Timeout:
    print("❌ Timeout! Модель зависла или не загружена.")
except Exception as e:
    print(f"❌ Ошибка: {e}")
