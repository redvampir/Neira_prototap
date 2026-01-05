"""
Content Extractor v1.0 — Извлечение чистого контента для обучения Нейры

Поддерживает:
- Текстовые файлы (.txt, .md, .py, .js, etc.)
- Веб-страницы (статьи, документация)
- YouTube видео (транскрипты)
- PDF документы

Защита от шума:
- Удаление рекламы, навигации, сайдбаров
- Извлечение основного контента
- Очистка от HTML/JS мусора
"""

import re
import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContent:
    """Извлечённый контент"""
    source: str  # URL или путь к файлу
    source_type: str  # file, web, youtube, pdf
    title: str
    content: str
    summary: Optional[str] = None
    word_count: int = 0
    language: str = "ru"
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "source_type": self.source_type,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "word_count": self.word_count,
            "language": self.language,
            "extracted_at": self.extracted_at,
            "metadata": self.metadata
        }


class NoiseFilter:
    """Фильтр шума — удаляет рекламу, навигацию и мусор"""
    
    # Паттерны для удаления
    NOISE_PATTERNS = [
        # Реклама
        r'(?i)(реклам[аы]|advertisement|sponsored|promo|banner)',
        r'(?i)(подпишись|subscribe|follow us|share this)',
        # Навигация
        r'(?i)(меню|menu|navigation|sidebar|footer|header)',
        r'(?i)(главная|home|about us|contact|войти|login|регистрация)',
        # Cookie и попапы
        r'(?i)(cookie|gdpr|privacy policy|terms of service)',
        r'(?i)(принять|accept|согласен|agree)',
        # Социальные сети
        r'(?i)(facebook|twitter|instagram|vk\.com|telegram)',
        r'(?i)(поделиться|share|like|comment)',
        # Мусор
        r'(?i)(loading|загрузка|please wait)',
        r'\[.*?\]',  # Квадратные скобки с контентом
        r'<script.*?</script>',
        r'<style.*?</style>',
        r'<noscript.*?</noscript>',
    ]
    
    # Теги для удаления
    NOISE_TAGS = [
        'script', 'style', 'nav', 'footer', 'header', 'aside',
        'iframe', 'noscript', 'form', 'button', 'input',
        'advertisement', 'ad', 'sidebar', 'menu', 'popup'
    ]
    
    # Классы/ID для удаления
    NOISE_CLASSES = [
        'ad', 'ads', 'advertisement', 'banner', 'popup', 'modal',
        'sidebar', 'menu', 'nav', 'navigation', 'footer', 'header',
        'social', 'share', 'comment', 'comments', 'related',
        'cookie', 'gdpr', 'newsletter', 'subscribe'
    ]
    
    @classmethod
    def clean_text(cls, text: str) -> str:
        """Очистка текста от шума"""
        if not text:
            return ""
        
        # Удаляем паттерны шума
        for pattern in cls.NOISE_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.DOTALL)
        
        # Удаляем множественные пробелы и переносы
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Удаляем строки короче 10 символов (обычно мусор)
        lines = text.split('\n')
        lines = [l.strip() for l in lines if len(l.strip()) > 10 or l.strip() == '']
        text = '\n'.join(lines)
        
        return text.strip()
    
    @classmethod
    def clean_html(cls, soup) -> None:
        """Удаление шумных элементов из BeautifulSoup"""
        # Удаляем шумные теги
        for tag in cls.NOISE_TAGS:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Удаляем элементы с шумными классами/ID
        for class_name in cls.NOISE_CLASSES:
            for element in soup.find_all(class_=re.compile(class_name, re.I)):
                element.decompose()
            for element in soup.find_all(id=re.compile(class_name, re.I)):
                element.decompose()


class ContentExtractor:
    """Извлекатель контента из разных источников"""
    
    # Поддерживаемые расширения файлов
    TEXT_EXTENSIONS = {
        '.txt', '.md', '.markdown', '.rst', '.text',
        '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h',
        '.html', '.htm', '.xml', '.json', '.yaml', '.yml',
        '.css', '.sql', '.sh', '.bat', '.ps1',
        '.ini', '.cfg', '.conf', '.env', '.log'
    }
    
    def __init__(self):
        self.extracted_count = 0
        self.total_words = 0
    
    async def extract(self, source: str) -> ExtractedContent:
        """
        Извлечь контент из источника
        
        Args:
            source: URL или путь к файлу
            
        Returns:
            ExtractedContent с очищенным контентом
        """
        source = source.strip()
        
        # Определяем тип источника
        if self._is_youtube(source):
            return await self._extract_youtube(source)
        elif self._is_url(source):
            return await self._extract_web(source)
        elif Path(source).exists():
            return await self._extract_file(source)
        else:
            raise ValueError(f"Неизвестный источник: {source}")
    
    def _is_url(self, source: str) -> bool:
        """Проверка, является ли источник URL"""
        return source.startswith(('http://', 'https://', 'www.'))
    
    def _is_youtube(self, source: str) -> bool:
        """Проверка, является ли источник YouTube"""
        youtube_patterns = [
            r'youtube\.com/watch',
            r'youtu\.be/',
            r'youtube\.com/embed',
            r'youtube\.com/v/'
        ]
        return any(re.search(p, source) for p in youtube_patterns)
    
    def _get_youtube_id(self, url: str) -> Optional[str]:
        """Извлечение ID видео YouTube"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\?/]+)',
            r'youtube\.com/v/([^&\?/]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    async def _extract_file(self, path: str) -> ExtractedContent:
        """Извлечение контента из файла"""
        file_path = Path(path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {path}")
        
        ext = file_path.suffix.lower()
        
        # PDF требует специальной обработки
        if ext == '.pdf':
            return await self._extract_pdf(path)
        
        # Текстовые файлы
        if ext in self.TEXT_EXTENSIONS or ext == '':
            try:
                content = file_path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                content = file_path.read_text(encoding='cp1251')
            
            # Очищаем контент
            content = NoiseFilter.clean_text(content)
            word_count = len(content.split())
            
            return ExtractedContent(
                source=str(file_path.absolute()),
                source_type="file",
                title=file_path.name,
                content=content,
                word_count=word_count,
                metadata={
                    "extension": ext,
                    "size_bytes": file_path.stat().st_size
                }
            )
        
        raise ValueError(f"Неподдерживаемый тип файла: {ext}")
    
    async def _extract_pdf(self, path: str) -> ExtractedContent:
        """Извлечение текста из PDF"""
        try:
            import pypdf
            
            reader = pypdf.PdfReader(path)
            text_parts = []
            
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            content = '\n\n'.join(text_parts)
            content = NoiseFilter.clean_text(content)
            
            return ExtractedContent(
                source=path,
                source_type="pdf",
                title=Path(path).name,
                content=content,
                word_count=len(content.split()),
                metadata={
                    "pages": len(reader.pages)
                }
            )
        except ImportError:
            raise ImportError("Для PDF установите: pip install pypdf")
    
    async def _extract_web(self, url: str) -> ExtractedContent:
        """Извлечение контента с веб-страницы"""
        try:
            import aiohttp
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("Установите: pip install aiohttp beautifulsoup4")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"HTTP ошибка: {response.status}")
                
                html = await response.text()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Удаляем шум
        NoiseFilter.clean_html(soup)
        
        # Получаем заголовок
        title = ""
        if soup.title:
            title = soup.title.string or ""
        if not title:
            h1 = soup.find('h1')
            title = h1.get_text() if h1 else urlparse(url).netloc
        
        # Пытаемся найти основной контент
        content = ""
        
        # Сначала ищем семантические теги
        main_selectors = [
            'article', 'main', '[role="main"]',
            '.article', '.post', '.content', '.entry',
            '#article', '#content', '#main'
        ]
        
        for selector in main_selectors:
            main = soup.select_one(selector)
            if main:
                content = main.get_text(separator='\n', strip=True)
                break
        
        # Если не нашли, берём body
        if not content:
            body = soup.find('body')
            if body:
                content = body.get_text(separator='\n', strip=True)
        
        # Очищаем контент
        content = NoiseFilter.clean_text(content)
        
        # Удаляем дубликаты строк (частая проблема)
        lines = content.split('\n')
        seen = set()
        unique_lines = []
        for line in lines:
            line_key = line.strip().lower()
            if line_key not in seen or line.strip() == '':
                seen.add(line_key)
                unique_lines.append(line)
        content = '\n'.join(unique_lines)
        
        return ExtractedContent(
            source=url,
            source_type="web",
            title=title.strip(),
            content=content,
            word_count=len(content.split()),
            metadata={
                "domain": urlparse(url).netloc
            }
        )
    
    async def _extract_youtube(self, url: str) -> ExtractedContent:
        """Извлечение транскрипта YouTube видео"""
        video_id = self._get_youtube_id(url)
        
        if not video_id:
            raise ValueError(f"Не удалось извлечь ID видео: {url}")
        
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            raise ImportError("Установите: pip install youtube-transcript-api")
        
        # Новый API (v1.0+)
        transcript = None
        api = YouTubeTranscriptApi()
        
        try:
            # Пробуем получить транскрипт напрямую
            transcript = api.fetch(video_id)
        except Exception as e:
            # Пробуем с указанием языков
            try:
                transcript = api.fetch(video_id, languages=['ru', 'en'])
            except Exception:
                raise Exception(f"Не удалось получить транскрипт для: {url}. Ошибка: {e}")
        
        if not transcript:
            raise Exception(f"Не удалось получить транскрипт для: {url}")
        
        # Собираем текст
        text_parts = [entry.text for entry in transcript]
        content = ' '.join(text_parts)
        
        # Очищаем
        content = NoiseFilter.clean_text(content)
        
        # Форматируем в абзацы (примерно по 5 предложений)
        sentences = re.split(r'(?<=[.!?])\s+', content)
        paragraphs = []
        for i in range(0, len(sentences), 5):
            paragraph = ' '.join(sentences[i:i+5])
            if paragraph.strip():
                paragraphs.append(paragraph)
        content = '\n\n'.join(paragraphs)
        
        # Получаем название видео
        title = f"YouTube: {video_id}"
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
                async with session.get(oembed_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        title = data.get('title', title)
        except Exception:
            pass
        
        return ExtractedContent(
            source=url,
            source_type="youtube",
            title=title,
            content=content,
            word_count=len(content.split()),
            metadata={
                "video_id": video_id,
                "duration_segments": len(transcript)
            }
        )
    
    async def extract_batch(self, sources: List[str]) -> List[ExtractedContent]:
        """Извлечение контента из нескольких источников"""
        results = []
        
        for source in sources:
            try:
                content = await self.extract(source)
                results.append(content)
                self.extracted_count += 1
                self.total_words += content.word_count
                logger.info(f"✓ Извлечено: {content.title} ({content.word_count} слов)")
            except Exception as e:
                logger.error(f"✗ Ошибка для {source}: {e}")
                results.append(ExtractedContent(
                    source=source,
                    source_type="error",
                    title="Ошибка извлечения",
                    content=str(e),
                    metadata={"error": str(e)}
                ))
        
        return results


class LearningManager:
    """Менеджер обучения — управляет процессом обучения Нейры"""
    
    def __init__(self, memory_system=None):
        self.extractor = ContentExtractor()
        self.memory = memory_system
        self.learned_sources: List[Dict] = []
        self.learning_history_file = Path("data/learning_history.json")
        self._load_history()
    
    def _load_history(self):
        """Загрузка истории обучения"""
        if self.learning_history_file.exists():
            try:
                self.learned_sources = json.loads(
                    self.learning_history_file.read_text(encoding='utf-8')
                )
            except Exception:
                self.learned_sources = []
    
    def _save_history(self):
        """Сохранение истории обучения"""
        self.learning_history_file.parent.mkdir(parents=True, exist_ok=True)
        self.learning_history_file.write_text(
            json.dumps(self.learned_sources, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    
    async def learn_from_source(self, source: str, 
                                 category: str = "knowledge",
                                 summarize: bool = True) -> Dict[str, Any]:
        """
        Обучение из источника
        
        Args:
            source: URL или путь к файлу
            category: Категория знаний
            summarize: Создавать ли краткое содержание
            
        Returns:
            Результат обучения
        """
        # Извлекаем контент
        content = await self.extractor.extract(source)
        
        # Создаём summary если нужно
        if summarize and len(content.content) > 500:
            content.summary = self._create_summary(content.content)
        
        # Сохраняем в память
        if self.memory:
            # Разбиваем на чанки для лучшего поиска
            chunks = self._chunk_content(content.content)
            
            for i, chunk in enumerate(chunks):
                self.memory.remember(
                    text=chunk,
                    source=f"{content.source}#chunk{i}",
                    category=category
                )
        
        # Записываем в историю
        history_entry = {
            "source": content.source,
            "source_type": content.source_type,
            "title": content.title,
            "word_count": content.word_count,
            "category": category,
            "learned_at": datetime.now().isoformat(),
            "summary": content.summary
        }
        self.learned_sources.append(history_entry)
        self._save_history()
        
        return {
            "success": True,
            "title": content.title,
            "source_type": content.source_type,
            "word_count": content.word_count,
            "chunks": len(self._chunk_content(content.content)),
            "summary": content.summary,
            "message": f"Изучила: {content.title} ({content.word_count} слов)"
        }
    
    async def learn_batch(self, sources: List[str], 
                          category: str = "knowledge") -> Dict[str, Any]:
        """Обучение из нескольких источников"""
        results = []
        success_count = 0
        total_words = 0
        
        for source in sources:
            try:
                result = await self.learn_from_source(source, category)
                results.append(result)
                if result.get("success"):
                    success_count += 1
                    total_words += result.get("word_count", 0)
            except Exception as e:
                results.append({
                    "success": False,
                    "source": source,
                    "error": str(e)
                })
        
        return {
            "total": len(sources),
            "success": success_count,
            "failed": len(sources) - success_count,
            "total_words": total_words,
            "results": results
        }
    
    def _create_summary(self, text: str, max_sentences: int = 5) -> str:
        """Создание краткого содержания (эвристический метод)"""
        # Разбиваем на предложения
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        if len(sentences) <= max_sentences:
            return text
        
        # Берём первое предложение (обычно важное)
        summary_sentences = [sentences[0]]
        
        # Ищем предложения с ключевыми словами
        keywords = ['важно', 'главн', 'основн', 'ключев', 'вывод', 'итог',
                    'important', 'main', 'key', 'conclusion', 'summary']
        
        for sentence in sentences[1:]:
            if any(kw in sentence.lower() for kw in keywords):
                summary_sentences.append(sentence)
                if len(summary_sentences) >= max_sentences:
                    break
        
        # Добавляем последнее предложение (часто вывод)
        if len(summary_sentences) < max_sentences and sentences[-1] not in summary_sentences:
            summary_sentences.append(sentences[-1])
        
        return ' '.join(summary_sentences[:max_sentences])
    
    def _chunk_content(self, text: str, chunk_size: int = 1000, 
                       overlap: int = 100) -> List[str]:
        """Разбиение контента на чанки для памяти"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Ищем конец предложения
            if end < len(text):
                # Ищем точку, вопрос или восклицательный знак
                for punct in '.!?\n':
                    punct_pos = text.rfind(punct, start, end)
                    if punct_pos > start:
                        end = punct_pos + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
        
        return chunks
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Получение статистики обучения"""
        total_words = sum(s.get('word_count', 0) for s in self.learned_sources)
        
        by_type = {}
        by_category = {}
        
        for source in self.learned_sources:
            source_type = source.get('source_type', 'unknown')
            category = source.get('category', 'unknown')
            
            by_type[source_type] = by_type.get(source_type, 0) + 1
            by_category[category] = by_category.get(category, 0) + 1
        
        return {
            "total_sources": len(self.learned_sources),
            "total_words": total_words,
            "by_type": by_type,
            "by_category": by_category,
            "recent": self.learned_sources[-5:] if self.learned_sources else []
        }
    
    def get_learned_topics(self) -> List[str]:
        """Получение списка изученных тем"""
        return [s.get('title', 'Unknown') for s in self.learned_sources]


# Тестирование
async def test_extractor():
    """Тест извлечения контента"""
    extractor = ContentExtractor()
    
    # Тест файла
    print("=== Тест файла ===")
    try:
        content = await extractor.extract("README.md")
        print(f"✓ {content.title}: {content.word_count} слов")
    except Exception as e:
        print(f"✗ Файл: {e}")
    
    # Тест URL
    print("\n=== Тест URL ===")
    try:
        content = await extractor.extract("https://docs.python.org/3/library/asyncio.html")
        print(f"✓ {content.title}: {content.word_count} слов")
        print(f"  Превью: {content.content[:200]}...")
    except Exception as e:
        print(f"✗ URL: {e}")


if __name__ == "__main__":
    asyncio.run(test_extractor())
