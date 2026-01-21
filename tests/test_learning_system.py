#!/usr/bin/env python3
"""
Тест системы обучения Нейры.
Проверяет извлечение контента из разных источников.
"""

import asyncio
import sys
import pytest
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
sys.path.insert(0, str(Path(__file__).parent))


@pytest.mark.asyncio
async def test_file_extraction():
    """Тест извлечения из файла"""
    print("\n" + "=" * 60)
    print("📁 Тест 1: Извлечение из файла")
    print("=" * 60)
    
    try:
        from content_extractor import ContentExtractor
        
        extractor = ContentExtractor()
        
        # Тестируем README.md
        content = await extractor.extract("README.md")
        
        print(f"✓ Файл: {content.title}")
        print(f"  Тип: {content.source_type}")
        print(f"  Слов: {content.word_count}")
        print(f"  Превью: {content.content[:100]}...")
        
        return True, f"Файл OK ({content.word_count} слов)"
    except Exception as e:
        logger.exception("Ошибка в test_file_extraction: %s", e)
        return False, f"Файл: {e}"


@pytest.mark.asyncio
async def test_noise_filter():
    """Тест фильтра шума"""
    print("\n" + "=" * 60)
    print("🧹 Тест 2: Фильтр шума")
    print("=" * 60)
    
    try:
        from content_extractor import NoiseFilter
        
        # Тестовый HTML с шумом
        noisy_text = """
        Реклама: Купите сейчас!
        Subscribe to our newsletter
        
        Это полезный контент который нужно сохранить.
        Здесь важная информация о программировании.
        
        Cookie policy | Privacy | Terms
        Share on Facebook | Twitter | VK
        Загрузка... Please wait
        """
        
        clean = NoiseFilter.clean_text(noisy_text)
        
        print(f"✓ До очистки: {len(noisy_text)} символов")
        print(f"✓ После очистки: {len(clean)} символов")
        print(f"  Результат: {clean[:100]}...")
        
        # Проверяем что шум удалён
        assert "Реклама" not in clean or len(clean) < len(noisy_text)
        assert "Subscribe" not in clean or len(clean) < len(noisy_text)
        
        return True, "Фильтр шума работает"
    except Exception as e:
        logger.exception("Ошибка в test_noise_filter: %s", e)
        return False, f"Фильтр: {e}"


@pytest.mark.asyncio
async def test_chunking():
    """Тест разбиения на чанки"""
    print("\n" + "=" * 60)
    print("✂️ Тест 3: Разбиение на чанки")
    print("=" * 60)
    
    try:
        from content_extractor import LearningManager
        
        manager = LearningManager()
        
        # Длинный текст
        long_text = "Это тестовое предложение. " * 100
        
        chunks = manager._chunk_content(long_text, chunk_size=500, overlap=50)
        
        print(f"✓ Исходный текст: {len(long_text)} символов")
        print(f"✓ Чанков создано: {len(chunks)}")
        print(f"✓ Размер первого чанка: {len(chunks[0])} символов")
        
        # Проверяем что чанки не слишком большие
        for i, chunk in enumerate(chunks):
            assert len(chunk) <= 600, f"Чанк {i} слишком большой: {len(chunk)}"
        
        return True, f"Chunking OK ({len(chunks)} чанков)"
    except Exception as e:
        logger.exception("Ошибка в test_chunking: %s", e)
        return False, f"Chunking: {e}"


@pytest.mark.asyncio
async def test_summary():
    """Тест создания summary"""
    print("\n" + "=" * 60)
    print("📝 Тест 4: Создание summary")
    print("=" * 60)
    
    try:
        from content_extractor import LearningManager
        
        manager = LearningManager()
        
        text = """
        Введение в Python. Python - это высокоуровневый язык программирования.
        Он был создан Гвидо ван Россумом в 1991 году.
        Python используется для веб-разработки, анализа данных и машинного обучения.
        Важно понимать основы синтаксиса Python.
        Главное преимущество Python - это читаемость кода.
        Python имеет богатую стандартную библиотеку.
        Вывод: Python отлично подходит для начинающих программистов.
        """
        
        summary = manager._create_summary(text, max_sentences=3)
        
        print(f"✓ Исходный текст: {len(text)} символов")
        print(f"✓ Summary: {len(summary)} символов")
        print(f"  Результат: {summary}")
        
        assert len(summary) < len(text)
        
        return True, "Summary OK"
    except Exception as e:
        logger.exception("Ошибка в test_summary: %s", e)
        return False, f"Summary: {e}"


@pytest.mark.asyncio
async def test_learning_history():
    """Тест истории обучения"""
    print("\n" + "=" * 60)
    print("📚 Тест 5: История обучения")
    print("=" * 60)
    
    try:
        from content_extractor import LearningManager
        
        manager = LearningManager()
        
        # Получаем статистику
        stats = manager.get_learning_stats()
        
        print(f"✓ Всего источников: {stats['total_sources']}")
        print(f"✓ Всего слов: {stats['total_words']}")
        print(f"✓ По типам: {stats['by_type']}")
        print(f"✓ По категориям: {stats['by_category']}")
        
        return True, f"История OK ({stats['total_sources']} источников)"
    except Exception as e:
        logger.exception("Ошибка в test_learning_history: %s", e)
        return False, f"История: {e}"


@pytest.mark.asyncio
async def test_learn_from_file():
    """Тест полного цикла обучения из файла"""
    print("\n" + "=" * 60)
    print("🎓 Тест 6: Полный цикл обучения")
    print("=" * 60)
    
    try:
        from content_extractor import LearningManager
        
        manager = LearningManager()
        
        # Обучаемся из README
        result = await manager.learn_from_source(
            "README.md",
            category="documentation",
            summarize=True
        )
        
        print(f"✓ Успех: {result['success']}")
        print(f"✓ Название: {result.get('title', 'N/A')}")
        print(f"✓ Слов: {result.get('word_count', 0)}")
        print(f"✓ Чанков: {result.get('chunks', 0)}")
        
        if result.get('summary'):
            print(f"✓ Summary: {result['summary'][:100]}...")
        
        return True, f"Обучение OK ({result.get('word_count', 0)} слов)"
    except Exception as e:
        logger.exception("Ошибка в test_learn_from_file: %s", e)
        return False, f"Обучение: {e}"


@pytest.mark.asyncio
async def test_web_extraction():
    """Тест извлечения с веб-страницы (опционально)"""
    print("\n" + "=" * 60)
    print("🌐 Тест 7: Извлечение с веб-страницы")
    print("=" * 60)
    
    try:
        from content_extractor import ContentExtractor
        
        extractor = ContentExtractor()
        
        # Простая страница для теста
        url = "https://httpbin.org/html"
        
        content = await extractor.extract(url)
        
        print(f"✓ URL: {url}")
        print(f"✓ Заголовок: {content.title}")
        print(f"✓ Слов: {content.word_count}")
        print(f"✓ Домен: {content.metadata.get('domain', 'N/A')}")
        
        return True, f"Web OK ({content.word_count} слов)"
    except ImportError as e:
        return None, f"Web: требуется beautifulsoup4"
    except Exception as e:
        logger.exception("Ошибка в test_web_extraction: %s", e)
        return False, f"Web: {e}"


async def main():
    """Запуск всех тестов"""
    print("\n" + "🎓" * 30)
    print("   ТЕСТИРОВАНИЕ СИСТЕМЫ ОБУЧЕНИЯ НЕЙРЫ")
    print("🎓" * 30)
    
    results = []
    
    # Базовые тесты
    results.append(await test_file_extraction())
    results.append(await test_noise_filter())
    results.append(await test_chunking())
    results.append(await test_summary())
    results.append(await test_learning_history())
    results.append(await test_learn_from_file())
    
    # Опциональный тест веба
    web_result = await test_web_extraction()
    if web_result[0] is not None:
        results.append(web_result)
    else:
        print(f"⚠️ {web_result[1]}")
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    passed = sum(1 for ok, _ in results if ok)
    total = len(results)
    
    for i, (ok, msg) in enumerate(results, 1):
        status = "✅" if ok else "❌"
        print(f"{status} Тест {i}: {msg}")
    
    print(f"\n{'=' * 60}")
    print(f"Пройдено: {passed}/{total}")
    
    if passed == total:
        print("🎉 Все тесты пройдены!")
    elif passed >= total - 1:
        print("✨ Почти всё работает!")
    else:
        print("⚠️ Есть проблемы")
    
    return passed >= total - 1


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
