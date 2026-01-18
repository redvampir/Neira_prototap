@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Тест системы обучения Нейры ===
echo.

python -c "
import sys
import os
os.chdir(os.path.dirname(os.path.abspath('%~f0')))
sys.path.insert(0, '.')

import asyncio
from content_extractor import ContentExtractor, NoiseFilter, LearningManager

async def test():
    print('1. Тест ContentExtractor...')
    extractor = ContentExtractor()
    content = await extractor.extract('README.md')
    print(f'   OK: {content.title} ({content.word_count} слов)')
    
    print('2. Тест NoiseFilter...')
    noisy = 'Реклама! Subscribe! Полезный контент. Cookie policy.'
    clean = NoiseFilter.clean_text(noisy)
    print(f'   OK: {len(noisy)} -> {len(clean)} символов')
    
    print('3. Тест LearningManager...')
    manager = LearningManager()
    chunks = manager._chunk_content('Test. ' * 200, chunk_size=500)
    print(f'   OK: {len(chunks)} чанков')
    
    stats = manager.get_learning_stats()
    print(f'   OK: {stats[\"total_sources\"]} источников в истории')
    
    print('4. Тест обучения...')
    result = await manager.learn_from_source('README.md', category='test')
    print(f'   OK: {result.get(\"word_count\", 0)} слов изучено')
    
    print()
    print('Все тесты пройдены!')

asyncio.run(test())
"

pause
