"""
Response Synthesizer v1.0 — Генерация ответов без LLM
Template-based сборка + фрагменты + RAG без генерации

Принцип: LLM не нужен для создания ответа, только для понимания новых паттернов.
Мы собираем ответы как конструктор из готовых фрагментов.
"""

import json
import os
import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import random


class ResponseMode(Enum):
    """Режимы генерации ответа"""
    TEMPLATE = "template"          # Простая подстановка в шаблон
    FRAGMENT_ASSEMBLY = "fragment" # Сборка из фрагментов
    RAG = "rag"                    # Поиск + компиляция без генерации
    HYBRID = "hybrid"              # Комбинированный


@dataclass
class ResponseFragment:
    """Фрагмент ответа (кирпичик для сборки)"""
    id: str
    text: str
    category: str = "general"  # greeting, explanation, code, instruction, emotion
    tags: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    
    # Метрики использования
    usage_count: int = 0
    success_rate: float = 1.0
    
    def apply_variables(self, **kwargs) -> str:
        """Подставить переменные в текст"""
        result = self.text
        
        # Подставляем переданные переменные
        for key, value in kwargs.items():
            result = result.replace(f"{{{key}}}", str(value))
        
        # Подставляем дефолтные переменные фрагмента
        for key, value in self.variables.items():
            if isinstance(value, list):
                result = result.replace(f"{{{key}}}", random.choice(value))
            else:
                result = result.replace(f"{{{key}}}", str(value))
        
        return result


@dataclass
class ResponseTemplate:
    """Шаблон ответа"""
    id: str
    name: str
    structure: List[str]  # Список fragment_id в порядке сборки
    mode: ResponseMode = ResponseMode.TEMPLATE
    
    # Метаданные
    category: str = "general"
    description: str = ""
    
    # Конфигурация
    allow_random_order: bool = False
    require_all_fragments: bool = True


class ResponseSynthesizer:
    """
    Синтезатор ответов без LLM
    
    Стратегии:
    1. Template mode: подстановка в готовый шаблон
    2. Fragment Assembly: сборка из фрагментов как конструктор
    3. RAG mode: поиск релевантных фрагментов в базе знаний
    4. Hybrid: комбинация стратегий
    """
    
    def __init__(
        self,
        fragments_file: str = "response_fragments.json",
        templates_file: str = "response_templates.json"
    ):
        self.fragments_file = fragments_file
        self.templates_file = templates_file
        
        self.fragments: Dict[str, ResponseFragment] = {}
        self.templates: Dict[str, ResponseTemplate] = {}
        
        self.load()
    
    def synthesize(
        self,
        template_id: Optional[str] = None,
        fragment_ids: Optional[List[str]] = None,
        variables: Optional[Dict[str, Any]] = None,
        mode: ResponseMode = ResponseMode.TEMPLATE
    ) -> str:
        """
        Синтезировать ответ
        
        Args:
            template_id: ID шаблона (для TEMPLATE mode)
            fragment_ids: Список ID фрагментов (для FRAGMENT mode)
            variables: Переменные для подстановки
            mode: Режим генерации
            
        Returns:
            Готовый ответ
        """
        variables = variables or {}
        
        if mode == ResponseMode.TEMPLATE:
            return self._synthesize_template(template_id, variables)
        elif mode == ResponseMode.FRAGMENT_ASSEMBLY:
            return self._synthesize_fragments(fragment_ids, variables)
        elif mode == ResponseMode.RAG:
            return self._synthesize_rag(variables)
        else:
            return self._synthesize_hybrid(template_id, fragment_ids, variables)
    
    def _synthesize_template(self, template_id: str, variables: Dict[str, Any]) -> str:
        """Синтез через шаблон"""
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template '{template_id}' not found")
        
        # Собираем фрагменты по порядку
        parts = []
        for fragment_id in template.structure:
            fragment = self.fragments.get(fragment_id)
            if fragment:
                part = fragment.apply_variables(**variables)
                parts.append(part)
                fragment.usage_count += 1
            elif template.require_all_fragments:
                raise ValueError(f"Fragment '{fragment_id}' not found")
        
        # Собираем финальный ответ
        return " ".join(parts)
    
    def _synthesize_fragments(self, fragment_ids: List[str], variables: Dict[str, Any]) -> str:
        """Синтез из отдельных фрагментов"""
        parts = []
        
        for fragment_id in fragment_ids:
            fragment = self.fragments.get(fragment_id)
            if fragment:
                part = fragment.apply_variables(**variables)
                parts.append(part)
                fragment.usage_count += 1
        
        return " ".join(parts)
    
    def _synthesize_rag(self, variables: Dict[str, Any]) -> str:
        """
        RAG без генерации - просто поиск и компиляция
        
        Ищем релевантные фрагменты по тегам/категории
        """
        # Получаем категорию из variables
        category = variables.get("category", "general")
        tags = variables.get("tags", [])
        
        # Ищем подходящие фрагменты
        relevant_fragments = []
        for fragment in self.fragments.values():
            # Совпадение категории
            if fragment.category == category:
                relevant_fragments.append(fragment)
            # Совпадение тегов
            elif any(tag in fragment.tags for tag in tags):
                relevant_fragments.append(fragment)
        
        if not relevant_fragments:
            return "🤔 Не нашла подходящий фрагмент ответа."
        
        # Берем наиболее используемые (проверенные)
        relevant_fragments.sort(key=lambda f: f.usage_count, reverse=True)
        
        # Собираем ответ из топ-3
        parts = []
        for fragment in relevant_fragments[:3]:
            part = fragment.apply_variables(**variables)
            parts.append(part)
            fragment.usage_count += 1
        
        return " ".join(parts)
    
    def _synthesize_hybrid(
        self,
        template_id: Optional[str],
        fragment_ids: Optional[List[str]],
        variables: Dict[str, Any]
    ) -> str:
        """Гибридный синтез"""
        # Сначала пытаемся template
        if template_id:
            try:
                return self._synthesize_template(template_id, variables)
            except:
                pass
        
        # Потом fragment assembly
        if fragment_ids:
            return self._synthesize_fragments(fragment_ids, variables)
        
        # Если ничего нет - RAG
        return self._synthesize_rag(variables)
    
    def add_fragment(self, fragment: ResponseFragment):
        """Добавить фрагмент"""
        self.fragments[fragment.id] = fragment
    
    def add_template(self, template: ResponseTemplate):
        """Добавить шаблон"""
        self.templates[template.id] = template
    
    def find_fragments_by_category(self, category: str) -> List[ResponseFragment]:
        """Найти фрагменты по категории"""
        return [f for f in self.fragments.values() if f.category == category]
    
    def find_fragments_by_tag(self, tag: str) -> List[ResponseFragment]:
        """Найти фрагменты по тегу"""
        return [f for f in self.fragments.values() if tag in f.tags]
    
    def save(self):
        """Сохранить фрагменты и шаблоны"""
        # Сохраняем фрагменты
        fragments_data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "fragments": {
                fid: {
                    "id": f.id,
                    "text": f.text,
                    "category": f.category,
                    "tags": f.tags,
                    "variables": f.variables,
                    "usage_count": f.usage_count,
                    "success_rate": f.success_rate
                }
                for fid, f in self.fragments.items()
            }
        }
        
        with open(self.fragments_file, 'w', encoding='utf-8') as file:
            json.dump(fragments_data, file, ensure_ascii=False, indent=2)
        
        # Сохраняем шаблоны
        templates_data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "templates": {
                tid: {
                    "id": t.id,
                    "name": t.name,
                    "structure": t.structure,
                    "mode": t.mode.value,
                    "category": t.category,
                    "description": t.description,
                    "allow_random_order": t.allow_random_order,
                    "require_all_fragments": t.require_all_fragments
                }
                for tid, t in self.templates.items()
            }
        }
        
        with open(self.templates_file, 'w', encoding='utf-8') as file:
            json.dump(templates_data, file, ensure_ascii=False, indent=2)
    
    def load(self):
        """Загрузить фрагменты и шаблоны"""
        # Загружаем фрагменты
        if os.path.exists(self.fragments_file):
            try:
                with open(self.fragments_file, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                
                for fid, fdata in data.get("fragments", {}).items():
                    self.fragments[fid] = ResponseFragment(**fdata)
                
                print(f"✅ Загружено {len(self.fragments)} фрагментов")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки фрагментов: {e}")
        else:
            print("ℹ️ Файл фрагментов не найден, создаю базовые")
            self._create_default_fragments()
        
        # Загружаем шаблоны
        if os.path.exists(self.templates_file):
            try:
                with open(self.templates_file, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                
                for tid, tdata in data.get("templates", {}).items():
                    tdata['mode'] = ResponseMode(tdata['mode'])
                    self.templates[tid] = ResponseTemplate(**tdata)
                
                print(f"✅ Загружено {len(self.templates)} шаблонов")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки шаблонов: {e}")
        else:
            print("ℹ️ Файл шаблонов не найден, создаю базовые")
            self._create_default_templates()
    
    def _create_default_fragments(self):
        """Создать базовые фрагменты"""
        defaults = [
            # Приветствия
            ResponseFragment(
                id="greeting_casual",
                text="{emoji} Привет!",
                category="greeting",
                tags=["greeting", "casual"],
                variables={"emoji": ["👋", "😊", "✨", "🌟"]}
            ),
            ResponseFragment(
                id="greeting_formal",
                text="Здравствуйте! Рада вас видеть.",
                category="greeting",
                tags=["greeting", "formal"]
            ),
            
            # Благодарности
            ResponseFragment(
                id="thanks_casual",
                text="{emoji} Пожалуйста!",
                category="gratitude",
                tags=["thanks", "casual"],
                variables={"emoji": ["😊", "💫", "✨"]}
            ),
            ResponseFragment(
                id="thanks_helpful",
                text="Рада помочь! Обращайся, если что.",
                category="gratitude",
                tags=["thanks", "helpful"]
            ),
            
            # Объяснения
            ResponseFragment(
                id="explanation_intro",
                text="Сейчас объясню:",
                category="explanation",
                tags=["explanation", "intro"]
            ),
            ResponseFragment(
                id="explanation_step",
                text="Шаг {step}: {description}",
                category="explanation",
                tags=["explanation", "step"]
            ),
            
            # Эмоции
            ResponseFragment(
                id="emotion_thinking",
                text="🤔 Дай подумать...",
                category="emotion",
                tags=["thinking", "processing"]
            ),
            ResponseFragment(
                id="emotion_excited",
                text="✨ О, это интересно!",
                category="emotion",
                tags=["excited", "interest"]
            ),
            
            # Код
            ResponseFragment(
                id="code_intro",
                text="Вот пример кода:",
                category="code",
                tags=["code", "intro"]
            ),
            ResponseFragment(
                id="code_explanation",
                text="Этот код делает следующее: {explanation}",
                category="code",
                tags=["code", "explanation"]
            ),
            
            # Ошибки
            ResponseFragment(
                id="error_not_understand",
                text="🤔 Не совсем поняла. Можешь переформулировать?",
                category="error",
                tags=["error", "clarification"]
            ),
            ResponseFragment(
                id="error_need_more_info",
                text="Мне нужно больше информации. Расскажи подробнее о {topic}.",
                category="error",
                tags=["error", "info_request"]
            ),
        ]
        
        for fragment in defaults:
            self.add_fragment(fragment)
        
        self.save()
        print(f"✅ Создано {len(defaults)} базовых фрагментов")
    
    def _create_default_templates(self):
        """Создать базовые шаблоны"""
        defaults = [
            ResponseTemplate(
                id="greeting_full",
                name="Полное приветствие",
                structure=["greeting_casual", "emotion_excited"],
                mode=ResponseMode.TEMPLATE,
                category="greeting",
                description="Дружелюбное приветствие с эмоцией"
            ),
            ResponseTemplate(
                id="thanks_full",
                name="Благодарность с предложением помощи",
                structure=["thanks_casual", "thanks_helpful"],
                mode=ResponseMode.TEMPLATE,
                category="gratitude",
                description="Благодарность + готовность помочь"
            ),
            ResponseTemplate(
                id="code_explanation_full",
                name="Объяснение кода",
                structure=["code_intro", "code_explanation"],
                mode=ResponseMode.TEMPLATE,
                category="code",
                description="Представление кода с объяснением"
            ),
        ]
        
        for template in defaults:
            self.add_template(template)
        
        self.save()
        print(f"✅ Создано {len(defaults)} базовых шаблонов")


# === Convenience функции ===

def create_synthesizer(
    fragments_file: str = "response_fragments.json",
    templates_file: str = "response_templates.json"
) -> ResponseSynthesizer:
    """Создать синтезатор ответов"""
    return ResponseSynthesizer(fragments_file, templates_file)


# === Тестирование ===
if __name__ == "__main__":
    print("=" * 60)
    print("🎨 Response Synthesizer Test")
    print("=" * 60)
    
    # Создаем синтезатор
    synth = create_synthesizer("test_fragments.json", "test_templates.json")
    
    print("\n📝 Тестовые синтезы:\n")
    
    # Тест 1: Template mode
    print("1. Template mode (greeting_full):")
    response = synth.synthesize(template_id="greeting_full", mode=ResponseMode.TEMPLATE)
    print(f"   → {response}\n")
    
    # Тест 2: Fragment assembly
    print("2. Fragment assembly:")
    response = synth.synthesize(
        fragment_ids=["greeting_casual", "emotion_thinking"],
        mode=ResponseMode.FRAGMENT_ASSEMBLY
    )
    print(f"   → {response}\n")
    
    # Тест 3: RAG mode
    print("3. RAG mode (category=gratitude):")
    response = synth.synthesize(
        variables={"category": "gratitude"},
        mode=ResponseMode.RAG
    )
    print(f"   → {response}\n")
    
    # Тест 4: Variables
    print("4. Variables (step explanation):")
    response = synth.synthesize(
        fragment_ids=["explanation_step"],
        variables={"step": "1", "description": "устанавливаем зависимости"},
        mode=ResponseMode.FRAGMENT_ASSEMBLY
    )
    print(f"   → {response}\n")
    
    # Статистика
    print("=" * 60)
    print("📊 Статистика:")
    print("=" * 60)
    print(f"\nФрагментов: {len(synth.fragments)}")
    print(f"Шаблонов: {len(synth.templates)}")
    
    print("\nТоп-5 фрагментов по использованию:")
    top_fragments = sorted(
        synth.fragments.values(),
        key=lambda f: f.usage_count,
        reverse=True
    )[:5]
    for i, frag in enumerate(top_fragments, 1):
        print(f"  {i}. {frag.id}: {frag.usage_count} раз")
    
    # Сохранение
    synth.save()
    print(f"\n💾 Сохранено")
