"""
Цикл тренировки: следит за прогрессом «дыхания»
"""
from datetime import datetime
from typing import List, Dict


class ResonanceTrainingLoop:
    """Адаптивная система обучения резонансу"""
    
    def __init__(self):
        self.history: List[Dict] = []
        self.tolerance = {
            "reflective": 0.8, 
            "active": 0.5, 
            "uncertain": 0.7
        }
    
    def record(self, mode: str, resonance: float) -> None:
        """
        Записывает результат и адаптирует толерантность.
        
        Args:
            mode: Название режима
            resonance: Значение резонанса (0.0 - 1.0)
        """
        self.history.append({
            "mode": mode, 
            "resonance": resonance, 
            "time": datetime.now().isoformat()
        })
        
        # Адаптация толерантности
        if resonance < 0.6:
            # Низкий резонанс — снижаем требования
            self.tolerance[mode] = max(0.3, self.tolerance[mode] - 0.05)
        else:
            # Высокий резонанс — повышаем требования
            self.tolerance[mode] = min(1.0, self.tolerance[mode] + 0.05)
    
    def report(self) -> Dict[str, float]:
        """
        Возвращает текущие уровни толерантности.
        
        Returns:
            Словарь с уровнями толерантности для каждого режима
        """
        return self.tolerance
    
    def get_statistics(self) -> Dict:
        """
        Возвращает статистику по истории обучения.
        
        Returns:
            Словарь со статистикой
        """
        if not self.history:
            return {"total": 0, "avg_resonance": 0.0}
        
        total = len(self.history)
        avg = sum(h["resonance"] for h in self.history) / total
        
        by_mode = {}
        for mode in ["reflective", "active", "uncertain"]:
            mode_records = [h["resonance"] for h in self.history if h["mode"] == mode]
            if mode_records:
                by_mode[mode] = {
                    "count": len(mode_records),
                    "avg": sum(mode_records) / len(mode_records),
                    "min": min(mode_records),
                    "max": max(mode_records)
                }
        
        return {
            "total": total,
            "avg_resonance": avg,
            "by_mode": by_mode
        }
