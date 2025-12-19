"""
Neira Wrapper v0.5 — Асинхронная обёртка для Backend API
Преобразует синхронный Neira в асинхронный интерфейс для FastAPI
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Добавляем parent directory в path для импорта Neira
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from main import Neira
from cells import get_model_status


@dataclass
class StreamChunk:
    """Chunk данных для стриминга"""
    type: str  # "stage" | "content" | "error" | "done"
    stage: Optional[str] = None  # "analysis" | "planning" | "execution" | "verification"
    content: str = ""
    metadata: Optional[Dict[str, Any]] = None


class NeiraWrapper:
    """
    Асинхронная обёртка над Neira для использования в FastAPI

    Преобразует синхронные вызовы в асинхронные и добавляет стриминг
    """

    def __init__(self, verbose: bool = False):
        """
        Args:
            verbose: Показывать отладочную информацию (False для API)
        """
        # Для backend отключаем фоновые watcher-потоки (они мешают чистому завершению
        # процесса и в консольных прогревах могут приводить к крешам/фаталам).
        os.environ.setdefault("NEIRA_ENABLE_CELL_WATCHER", "false")

        # Инициализируем Neira в отдельном потоке
        self.neira = Neira(verbose=verbose)
        self.is_processing = False

    async def process_stream(self, user_input: str) -> AsyncGenerator[StreamChunk, None]:
        """
        Обработка запроса с потоковым выводом

        Yields:
            StreamChunk с информацией о текущем этапе и прогрессе
        """
        if self.is_processing:
            yield StreamChunk(
                type="error",
                content="Neira уже обрабатывает другой запрос. Подождите завершения."
            )
            return

        self.is_processing = True

        try:
            # Этап 1: Анализ
            yield StreamChunk(
                type="stage",
                stage="analysis",
                content="Анализирую запрос...",
                metadata={"timestamp": datetime.now().isoformat()}
            )

            # Запускаем в executor для неблокирующего выполнения
            loop = asyncio.get_event_loop()

            # Симуляция прогресса (в будущем заменим на реальный streaming)
            await asyncio.sleep(0.5)

            # Этап 2: Планирование
            yield StreamChunk(
                type="stage",
                stage="planning",
                content="Составляю план действий..."
            )
            await asyncio.sleep(0.3)

            # Этап 3: Исполнение
            yield StreamChunk(
                type="stage",
                stage="execution",
                content="Выполняю задачу..."
            )

            # Основная обработка в отдельном потоке
            response = await loop.run_in_executor(
                None,
                self.neira.process,
                user_input
            )

            # Этап 4: Верификация (уже завершена в process)
            yield StreamChunk(
                type="stage",
                stage="verification",
                content="Проверяю результат..."
            )
            await asyncio.sleep(0.2)
            
            # Защита от пустого ответа
            if not response or not response.strip():
                yield StreamChunk(
                    type="error",
                    content="Не удалось сгенерировать ответ. Попробуйте переформулировать вопрос."
                )
                return

            # Финальный результат
            yield StreamChunk(
                type="content",
                content=response,
                metadata={
                    "timestamp": datetime.now().isoformat(),
                    "model": self.neira.model_manager.current_model if self.neira.model_manager else "unknown"
                }
            )

            yield StreamChunk(type="done", content="Готово")

        except Exception as e:
            yield StreamChunk(
                type="error",
                content=f"Ошибка при обработке: {str(e)}"
            )
        finally:
            self.is_processing = False

    async def process(self, user_input: str) -> str:
        """
        Простая обработка без стриминга (для REST API)

        Returns:
            Полный ответ Neira
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.neira.process,
            user_input
        )

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику системы"""
        try:
            stats_text = self.neira.cmd_stats()

            # Парсим текст статистики в структурированный формат
            status = get_model_status()

            result = {
                "timestamp": datetime.now().isoformat(),
                "is_processing": self.is_processing,
                "models": {
                    "local": {
                        "code": status.get("code_model_ready", False),
                        "reason": status.get("reason_model_ready", False),
                        "personality": status.get("personality_model_ready", False)
                    },
                    "cloud": {
                        "code": status.get("cloud_code_ready", False),
                        "universal": status.get("cloud_universal_ready", False),
                        "vision": status.get("cloud_vision_ready", False)
                    }
                },
                "memory": {
                    "total": self.neira.memory.get_stats().get("total", 0),
                    "session_context": len(self.neira.memory.session_context)
                }
            }

            # Добавляем данные ModelManager если доступен
            if self.neira.model_manager:
                manager_stats = self.neira.model_manager.get_stats()
                result["model_manager"] = {
                    "current_model": manager_stats.get("current_model"),
                    "switches": manager_stats.get("switches", 0),
                    "loaded_models": manager_stats.get("loaded_models", []),
                    "max_vram_gb": manager_stats.get("max_vram_gb", 8.0)
                }

            # Добавляем данные Experience если доступны
            if self.neira.experience:
                exp_stats = self.neira.experience.get_stats()
                result["experience"] = {
                    "total": exp_stats.get("total", 0),
                    "avg_score": exp_stats.get("avg_score", 0),
                    "by_type": exp_stats.get("by_type", {}),
                    "by_verdict": exp_stats.get("by_verdict", {})
                }

            return result

        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def get_memory(self, limit: int = 10) -> Dict[str, Any]:
        """
        Получить последние записи памяти

        Args:
            limit: Количество последних записей
        """
        try:
            memories = self.neira.memory.memories[-limit:]
            return {
                "total": len(self.neira.memory.memories),
                "recent": [
                    {
                        "text": m.text,
                        "timestamp": m.timestamp,
                        "importance": m.importance,
                        "category": m.category,
                        "source": m.source
                    }
                    for m in memories
                ],
                "stats": self.neira.memory.get_stats()
            }
        except Exception as e:
            return {"error": str(e)}

    def get_experience(self) -> Dict[str, Any]:
        """Получить данные опыта"""
        if not self.neira.experience:
            return {"error": "Experience system not available"}

        try:
            stats = self.neira.experience.get_stats()
            personality = self.neira.experience.personality

            return {
                "stats": stats,
                "personality": {
                    "name": personality.get("name"),
                    "version": personality.get("version"),
                    "traits": personality.get("traits", {}),
                    "strengths": personality.get("strengths", []),
                    "weaknesses": personality.get("weaknesses", []),
                    "insights": personality.get("insights", [])[-10:]  # Last 10
                }
            }
        except Exception as e:
            return {"error": str(e)}

    def clear_memory(self) -> Dict[str, str]:
        """Очистить память"""
        try:
            self.neira.memory.memories = []
            self.neira.memory.save()
            return {"status": "success", "message": "Memory cleared"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # === Самосознание и Органы (v0.6) ===

    def get_self_description(self) -> Dict[str, Any]:
        """Получить описание себя (самосознание)"""
        try:
            if self.neira.introspection:
                description = self.neira.introspection.get_self_description()
                organs_count = len(self.neira.introspection.organs)
                active_count = len([o for o in self.neira.introspection.organs.values() if o.status == "active"])
                
                return {
                    "description": description,
                    "summary": {
                        "total_organs": organs_count,
                        "active_organs": active_count,
                        "growing_organs": organs_count - active_count,
                        "has_evolution": self.neira.evolution is not None,
                        "has_experience": self.neira.experience is not None
                    }
                }
            return {"error": "Introspection cell not available"}
        except Exception as e:
            return {"error": str(e)}

    def get_organs(self) -> Dict[str, Any]:
        """Получить список всех органов"""
        try:
            if self.neira.introspection:
                organs = {}
                for key, organ in self.neira.introspection.organs.items():
                    organs[key] = {
                        "name": organ.name,
                        "file": organ.file,
                        "description": organ.description,
                        "capabilities": organ.capabilities,
                        "status": organ.status,
                        "uses_count": organ.uses_count
                    }
                return {
                    "organs": organs,
                    "total": len(organs),
                    "by_status": {
                        "active": len([o for o in organs.values() if o["status"] == "active"]),
                        "growing": len([o for o in organs.values() if o["status"] == "growing"]),
                        "dormant": len([o for o in organs.values() if o["status"] == "dormant"])
                    }
                }
            return {"error": "Introspection cell not available"}
        except Exception as e:
            return {"error": str(e)}

    def get_organ_details(self, organ_name: str) -> Dict[str, Any]:
        """Получить детали конкретного органа"""
        try:
            if self.neira.introspection:
                organ = self.neira.introspection.organs.get(organ_name)
                if organ:
                    return {
                        "name": organ.name,
                        "file": organ.file,
                        "description": organ.description,
                        "capabilities": organ.capabilities,
                        "status": organ.status,
                        "uses_count": organ.uses_count
                    }
                return {"error": f"Organ '{organ_name}' not found"}
            return {"error": "Introspection cell not available"}
        except Exception as e:
            return {"error": str(e)}

    def get_growth_capabilities(self) -> Dict[str, Any]:
        """Информация о возможностях роста"""
        try:
            if self.neira.introspection:
                return {
                    "capabilities": self.neira.introspection.get_growth_capabilities(),
                    "cell_factory_available": self.neira.evolution.cell_factory is not None if self.neira.evolution else False,
                    "can_grow": True
                }
            return {"error": "Introspection cell not available"}
        except Exception as e:
            return {"error": str(e)}


# === ТЕСТ ===
if __name__ == "__main__":
    async def test():
        print("Testing NeiraWrapper...")
        wrapper = NeiraWrapper(verbose=True)

        print("\n1. Testing stats...")
        stats = wrapper.get_stats()
        print(f"Stats: {stats}")

        print("\n2. Testing streaming...")
        async for chunk in wrapper.process_stream("Привет, как дела?"):
            print(f"[{chunk.type}] {chunk.stage or ''}: {chunk.content}")

    asyncio.run(test())
