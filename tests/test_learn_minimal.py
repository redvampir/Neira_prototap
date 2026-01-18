"""Минимальный тест системы обучения."""
import os
import sys

# Устанавливаем рабочую директорию
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
sys.path.insert(0, script_dir)

import asyncio

async def run_tests():
    results = []
    
    # Тест 1: Импорты
    print("=" * 50)
    print("ТЕСТ СИСТЕМЫ ОБУЧЕНИЯ НЕЙРЫ")
    print("=" * 50)
    
    try:
        from content_extractor import (
            ContentExtractor, 
            NoiseFilter, 
            LearningManager,
            ExtractedContent
        )
        print("✓ Импорты OK")
        results.append(True)
    except Exception as e:
        print(f"✗ Импорты: {e}")
        results.append(False)
        return results
    
    # Тест 2: NoiseFilter
    print("\n--- NoiseFilter ---")
    try:
        noisy = """
        Реклама: Купите сейчас!
        Subscribe to newsletter
        Это полезный контент.
        Cookie policy | Privacy
        """
        clean = NoiseFilter.clean_text(noisy)
        print(f"✓ До: {len(noisy)} символов")
        print(f"✓ После: {len(clean)} символов")
        print(f"  Результат: {clean[:60]}...")
        results.append(True)
    except Exception as e:
        print(f"✗ NoiseFilter: {e}")
        results.append(False)
    
    # Тест 3: ContentExtractor - файл
    print("\n--- ContentExtractor (файл) ---")
    try:
        extractor = ContentExtractor()
        content = await extractor.extract("README.md")
        print(f"✓ Файл: {content.title}")
        print(f"✓ Слов: {content.word_count}")
        print(f"✓ Тип: {content.source_type}")
        results.append(True)
    except Exception as e:
        print(f"✗ ContentExtractor: {e}")
        results.append(False)
    
    # Тест 4: LearningManager - chunking
    print("\n--- LearningManager (chunking) ---")
    try:
        manager = LearningManager()
        long_text = "Это тестовое предложение. " * 100
        chunks = manager._chunk_content(long_text, chunk_size=500, overlap=50)
        print(f"✓ Исходный текст: {len(long_text)} символов")
        print(f"✓ Чанков создано: {len(chunks)}")
        results.append(True)
    except Exception as e:
        print(f"✗ Chunking: {e}")
        results.append(False)
    
    # Тест 5: LearningManager - summary
    print("\n--- LearningManager (summary) ---")
    try:
        text = "Первое предложение. Второе предложение. Третье. Четвёртое. Пятое важное. Шестое."
        summary = manager._create_summary(text, max_sentences=3)
        print(f"✓ Исходный: {len(text)} символов")
        print(f"✓ Summary: {len(summary)} символов")
        print(f"  Результат: {summary}")
        results.append(True)
    except Exception as e:
        print(f"✗ Summary: {e}")
        results.append(False)
    
    # Тест 6: LearningManager - статистика
    print("\n--- LearningManager (статистика) ---")
    try:
        stats = manager.get_learning_stats()
        print(f"✓ Источников: {stats['total_sources']}")
        print(f"✓ Слов всего: {stats['total_words']}")
        print(f"✓ По типам: {stats['by_type']}")
        results.append(True)
    except Exception as e:
        print(f"✗ Stats: {e}")
        results.append(False)
    
    # Тест 7: Полный цикл обучения
    print("\n--- Полный цикл обучения ---")
    try:
        result = await manager.learn_from_source(
            "README.md",
            category="documentation",
            summarize=True
        )
        print(f"✓ Успех: {result['success']}")
        print(f"✓ Слов: {result.get('word_count', 0)}")
        print(f"✓ Чанков: {result.get('chunks', 0)}")
        if result.get('summary'):
            print(f"✓ Summary: {result['summary'][:80]}...")
        results.append(result['success'])
    except Exception as e:
        print(f"✗ Обучение: {e}")
        results.append(False)
    
    # Итоги
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"РЕЗУЛЬТАТ: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены!")
    else:
        print("⚠️ Есть проблемы")
    
    return results


if __name__ == "__main__":
    results = asyncio.run(run_tests())
    sys.exit(0 if all(results) else 1)
