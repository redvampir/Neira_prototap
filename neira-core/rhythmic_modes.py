"""
Ритмические режимы: определяет три базовых режима и их метафоры
"""
from dataclasses import dataclass
from typing import Literal


@dataclass
class RhythmicMode:
    """Описание ритмического режима"""
    tempo: Literal["slow", "fast", "variable"]
    rhythm: Literal["legato", "staccato", "syncopated"]
    tone: Literal["neutral", "assertive", "doubtful"]
    breath: Literal["long", "short", "irregular"]
    metaphor: str
    max_sentence_length: int
    prefer_conjunctions: bool
    allow_questions: bool
    modal_words_ratio: float


RHYTHMIC_MODES = {
    "reflective": RhythmicMode(
        "slow", "legato", "neutral", "long",
        "низкий гул струн, шаги в библиотеке", 
        150, True, False, 0.1
    ),
    "active": RhythmicMode(
        "fast", "staccato", "assertive", "short",
        "перкуссия, барабаны, акценты", 
        40, False, False, 0.0
    ),
    "uncertain": RhythmicMode(
        "variable", "syncopated", "doubtful", "irregular",
        "скрипка с паузами, ищет ноту", 
        80, True, True, 0.3
    )
}
