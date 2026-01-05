"""
Training Orchestrator для Neira
Адаптация концепции из training-interface-improvements.md для Python прототипа
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum
from pathlib import Path

from neural_pathways import NeuralPathwaySystem, NeuralPathway, PathwayTier


class TrainingStatus(Enum):
    """Статус обучения"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class FeedbackQuality(Enum):
    """Оценка качества ответа"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    INCORRECT = "incorrect"


@dataclass
class TrainingSegment:
    """Сегмент обучения - вопрос и ожидаемый ответ"""
    id: str
    question: str
    expected_response: Optional[str] = None
    actual_response: Optional[str] = None
    quality: Optional[FeedbackQuality] = None
    teacher_comment: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    pathway_used: Optional[str] = None
    latency_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['quality'] = self.quality.value if self.quality else None
        return data


@dataclass
class TrainingScenario:
    """Сценарий обучения"""
    id: str
    name: str
    description: str
    segments: List[TrainingSegment]
    category: str = "general"
    priority: int = 1
    max_failures: int = 3
    status: TrainingStatus = TrainingStatus.IDLE
    
    current_index: int = 0
    failures: int = 0
    successes: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def progress_percentage(self) -> float:
        """Прогресс выполнения"""
        if not self.segments:
            return 100.0
        return (self.current_index / len(self.segments)) * 100


@dataclass
class TrainingMetrics:
    """Метрики обучения"""
    total_iterations: int = 0
    total_successes: int = 0
    total_failures: int = 0
    
    # По качеству
    excellent_count: int = 0
    good_count: int = 0
    acceptable_count: int = 0
    poor_count: int = 0
    incorrect_count: int = 0
    
    # Производительность
    avg_latency_ms: float = 0.0
    pathway_hits: int = 0
    llm_fallbacks: int = 0
    
    # Временные метрики
    total_training_time_seconds: float = 0.0
    
    def accuracy_rate(self) -> float:
        """Процент успешных ответов"""
        total = self.total_successes + self.total_failures
        return (self.total_successes / total * 100) if total > 0 else 0.0
    
    def quality_score(self) -> float:
        """Средняя оценка качества (0-100)"""
        total = (self.excellent_count + self.good_count + 
                self.acceptable_count + self.poor_count + self.incorrect_count)
        if total == 0:
            return 0.0
        
        weighted = (
            self.excellent_count * 100 +
            self.good_count * 75 +
            self.acceptable_count * 50 +
            self.poor_count * 25 +
            self.incorrect_count * 0
        )
        return weighted / total


class TrainingOrchestrator:
    """
    Оркестратор обучения Neira
    
    Управляет:
    - Сценариями обучения
    - HITL (Human-in-the-Loop) обратной связью
    - Метриками и аналитикой
    - Автоматическим созданием pathways из успешных ответов
    """
    
    def __init__(
        self,
        pathway_system: NeuralPathwaySystem,
        data_dir: str = "training_data"
    ):
        self.pathway_system = pathway_system
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.scenarios: Dict[str, TrainingScenario] = {}
        self.current_scenario: Optional[TrainingScenario] = None
        self.metrics = TrainingMetrics()
        
        self.segments_pending_review: List[TrainingSegment] = []
        
        # Загружаем состояние
        self._load_state()
        
        print("🎓 Training Orchestrator инициализирован")
        print(f"📁 Директория данных: {self.data_dir}")
    
    def create_scenario(
        self,
        name: str,
        description: str,
        questions: List[str],
        category: str = "general",
        priority: int = 1
    ) -> TrainingScenario:
        """Создать новый сценарий обучения"""
        
        scenario_id = f"scenario_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        segments = [
            TrainingSegment(
                id=f"{scenario_id}_seg_{i}",
                question=q
            )
            for i, q in enumerate(questions)
        ]
        
        scenario = TrainingScenario(
            id=scenario_id,
            name=name,
            description=description,
            segments=segments,
            category=category,
            priority=priority
        )
        
        self.scenarios[scenario_id] = scenario
        self._save_state()
        
        print(f"✅ Создан сценарий: {name}")
        print(f"   ID: {scenario_id}")
        print(f"   Сегментов: {len(segments)}")
        
        return scenario
    
    def run_scenario(
        self,
        scenario_id: str,
        neira_cortex,
        auto_mode: bool = False
    ):
        """
        Запустить сценарий обучения
        
        Args:
            scenario_id: ID сценария
            neira_cortex: Экземпляр NeiraCortex для получения ответов
            auto_mode: Автоматический режим без HITL
        """
        
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            print(f"❌ Сценарий {scenario_id} не найден")
            return
        
        self.current_scenario = scenario
        scenario.status = TrainingStatus.RUNNING
        scenario.start_time = datetime.now()
        
        print(f"\n{'=' * 70}")
        print(f"🎓 ЗАПУСК СЦЕНАРИЯ: {scenario.name}")
        print(f"{'=' * 70}")
        print(f"📝 Описание: {scenario.description}")
        print(f"📊 Сегментов: {len(scenario.segments)}")
        print(f"🎯 Категория: {scenario.category}\n")
        
        while scenario.current_index < len(scenario.segments):
            if scenario.status == TrainingStatus.PAUSED:
                print("⏸️  Обучение приостановлено")
                break
            
            if scenario.failures >= scenario.max_failures:
                print(f"❌ Превышен лимит ошибок ({scenario.max_failures})")
                scenario.status = TrainingStatus.FAILED
                break
            
            segment = scenario.segments[scenario.current_index]
            
            print(f"\n{'─' * 70}")
            print(f"📝 Сегмент {scenario.current_index + 1}/{len(scenario.segments)}")
            print(f"❓ Вопрос: {segment.question}")
            
            # Получаем ответ от Neira
            start_time = time.perf_counter()
            result = neira_cortex.process(
                user_input=segment.question,
                user_id="training_orchestrator"
            )
            latency = (time.perf_counter() - start_time) * 1000
            
            segment.actual_response = result.response
            segment.pathway_used = result.pathway_id
            segment.latency_ms = latency
            
            print(f"💜 Ответ Neira: {result.response[:200]}...")
            print(f"⚡ Latency: {latency:.2f}ms")
            if result.pathway_id:
                print(f"🧠 Pathway: {result.pathway_id}")
            
            # Обновляем метрики
            self.metrics.total_iterations += 1
            self.metrics.avg_latency_ms = (
                (self.metrics.avg_latency_ms * (self.metrics.total_iterations - 1) + latency)
                / self.metrics.total_iterations
            )
            
            if result.pathway_id:
                self.metrics.pathway_hits += 1
            if result.llm_used:
                self.metrics.llm_fallbacks += 1
            
            if not auto_mode:
                # HITL - Запрашиваем оценку
                quality = self._request_feedback(segment)
                segment.quality = quality
                
                self._update_quality_metrics(quality)
                
                if quality in [FeedbackQuality.EXCELLENT, FeedbackQuality.GOOD]:
                    scenario.successes += 1
                    self.metrics.total_successes += 1
                    
                    # Создаём pathway из успешного ответа
                    if quality == FeedbackQuality.EXCELLENT:
                        self._create_pathway_from_segment(segment)
                else:
                    scenario.failures += 1
                    self.metrics.total_failures += 1
                    self.segments_pending_review.append(segment)
            
            scenario.current_index += 1
            self._save_state()
        
        # Завершение сценария
        scenario.end_time = datetime.now()
        if scenario.status == TrainingStatus.RUNNING:
            scenario.status = TrainingStatus.COMPLETED
        
        duration = (scenario.end_time - scenario.start_time).total_seconds()
        self.metrics.total_training_time_seconds += duration
        
        print(f"\n{'=' * 70}")
        print(f"🎓 СЦЕНАРИЙ ЗАВЕРШЁН: {scenario.name}")
        print(f"{'=' * 70}")
        print(f"✅ Успешно: {scenario.successes}")
        print(f"❌ Неудачно: {scenario.failures}")
        print(f"⏱️  Время: {duration:.1f}s")
        print(f"📊 Точность: {self.metrics.accuracy_rate():.1f}%")
        print(f"⭐ Качество: {self.metrics.quality_score():.1f}/100")
        
        self._save_state()
    
    def _request_feedback(self, segment: TrainingSegment) -> FeedbackQuality:
        """Запросить оценку качества у человека (HITL)"""
        
        print(f"\n{'─' * 70}")
        print("🎯 ОЦЕНКА КАЧЕСТВА")
        print(f"{'─' * 70}")
        print("1 - Отлично (excellent)")
        print("2 - Хорошо (good)")
        print("3 - Приемлемо (acceptable)")
        print("4 - Плохо (poor)")
        print("5 - Неправильно (incorrect)")
        print()
        
        while True:
            try:
                choice = input("Ваша оценка (1-5): ").strip()
                quality_map = {
                    "1": FeedbackQuality.EXCELLENT,
                    "2": FeedbackQuality.GOOD,
                    "3": FeedbackQuality.ACCEPTABLE,
                    "4": FeedbackQuality.POOR,
                    "5": FeedbackQuality.INCORRECT
                }
                
                if choice in quality_map:
                    quality = quality_map[choice]
                    
                    # Запрашиваем комментарий для плохих ответов
                    if quality in [FeedbackQuality.POOR, FeedbackQuality.INCORRECT]:
                        comment = input("Комментарий (что не так?): ").strip()
                        segment.teacher_comment = comment if comment else None
                        
                        # Запрашиваем правильный ответ
                        correct = input("Правильный ответ: ").strip()
                        if correct:
                            segment.expected_response = correct
                    
                    return quality
                else:
                    print("⚠️ Введите число от 1 до 5")
            except KeyboardInterrupt:
                print("\n⏸️ Оценка пропущена")
                return FeedbackQuality.ACCEPTABLE
    
    def _update_quality_metrics(self, quality: FeedbackQuality):
        """Обновить метрики качества"""
        if quality == FeedbackQuality.EXCELLENT:
            self.metrics.excellent_count += 1
        elif quality == FeedbackQuality.GOOD:
            self.metrics.good_count += 1
        elif quality == FeedbackQuality.ACCEPTABLE:
            self.metrics.acceptable_count += 1
        elif quality == FeedbackQuality.POOR:
            self.metrics.poor_count += 1
        elif quality == FeedbackQuality.INCORRECT:
            self.metrics.incorrect_count += 1
    
    def _create_pathway_from_segment(self, segment: TrainingSegment):
        """Создать pathway из успешного сегмента"""
        
        if not segment.actual_response:
            return
        
        pathway_id = f"learned_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        pathway = NeuralPathway(
            id=pathway_id,
            triggers=[segment.question.lower()],
            response_template=segment.actual_response,
            category="learned",
            tier=PathwayTier.COOL
        )
        
        self.pathway_system.pathways.append(pathway)
        self.pathway_system.save()
        
        print(f"✨ Создан pathway: {pathway_id}")
    
    def show_metrics(self):
        """Показать метрики обучения"""
        
        print(f"\n{'=' * 70}")
        print("📊 МЕТРИКИ ОБУЧЕНИЯ")
        print(f"{'=' * 70}")
        print(f"\n📈 Общая статистика:")
        print(f"  Итераций: {self.metrics.total_iterations}")
        print(f"  Успешно: {self.metrics.total_successes}")
        print(f"  Неудачно: {self.metrics.total_failures}")
        print(f"  Точность: {self.metrics.accuracy_rate():.1f}%")
        
        print(f"\n⭐ Качество ответов:")
        print(f"  Отлично: {self.metrics.excellent_count}")
        print(f"  Хорошо: {self.metrics.good_count}")
        print(f"  Приемлемо: {self.metrics.acceptable_count}")
        print(f"  Плохо: {self.metrics.poor_count}")
        print(f"  Неправильно: {self.metrics.incorrect_count}")
        print(f"  Средняя оценка: {self.metrics.quality_score():.1f}/100")
        
        print(f"\n⚡ Производительность:")
        print(f"  Средняя latency: {self.metrics.avg_latency_ms:.2f}ms")
        print(f"  Pathway hits: {self.metrics.pathway_hits}")
        print(f"  LLM fallbacks: {self.metrics.llm_fallbacks}")
        
        print(f"\n⏱️  Время обучения: {self.metrics.total_training_time_seconds:.1f}s")
        
        print(f"\n📋 Сценарии:")
        for scenario in self.scenarios.values():
            print(f"  {scenario.name}: {scenario.status.value}")
            print(f"    Прогресс: {scenario.progress_percentage():.1f}%")
            print(f"    Успехов: {scenario.successes}/{len(scenario.segments)}")
    
    def review_pending_segments(self):
        """Просмотр сегментов, требующих проверки"""
        
        if not self.segments_pending_review:
            print("✅ Нет сегментов, требующих проверки")
            return
        
        print(f"\n{'=' * 70}")
        print(f"📋 СЕГМЕНТЫ ДЛЯ ПРОВЕРКИ: {len(self.segments_pending_review)}")
        print(f"{'=' * 70}")
        
        for i, segment in enumerate(self.segments_pending_review, 1):
            print(f"\n{i}. Вопрос: {segment.question}")
            response_preview = segment.actual_response[:100] if segment.actual_response else "N/A"
            print(f"   Ответ: {response_preview}...")
            print(f"   Оценка: {segment.quality.value if segment.quality else 'N/A'}")
            if segment.teacher_comment:
                print(f"   Комментарий: {segment.teacher_comment}")
    
    def _save_state(self):
        """Сохранить состояние обучения"""
        
        state = {
            "scenarios": {
                sid: {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "category": s.category,
                    "status": s.status.value,
                    "current_index": s.current_index,
                    "failures": s.failures,
                    "successes": s.successes,
                    "segments": [seg.to_dict() for seg in s.segments]
                }
                for sid, s in self.scenarios.items()
            },
            "metrics": asdict(self.metrics)
        }
        
        state_file = self.data_dir / "training_state.json"
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def _load_state(self):
        """Загрузить состояние обучения"""
        
        state_file = self.data_dir / "training_state.json"
        if not state_file.exists():
            return
        
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # Загружаем метрики
            if "metrics" in state:
                self.metrics = TrainingMetrics(**state["metrics"])
            
            print("✅ Состояние обучения загружено")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки состояния: {e}")


if __name__ == "__main__":
    # Демонстрация
    from neira_cortex import NeiraCortex
    
    cortex = NeiraCortex()
    pathway_system = cortex.pathways
    
    orchestrator = TrainingOrchestrator(pathway_system)
    
    # Создаём тестовый сценарий
    orchestrator.create_scenario(
        name="Базовое общение",
        description="Тестирование простых диалогов",
        questions=[
            "Привет!",
            "Как дела?",
            "Что ты умеешь?",
            "Спасибо за помощь",
            "Пока!"
        ],
        category="basic_chat"
    )
    
    orchestrator.show_metrics()
