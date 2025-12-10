"""
Neira Web Cell v0.3 — Поиск в интернете
Позволяет искать информацию и учиться из сети.

Использует DuckDuckGo (бесплатно, без API ключей).
pip install ddgs
"""

import requests
from typing import List, Dict, Optional
from dataclasses import dataclass

# Попробуем импортировать duckduckgo
try:
    from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    print("⚠️ ddgs не установлен. Выполни: pip install ddgs")

from cells import Cell, CellResult, MemoryCell, OLLAMA_URL, MODEL_REASON, TIMEOUT


@dataclass
class SearchResult:
    """Результат поиска"""
    title: str
    url: str
    snippet: str
    

class WebSearchCell(Cell):
    """Клетка поиска в интернете"""
    
    name = "web_search"
    system_prompt = """Ты — исследователь. Анализируй результаты поиска и извлекай полезную информацию.
Будь точной, указывай источники."""
    
    def __init__(self, memory: Optional[MemoryCell] = None):
        super().__init__(memory)
        self.ddgs = DDGS() if DDGS_AVAILABLE else None
    
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Поиск в DuckDuckGo"""
        if not self.ddgs:
            print("❌ Поиск недоступен (установи duckduckgo-search)")
            return []
        
        try:
            results = []
            for r in self.ddgs.text(query, max_results=max_results):
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", "")
                ))
            return results
        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")
            return []
    
    def search_and_summarize(self, query: str) -> CellResult:
        """Поиск + суммаризация результатов"""
        
        print(f"🔎 Ищу: {query}")
        results = self.search(query)
        
        if not results:
            return CellResult(
                content="Не удалось найти информацию.",
                confidence=0.1,
                cell_name=self.name
            )
        
        # Формируем контекст из результатов
        context = "Результаты поиска:\n\n"
        for i, r in enumerate(results, 1):
            context += f"{i}. **{r.title}**\n"
            context += f"   {r.snippet}\n"
            context += f"   Источник: {r.url}\n\n"
        
        # Просим LLM обработать
        prompt = f"""Запрос пользователя: {query}

{context}

Проанализируй результаты и дай полезный ответ. Укажи источники."""

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_REASON,
                "prompt": prompt,
                "system": self.system_prompt,
                "stream": False,
                "options": {"temperature": 0.5, "num_predict": 2048}
            },
            timeout=TIMEOUT
        )
        
        answer = response.json().get("response", "")
        
        return CellResult(
            content=answer,
            confidence=0.7,
            cell_name=self.name,
            metadata={
                "query": query,
                "sources": [r.url for r in results],
                "results_count": len(results)
            }
        )
    
    def learn_topic(self, topic: str) -> List[Dict]:
        """Изучить тему и извлечь факты для памяти"""
        
        print(f"📖 Изучаю тему: {topic}")
        
        # Поиск
        results = self.search(topic, max_results=7)
        if not results:
            return []
        
        # Собираем весь текст
        all_text = "\n".join([f"{r.title}: {r.snippet}" for r in results])
        
        # Извлекаем факты
        prompt = f"""Тема: {topic}

Информация из интернета:
{all_text}

Извлеки ключевые факты для запоминания.
Формат JSON:
{{"facts": [
    {{"text": "факт", "importance": 0.0-1.0}},
    ...
]}}

ТОЛЬКО JSON:"""

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_REASON,
                "prompt": prompt,
                "system": "Ты — экстрактор знаний. Извлекай точные факты.",
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 1024}
            },
            timeout=TIMEOUT
        )
        
        result = response.json().get("response", "")
        
        # Парсим JSON
        try:
            import json
            start = result.find("{")
            end = result.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(result[start:end])
                facts = data.get("facts", [])
                
                # Добавляем метаданные
                for fact in facts:
                    fact["source"] = "web"
                    fact["category"] = "learned"
                    fact["topic"] = topic
                
                print(f"📚 Извлечено фактов: {len(facts)}")
                return facts
        except Exception as e:
            print(f"⚠️ Ошибка парсинга: {e}")
        
        return []
    
    def process(self, query: str) -> CellResult:
        """Основной метод — поиск и ответ"""
        return self.search_and_summarize(query)


class WebLearnerCell(Cell):
    """Клетка обучения из интернета — ищет, учит, запоминает"""
    
    name = "web_learner"
    
    def __init__(self, memory: MemoryCell):
        super().__init__(memory)
        self.searcher = WebSearchCell(memory)
    
    def learn(self, topic: str) -> CellResult:
        """Изучить тему и сохранить в память"""
        
        facts = self.searcher.learn_topic(topic)
        
        if not facts:
            return CellResult(
                content=f"Не удалось найти информацию по теме: {topic}",
                confidence=0.2,
                cell_name=self.name
            )
        
        # Сохраняем в память
        saved = 0
        for fact in facts:
            if fact.get("importance", 0) >= 0.5:
                self.memory.remember(
                    text=fact["text"],
                    importance=fact.get("importance", 0.6),
                    category="learned",
                    source="web"
                )
                saved += 1
        
        summary = f"Изучена тема: {topic}\n"
        summary += f"Найдено фактов: {len(facts)}\n"
        summary += f"Сохранено в память: {saved}\n\n"
        summary += "Ключевые факты:\n"
        for fact in facts[:5]:
            summary += f"• {fact['text']}\n"
        
        return CellResult(
            content=summary,
            confidence=0.8,
            cell_name=self.name,
            metadata={"topic": topic, "facts_found": len(facts), "facts_saved": saved}
        )
    
    def process(self, topic: str) -> CellResult:
        return self.learn(topic)


# === ТЕСТ ===
if __name__ == "__main__":
    print("=" * 50)
    print("Тест WebSearchCell")
    print("=" * 50)
    
    if not DDGS_AVAILABLE:
        print("\n❌ Установи: pip install duckduckgo-search")
    else:
        cell = WebSearchCell()
        result = cell.process("Python dataclass примеры")
        print(f"\nРезультат:\n{result.content}")
