"""
Спектр личности: фиксирует диапазон черт личности
"""
from dataclasses import dataclass
from typing import Dict


@dataclass
class PersonalitySpectrum:
    """
    Определяет диапазон возможных состояний личности.
    
    Каждая черта имеет нижнюю и верхнюю границу,
    а также текущее состояние.
    """
    lower_bound: Dict[str, float]
    upper_bound: Dict[str, float]
    current_state: Dict[str, float]
    
    def is_within_bounds(self, trait: str, value: float) -> bool:
        """
        Проверяет, находится ли значение в допустимых границах.
        
        Args:
            trait: Название черты
            value: Проверяемое значение
            
        Returns:
            True если значение в границах, иначе False
        """
        if trait not in self.lower_bound or trait not in self.upper_bound:
            return False
        
        return self.lower_bound[trait] <= value <= self.upper_bound[trait]
    
    def update_state(self, trait: str, value: float) -> bool:
        """
        Обновляет текущее состояние черты, если значение в границах.
        
        Args:
            trait: Название черты
            value: Новое значение
            
        Returns:
            True если обновление прошло успешно, иначе False
        """
        if self.is_within_bounds(trait, value):
            self.current_state[trait] = value
            return True
        return False
    
    def get_distance_from_center(self, trait: str) -> float:
        """
        Вычисляет расстояние текущего значения от центра диапазона.
        
        Args:
            trait: Название черты
            
        Returns:
            Нормализованное расстояние от центра (-1.0 до 1.0)
        """
        if trait not in self.current_state:
            return 0.0
        
        center = (self.lower_bound[trait] + self.upper_bound[trait]) / 2
        half_range = (self.upper_bound[trait] - self.lower_bound[trait]) / 2
        
        if half_range == 0:
            return 0.0
        
        return (self.current_state[trait] - center) / half_range


def create_default_spectrum() -> PersonalitySpectrum:
    """
    Создаёт спектр личности с базовыми настройками.
    
    Returns:
        PersonalitySpectrum с начальными значениями
    """
    traits = ["reflective", "active", "uncertain"]
    
    return PersonalitySpectrum(
        lower_bound={t: 0.3 for t in traits},
        upper_bound={t: 1.0 for t in traits},
        current_state={t: 0.6 for t in traits}
    )
