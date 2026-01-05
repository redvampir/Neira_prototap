import asyncio
import threading
import inspect
import logging
from typing import Any, Callable, Dict, List

logger = logging.getLogger("neira.eventbus")


class EventBus:
    def __init__(self):
        self._subs: Dict[str, List[Callable[..., Any]]] = {}

    def subscribe(self, event_name: str, callback: Callable[..., Any]) -> None:
        if event_name not in self._subs:
            self._subs[event_name] = []
        self._subs[event_name].append(callback)
        logger.debug("Subscribed to event %s: %s", event_name, callback)

    def emit(self, event_name: str, *args, **kwargs) -> None:
        """Emit an event. Subscribers may be sync or async callables.
        
        Простая реализация: вызываем подписчики синхронно в текущем потоке.
        - Для async-функций: пытаемся поставить coroutine в текущий loop (если есть),
          иначе выполняем через `asyncio.run` (блокирующе).
        - Для sync-функций: вызываем прямо (не порождаем новые потоки).
        Это быстрый патч для hot-registration; если потребуется более надёжная
        интеграция с основным asyncio loop — реализуем очередь и call_soon_threadsafe.
        """
        subs = list(self._subs.get(event_name, []))
        if not subs:
            return

        for cb in subs:
            try:
                if inspect.iscoroutinefunction(cb):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(cb(*args, **kwargs))
                    except RuntimeError:
                        # Нет запущенного event loop в этом потоке — выполним блокирующе
                        try:
                            asyncio.run(cb(*args, **kwargs))
                        except Exception:
                            logger.exception("Error running coroutine subscriber via asyncio.run")
                else:
                    # sync callable -> вызываем в текущем потоке
                    try:
                        cb(*args, **kwargs)
                    except Exception:
                        logger.exception("Error in sync event subscriber")
            except Exception:
                logger.exception("Error while emitting event '%s'", event_name)


def _safe_call(cb: Callable[..., Any], args, kwargs) -> None:
    try:
        cb(*args, **kwargs)
    except Exception:
        logger.exception("Error in event subscriber")


# Global bus instance
event_bus = EventBus()
