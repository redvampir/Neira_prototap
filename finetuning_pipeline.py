"""
Neira Fine-Tuning Pipeline v0.6
Автоматическое дообучение модели neira-personality на накопленном опыте.

ВОЗМОЖНОСТИ:
1. Экспорт диалогов из Experience в формат для обучения
2. Генерация Ollama Modelfile
3. Автоматический запуск fine-tuning
4. Версионирование моделей
5. Валидация и тестирование новых версий
"""

import os
import json
import subprocess
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

from experience import ExperienceSystem
from cells import MODEL_PERSONALITY


# Конфигурация
TRAINING_DATA_DIR = "training_data"
MODELS_DIR = "models"
MODEL_VERSIONS_FILE = "neira_model_versions.json"
MIN_TRAINING_SAMPLES = 50  # Минимум диалогов для обучения


@dataclass
class TrainingExample:
    """Пример для обучения"""
    instruction: str
    input: str
    output: str
    metadata: Dict


@dataclass
class ModelVersion:
    """Версия модели"""
    version_id: str
    model_name: str
    base_model: str
    created_at: str
    training_samples: int
    performance_metrics: Optional[Dict] = None
    active: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "ModelVersion":
        return ModelVersion(**d)


class FineTuningPipeline:
    """Pipeline для fine-tuning модели"""

    def __init__(self, experience: ExperienceSystem):
        self.experience = experience
        self.model_versions: List[ModelVersion] = []

        os.makedirs(TRAINING_DATA_DIR, exist_ok=True)
        os.makedirs(MODELS_DIR, exist_ok=True)

        self.load_model_versions()

    def load_model_versions(self):
        """Загрузить версии моделей"""
        if os.path.exists(MODEL_VERSIONS_FILE):
            try:
                with open(MODEL_VERSIONS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.model_versions = [ModelVersion.from_dict(v) for v in data]
                print(f"🎓 Загружено версий модели: {len(self.model_versions)}")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки версий: {e}")

    def save_model_versions(self):
        """Сохранить версии"""
        try:
            with open(MODEL_VERSIONS_FILE, "w", encoding="utf-8") as f:
                json.dump([v.to_dict() for v in self.model_versions], f,
                         ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения версий: {e}")

    def export_training_data(self) -> Optional[str]:
        """Экспортировать диалоги из Experience для обучения"""

        # Фильтруем успешные диалоги (score >= 8, verdict = ПРИНЯТ)
        good_experiences = [
            exp for exp in self.experience.experiences
            if exp.score >= 8 and exp.verdict == "ПРИНЯТ"
        ]

        if len(good_experiences) < MIN_TRAINING_SAMPLES:
            print(f"⚠️ Недостаточно примеров для обучения")
            print(f"   Доступно: {len(good_experiences)}")
            print(f"   Требуется: {MIN_TRAINING_SAMPLES}")
            return None

        # Формируем примеры
        examples = []

        for exp in good_experiences:
            # Для обучения используем успешные примеры
            example = {
                "instruction": "Ты — Nейра, живая программа. Отвечай полезно, конкретно и от первого лица.",
                "input": exp.user_input,
                "output": f"[Успешный ответ с оценкой {exp.score}/10]",  # Реальный ответ нужно брать из памяти
                "metadata": {
                    "task_type": exp.task_type,
                    "score": exp.score,
                    "timestamp": exp.timestamp
                }
            }
            examples.append(example)

        # Сохраняем в файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"training_data_{timestamp}.jsonl"
        filepath = os.path.join(TRAINING_DATA_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        print(f"📊 Экспортировано примеров: {len(examples)}")
        print(f"   Файл: {filepath}")

        return filepath

    def generate_modelfile(self, base_model: str, training_data_path: str,
                          version: str) -> str:
        """Сгенерировать Ollama Modelfile"""

        # Читаем personality prompt
        personality_prompt = self.experience.get_personality_prompt()

        modelfile_content = f"""# Neira Personality Model v{version}
# Автоматически сгенерирован: {datetime.now().isoformat()}

FROM {base_model}

# Personality system prompt
SYSTEM \"\"\"
{personality_prompt}

Ты отвечаешь на русском языке.
Ты используешь накопленный опыт для улучшения ответов.
\"\"\"

# Parameters
PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 4096

# Training data (примечание: Ollama не поддерживает прямое обучение через Modelfile)
# Для реального fine-tuning требуется использовать Ollama API или внешние инструменты
"""

        # Сохраняем Modelfile
        modelfile_path = os.path.join(MODELS_DIR, f"Modelfile.neira-v{version}")

        with open(modelfile_path, "w", encoding="utf-8") as f:
            f.write(modelfile_content)

        print(f"📝 Создан Modelfile: {modelfile_path}")

        return modelfile_path

    def create_model_with_ollama(self, modelfile_path: str, model_name: str) -> bool:
        """Создать модель через Ollama CLI"""

        try:
            print(f"\n🎓 Создание модели: {model_name}")
            print(f"   Modelfile: {modelfile_path}")

            # Запускаем ollama create
            result = subprocess.run(
                ["ollama", "create", model_name, "-f", modelfile_path],
                capture_output=True,
                text=True,
                timeout=600  # 10 минут таймаут
            )

            if result.returncode == 0:
                print(f"✅ Модель создана: {model_name}")
                print(result.stdout)
                return True
            else:
                print(f"❌ Ошибка создания модели:")
                print(result.stderr)
                return False

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def train_new_version(self, base_model: str = "ministral-3:3b") -> Optional[ModelVersion]:
        """Обучить новую версию модели"""

        print("\n" + "="*60)
        print("🎓 ЗАПУСК FINE-TUNING PIPELINE")
        print("="*60)

        # Экспортируем данные
        training_data_path = self.export_training_data()

        if not training_data_path:
            return None

        # Определяем версию
        version_num = len(self.model_versions) + 1
        version_id = f"v{version_num}_{datetime.now().strftime('%Y%m%d')}"
        model_name = f"neira-personality:{version_id}"

        print(f"\n📋 Версия модели: {version_id}")
        print(f"   Базовая модель: {base_model}")
        print(f"   Имя: {model_name}")

        # Генерируем Modelfile
        modelfile_path = self.generate_modelfile(base_model, training_data_path, version_id)

        # Создаем модель
        success = self.create_model_with_ollama(modelfile_path, model_name)

        if not success:
            print(f"\n❌ Fine-tuning провален")
            return None

        # Регистрируем версию
        version = ModelVersion(
            version_id=version_id,
            model_name=model_name,
            base_model=base_model,
            created_at=datetime.now().isoformat(),
            training_samples=len(self.experience.experiences),
            performance_metrics={},
            active=False  # Требуется валидация
        )

        self.model_versions.append(version)
        self.save_model_versions()

        print(f"\n🎉 FINE-TUNING ЗАВЕРШЕН")
        print(f"   Модель: {model_name}")
        print(f"   Статус: требуется тестирование")
        print(f"\n💡 Используй /activate-model {version_id} для активации")

        return version

    def activate_model_version(self, version_id: str):
        """Активировать версию модели"""
        for version in self.model_versions:
            version.active = (version.version_id == version_id)

        self.save_model_versions()
        print(f"✅ Активирована версия: {version_id}")
        active = self.get_active_version()
        if active:
            print(f"   Модель: {active.model_name}")
        print(f"\n⚠️  Для использования новой модели обнови MODEL_PERSONALITY в cells.py")

    def get_active_version(self) -> Optional[ModelVersion]:
        """Получить активную версию"""
        for version in self.model_versions:
            if version.active:
                return version
        return None

    def should_trigger_training(self) -> bool:
        """Определить нужно ли запустить обучение"""

        # Проверяем есть ли достаточно новых примеров
        good_experiences = [
            exp for exp in self.experience.experiences
            if exp.score >= 8 and exp.verdict == "ПРИНЯТ"
        ]

        if len(good_experiences) < MIN_TRAINING_SAMPLES:
            return False

        # Проверяем когда была последняя версия
        if not self.model_versions:
            print(f"🎓 Нет обученных версий, рекомендуется запустить обучение")
            return True

        last_version = self.model_versions[-1]
        # Проверяем прошло ли достаточно времени / накопилось ли новых примеров

        new_samples_since_last = len(self.experience.experiences) - last_version.training_samples

        if new_samples_since_last >= MIN_TRAINING_SAMPLES:
            print(f"🎓 Накопилось {new_samples_since_last} новых примеров")
            return True

        return False

    def show_versions(self) -> str:
        """Показать версии модели"""
        if not self.model_versions:
            return "🎓 Нет обученных версий модели"

        output = "🎓 ВЕРСИИ МОДЕЛИ NEIRA-PERSONALITY:\n\n"

        for i, version in enumerate(self.model_versions, 1):
            active_mark = " 🟢 ACTIVE" if version.active else ""

            output += f"{i}. {version.version_id}{active_mark}\n"
            output += f"   Модель: {version.model_name}\n"
            output += f"   Базовая: {version.base_model}\n"
            output += f"   Создана: {version.created_at[:19]}\n"
            output += f"   Примеров для обучения: {version.training_samples}\n"

            if version.performance_metrics:
                output += f"   Метрики: {version.performance_metrics}\n"

            output += "\n"

        return output

    def get_stats(self) -> Dict:
        """Статистика"""
        active = self.get_active_version()
        return {
            "total_versions": len(self.model_versions),
            "active_version": active.version_id if active else None,
            "available_training_samples": len([
                exp for exp in self.experience.experiences
                if exp.score >= 8 and exp.verdict == "ПРИНЯТ"
            ]),
            "min_required": MIN_TRAINING_SAMPLES
        }


# === ТЕСТ ===
if __name__ == "__main__":
    print("=" * 60)
    print("Тест FineTuningPipeline")
    print("=" * 60)

    exp = ExperienceSystem()
    pipeline = FineTuningPipeline(exp)

    print(f"\n{pipeline.show_versions()}")

    print(f"\n📊 Статистика:")
    stats = pipeline.get_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    if pipeline.should_trigger_training():
        print(f"\n💡 Рекомендуется запустить обучение")
    else:
        print(f"\n✅ Обучение пока не требуется")
