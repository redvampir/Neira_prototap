"""
Детектор резонанса: измеряет согласованность между режимом и эхом
"""
from rhythmic_modes import RHYTHMIC_MODES


class ResonanceDetector:
    """Измеряет искренность (синхронность ритма и дыхания)"""
    
    def measure_resonance(self, echo: dict, mode_key: str) -> float:
        """
        Измеряет резонанс между эхом текста и заданным режимом.
        
        Args:
            echo: Словарь с параметрами эха (из EchoLayer)
            mode_key: Ключ режима из RHYTHMIC_MODES
            
        Returns:
            Оценка резонанса от 0.0 до 1.0
        """
        mode = RHYTHMIC_MODES[mode_key]
        score = 1.0
        
        # Проверка согласованности темпа и дыхания
        if mode.tempo == "fast" and echo["breath"] != "short":
            score -= 0.2
        
        # Проверка согласованности ритма и дыхания
        if mode.rhythm == "legato" and echo["breath"] == "short":
            score -= 0.2
        
        # Проверка согласованности тона и тона режима
        if mode.tone == "assertive" and echo["tone"] != "statement":
            score -= 0.2
        
        # Дополнительные проверки
        if mode.tempo == "slow" and echo["tempo"] == "fast":
            score -= 0.15
        
        if mode.rhythm == "staccato" and echo["rhythm"] != "staccato":
            score -= 0.15
        
        if mode.tone == "doubtful" and echo["tone"] != "question":
            score -= 0.1
        
        return max(score, 0.0)
