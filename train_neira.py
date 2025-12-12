"""
Neira Training System v1.0 — Обучение через терминал
Интерактивная система для обучения Neira новым паттернам

Возможности:
- Добавление новых Neural Pathways
- Создание фрагментов ответов
- Создание шаблонов
- Просмотр статистики
- Импорт из существующей памяти
"""

import json
import os
import sys
from typing import Optional, List, Dict, Any
from datetime import datetime

from neural_pathways import NeuralPathway, NeuralPathwaySystem, PathwayTier
from response_synthesizer import ResponseFragment, ResponseTemplate, ResponseSynthesizer, ResponseMode
from neira_cortex import NeiraCortex


class NeiraTrainer:
    """Система обучения Neira"""
    
    def __init__(self):
        self.cortex = NeiraCortex(use_llm=False)
        self.pathways = self.cortex.pathways
        self.synthesizer = self.cortex.synthesizer
        
        print("\n" + "=" * 60)
        print("🎓 Neira Training System v1.0")
        print("=" * 60)
        print("Обучаем Neira новым паттернам ответов!")
        print()
    
    def main_menu(self):
        """Главное меню"""
        while True:
            print("\n" + "─" * 60)
            print("📚 Главное меню:")
            print("─" * 60)
            print("1. Добавить новый Neural Pathway")
            print("2. Добавить фрагмент ответа")
            print("3. Создать шаблон ответа")
            print("4. Просмотреть статистику")
            print("5. Протестировать Neira")
            print("6. Импорт из памяти (neira_memory.json)")
            print("7. Сохранить и выйти")
            print("─" * 60)
            
            choice = input("\nВыбери действие (1-7): ").strip()
            
            if choice == "1":
                self.add_pathway()
            elif choice == "2":
                self.add_fragment()
            elif choice == "3":
                self.add_template()
            elif choice == "4":
                self.show_stats()
            elif choice == "5":
                self.test_neira()
            elif choice == "6":
                self.import_from_memory()
            elif choice == "7":
                self.save_and_exit()
                break
            else:
                print("❌ Неверный выбор, попробуй еще раз")
    
    def add_pathway(self):
        """Добавить новый pathway"""
        print("\n" + "─" * 60)
        print("➕ Добавление нового Neural Pathway")
        print("─" * 60)
        
        # ID
        pathway_id = input("ID pathway (например: greeting_morning): ").strip()
        if not pathway_id:
            print("❌ ID не может быть пустым")
            return
        
        # Проверка существования
        if self.pathways.get_by_id(pathway_id):
            print(f"⚠️ Pathway с ID '{pathway_id}' уже существует")
            return
        
        # Триггеры
        print("\nВведи триггеры (ключевые фразы), каждый на новой строке.")
        print("Когда закончишь, введи пустую строку:")
        triggers = []
        while True:
            trigger = input(f"  Триггер {len(triggers) + 1}: ").strip()
            if not trigger:
                break
            triggers.append(trigger)
        
        if not triggers:
            print("❌ Нужен хотя бы один триггер")
            return
        
        # Шаблон ответа
        response_template = input("\nШаблон ответа: ").strip()
        if not response_template:
            print("❌ Шаблон ответа не может быть пустым")
            return
        
        # Категория
        print("\nКатегория:")
        print("1. greeting (приветствие)")
        print("2. gratitude (благодарность)")
        print("3. question (вопрос)")
        print("4. task (задача)")
        print("5. code (код)")
        print("6. chat (общение)")
        print("7. general (общая)")
        category_choice = input("Выбери категорию (1-7): ").strip()
        
        category_map = {
            "1": "greeting", "2": "gratitude", "3": "question",
            "4": "task", "5": "code", "6": "chat", "7": "general"
        }
        category = category_map.get(category_choice, "general")
        
        # Tier
        print("\nTier (приоритет):")
        print("1. HOT (частые запросы)")
        print("2. WARM (популярные)")
        print("3. COOL (нишевые)")
        print("4. COLD (индивидуальные)")
        tier_choice = input("Выбери tier (1-4, Enter=COLD): ").strip()
        
        tier_map = {
            "1": PathwayTier.HOT,
            "2": PathwayTier.WARM,
            "3": PathwayTier.COOL,
            "4": PathwayTier.COLD
        }
        tier = tier_map.get(tier_choice, PathwayTier.COLD)
        
        # Confidence threshold
        confidence_str = input("\nМинимальный confidence (0-1, Enter=0.7): ").strip()
        try:
            confidence_threshold = float(confidence_str) if confidence_str else 0.7
        except:
            confidence_threshold = 0.7
        
        # Создаем pathway
        pathway = NeuralPathway(
            id=pathway_id,
            triggers=triggers,
            response_template=response_template,
            category=category,
            tier=tier,
            confidence_threshold=confidence_threshold
        )
        
        # Добавляем
        self.pathways.add(pathway, tier=tier)
        
        print(f"\n✅ Pathway '{pathway_id}' успешно добавлен!")
        print(f"   Триггеры: {', '.join(triggers)}")
        print(f"   Tier: {tier.value}")
        
        # Сохраняем
        self.pathways.save()
    
    def add_fragment(self):
        """Добавить фрагмент ответа"""
        print("\n" + "─" * 60)
        print("➕ Добавление фрагмента ответа")
        print("─" * 60)
        
        # ID
        fragment_id = input("ID фрагмента (например: greeting_emoji): ").strip()
        if not fragment_id:
            print("❌ ID не может быть пустым")
            return
        
        # Текст
        text = input("Текст фрагмента (можно использовать {переменные}): ").strip()
        if not text:
            print("❌ Текст не может быть пустым")
            return
        
        # Категория
        category = input("Категория (Enter=general): ").strip() or "general"
        
        # Теги
        print("\nТеги (через запятую):")
        tags_input = input("  Теги: ").strip()
        tags = [t.strip() for t in tags_input.split(",") if t.strip()]
        
        # Создаем фрагмент
        fragment = ResponseFragment(
            id=fragment_id,
            text=text,
            category=category,
            tags=tags
        )
        
        # Добавляем
        self.synthesizer.add_fragment(fragment)
        
        print(f"\n✅ Фрагмент '{fragment_id}' успешно добавлен!")
        
        # Сохраняем
        self.synthesizer.save()
    
    def add_template(self):
        """Создать шаблон ответа"""
        print("\n" + "─" * 60)
        print("➕ Создание шаблона ответа")
        print("─" * 60)
        
        # ID
        template_id = input("ID шаблона (например: greeting_extended): ").strip()
        if not template_id:
            print("❌ ID не может быть пустым")
            return
        
        # Название
        name = input("Название шаблона: ").strip() or template_id
        
        # Структура (список fragment_id)
        print("\nСтруктура (fragment IDs через запятую):")
        print(f"Доступные фрагменты: {', '.join(list(self.synthesizer.fragments.keys())[:10])}")
        structure_input = input("  Fragment IDs: ").strip()
        structure = [s.strip() for s in structure_input.split(",") if s.strip()]
        
        if not structure:
            print("❌ Нужен хотя бы один фрагмент")
            return
        
        # Категория
        category = input("Категория (Enter=general): ").strip() or "general"
        
        # Описание
        description = input("Описание (Enter=пусто): ").strip() or ""
        
        # Создаем шаблон
        template = ResponseTemplate(
            id=template_id,
            name=name,
            structure=structure,
            mode=ResponseMode.TEMPLATE,
            category=category,
            description=description
        )
        
        # Добавляем
        self.synthesizer.add_template(template)
        
        print(f"\n✅ Шаблон '{template_id}' успешно создан!")
        print(f"   Структура: {' → '.join(structure)}")
        
        # Сохраняем
        self.synthesizer.save()
    
    def show_stats(self):
        """Показать статистику"""
        print("\n" + "=" * 60)
        print("📊 Статистика Neira")
        print("=" * 60)
        
        stats = self.cortex.get_stats()
        
        print(f"\n🧠 Neural Pathways: {len(self.pathways.pathways)}")
        print("  По tiers:")
        for tier, count in stats['pathways']['by_tier'].items():
            print(f"    {tier}: {count}")
        
        print(f"\n🎨 Фрагменты ответов: {len(self.synthesizer.fragments)}")
        print("  Топ-5 по использованию:")
        top_fragments = sorted(
            self.synthesizer.fragments.values(),
            key=lambda f: f.usage_count,
            reverse=True
        )[:5]
        for i, frag in enumerate(top_fragments, 1):
            print(f"    {i}. {frag.id}: {frag.usage_count} раз")
        
        print(f"\n📋 Шаблонов: {len(self.synthesizer.templates)}")
        
        if stats['total_requests'] > 0:
            print(f"\n📈 Запросов обработано: {stats['total_requests']}")
            print("  Покрытие:")
            for tier, coverage in stats['pathways']['coverage'].items():
                print(f"    {tier}: {coverage}")
    
    def test_neira(self):
        """Протестировать Neira"""
        print("\n" + "─" * 60)
        print("🧪 Тестирование Neira")
        print("─" * 60)
        print("Введи запросы для тестирования (пустая строка для выхода):")
        
        while True:
            user_input = input("\n👤 Ты: ").strip()
            if not user_input:
                break
            
            # Обрабатываем через cortex
            result = self.cortex.process(user_input, user_id="test_user")
            
            # Показываем ответ
            print(f"🤖 Neira: {result.response}")
            
            # Показываем метаданные
            print(f"   📊 {result.strategy.value} | "
                  f"{result.intent.value} | "
                  f"{result.latency_ms:.1f}ms" +
                  (f" | {result.pathway_tier.value}" if result.pathway_tier else ""))
    
    def import_from_memory(self):
        """Импорт паттернов из существующей памяти"""
        print("\n" + "─" * 60)
        print("📥 Импорт из neira_memory.json")
        print("─" * 60)
        
        memory_file = "neira_memory.json"
        
        if not os.path.exists(memory_file):
            print(f"❌ Файл {memory_file} не найден")
            return
        
        try:
            with open(memory_file, 'r', encoding='utf-8') as f:
                memory = json.load(f)
            
            # Извлекаем диалоги
            dialogues = memory.get("dialogues", [])
            
            if not dialogues:
                print("⚠️ В памяти нет диалогов для импорта")
                return
            
            print(f"\nНайдено диалогов: {len(dialogues)}")
            
            # Анализируем частые паттерны
            patterns = {}
            
            for dialogue in dialogues:
                user_msg = dialogue.get("user", "").lower().strip()
                neira_msg = dialogue.get("neira", "").strip()
                
                if not user_msg or not neira_msg:
                    continue
                
                # Простой паттерн - первые 3 слова
                words = user_msg.split()[:3]
                pattern_key = " ".join(words)
                
                if pattern_key not in patterns:
                    patterns[pattern_key] = {
                        "count": 0,
                        "user_examples": [],
                        "neira_examples": []
                    }
                
                patterns[pattern_key]["count"] += 1
                if len(patterns[pattern_key]["user_examples"]) < 3:
                    patterns[pattern_key]["user_examples"].append(user_msg)
                if len(patterns[pattern_key]["neira_examples"]) < 1:
                    patterns[pattern_key]["neira_examples"].append(neira_msg)
            
            # Фильтруем частые паттерны (>= 3 раза)
            frequent = {k: v for k, v in patterns.items() if v["count"] >= 3}
            
            print(f"Найдено частых паттернов: {len(frequent)}")
            
            if not frequent:
                print("⚠️ Недостаточно повторяющихся паттернов для импорта")
                return
            
            # Показываем топ-10
            sorted_patterns = sorted(
                frequent.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:10]
            
            print("\nТоп-10 частых паттернов:")
            for i, (pattern, data) in enumerate(sorted_patterns, 1):
                print(f"{i}. \"{pattern}\" (встречается {data['count']} раз)")
            
            # Предлагаем импортировать
            confirm = input("\nИмпортировать эти паттерны как pathways? (y/n): ").strip().lower()
            
            if confirm != 'y':
                print("❌ Импорт отменен")
                return
            
            # Создаем pathways
            imported = 0
            for pattern, data in sorted_patterns:
                pathway_id = f"imported_{pattern.replace(' ', '_')}"
                
                # Проверяем существование
                if self.pathways.get_by_id(pathway_id):
                    continue
                
                # Определяем tier по частоте
                count = data["count"]
                if count >= 50:
                    tier = PathwayTier.HOT
                elif count >= 20:
                    tier = PathwayTier.WARM
                elif count >= 10:
                    tier = PathwayTier.COOL
                else:
                    tier = PathwayTier.COLD
                
                # Создаем pathway
                pathway = NeuralPathway(
                    id=pathway_id,
                    triggers=data["user_examples"],
                    response_template=data["neira_examples"][0],
                    category="chat",
                    tier=tier,
                    success_count=count  # Предзаполняем статистику
                )
                
                self.pathways.add(pathway, tier=tier)
                imported += 1
            
            print(f"\n✅ Импортировано {imported} pathways")
            
            # Сохраняем
            self.pathways.save()
            
        except Exception as e:
            print(f"❌ Ошибка импорта: {e}")
    
    def save_and_exit(self):
        """Сохранить все и выйти"""
        print("\n💾 Сохранение всех данных...")
        self.cortex.save_all()
        print("✅ Данные сохранены!")
        print("\n👋 До встречи! Neira стала умнее 🧠✨")


def main():
    """Главная функция"""
    try:
        trainer = NeiraTrainer()
        trainer.main_menu()
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        print("💾 Не забудь сохранить изменения!")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
