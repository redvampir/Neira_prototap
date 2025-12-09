"""
Neira A/B Testing Framework v0.6
Фреймворк для A/B тестирования клеток, промптов и моделей.

ВОЗМОЖНОСТИ:
1. A/B тестирование двух+ вариантов
2. Сбор метрик (score, confidence, latency, success rate)
3. Статистический анализ результатов
4. Автоматическое принятие решений
5. Multi-armed bandit алгоритм для оптимизации
"""

import os
import json
import time
import random
from typing import List, Dict, Optional, Tuple, Callable, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
import statistics


# Конфигурация
AB_TESTS_FILE = "neira_ab_tests.json"
MIN_SAMPLES_PER_VARIANT = 10  # Минимум тестов для принятия решения
CONFIDENCE_THRESHOLD = 0.95   # Уровень достоверности
EPSILON_GREEDY = 0.2          # Вероятность исследования в epsilon-greedy


@dataclass
class TestSample:
    """Один тестовый запуск"""
    variant_id: str
    score: float
    confidence: float
    latency_ms: float
    success: bool
    timestamp: str
    metadata: Dict = field(default_factory=dict)


@dataclass
class Variant:
    """Вариант для тестирования"""
    variant_id: str
    name: str
    description: str
    samples: List[TestSample] = field(default_factory=list)

    # Метрики
    avg_score: float = 0.0
    avg_confidence: float = 0.0
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0
    total_samples: int = 0

    def update_metrics(self):
        """Пересчитать метрики на основе samples"""
        if not self.samples:
            return

        self.total_samples = len(self.samples)
        self.avg_score = statistics.mean(s.score for s in self.samples)
        self.avg_confidence = statistics.mean(s.confidence for s in self.samples)
        self.avg_latency_ms = statistics.mean(s.latency_ms for s in self.samples)
        self.success_rate = sum(1 for s in self.samples if s.success) / self.total_samples

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "samples": [asdict(s) for s in self.samples]
        }

    @staticmethod
    def from_dict(d: dict) -> "Variant":
        samples = [TestSample(**s) for s in d.pop("samples", [])]
        variant = Variant(**d)
        variant.samples = samples
        return variant


@dataclass
class ABTest:
    """A/B тест"""
    test_id: str
    test_name: str
    created_at: str
    status: str  # running, completed, cancelled
    variants: List[Variant] = field(default_factory=list)
    winner_variant_id: Optional[str] = None
    decision_reason: Optional[str] = None
    algorithm: str = "epsilon_greedy"  # epsilon_greedy, round_robin, ucb

    def to_dict(self) -> dict:
        data = asdict(self)
        data["variants"] = [v.to_dict() for v in self.variants]
        return data

    @staticmethod
    def from_dict(d: dict) -> "ABTest":
        variants = [Variant.from_dict(v) for v in d.pop("variants", [])]
        test = ABTest(**d)
        test.variants = variants
        return test


class ABTestingFramework:
    """Фреймворк для A/B тестирования"""

    def __init__(self):
        self.tests: Dict[str, ABTest] = {}
        self.load_tests()

    def load_tests(self):
        """Загрузить тесты из файла"""
        if os.path.exists(AB_TESTS_FILE):
            try:
                with open(AB_TESTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.tests = {
                        test_id: ABTest.from_dict(test_data)
                        for test_id, test_data in data.items()
                    }
                print(f"🧪 Загружено A/B тестов: {len(self.tests)}")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки тестов: {e}")

    def save_tests(self):
        """Сохранить тесты"""
        try:
            data = {
                test_id: test.to_dict()
                for test_id, test in self.tests.items()
            }

            with open(AB_TESTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения тестов: {e}")

    def create_test(self, test_name: str, variants: List[Tuple[str, str]],
                   algorithm: str = "epsilon_greedy") -> ABTest:
        """
        Создать новый A/B тест

        Args:
            test_name: Имя теста
            variants: [(variant_id, description), ...]
            algorithm: Алгоритм выбора варианта
        """
        test_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        test = ABTest(
            test_id=test_id,
            test_name=test_name,
            created_at=datetime.now().isoformat(),
            status="running",
            algorithm=algorithm
        )

        # Создаем варианты
        for variant_id, description in variants:
            variant = Variant(
                variant_id=variant_id,
                name=variant_id,
                description=description
            )
            test.variants.append(variant)

        self.tests[test_id] = test
        self.save_tests()

        print(f"🧪 Создан A/B тест: {test_id}")
        print(f"   Имя: {test_name}")
        print(f"   Варианты: {', '.join(v.variant_id for v in test.variants)}")
        print(f"   Алгоритм: {algorithm}")

        return test

    def select_variant(self, test_id: str) -> Optional[Variant]:
        """Выбрать вариант для следующего теста"""
        if test_id not in self.tests:
            return None

        test = self.tests[test_id]

        if test.status != "running":
            return None

        algorithm = test.algorithm

        if algorithm == "round_robin":
            return self._round_robin_select(test)
        elif algorithm == "epsilon_greedy":
            return self._epsilon_greedy_select(test)
        elif algorithm == "ucb":
            return self._ucb_select(test)
        else:
            return random.choice(test.variants)

    def _round_robin_select(self, test: ABTest) -> Variant:
        """Round-robin выбор"""
        # Выбираем вариант с минимумом тестов
        return min(test.variants, key=lambda v: v.total_samples)

    def _epsilon_greedy_select(self, test: ABTest) -> Variant:
        """Epsilon-greedy: исследование vs эксплуатация"""
        if random.random() < EPSILON_GREEDY:
            # Исследование: случайный выбор
            return random.choice(test.variants)
        else:
            # Эксплуатация: лучший по метрике
            return max(test.variants, key=lambda v: v.avg_score if v.total_samples > 0 else 0)

    def _ucb_select(self, test: ABTest) -> Variant:
        """Upper Confidence Bound"""
        import math

        total_trials = sum(v.total_samples for v in test.variants)

        if total_trials == 0:
            return random.choice(test.variants)

        def ucb_score(variant: Variant) -> float:
            if variant.total_samples == 0:
                return float('inf')

            mean_score = variant.avg_score / 10  # Нормализуем к [0, 1]
            exploration = math.sqrt(2 * math.log(total_trials) / variant.total_samples)

            return mean_score + exploration

        return max(test.variants, key=ucb_score)

    def record_result(self, test_id: str, variant_id: str,
                     score: float, confidence: float,
                     latency_ms: float, success: bool,
                     metadata: Optional[Dict] = None):
        """Записать результат теста"""
        if test_id not in self.tests:
            return

        test = self.tests[test_id]
        variant = next((v for v in test.variants if v.variant_id == variant_id), None)

        if not variant:
            return

        sample = TestSample(
            variant_id=variant_id,
            score=score,
            confidence=confidence,
            latency_ms=latency_ms,
            success=success,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {}
        )

        variant.samples.append(sample)
        variant.update_metrics()

        self.save_tests()

    def analyze_test(self, test_id: str) -> Dict:
        """Статистический анализ теста"""
        if test_id not in self.tests:
            return {}

        test = self.tests[test_id]

        # Проверяем достаточно ли данных
        min_samples_ok = all(v.total_samples >= MIN_SAMPLES_PER_VARIANT for v in test.variants)

        if not min_samples_ok:
            return {
                "ready": False,
                "reason": f"Недостаточно тестов (минимум {MIN_SAMPLES_PER_VARIANT} на вариант)"
            }

        # Находим лучший вариант по score
        best_variant = max(test.variants, key=lambda v: v.avg_score)

        # Вычисляем разницу с другими
        comparisons = []

        for variant in test.variants:
            if variant.variant_id == best_variant.variant_id:
                continue

            score_diff = best_variant.avg_score - variant.avg_score
            latency_diff = variant.avg_latency_ms - best_variant.avg_latency_ms
            success_rate_diff = best_variant.success_rate - variant.success_rate

            # Простой статистический тест (t-test упрощенный)
            significance = self._simple_significance_test(
                [s.score for s in best_variant.samples],
                [s.score for s in variant.samples]
            )

            comparisons.append({
                "variant": variant.variant_id,
                "score_diff": score_diff,
                "latency_diff_ms": latency_diff,
                "success_rate_diff": success_rate_diff,
                "significant": significance
            })

        return {
            "ready": True,
            "best_variant": best_variant.variant_id,
            "best_metrics": {
                "score": best_variant.avg_score,
                "confidence": best_variant.avg_confidence,
                "latency_ms": best_variant.avg_latency_ms,
                "success_rate": best_variant.success_rate
            },
            "comparisons": comparisons
        }

    def _simple_significance_test(self, samples_a: List[float],
                                  samples_b: List[float]) -> bool:
        """Упрощенный тест значимости различий"""
        if len(samples_a) < 3 or len(samples_b) < 3:
            return False

        mean_a = statistics.mean(samples_a)
        mean_b = statistics.mean(samples_b)
        stdev_a = statistics.stdev(samples_a)
        stdev_b = statistics.stdev(samples_b)

        # Простая эвристика: разница > 0.5 * среднее отклонение
        pooled_stdev = (stdev_a + stdev_b) / 2
        diff = abs(mean_a - mean_b)

        return diff > 0.5 * pooled_stdev

    def make_decision(self, test_id: str, auto_activate: bool = False) -> Optional[str]:
        """Принять решение о победителе"""
        analysis = self.analyze_test(test_id)

        if not analysis.get("ready"):
            print(f"⏸️ Тест не готов: {analysis.get('reason')}")
            return None

        test = self.tests[test_id]
        winner_id = analysis["best_variant"]

        # Проверяем значимость улучшений
        significant_improvements = sum(
            1 for c in analysis["comparisons"] if c["significant"] and c["score_diff"] > 0
        )

        if significant_improvements < len(test.variants) - 1:
            print(f"⚠️ Улучшения не значимы статистически")
            return None

        # Фиксируем решение
        test.winner_variant_id = winner_id
        test.status = "completed"
        test.decision_reason = f"Лучший вариант по score: {analysis['best_metrics']['score']:.2f}"

        self.save_tests()

        print(f"\n🏆 ПОБЕДИТЕЛЬ ТЕСТА {test_id}:")
        print(f"   Вариант: {winner_id}")
        print(f"   Score: {analysis['best_metrics']['score']:.2f}/10")
        print(f"   Success rate: {analysis['best_metrics']['success_rate']*100:.0f}%")
        print(f"   Latency: {analysis['best_metrics']['latency_ms']:.0f}ms")

        if auto_activate:
            print(f"\n   ✅ Автоактивация победителя")

        return winner_id

    def show_test_results(self, test_id: str) -> str:
        """Показать результаты теста"""
        if test_id not in self.tests:
            return f"⚠️ Тест не найден: {test_id}"

        test = self.tests[test_id]

        output = f"🧪 A/B ТЕСТ: {test.test_name}\n\n"
        output += f"ID: {test_id}\n"
        output += f"Статус: {test.status}\n"
        output += f"Создан: {test.created_at[:19]}\n"
        output += f"Алгоритм: {test.algorithm}\n\n"

        output += f"ВАРИАНТЫ:\n\n"

        for i, variant in enumerate(test.variants, 1):
            winner_mark = " 🏆 ПОБЕДИТЕЛЬ" if variant.variant_id == test.winner_variant_id else ""

            output += f"{i}. {variant.variant_id}{winner_mark}\n"
            output += f"   Описание: {variant.description}\n"
            output += f"   Тестов: {variant.total_samples}\n"

            if variant.total_samples > 0:
                output += f"   Score: {variant.avg_score:.2f}/10\n"
                output += f"   Confidence: {variant.avg_confidence:.2f}\n"
                output += f"   Latency: {variant.avg_latency_ms:.0f}ms\n"
                output += f"   Success rate: {variant.success_rate*100:.0f}%\n"

            output += "\n"

        if test.status == "completed" and test.decision_reason:
            output += f"РЕШЕНИЕ: {test.decision_reason}\n"

        return output

    def get_active_tests(self) -> List[ABTest]:
        """Получить активные тесты"""
        return [t for t in self.tests.values() if t.status == "running"]

    def cancel_test(self, test_id: str):
        """Отменить тест"""
        if test_id in self.tests:
            self.tests[test_id].status = "cancelled"
            self.save_tests()
            print(f"❌ Тест отменен: {test_id}")

    def get_stats(self) -> Dict:
        """Статистика"""
        return {
            "total_tests": len(self.tests),
            "running": len([t for t in self.tests.values() if t.status == "running"]),
            "completed": len([t for t in self.tests.values() if t.status == "completed"]),
            "cancelled": len([t for t in self.tests.values() if t.status == "cancelled"])
        }


# === ТЕСТ ===
if __name__ == "__main__":
    print("=" * 60)
    print("Тест ABTestingFramework")
    print("=" * 60)

    framework = ABTestingFramework()

    # Создаем тест
    test = framework.create_test(
        "Prompts comparison",
        variants=[
            ("variant_a", "Промпт версия A"),
            ("variant_b", "Промпт версия B")
        ]
    )

    # Симулируем тесты
    for i in range(15):
        variant = framework.select_variant(test.test_id)

        # Симулируем результаты (B лучше A)
        if variant.variant_id == "variant_b":
            score = random.uniform(7, 9)
            success = random.random() > 0.1
        else:
            score = random.uniform(5, 7)
            success = random.random() > 0.3

        framework.record_result(
            test.test_id,
            variant.variant_id,
            score=score,
            confidence=random.uniform(0.6, 0.9),
            latency_ms=random.uniform(100, 500),
            success=success
        )

    print(f"\n{framework.show_test_results(test.test_id)}")

    # Анализ
    winner = framework.make_decision(test.test_id)

    print(f"\n📊 Статистика:")
    print(json.dumps(framework.get_stats(), indent=2))
