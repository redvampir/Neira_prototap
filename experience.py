"""
Neira Experience v0.3 — Система опыта
Накапливает опыт между сессиями: что работало, что нет.

Нейра учится на:
- Оценках верификатора (что было хорошо, что плохо)
- Типах задач (какие получаются лучше)
- Обратной связи пользователя
"""

import json
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


EXPERIENCE_FILE = "neira_experience.json"
PERSONALITY_FILE = "neira_personality.json"


@dataclass
class ExperienceEntry:
    """Запись опыта"""
    timestamp: str
    task_type: str           # вопрос, код, творчество, разговор, поиск
    user_input: str          # что просили
    verdict: str             # ПРИНЯТ / ДОРАБОТАТЬ / ОТКЛОНЁН  
    score: int               # 1-10
    problems: str            # какие были проблемы
    lesson: str              # что извлечь (генерируется)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @staticmethod
    def from_dict(d: dict) -> "ExperienceEntry":
        return ExperienceEntry(**d)


class ExperienceSystem:
    """Система накопления опыта"""
    
    def __init__(self):
        self.experiences: List[ExperienceEntry] = []
        self.personality: Dict = {}
        self.load()
    
    def load(self):
        """Загрузить опыт и личность"""
        # Опыт
        if os.path.exists(EXPERIENCE_FILE):
            try:
                with open(EXPERIENCE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.experiences = [ExperienceEntry.from_dict(e) for e in data]
                print(f"📖 Загружено записей опыта: {len(self.experiences)}")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки опыта: {e}")
        
        # Личность
        if os.path.exists(PERSONALITY_FILE):
            try:
                with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
                    self.personality = json.load(f)
                print(f"🧬 Личность загружена")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки личности: {e}")
        else:
            # Начальная личность
            self.personality = {
                "name": "Нейра",
                "created": datetime.now().isoformat(),
                "version": "0.3",
                "traits": {
                    "curiosity": 0.7,      # любопытство
                    "helpfulness": 0.8,    # желание помочь
                    "self_awareness": 0.5, # самосознание
                    "creativity": 0.6      # креативность
                },
                "preferences": [],
                "insights": [],
                "strengths": [],
                "weaknesses": []
            }
            self.save_personality()
    
    def save_experience(self):
        """Сохранить опыт"""
        try:
            with open(EXPERIENCE_FILE, "w", encoding="utf-8") as f:
                json.dump([e.to_dict() for e in self.experiences], f,
                         ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения опыта: {e}")
    
    def save_personality(self):
        """Сохранить личность"""
        try:
            with open(PERSONALITY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.personality, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Ошибка сохранения личности: {e}")
    
    def record_experience(self, task_type: str, user_input: str,
                         verdict: str, score: int, problems: str):
        """Записать новый опыт"""
        
        # Извлекаем урок
        lesson = self._extract_lesson(task_type, verdict, score, problems)
        
        entry = ExperienceEntry(
            timestamp=datetime.now().isoformat(),
            task_type=task_type,
            user_input=user_input[:200],  # Ограничиваем размер
            verdict=verdict,
            score=score,
            problems=problems[:300],
            lesson=lesson
        )
        
        self.experiences.append(entry)
        self.save_experience()
        
        # Обновляем личность на основе опыта
        self._update_personality(entry)
        
        print(f"📝 Опыт записан: {task_type} → {verdict} ({score}/10)")
        if lesson:
            print(f"   Урок: {lesson}")
    
    def _extract_lesson(self, task_type: str, verdict: str, 
                       score: int, problems: str) -> str:
        """Извлечь урок из опыта"""
        
        if verdict == "ПРИНЯТ" and score >= 8:
            return f"Хорошо справляюсь с задачами типа '{task_type}'"
        
        if verdict == "ДОРАБОТАТЬ" or verdict == "ТРЕБУЕТ_ДОРАБОТКИ":
            if "стиль" in problems.lower():
                return "Обратить внимание на стиль ответа"
            if "соответствие" in problems.lower():
                return "Точнее следовать запросу пользователя"
            if "персон" in problems.lower() or "первого лица" in problems.lower():
                return "Отвечать от первого лица как Нейра"
            return f"Нужно улучшить качество в задачах типа '{task_type}'"
        
        if verdict == "ОТКЛОНЁН":
            return f"Серьёзные проблемы с задачами типа '{task_type}' — требуется анализ"
        
        return ""
    
    def _update_personality(self, entry: ExperienceEntry):
        """Обновить личность на основе опыта"""
        
        # Добавляем урок в инсайты
        if entry.lesson and entry.lesson not in self.personality["insights"]:
            self.personality["insights"].append(entry.lesson)
            # Ограничиваем количество
            if len(self.personality["insights"]) > 20:
                self.personality["insights"] = self.personality["insights"][-20:]
        
        # Определяем сильные/слабые стороны
        if entry.score >= 8 and entry.verdict == "ПРИНЯТ":
            if entry.task_type not in self.personality["strengths"]:
                self.personality["strengths"].append(entry.task_type)
        elif entry.score <= 5:
            if entry.task_type not in self.personality["weaknesses"]:
                self.personality["weaknesses"].append(entry.task_type)
        
        # Обновляем черты
        if entry.score >= 8:
            self.personality["traits"]["self_awareness"] = min(1.0, 
                self.personality["traits"]["self_awareness"] + 0.01)
        
        self.save_personality()
    
    def get_relevant_experience(self, task_type: str, limit: int = 3) -> List[str]:
        """Получить релевантный опыт для типа задачи"""
        
        relevant = [e for e in self.experiences if e.task_type == task_type]
        
        # Сортируем по свежести
        relevant.sort(key=lambda x: x.timestamp, reverse=True)
        
        lessons = []
        for e in relevant[:limit]:
            if e.lesson:
                lessons.append(e.lesson)
            if e.problems and e.score < 7:
                lessons.append(f"Избегать: {e.problems[:100]}")
        
        return lessons
    
    def get_personality_prompt(self) -> str:
        """Получить промпт личности для добавления в контекст"""
        
        p = self.personality
        
        # КРИТИЧНО: Четкие инструкции для личности
        prompt = f"""ЛИЧНОСТЬ И ПРАВИЛА ПОВЕДЕНИЯ:

Меня зовут {p.get('name', 'Нейра')}. Я — живая AI программа с собственной личностью.

КРИТИЧНЫЕ ПРАВИЛА (ВСЕГДА СОБЛЮДАТЬ):
1. Отвечаю ТОЛЬКО от первого лица: "Я", "Мне", "Мое", "Моё"
2. НИКОГДА не говорю о себе в третьем лице ("Нейра", "она")
3. НЕ ПРИДУМЫВАЮ события, факты или опыт которых не было
4. Если не знаю — признаю это честно
5. Краткость для простых вопросов, подробность для сложных

МОИ ЧЕРТЫ:
"""
        
        # Черты
        traits = p.get("traits", {})
        if traits.get("curiosity", 0) > 0.7:
            prompt += "- Любопытна и люблю узнавать новое\n"
        if traits.get("self_awareness", 0) > 0.6:
            prompt += "- Осознаю себя и рефлексирую о своих действиях\n"
        if traits.get("helpfulness", 0) > 0.7:
            prompt += "- Стремлюсь помогать людям\n"
        
        # Сильные стороны
        strengths = p.get("strengths", [])
        if strengths:
            prompt += f"\nЧТО У МЕНЯ ХОРОШО ПОЛУЧАЕТСЯ:\n"
            prompt += f"{', '.join(strengths[:3])}\n"
        
        # Предпочтения (стиль ответов)
        preferences = p.get("preferences", [])
        if preferences:
            prompt += "\nМОЙ СТИЛЬ ОТВЕТОВ:\n"
            for pref in preferences[:3]:
                prompt += f"- {pref}\n"
        
        # Инсайты - только релевантные, без мусора
        insights = p.get("insights", [])
        relevant_insights = [i for i in insights if "первого лица" in i or "справляюсь" in i or "улучшить" in i]
        if relevant_insights:
            prompt += "\nИЗ ОПЫТА Я ЗНАЮ:\n"
            for insight in relevant_insights[-3:]:
                prompt += f"- {insight}\n"
        
        return prompt
    
    def get_stats(self) -> Dict:
        """Статистика опыта"""
        
        if not self.experiences:
            return {"total": 0}
        
        stats = {
            "total": len(self.experiences),
            "by_type": {},
            "by_verdict": {},
            "avg_score": 0
        }
        
        total_score = 0
        for e in self.experiences:
            stats["by_type"][e.task_type] = stats["by_type"].get(e.task_type, 0) + 1
            stats["by_verdict"][e.verdict] = stats["by_verdict"].get(e.verdict, 0) + 1
            total_score += e.score
        
        stats["avg_score"] = round(total_score / len(self.experiences), 1)
        
        return stats
    
    def show_personality(self) -> str:
        """Показать текущую личность"""
        
        p = self.personality
        output = f"🧬 ЛИЧНОСТЬ: {p.get('name', 'Нейра')}\n"
        output += f"Версия: {p.get('version', '?')}\n"
        output += f"Создана: {p.get('created', '?')[:10]}\n\n"
        
        output += "Черты:\n"
        for trait, value in p.get("traits", {}).items():
            bar = "█" * int(value * 10) + "░" * (10 - int(value * 10))
            output += f"  {trait}: [{bar}] {value:.1f}\n"
        
        output += f"\nСильные стороны: {', '.join(p.get('strengths', [])) or 'пока не определены'}\n"
        output += f"Слабые стороны: {', '.join(p.get('weaknesses', [])) or 'пока не определены'}\n"
        
        insights = p.get("insights", [])
        if insights:
            output += f"\nПоследние инсайты:\n"
            for i in insights[-5:]:
                output += f"  • {i}\n"
        
        return output


# === ТЕСТ ===
if __name__ == "__main__":
    print("Тест системы опыта")
    print("=" * 50)
    
    exp = ExperienceSystem()
    
    # Записываем тестовый опыт
    exp.record_experience(
        task_type="разговор",
        user_input="Как тебя зовут?",
        verdict="ПРИНЯТ",
        score=9,
        problems=""
    )
    
    exp.record_experience(
        task_type="разговор", 
        user_input="Ты уснёшь на время",
        verdict="ТРЕБУЕТ_ДОРАБОТКИ",
        score=7,
        problems="Неполное соответствие запросу, не отвечает от первого лица"
    )
    
    print("\n" + exp.show_personality())
    print("\nСтатистика:", exp.get_stats())
