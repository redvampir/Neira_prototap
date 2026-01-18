"""
Быстрый тест LLM провайдеров - проверяем доступность LM Studio / Ollama
"""
import os
import requests
import json

# === LM Studio (основной) ===
LMSTUDIO_URL = os.getenv("NEIRA_LMSTUDIO_URL", "http://localhost:1234/v1/chat/completions")
LMSTUDIO_MODEL = os.getenv("NEIRA_LMSTUDIO_MODEL", "qwen/qwen2.5-coder-14b")

# === Ollama (резервный) ===
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = os.getenv("NEIRA_OLLAMA_MODEL", "nemotron-mini")


def test_lmstudio():
    """Тест LM Studio"""
    print(f"\n🔍 Проверяю LM Studio ({LMSTUDIO_MODEL})...")
    try:
        response = requests.post(
            LMSTUDIO_URL,
            json={
                "model": LMSTUDIO_MODEL,
                "messages": [
                    {"role": "system", "content": "Ты - Нейра, живая программа."},
                    {"role": "user", "content": "Привет! Представься кратко."}
                ],
                "max_tokens": 100
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"✅ LM Studio работает!")
            print(f"📝 Ответ: {answer[:200]}")
            return True
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ LM Studio не запущена! Запусти Local Server в LM Studio")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_ollama():
    """Тест Ollama (резервный)"""
    print(f"\n🔍 Проверяю Ollama ({OLLAMA_MODEL})...")
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
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
            if answer.strip():
                print(f"✅ Ollama работает!")
                print(f"📝 Ответ: {answer[:200]}")
                return True
            else:
                print("⚠️ Пустой ответ от Ollama")
                return False
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Ollama не запущена")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


if __name__ == "__main__":
    print("=== Тест LLM провайдеров Нейры ===")
    
    lm_ok = test_lmstudio()
    ollama_ok = test_ollama()
    
    print("\n=== Итог ===")
    print(f"LM Studio: {'✅ OK' if lm_ok else '❌ Недоступна'}")
    print(f"Ollama:    {'✅ OK' if ollama_ok else '❌ Недоступна'}")
    
    if lm_ok:
        print("\n💡 Рекомендуется: LM Studio (основной провайдер)")
    elif ollama_ok:
        print("\n💡 Используется: Ollama (резервный)")
    else:
        print("\n⚠️ Ни один локальный LLM не доступен!")
