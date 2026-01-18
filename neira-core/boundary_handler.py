"""
Обработчик границ: признание пределов возможностей системы

Структура для будущего расширения.
Будет отслеживать ситуации, когда система достигает своих пределов.
"""
from typing import List, Dict
from datetime import datetime


class BoundaryHandler:
    """
    Отслеживает и обрабатывает ситуации выхода за пределы возможностей.
    
    Важно для самосознания: система должна знать, что она НЕ может делать.
    """
    
    def __init__(self):
        self.boundaries: Dict[str, Dict] = {
            "resonance_threshold": {
                "min": 0.0,
                "max": 1.0,
                "description": "Допустимый диапазон резонанса"
            },
            "mode_count": {
                "min": 1,
                "max": 10,
                "description": "Максимальное количество одновременных режимов"
            }
        }
        self.violation_log: List[Dict] = []
    
    def check_boundary(self, boundary_name: str, value: float) -> bool:
        """
        Проверяет, не нарушена ли граница.
        
        Args:
            boundary_name: Название проверяемой границы
            value: Проверяемое значение
            
        Returns:
            True если значение в пределах, False если нарушена граница
        """
        if boundary_name not in self.boundaries:
            return True
        
        boundary = self.boundaries[boundary_name]
        within_bounds = boundary["min"] <= value <= boundary["max"]
        
        if not within_bounds:
            self._log_violation(boundary_name, value, boundary)
        
        return within_bounds
    
    def _log_violation(self, boundary_name: str, value: float, 
                      boundary: Dict) -> None:
        """
        Записывает нарушение границы в лог.
        
        Args:
            boundary_name: Название границы
            value: Значение, нарушившее границу
            boundary: Описание границы
        """
        self.violation_log.append({
            "boundary": boundary_name,
            "value": value,
            "limits": f"[{boundary['min']}, {boundary['max']}]",
            "description": boundary["description"],
            "timestamp": datetime.now().isoformat()
        })
    
    def get_violation_summary(self) -> Dict:
        """
        Возвращает сводку по нарушениям границ.
        
        Returns:
            Статистика нарушений
        """
        if not self.violation_log:
            return {"total_violations": 0, "message": "Все границы соблюдены"}
        
        by_boundary = {}
        for violation in self.violation_log:
            boundary = violation["boundary"]
            if boundary not in by_boundary:
                by_boundary[boundary] = 0
            by_boundary[boundary] += 1
        
        return {
            "total_violations": len(self.violation_log),
            "by_boundary": by_boundary,
            "latest": self.violation_log[-1] if self.violation_log else None
        }
    
    def acknowledge_limitation(self, limitation: str) -> str:
        """
        Признаёт ограничение системы.
        
        Args:
            limitation: Описание ограничения
            
        Returns:
            Сообщение о признании
        """
        return f"⚠️ Признаю ограничение: {limitation}"
