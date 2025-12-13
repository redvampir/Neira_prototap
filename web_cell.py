"""
Neira Web Cell v0.3 — Поиск в интернете
Позволяет искать информацию и учиться из сети.

Использует DuckDuckGo (бесплатно, без API ключей).
pip install duckduckgo-search
"""

import importlib
import importlib.util

REQUESTS_AVAILABLE = importlib.util.find_spec("requests") is not None
if REQUESTS_AVAILABLE:
    import requests
else:
    class _RequestsStub:
        def post(self, *args, **kwargs):
            raise ImportError("requests не установлен")

    requests = _RequestsStub()
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# Попробуем импортировать duckduckgo
DDGS_AVAILABLE = importlib.util.find_spec("duckduckgo_search") is not None
if DDGS_AVAILABLE:
    from duckduckgo_search import DDGS
else:
    print("⚠️ duckduckgo-search не установлен. Выполни: pip install duckduckgo-search")

_cells_spec = importlib.util.find_spec("cells")
if _cells_spec is None:
    raise ImportError("Модуль cells обязателен для работы web_cell")

from cells import Cell, CellResult, MemoryCell, OLLAMA_URL, TIMEOUT  # type: ignore
_cells_module = importlib.import_module("cells")
_model_chat_spec = getattr(_cells_module, "MODEL_CHAT", None)
_model_reason_spec = getattr(_cells_module, "MODEL_REASON", None)
MODEL = _model_chat_spec or _model_reason_spec
if MODEL is None:
    raise ImportError("Не найдены MODEL_CHAT или MODEL_REASON в cells")


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
    
    def __init__(self, memory: Optional[MemoryCell] = None, model_manager=None):
        super().__init__(memory, model_manager)
        self.ddgs = DDGS() if DDGS_AVAILABLE else None

    def search(self, query: str, max_results: int = 5) -> Tuple[List[SearchResult], Dict[str, str]]:
        """Поиск в DuckDuckGo"""
        if not self.ddgs:
            reason = {
                "reason_code": "ddg_unavailable",
                "reason_detail": "duckduckgo-search не установлен"
            }
            print("❌ Поиск недоступен (установи duckduckgo-search)")
            return [], reason

        try:
            results = []
            for r in self.ddgs.text(query, max_results=max_results):
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", "")
                ))
            return results, {}
        except Exception as e:
            reason = {
                "reason_code": "ddg_error",
                "reason_detail": str(e)
            }
            print(f"❌ Ошибка поиска: {e}")
            return [], reason
    
    def search_and_summarize(self, query: str) -> CellResult:
        """Поиск + суммаризация результатов"""
        
        print(f"🔎 Ищу: {query}")
        results, reason = self.search(query)

        if not results:
            reason_code = reason.get("reason_code", "no_results")
            reason_detail = reason.get("reason_detail", "результатов нет")
            return CellResult(
                content=f"Не удалось найти информацию (причина: {reason_code}).",
                confidence=0.1,
                cell_name=self.name,
                metadata={
                    "query": query,
                    "reason_code": reason_code,
                    "reason_detail": reason_detail
                }
            )

        # Формируем контекст из результатов
        context = "Результаты поиска:\n\n"
        for i, r in enumerate(results, 1):
            context += f"{i}. **{r.title}**\n"
            context += f"   {r.snippet}\n"
            context += f"   Источник: {r.url}\n\n"

        if not REQUESTS_AVAILABLE:
            return CellResult(
                content="Не удалось получить сводку (причина: requests_missing).",
                confidence=0.05,
                cell_name=self.name,
                metadata={
                    "query": query,
                    "reason_code": "requests_missing",
                    "reason_detail": "requests не установлен",
                    "sources": [r.url for r in results],
                    "results_count": len(results)
                }
            )

        # Просим LLM обработать
        prompt = f"""Запрос пользователя: {query}

{context}

Проанализируй результаты и дай полезный ответ. Укажи источники."""

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "system": self.system_prompt,
                    "stream": False,
                    "options": {"temperature": 0.5, "num_predict": 2048}
                },
                timeout=TIMEOUT
            )
            answer = response.json().get("response", "")
        except Exception as e:
            return CellResult(
                content="Не удалось получить сводку (причина: requests_error).",
                confidence=0.05,
                cell_name=self.name,
                metadata={
                    "query": query,
                    "reason_code": "requests_error",
                    "reason_detail": str(e),
                    "sources": [r.url for r in results],
                    "results_count": len(results)
                }
            )

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
    
    def learn_topic(self, topic: str) -> Tuple[List[Dict], Dict[str, str]]:
        """Изучить тему и извлечь факты для памяти"""
        
        print(f"📖 Изучаю тему: {topic}")
        
        # Поиск
        results, reason = self.search(topic, max_results=7)
        if not results:
            return [], reason

        if not REQUESTS_AVAILABLE:
            return [], {
                "reason_code": "requests_missing",
                "reason_detail": "requests не установлен"
            }

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

        if not REQUESTS_AVAILABLE:
            return [], {
                "reason_code": "requests_missing",
                "reason_detail": "requests не установлен"
            }

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "system": "Ты — экстрактор знаний. Извлекай точные факты.",
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 1024}
                },
                timeout=TIMEOUT
            )
            result = response.json().get("response", "")
        except Exception as e:
            return [], {"reason_code": "requests_error", "reason_detail": str(e)}
        
        # Парсим JSON
        parse_error: Optional[str] = None
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
                return facts, {}
        except Exception as e:
            parse_error = str(e)
            print(f"⚠️ Ошибка парсинга: {parse_error}")

        return [], {"reason_code": "parse_error", "reason_detail": parse_error or "unknown"}
    
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

        facts, reason = self.searcher.learn_topic(topic)

        if not facts:
            reason_code = reason.get("reason_code", "no_results")
            return CellResult(
                content=f"Не удалось найти информацию по теме: {topic} (причина: {reason_code}).",
                confidence=0.2,
                cell_name=self.name,
                metadata={"topic": topic, **reason}
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

    cell = WebSearchCell()
    result = cell.process("Python dataclass примеры")
    print(f"\nРезультат:\n{result.content}")

    if result.metadata:
        print(f"Метаданные: {result.metadata}")
