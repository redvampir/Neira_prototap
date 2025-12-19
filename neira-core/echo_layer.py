"""
Эхо-слой: извлекает музыкальные параметры текста (темп, ритм, дыхание, тон)
"""
import statistics

try:
    import numpy as np  # type: ignore
    _NUMPY_AVAILABLE = True
except Exception:
    np = None  # type: ignore
    _NUMPY_AVAILABLE = False


class EchoLayer:
    """Извлекает музыкальные параметры текста"""
    
    def measure_echo(self, text: str) -> dict:
        """
        Анализирует текст и возвращает его музыкальные характеристики.
        
        Args:
            text: Анализируемый текст
            
        Returns:
            dict с параметрами: tempo, rhythm, breath, tone
        """
        sentences = text.split('.')
        lengths = [len(s) for s in sentences if s.strip()]
        if _NUMPY_AVAILABLE and np is not None:
            avg_sentence_length = float(np.mean(lengths)) if lengths else 0.0
        else:
            avg_sentence_length = float(statistics.mean(lengths)) if lengths else 0.0
        
        tempo = "fast" if avg_sentence_length < 60 else "slow"
        rhythm = "staccato" if len(sentences) > 5 else "legato"
        breath = "short" if text.count(',') < len(sentences) else "long"
        tone = "question" if '?' in text else "statement"

        return {
            "tempo": tempo,
            "rhythm": rhythm,
            "breath": breath,
            "tone": tone
        }
