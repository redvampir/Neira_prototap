#!/usr/bin/env python3
"""
Скачивание NVIDIA Nemotron Nano 9B v2 в формате GGUF
"""

from huggingface_hub import hf_hub_download
import os

def download_nemotron():
    """Скачать модель Nemotron с HuggingFace"""
    
    print("🚀 Скачивание NVIDIA Nemotron Nano 9B v2 (Q4_K_M квантизация)")
    print("Размер: ~5.5 GB")
    print()
    
    repo_id = "MaziyarPanahi/NVIDIA-Nemotron-Nano-9B-v2-GGUF"
    filename = "NVIDIA-Nemotron-Nano-9B-v2.Q4_K_M.gguf"
    local_dir = "models/nemotron9b"
    
    # Создаём директорию если не существует
    os.makedirs(local_dir, exist_ok=True)
    
    try:
        print(f"📥 Скачивание из {repo_id}...")
        file_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=local_dir
        )
        
        print(f"\n✅ Успешно скачано в: {file_path}")
        print()
        print("Следующий шаг: Импорт в Ollama")
        print("1. Создай Modelfile:")
        print(f'   FROM {file_path}')
        print()
        print("2. Импортируй модель:")
        print("   ollama create nemotron-mini -f Modelfile")
        
        return file_path
        
    except Exception as e:
        print(f"\n❌ Ошибка скачивания: {e}")
        return None


if __name__ == "__main__":
    download_nemotron()
