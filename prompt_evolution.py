"""
Neira Prompt Evolution System v0.6
Система эволюции system prompts через A/B тестирование и генетические операции.

ВОЗМОЖНОСТИ:
1. Версионирование промптов для каждой клетки
2. Генерация вариантов (мутации, кроссовер)
3. A/B тестирование промптов на задачах
4. Автоматический выбор лучшего промпта
5. Откат к предыдущим версиям при ухудшении
"""

import os
import json
import random
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import requests

from cells import (
    DEFAULT_MAX_RESPONSE_TOKENS,
    OLLAMA_NUM_CTX,
    OLLAMA_URL,
    MODEL_REASON,
    TIMEOUT,
    _MODEL_LAYERS,
    _merge_system_prompt,
)


# Конфигурация
PROMPTS_HISTORY_FILE = "neira_prompts_history.json"
MIN_TESTS_PER_VARIANT = 5    # Минимум тестов для оценки варианта
MUTATION_STRENGTH = 0.3       # Сила мутации (0.0-1.0)
CROSSOVER_RATE = 0.5         # Вероятность кроссовера


def _build_ollama_options(temperature: float, max_tokens: int) -> Dict[str, Any]:
    options: Dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
    if OLLAMA_NUM_CTX:
        options["num_ctx"] = OLLAMA_NUM_CTX
    if _MODEL_LAYERS is not None:
        adapter = _MODEL_LAYERS.get_active_adapter(MODEL_REASON)
        if adapter:
            options["adapter"] = adapter
    return options


def _merge_layer_system_prompt(base_prompt: str) -> str:
    if _MODEL_LAYERS is None:
        return base_prompt
    layer_prompt = _MODEL_LAYERS.get_active_prompt(MODEL_REASON)
    return _merge_system_prompt(base_prompt, layer_prompt)


@dataclass
class PromptVersion:
    """Версия промпта"""
    version_id: str
    cell_name: str
    prompt_text: str
    created_at: str
    parent_version: Optional[str] = None
    generation_method: str = "manual"  # manual, mutation, crossover

    # Метрики производительности
    tests_count: int = 0
    avg_score: float = 0.0
    success_rate: float = 0.0
    avg_confidence: float = 0.0

    active: bool = False  # Активная версия

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "PromptVersion":
        return PromptVersion(**d)


@dataclass
class PromptTest:
    """Результат теста промпта"""
    version_id: str
    task: str
    score: int
    confidence: float
    verdict: str
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


class PromptEvolutionSystem:
    """Система эволюции промптов"""

    def __init__(self):
        self.versions: Dict[str, List[PromptVersion]] = {}  # cell_name -> versions
        self.tests: List[PromptTest] = []
        self.enabled = True
        self.load_history()

    def load_history(self):
        """Загрузить историю промптов"""
        if os.path.exists(PROMPTS_HISTORY_FILE):
            try:
                with open(PROMPTS_HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)

                    # Восстанавливаем версии
                    for cell_name, versions_data in data.get("versions", {}).items():
                        self.versions[cell_name] = [
                            PromptVersion.from_dict(v) for v in versions_data
                        ]

                    print(f"🧬 Загружено версий промптов: {sum(len(v) for v in self.versions.values())}")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки истории промптов: {e}")

    def save_history(self):
        """Сохранить историю промптов"""
        try:
            data = {
                "versions": {
                    cell_name: [v.to_dict() for v in versions]
                    for cell_name, versions in self.versions.items()
                }
            }

            with open(PROMPTS_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения истории: {e}")

    def register_prompt(self, cell_name: str, prompt_text: str,
                       parent_version: Optional[str] = None,
                       generation_method: str = "manual") -> PromptVersion:
        """Зарегистрировать новую версию промпта"""

        version_id = f"{cell_name}_v{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        version = PromptVersion(
            version_id=version_id,
            cell_name=cell_name,
            prompt_text=prompt_text,
            created_at=datetime.now().isoformat(),
            parent_version=parent_version,
            generation_method=generation_method
        )

        if cell_name not in self.versions:
            self.versions[cell_name] = []

        self.versions[cell_name].append(version)
        self.save_history()

        print(f"📝 Зарегистрирована версия: {version_id}")
        return version

    def get_active_prompt(self, cell_name: str) -> Optional[PromptVersion]:
        """Получить активную версию промпта"""
        if cell_name not in self.versions:
            return None

        for version in reversed(self.versions[cell_name]):
            if version.active:
                return version

        # Если нет активной, возвращаем последнюю
        return self.versions[cell_name][-1] if self.versions[cell_name] else None

    def set_active_prompt(self, version_id: str):
        """Установить активную версию промпта"""
        for cell_name, versions in self.versions.items():
            for v in versions:
                if v.version_id == version_id:
                    # Деактивируем все предыдущие
                    for other in versions:
                        other.active = False
                    v.active = True
                    self.save_history()
                    print(f"✅ Активирована версия: {version_id}")
                    return

        print(f"⚠️ Версия не найдена: {version_id}")

    def record_test(self, version_id: str, task: str, score: int,
                   confidence: float, verdict: str):
        """Записать результат теста промпта"""

        test = PromptTest(
            version_id=version_id,
            task=task,
            score=score,
            confidence=confidence,
            verdict=verdict,
            timestamp=datetime.now().isoformat()
        )

        self.tests.append(test)

        # Обновляем метрики версии
        for versions in self.versions.values():
            for v in versions:
                if v.version_id == version_id:
                    # Пересчитываем метрики
                    version_tests = [t for t in self.tests if t.version_id == version_id]

                    v.tests_count = len(version_tests)
                    v.avg_score = sum(t.score for t in version_tests) / len(version_tests)
                    v.success_rate = sum(1 for t in version_tests if t.verdict == "ПРИНЯТ") / len(version_tests)
                    v.avg_confidence = sum(t.confidence for t in version_tests) / len(version_tests)

                    self.save_history()
                    break

    def mutate_prompt(self, base_prompt: str, strength: float = MUTATION_STRENGTH) -> str:
        """Мутация промпта (генерация варианта)"""

        mutation_types = [
            "усилить строгость",
            "добавить примеры",
            "упростить формулировки",
            "сделать более структурированным",
            "добавить проверки качества"
        ]

        mutation = random.choice(mutation_types)

        prompt = f"""Ты — эволюционер промптов.

БАЗОВЫЙ ПРОМПТ:
{base_prompt}

ЗАДАЧА: Улучши промпт через: {mutation}

ТРЕБОВАНИЯ:
- Сохрани общую цель и структуру
- Сделай изменения ({int(strength * 100)}% модификация)
- Будь конкретной, не добавляй общих фраз

УЛУЧШЕННЫЙ ПРОМПТ:"""

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_REASON,
                    "prompt": prompt,
                    "system": _merge_layer_system_prompt("Ты — редактор промптов. Выводи только текст промпта."),
                    "stream": False,
                    "options": _build_ollama_options(0.5 + strength * 0.3, min(DEFAULT_MAX_RESPONSE_TOKENS, 2048))
                },
                timeout=TIMEOUT
            )

            mutated = response.json().get("response", base_prompt)
            return mutated.strip()

        except Exception as e:
            print(f"⚠️ Ошибка мутации: {e}")
            return base_prompt

    def crossover_prompts(self, prompt_a: str, prompt_b: str) -> str:
        """Кроссовер (скрещивание) двух промптов"""

        prompt = f"""Ты — генетический оператор для промптов.

ПРОМПТ A:
{prompt_a}

ПРОМПТ B:
{prompt_b}

ЗАДАЧА: Создай гибридный промпт, взяв лучшие части из A и B.

ТРЕБОВАНИЯ:
- Объедини сильные стороны обоих
- Сохрани логичную структуру
- Убери дублирования

ГИБРИДНЫЙ ПРОМПТ:"""

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_REASON,
                    "prompt": prompt,
                    "system": _merge_layer_system_prompt("Ты — создатель гибридов. Выводи только текст промпта."),
                    "stream": False,
                    "options": _build_ollama_options(0.6, min(DEFAULT_MAX_RESPONSE_TOKENS, 2048))
                },
                timeout=TIMEOUT
            )

            hybrid = response.json().get("response", prompt_a)
            return hybrid.strip()

        except Exception as e:
            print(f"⚠️ Ошибка кроссовера: {e}")
            return prompt_a

    def evolve_prompt(self, cell_name: str) -> Optional[PromptVersion]:
        """Эволюционировать промпт для клетки"""

        if cell_name not in self.versions or not self.versions[cell_name]:
            print(f"⚠️ Нет базовой версии для {cell_name}")
            return None

        current = self.get_active_prompt(cell_name)
        if not current:
            current = self.versions[cell_name][-1]

        print(f"\n🧬 ЭВОЛЮЦИЯ ПРОМПТА: {cell_name}")
        print(f"   Базовая версия: {current.version_id}")
        print(f"   Тестов: {current.tests_count}, Средний score: {current.avg_score:.1f}")

        # Генерируем новый вариант
        method = random.choice(["mutation", "crossover"] if len(self.versions[cell_name]) > 1 else ["mutation"])

        if method == "mutation":
            new_prompt = self.mutate_prompt(current.prompt_text)
            parent_id = current.version_id
            print(f"   Метод: мутация")

        else:  # crossover
            # Выбираем другую хорошую версию
            candidates = [v for v in self.versions[cell_name]
                         if v.version_id != current.version_id and v.tests_count >= MIN_TESTS_PER_VARIANT]

            if not candidates:
                # Fallback на мутацию
                new_prompt = self.mutate_prompt(current.prompt_text)
                parent_id = current.version_id
                method = "mutation"
                print(f"   Метод: мутация (fallback)")
            else:
                other = max(candidates, key=lambda v: v.avg_score)
                new_prompt = self.crossover_prompts(current.prompt_text, other.prompt_text)
                parent_id = f"{current.version_id}+{other.version_id}"
                print(f"   Метод: кроссовер с {other.version_id}")

        # Регистрируем новую версию
        new_version = self.register_prompt(
            cell_name=cell_name,
            prompt_text=new_prompt,
            parent_version=parent_id,
            generation_method=method
        )

        print(f"   Новая версия: {new_version.version_id}")
        print(f"   Требуется {MIN_TESTS_PER_VARIANT} тестов для оценки")

        return new_version

    def should_activate_version(self, version_id: str) -> bool:
        """Определить нужно ли активировать версию"""

        for cell_name, versions in self.versions.items():
            new_version = None
            current_version = self.get_active_prompt(cell_name)

            for v in versions:
                if v.version_id == version_id:
                    new_version = v
                    break

            if new_version and new_version.tests_count >= MIN_TESTS_PER_VARIANT:
                # Сравниваем с текущей версией
                if not current_version or new_version.avg_score > current_version.avg_score:
                    print(f"🎯 Новая версия лучше!")
                    print(f"   {new_version.version_id}: {new_version.avg_score:.1f} score")
                    if current_version:
                        print(f"   vs {current_version.version_id}: {current_version.avg_score:.1f} score")
                    return True

        return False

    def auto_evolution_cycle(self, cell_names: List[str]) -> Dict[str, PromptVersion]:
        """Автоматический цикл эволюции для списка клеток"""

        print("\n" + "="*60)
        print("🧬 АВТОМАТИЧЕСКАЯ ЭВОЛЮЦИЯ ПРОМПТОВ")
        print("="*60)

        evolved = {}

        for cell_name in cell_names:
            current = self.get_active_prompt(cell_name)

            # Проверяем нужна ли эволюция
            if current and current.tests_count >= MIN_TESTS_PER_VARIANT:
                if current.avg_score < 7.5:  # Плохая производительность
                    print(f"\n🔴 {cell_name}: производительность низкая ({current.avg_score:.1f})")
                    new_version = self.evolve_prompt(cell_name)
                    if new_version:
                        evolved[cell_name] = new_version
                else:
                    print(f"\n✅ {cell_name}: производительность хорошая ({current.avg_score:.1f})")
            else:
                print(f"\n⏸️ {cell_name}: недостаточно тестов для оценки")

        return evolved

    def get_stats(self) -> Dict:
        """Статистика эволюции промптов"""
        stats = {
            "cells": len(self.versions),
            "total_versions": sum(len(v) for v in self.versions.values()),
            "total_tests": len(self.tests),
            "by_cell": {}
        }

        for cell_name, versions in self.versions.items():
            active = self.get_active_prompt(cell_name)
            stats["by_cell"][cell_name] = {
                "versions": len(versions),
                "active_version": active.version_id if active else None,
                "active_score": active.avg_score if active else 0.0,
                "active_tests": active.tests_count if active else 0
            }

        return stats

    def show_evolution_tree(self, cell_name: str) -> str:
        """Показать дерево эволюции промптов"""

        if cell_name not in self.versions:
            return f"⚠️ Нет версий для {cell_name}"

        output = f"🌳 ДЕРЕВО ЭВОЛЮЦИИ: {cell_name}\n\n"

        for i, version in enumerate(self.versions[cell_name]):
            active_mark = " 🟢 ACTIVE" if version.active else ""

            output += f"{i+1}. {version.version_id}{active_mark}\n"
            output += f"   Создана: {version.created_at[:19]}\n"
            output += f"   Метод: {version.generation_method}\n"

            if version.parent_version:
                output += f"   Родитель: {version.parent_version}\n"

            if version.tests_count > 0:
                output += f"   Тестов: {version.tests_count}\n"
                output += f"   Score: {version.avg_score:.1f}/10\n"
                output += f"   Success: {version.success_rate*100:.0f}%\n"
                output += f"   Confidence: {version.avg_confidence:.2f}\n"
            else:
                output += f"   Тестов: 0 (не протестирована)\n"

            output += "\n"

        return output

    def start_voting_session(self, cell_name: str, version_id_1: str,
                            version_id_2: str) -> Optional[Dict]:
        """Начать сессию интерактивного голосования между двумя версиями"""

        if cell_name not in self.versions:
            return None

        # Находим версии
        version_1 = next((v for v in self.versions[cell_name] if v.version_id == version_id_1), None)
        version_2 = next((v for v in self.versions[cell_name] if v.version_id == version_id_2), None)

        if not version_1 or not version_2:
            return None

        return {
            "cell_name": cell_name,
            "version_1": version_1,
            "version_2": version_2,
            "prompts": {
                version_id_1: version_1.prompt_text,
                version_id_2: version_2.prompt_text
            }
        }

    def record_voting_result(self, cell_name: str, version_id: str,
                            score: int, user_feedback: str = "") -> bool:
        """Записать результат голосования пользователя"""

        if cell_name not in self.versions:
            return False

        version = next((v for v in self.versions[cell_name] if v.version_id == version_id), None)

        if not version:
            return False

        # Записываем как тест
        test = PromptTest(
            test_id=f"vote_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            cell_name=cell_name,
            version_id=version_id,
            task_description=f"Пользовательское голосование: {user_feedback[:100]}",
            score=float(score),
            confidence=0.9,  # Высокая уверенность для ручных оценок
            success=score >= 7,
            timestamp=datetime.now().isoformat(),
            metadata={"source": "manual_voting", "feedback": user_feedback}
        )

        self.tests.append(test)

        # Обновляем метрики версии
        version_tests = [t for t in self.tests if t.version_id == version_id]
        if version_tests:
            version.tests_count = len(version_tests)
            version.avg_score = sum(t.score for t in version_tests) / len(version_tests)
            version.success_rate = sum(1 for t in version_tests if t.success) / len(version_tests)
            version.avg_confidence = sum(t.confidence for t in version_tests) / len(version_tests)

        self.save_versions()
        self.save_tests()

        return True

    def format_voting_prompt(self, session: Dict, task_description: str) -> str:
        """Форматировать промпт для интерактивного голосования"""

        output = "🗳️ ИНТЕРАКТИВНОЕ ГОЛОСОВАНИЕ ПРОМПТОВ\n\n"
        output += f"Клетка: {session['cell_name']}\n"
        output += f"Задача для тестирования: {task_description}\n\n"
        output += "="*60 + "\n"
        output += f"ВАРИАНТ A: {session['version_1'].version_id}\n"
        output += "="*60 + "\n"
        output += session['prompts'][session['version_1'].version_id] + "\n\n"
        output += "="*60 + "\n"
        output += f"ВАРИАНТ B: {session['version_2'].version_id}\n"
        output += "="*60 + "\n"
        output += session['prompts'][session['version_2'].version_id] + "\n\n"
        output += "="*60 + "\n\n"
        output += "💡 ИНСТРУКЦИИ:\n"
        output += "1. Протестируй оба варианта на задаче выше\n"
        output += "2. Оцени каждый вариант от 1 до 10\n"
        output += "3. Используй команды:\n"
        output += f"   /vote-record {session['cell_name']} {session['version_1'].version_id} <оценка> <комментарий>\n"
        output += f"   /vote-record {session['cell_name']} {session['version_2'].version_id} <оценка> <комментарий>\n"

        return output

    def show_voting_results(self, cell_name: str, version_id_1: str, version_id_2: str) -> str:
        """Показать результаты сравнения двух версий"""

        if cell_name not in self.versions:
            return f"⚠️ Нет версий для {cell_name}"

        version_1 = next((v for v in self.versions[cell_name] if v.version_id == version_id_1), None)
        version_2 = next((v for v in self.versions[cell_name] if v.version_id == version_id_2), None)

        if not version_1 or not version_2:
            return "⚠️ Одна из версий не найдена"

        output = "🗳️ РЕЗУЛЬТАТЫ СРАВНЕНИЯ\n\n"

        output += f"ВАРИАНТ A: {version_1.version_id}\n"
        output += f"  Score: {version_1.avg_score:.1f}/10\n"
        output += f"  Success rate: {version_1.success_rate*100:.0f}%\n"
        output += f"  Тестов: {version_1.tests_count}\n\n"

        output += f"ВАРИАНТ B: {version_2.version_id}\n"
        output += f"  Score: {version_2.avg_score:.1f}/10\n"
        output += f"  Success rate: {version_2.success_rate*100:.0f}%\n"
        output += f"  Тестов: {version_2.tests_count}\n\n"

        if version_1.avg_score > version_2.avg_score:
            winner = "A"
            diff = version_1.avg_score - version_2.avg_score
        elif version_2.avg_score > version_1.avg_score:
            winner = "B"
            diff = version_2.avg_score - version_1.avg_score
        else:
            winner = "Ничья"
            diff = 0.0

        output += f"🏆 ПОБЕДИТЕЛЬ: Вариант {winner}"
        if diff > 0:
            output += f" (+{diff:.1f} очков)\n"
        else:
            output += "\n"

        return output


# === ТЕСТ ===
if __name__ == "__main__":
    print("=" * 60)
    print("Тест PromptEvolutionSystem")
    print("=" * 60)

    pes = PromptEvolutionSystem()

    # Регистрируем базовый промпт
    base_prompt = """Ты — аналитик. Анализируй запросы."""

    version = pes.register_prompt("analyzer", base_prompt)
    pes.set_active_prompt(version.version_id)

    # Симулируем тесты
    for i in range(7):
        pes.record_test(version.version_id, f"task_{i}", random.randint(5, 8), 0.7, "ПРИНЯТ")

    print(pes.show_evolution_tree("analyzer"))

    # Эволюционируем
    new_version = pes.evolve_prompt("analyzer")

    print(f"\n📊 Статистика:")
    stats = pes.get_stats()
    print(json.dumps(stats, indent=2, ensure_ascii=False))
