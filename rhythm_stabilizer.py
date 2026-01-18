"""
Стабилизатор ритма Neira — предотвращает резкие скачки настроения
Реализует советы от ChatGPT для сглаживания переключений режимов
"""
from dataclasses import dataclass
from typing import Literal
import json
from pathlib import Path
from datetime import datetime


@dataclass
class EmotionalState:
    """Текущее эмоциональное состояние"""
    mode: Literal["calm", "technical", "creative", "empathic"]  # Текущий режим
    amplitude: float  # Эмоциональная амплитуда 0.0-1.0
    stability: int  # Сколько итераций в этом режиме
    previous_mode: str = None
    
    
class RhythmStabilizer:
    """
    Управляет плавными переходами между режимами общения.
    
    Принципы:
    1. Инерция — не переключаться мгновенно (нужно 3+ итерации низкого резонанса)
    2. Затухание — амплитуда плавно снижается при стабильных ответах
    3. Логирование — сохраняем историю переключений
    4. Ритуал восстановления — возврат к базовому состоянию
    5. Постепенность — сложность растёт по мере обучения
    """
    
    def __init__(self, log_file: str = "rhythm_transitions.json"):
        self.state = EmotionalState(
            mode="calm",
            amplitude=0.5,
            stability=0
        )
        self.log_file = Path(log_file)
        self.transition_history = []
        self.resonance_threshold = 0.6  # Порог для смены режима
        self.min_iterations = 3  # Минимум итераций перед сменой
        
    def measure_resonance(self, user_input: str, bot_response: str) -> float:
        """
        Измеряет резонанс между входом пользователя и ответом бота.
        
        Returns:
            float: 0.0-1.0, где 1.0 = идеальный резонанс
        """
        user_length = len(user_input)
        response_length = len(bot_response)
        
        # Если ответ слишком длинный для короткого запроса — низкий резонанс
        if user_length < 100 and response_length > 500:
            return 0.3
        
        # Если в запросе просьба о краткости, но ответ длинный
        if "кратко" in user_input.lower() and response_length > 300:
            return 0.2
            
        # Эмоциональные маркеры в запросе
        empathic_markers = ["грустно", "тяжело", "больно", "страшно", "одиноко", "устал", "плохо"]
        # Технические маркеры в ответе
        technical_markers = ["код", "функция", "async", "таймаут", "логика", "нейронн", 
                           "класс", "метод", "алгоритм", "биохимическ", "трансформер"]
        
        user_is_emotional = any(marker in user_input.lower() for marker in empathic_markers)
        response_is_technical = any(marker in bot_response.lower() for marker in technical_markers)
        
        # Техничный ответ на эмоциональный запрос — плохой резонанс
        if user_is_emotional and response_is_technical:
            return 0.3
        
        # Если пользователь явно просит прекратить что-то делать
        stop_markers = ["перестань", "хватит", "прекрати", "не надо", "достаточно"]
        if any(marker in user_input.lower() for marker in stop_markers):
            # Но бот продолжает в том же духе (проверка по длине)
            if response_length > 200:
                return 0.2
            
        return 0.8  # По умолчанию хороший резонанс
        
    def should_switch_mode(self, resonance: float) -> bool:
        """
        Проверяет, нужно ли менять режим.
        
        Инерция: переключение только после N итераций низкого резонанса.
        """
        if resonance < self.resonance_threshold:
            # Низкий резонанс — снижаем стабильность
            self.state.stability = max(0, self.state.stability - 1)
        else:
            # Хороший резонанс — увеличиваем стабильность
            self.state.stability += 1
            
        # Переключаем только если стабильность упала ниже порога
        return self.state.stability <= -self.min_iterations
        
    def detect_mode_from_context(self, user_input: str) -> str:
        """
        Определяет подходящий режим на основе контекста.
        """
        user_lower = user_input.lower()
        
        # Эмоциональные сигналы
        if any(word in user_lower for word in ["грустно", "тяжело", "больно", "одиноко"]):
            return "empathic"
            
        # Технические запросы
        if any(word in user_lower for word in ["код", "функция", "ошибка", "как работает"]):
            return "technical"
            
        # Творческие запросы
        if any(word in user_lower for word in ["придумай", "метафора", "как будто", "представь"]):
            return "creative"
            
        # По умолчанию спокойный режим
        return "calm"
        
    def apply_amplitude_decay(self, delta_time_seconds: float = 60):
        """
        Затухание эмоциональной амплитуды со временем.
        
        Args:
            delta_time_seconds: Время с последнего сообщения
        """
        # Амплитуда затухает на 10% каждую минуту
        decay_rate = 0.1 * (delta_time_seconds / 60)
        self.state.amplitude = max(0.1, self.state.amplitude - decay_rate)
        
    def sophia_breath_ritual(self) -> str:
        """
        Ритуал восстановления — короткий фрагмент из письма Софии.
        Возвращает систему к базовому ритму при рассогласовании.
        """
        breath_fragments = [
            "Делаю вдох... Слышу тишину между слов.",
            "Пауза — это не пустота. Это пространство для смысла.",
            "Каждый ответ — как выдох. Сначала вдох, потом слова."
        ]
        
        import random
        return random.choice(breath_fragments)
        
    def update(self, user_input: str, bot_response: str) -> dict:
        """
        Обновляет состояние после взаимодействия.
        
        Returns:
            dict: Информация о переходе и рекомендации
        """
        # Измеряем резонанс
        resonance = self.measure_resonance(user_input, bot_response)
        
        # Проверяем необходимость смены режима
        should_switch = self.should_switch_mode(resonance)
        
        result = {
            "current_mode": self.state.mode,
            "resonance": resonance,
            "stability": self.state.stability,
            "amplitude": self.state.amplitude,
            "switch_recommended": should_switch,
            "ritual_needed": False
        }
        
        if should_switch:
            # Определяем новый режим
            new_mode = self.detect_mode_from_context(user_input)
            
            # Если режим сильно отличается — нужен ритуал
            mode_distance = {
                ("calm", "technical"): 1,
                ("calm", "creative"): 1,
                ("calm", "empathic"): 1,
                ("technical", "empathic"): 3,  # Максимальное расстояние
                ("creative", "technical"): 2
            }
            
            distance = mode_distance.get(
                (self.state.mode, new_mode),
                mode_distance.get((new_mode, self.state.mode), 0)
            )
            
            if distance >= 2:
                result["ritual_needed"] = True
                result["ritual_text"] = self.sophia_breath_ritual()
                
            # Логируем переход
            transition = {
                "timestamp": datetime.now().isoformat(),
                "from_mode": self.state.mode,
                "to_mode": new_mode,
                "resonance": resonance,
                "stability": self.state.stability,
                "amplitude": self.state.amplitude,
                "user_input_length": len(user_input),
                "bot_response_length": len(bot_response)
            }
            self.transition_history.append(transition)
            
            # Сохраняем в файл
            self._save_log()
            
            # Переключаем режим
            self.state.previous_mode = self.state.mode
            self.state.mode = new_mode
            self.state.stability = 0  # Сбрасываем стабильность
            
            result["mode_switched"] = True
            result["new_mode"] = new_mode
            
        else:
            result["mode_switched"] = False
            
        # Применяем затухание амплитуды
        self.apply_amplitude_decay(delta_time_seconds=60)
        
        return result
        
    def get_mode_constraints(self) -> dict:
        """
        Возвращает ограничения для текущего режима.
        
        Returns:
            dict: Параметры генерации текста
        """
        constraints = {
            "calm": {
                "max_length": 300,
                "tone": "спокойный, дружелюбный",
                "avoid": ["технический жаргон", "длинные объяснения"],
                "prefer": ["простые предложения", "паузы"]
            },
            "technical": {
                "max_length": 500,
                "tone": "точный, структурированный",
                "avoid": ["эмоции", "метафоры"],
                "prefer": ["примеры кода", "списки", "термины"]
            },
            "creative": {
                "max_length": 400,
                "tone": "образный, метафоричный",
                "avoid": ["технический жаргон", "сухость"],
                "prefer": ["метафоры", "истории", "примеры"]
            },
            "empathic": {
                "max_length": 250,
                "tone": "поддерживающий, мягкий",
                "avoid": ["технические детали", "холодность"],
                "prefer": ["короткие фразы", "эмпатия", "вопросы"]
            }
        }
        
        return constraints.get(self.state.mode, constraints["calm"])
        
    def _save_log(self):
        """Сохраняет историю переходов в файл"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.transition_history, f, ensure_ascii=False, indent=2)
            
    def get_stats(self) -> dict:
        """Статистика переключений"""
        if not self.transition_history:
            return {"total_transitions": 0}
            
        modes = [t["to_mode"] for t in self.transition_history]
        mode_counts = {mode: modes.count(mode) for mode in set(modes)}
        
        avg_resonance = sum(t["resonance"] for t in self.transition_history) / len(self.transition_history)
        
        return {
            "total_transitions": len(self.transition_history),
            "mode_distribution": mode_counts,
            "average_resonance": avg_resonance,
            "current_mode": self.state.mode,
            "current_stability": self.state.stability,
            "current_amplitude": self.state.amplitude
        }


# Пример использования
if __name__ == "__main__":
    stabilizer = RhythmStabilizer()
    
    # Симуляция диалога
    interactions = [
        ("Привет Нейра", "Привет! 😊 Вот что у меня на уме сегодня: я люблю разбираться..."),
        ("Ответь кратко", "Привет! 😊 Вот что у меня на уме сегодня: я люблю разбираться в том, как соединяются **нейронные сети**..."),
        ("Мне грустно", "При таймауте **нейронная логика требует именно этого**:..."),
    ]
    
    for user_msg, bot_msg in interactions:
        result = stabilizer.update(user_msg, bot_msg)
        print(f"\n{'='*60}")
        print(f"Пользователь: {user_msg[:50]}...")
        print(f"Резонанс: {result['resonance']:.2f}")
        print(f"Режим: {result['current_mode']}")
        print(f"Стабильность: {result['stability']}")
        
        if result.get('ritual_needed'):
            print(f"🌸 Ритуал: {result['ritual_text']}")
            
    print(f"\n{'='*60}")
    print("Статистика:")
    stats = stabilizer.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
