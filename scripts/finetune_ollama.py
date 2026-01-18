"""
Скрипт для fine-tuning модели Ollama на Cell Router логике

Процесс:
1. Конвертация JSONL датасета в формат Ollama
2. Создание fine-tuned модели через Modelfile
3. Тестирование новой модели
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict


class OllamaFineTuner:
    def __init__(self, base_model: str = "ministral-3:3b"):
        self.base_model = base_model
        self.project_root = Path(__file__).parent
        dataset_override = os.getenv("NEIRA_TRAINING_DATASET")
        modelfile_override = os.getenv("NEIRA_TRAINING_MODELFILE")
        name_override = os.getenv("NEIRA_TRAINING_MODEL_NAME")
        self.dataset_file = Path(dataset_override) if dataset_override else (self.project_root / "training_dataset.jsonl")
        self.modelfile = Path(modelfile_override) if modelfile_override else (self.project_root / "Modelfile")
        self.new_model_name = name_override or "neira-cell-router:latest"
    
    def check_ollama(self) -> bool:
        """Проверить что Ollama установлен и работает."""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            print("✅ Ollama найден")
            print(f"Доступные модели:\n{result.stdout}")
            return True
        except FileNotFoundError:
            print("❌ Ollama не найден. Установите: https://ollama.ai")
            return False
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка при запуске Ollama: {e}")
            return False
    
    def check_base_model(self) -> bool:
        """Проверить что базовая модель скачана."""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            
            if self.base_model in result.stdout:
                print(f"✅ Базовая модель {self.base_model} найдена")
                return True
            else:
                print(f"⚠️ Модель {self.base_model} не найдена")
                print(f"Скачиваю: ollama pull {self.base_model}")
                
                subprocess.run(
                    ["ollama", "pull", self.base_model],
                    check=True
                )
                print(f"✅ Модель {self.base_model} скачана")
                return True
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка при проверке модели: {e}")
            return False
    
    def load_dataset(self) -> List[Dict[str, str]]:
        """Загрузить training датасет."""
        if not self.dataset_file.exists():
            print(f"❌ Датасет не найден: {self.dataset_file}")
            return []
        
        dataset = []
        with open(self.dataset_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    dataset.append(json.loads(line))
        
        print(f"✅ Загружено примеров: {len(dataset)}")
        return dataset
    
    def validate_dataset(self, dataset: List[Dict[str, str]]) -> bool:
        """Валидация датасета."""
        if not dataset:
            print("❌ Датасет пустой")
            return False
        
        required_keys = {"prompt", "completion"}
        for i, example in enumerate(dataset):
            if not required_keys.issubset(example.keys()):
                print(f"❌ Пример {i} не содержит {required_keys}")
                return False
        
        print(f"✅ Датасет валидный ({len(dataset)} примеров)")
        return True
    
    def create_model(self) -> bool:
        """Создать fine-tuned модель через Modelfile."""
        if not self.modelfile.exists():
            print(f"❌ Modelfile не найден: {self.modelfile}")
            return False
        
        print(f"\n🚀 Создаю модель {self.new_model_name}...")
        print(f"   Базовая модель: {self.base_model}")
        print(f"   Modelfile: {self.modelfile}")
        
        try:
            # Ollama create читает Modelfile из текущей директории
            subprocess.run(
                ["ollama", "create", self.new_model_name, "-f", str(self.modelfile)],
                cwd=self.project_root,
                check=True
            )
            
            print(f"✅ Модель {self.new_model_name} создана!")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка при создании модели: {e}")
            return False
    
    def test_model(self):
        """Протестировать новую модель."""
        print(f"\n🧪 Тестирую модель {self.new_model_name}...\n")
        
        test_prompts = [
            "Создай интерфейс для игры в крестики-нолики",
            "Напиши функцию для сортировки массива",
            "Проанализируй код в файле main.py"
        ]
        
        for prompt in test_prompts:
            print(f"\n📝 Промпт: {prompt}")
            print("-" * 60)
            
            try:
                result = subprocess.run(
                    ["ollama", "run", self.new_model_name, prompt],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                response = result.stdout.strip()
                print(f"🤖 Ответ: {response[:500]}...")
                
            except subprocess.TimeoutExpired:
                print("⏱️ Timeout (30s)")
            except Exception as e:
                print(f"❌ Ошибка: {e}")
    
    def run(self):
        """Запустить полный процесс fine-tuning."""
        print("=" * 70)
        print("🧠 OLLAMA FINE-TUNING: Neira Cell Router")
        print("=" * 70)
        print()
        
        # 1. Проверки
        if not self.check_ollama():
            return
        
        if not self.check_base_model():
            return
        
        # 2. Датасет
        dataset = self.load_dataset()
        if not self.validate_dataset(dataset):
            return
        
        # 3. Создание модели
        print("\n" + "=" * 70)
        print("ВАЖНО: Ollama в данный момент не поддерживает прямой fine-tuning")
        print("Вместо этого мы создаём модель с расширенным system prompt")
        print("=" * 70)
        
        if not self.create_model():
            return
        
        # 4. Тестирование
        self.test_model()
        
        print("\n" + "=" * 70)
        print("✅ ПРОЦЕСС ЗАВЕРШЁН")
        print("=" * 70)
        print(f"\n📋 Следующие шаги:")
        print(f"1. Протестируйте модель: ollama run {self.new_model_name}")
        print(f"2. Интегрируйте в Neira: измените OLLAMA_MODEL в neira_config.py")
        print(f"3. Перезапустите backend: python -m backend.api")
        print()


if __name__ == "__main__":
    tuner = OllamaFineTuner()
    tuner.run()
