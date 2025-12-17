"""
Гибридные режимы: создаёт промежуточные режимы между базовыми

Пока структура для будущего расширения.
Можно будет добавить смешивание режимов, переходные состояния.
"""
from rhythmic_modes import RhythmicMode, RHYTHMIC_MODES
from typing import Dict


class HybridModeGenerator:
    """
    Генератор гибридных ритмических режимов.
    
    Позволяет создавать промежуточные состояния между
    базовыми режимами (reflective, active, uncertain).
    """
    
    def __init__(self):
        self.base_modes = RHYTHMIC_MODES
        self.custom_modes: Dict[str, RhythmicMode] = {}
    
    def blend_modes(self, mode1_key: str, mode2_key: str, 
                   ratio: float = 0.5, name: str | None = None) -> RhythmicMode:
        """
        Создаёт гибридный режим путём смешивания двух базовых.
        
        Args:
            mode1_key: Ключ первого режима
            mode2_key: Ключ второго режима
            ratio: Пропорция смешивания (0.0 = mode1, 1.0 = mode2)
            name: Название гибридного режима
            
        Returns:
            Новый RhythmicMode
        """
        mode1 = self.base_modes[mode1_key]
        mode2 = self.base_modes[mode2_key]
        
        # Пока возвращаем доминирующий режим
        # В будущем можно добавить более сложное смешивание
        dominant = mode2 if ratio > 0.5 else mode1
        
        hybrid_name = name or f"{mode1_key}_{mode2_key}_hybrid"
        
        return RhythmicMode(
            tempo=dominant.tempo,
            rhythm=dominant.rhythm,
            tone=dominant.tone,
            breath=dominant.breath,
            metaphor=f"гибрид: {mode1.metaphor} → {mode2.metaphor}",
            max_sentence_length=int(mode1.max_sentence_length * (1-ratio) + 
                                  mode2.max_sentence_length * ratio),
            prefer_conjunctions=dominant.prefer_conjunctions,
            allow_questions=dominant.allow_questions,
            modal_words_ratio=(mode1.modal_words_ratio * (1-ratio) + 
                             mode2.modal_words_ratio * ratio)
        )
    
    def register_custom_mode(self, name: str, mode: RhythmicMode) -> None:
        """
        Регистрирует пользовательский режим.
        
        Args:
            name: Название режима
            mode: Объект RhythmicMode
        """
        self.custom_modes[name] = mode
    
    def get_all_modes(self) -> Dict[str, RhythmicMode]:
        """
        Возвращает все доступные режимы (базовые + кастомные).
        
        Returns:
            Словарь всех режимов
        """
        return {**self.base_modes, **self.custom_modes}
