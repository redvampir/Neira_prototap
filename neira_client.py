"""
NeiraClient v1.0 — Универсальный клиент для подключения к Neira Server

Используется всеми точками входа:
- Telegram Bot
- VS Code Extension (через neira_server.py который сам использует клиента для проверки)
- Desktop App
- CLI

Функции:
- Автозапуск сервера если не работает
- HTTP API для всех операций
- Проверка health
- Graceful fallback при ошибках
"""

import asyncio
import atexit
import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urljoin

import aiohttp
import requests

logger = logging.getLogger("NeiraClient")


# ============== Configuration ==============

DEFAULT_SERVER_HOST = os.getenv("NEIRA_SERVER_HOST", "localhost")
DEFAULT_SERVER_PORT = int(os.getenv("NEIRA_SERVER_PORT", "8765"))
DEFAULT_SERVER_URL = f"http://{DEFAULT_SERVER_HOST}:{DEFAULT_SERVER_PORT}"

# Таймауты
CONNECT_TIMEOUT = float(os.getenv("NEIRA_CLIENT_CONNECT_TIMEOUT", "5.0"))
REQUEST_TIMEOUT = float(os.getenv("NEIRA_CLIENT_REQUEST_TIMEOUT", "120.0"))
HEALTH_CHECK_TIMEOUT = float(os.getenv("NEIRA_CLIENT_HEALTH_TIMEOUT", "2.0"))

# Автозапуск
AUTO_START_SERVER = os.getenv("NEIRA_AUTO_START_SERVER", "true").lower() in ("true", "1", "yes")
SERVER_START_WAIT = float(os.getenv("NEIRA_SERVER_START_WAIT", "10.0"))
SERVER_SCRIPT = os.getenv("NEIRA_SERVER_SCRIPT", "neira_server.py")


# ============== Data Classes ==============

@dataclass
class NeiraResponse:
    """Ответ от Neira Server"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    
    @classmethod
    def from_json(cls, json_data: Dict) -> "NeiraResponse":
        return cls(
            success=json_data.get("success", False),
            data=json_data.get("data"),
            error=json_data.get("error"),
            request_id=json_data.get("request_id")
        )
    
    @classmethod
    def error_response(cls, error: str) -> "NeiraResponse":
        return cls(success=False, error=error)


@dataclass 
class ServerStatus:
    """Статус Neira Server"""
    online: bool
    neira_ready: bool = False
    version: str = ""
    uptime_seconds: float = 0
    requests_processed: int = 0
    error: Optional[str] = None


# ============== Server Process Manager ==============

class ServerProcessManager:
    """
    Управление процессом Neira Server
    
    - Запуск сервера
    - Остановка при выходе
    - Проверка статуса
    """
    
    _instance: Optional["ServerProcessManager"] = None
    _process: Optional[subprocess.Popen] = None
    _started_by_us: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def start_server(self, script_path: Optional[str] = None) -> bool:
        """
        Запустить Neira Server
        
        Returns:
            True если сервер запущен успешно
        """
        if self._process is not None and self._process.poll() is None:
            logger.info("Сервер уже запущен этим клиентом")
            return True
        
        # Определяем путь к скрипту
        if script_path is None:
            base_dir = Path(__file__).parent
            script_path = str(base_dir / SERVER_SCRIPT)
        
        if not Path(script_path).exists():
            logger.error(f"Скрипт сервера не найден: {script_path}")
            return False
        
        try:
            # Определяем Python интерпретатор
            python_exe = sys.executable
            
            # Запускаем сервер в фоне
            logger.info(f"🚀 Запуск Neira Server: {script_path}")
            
            # Создаём процесс
            # На Windows используем CREATE_NEW_PROCESS_GROUP для graceful shutdown
            kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "cwd": str(Path(script_path).parent),
            }
            
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True
            
            self._process = subprocess.Popen(
                [python_exe, script_path],
                **kwargs
            )
            
            self._started_by_us = True
            
            # Регистрируем cleanup при выходе
            atexit.register(self.stop_server)
            
            # Ждём пока сервер поднимется
            start_time = time.time()
            while time.time() - start_time < SERVER_START_WAIT:
                if self._check_server_health():
                    logger.info(f"✅ Neira Server запущен (PID: {self._process.pid})")
                    return True
                time.sleep(0.5)
            
            logger.error("⏱️ Timeout ожидания запуска сервера")
            self.stop_server()
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска сервера: {e}")
            return False
    
    def stop_server(self):
        """Остановить сервер если мы его запустили"""
        if self._process is None or not self._started_by_us:
            return
        
        if self._process.poll() is not None:
            # Уже завершился
            return
        
        try:
            logger.info(f"🛑 Останавливаем Neira Server (PID: {self._process.pid})")
            
            if sys.platform == "win32":
                # На Windows отправляем CTRL_BREAK_EVENT
                self._process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                # На Unix отправляем SIGTERM
                self._process.terminate()
            
            # Ждём завершения
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Сервер не завершился, принудительное завершение")
                self._process.kill()
            
            logger.info("✅ Сервер остановлен")
            
        except Exception as e:
            logger.warning(f"Ошибка остановки сервера: {e}")
        
        finally:
            self._process = None
            self._started_by_us = False
    
    def _check_server_health(self) -> bool:
        """Быстрая проверка доступности сервера"""
        try:
            response = requests.get(
                f"{DEFAULT_SERVER_URL}/health",
                timeout=HEALTH_CHECK_TIMEOUT
            )
            return response.status_code == 200
        except:
            return False
    
    @property
    def is_running(self) -> bool:
        """Проверить работает ли сервер запущенный нами"""
        if self._process is None:
            return False
        return self._process.poll() is None


# ============== Neira Client ==============

class NeiraClient:
    """
    Универсальный клиент для Neira Server
    
    Поддерживает:
    - Синхронные запросы (requests)
    - Асинхронные запросы (aiohttp)
    - Автозапуск сервера
    """
    
    def __init__(
        self,
        server_url: str = DEFAULT_SERVER_URL,
        auto_start: bool = AUTO_START_SERVER,
        user_id: Optional[str] = None
    ):
        self.server_url = server_url.rstrip("/")
        self.auto_start = auto_start
        self.user_id = user_id
        self.process_manager = ServerProcessManager()
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False
    
    # ============== Connection ==============
    
    def connect(self) -> bool:
        """
        Подключиться к серверу (синхронно)
        
        Returns:
            True если подключение успешно
        """
        # Проверяем доступность
        if self._check_health_sync():
            self._connected = True
            logger.info(f"✅ Подключено к Neira Server: {self.server_url}")
            return True
        
        # Пробуем автозапуск
        if self.auto_start:
            logger.info("🔄 Сервер недоступен, пробуем автозапуск...")
            if self.process_manager.start_server():
                self._connected = True
                return True
        
        logger.error(f"❌ Не удалось подключиться к Neira Server: {self.server_url}")
        return False
    
    async def connect_async(self) -> bool:
        """
        Подключиться к серверу (асинхронно)
        """
        # Проверяем доступность
        if await self._check_health_async():
            self._connected = True
            logger.info(f"✅ Подключено к Neira Server: {self.server_url}")
            return True
        
        # Автозапуск (синхронный, т.к. subprocess)
        if self.auto_start:
            logger.info("🔄 Сервер недоступен, пробуем автозапуск...")
            # Запускаем в executor чтобы не блокировать
            loop = asyncio.get_event_loop()
            started = await loop.run_in_executor(
                None, 
                self.process_manager.start_server
            )
            if started:
                self._connected = True
                return True
        
        logger.error(f"❌ Не удалось подключиться к Neira Server: {self.server_url}")
        return False
    
    def disconnect(self):
        """Отключиться от сервера"""
        self._connected = False
        if self._session:
            # Закрытие сессии должно быть асинхронным
            pass
    
    # ============== Health Check ==============
    
    def _check_health_sync(self) -> bool:
        """Синхронная проверка health"""
        try:
            response = requests.get(
                f"{self.server_url}/health",
                timeout=HEALTH_CHECK_TIMEOUT
            )
            return response.status_code == 200
        except:
            return False
    
    async def _check_health_async(self) -> bool:
        """Асинхронная проверка health"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.server_url}/health",
                    timeout=aiohttp.ClientTimeout(total=HEALTH_CHECK_TIMEOUT)
                ) as response:
                    return response.status == 200
        except:
            return False
    
    def get_status(self) -> ServerStatus:
        """Получить статус сервера (синхронно)"""
        try:
            response = requests.get(
                f"{self.server_url}/health",
                timeout=HEALTH_CHECK_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json().get("data", {})
                return ServerStatus(
                    online=True,
                    neira_ready=data.get("neira_ready", False),
                    version=data.get("version", ""),
                    uptime_seconds=data.get("uptime_seconds", 0),
                    requests_processed=data.get("requests_processed", 0)
                )
        except Exception as e:
            return ServerStatus(online=False, error=str(e))
        
        return ServerStatus(online=False, error="Unknown error")
    
    async def get_status_async(self) -> ServerStatus:
        """Получить статус сервера (асинхронно)"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.server_url}/health",
                    timeout=aiohttp.ClientTimeout(total=HEALTH_CHECK_TIMEOUT)
                ) as response:
                    if response.status == 200:
                        json_data = await response.json()
                        data = json_data.get("data", {})
                        return ServerStatus(
                            online=True,
                            neira_ready=data.get("neira_ready", False),
                            version=data.get("version", ""),
                            uptime_seconds=data.get("uptime_seconds", 0),
                            requests_processed=data.get("requests_processed", 0)
                        )
        except Exception as e:
            return ServerStatus(online=False, error=str(e))
        
        return ServerStatus(online=False, error="Unknown error")
    
    # ============== Core API ==============
    
    def chat(self, message: str, context: str = "") -> NeiraResponse:
        """
        Отправить сообщение в чат (синхронно)
        """
        return self._post_sync("/chat", {
            "message": message,
            "context": context,
            "user_id": self.user_id
        })
    
    async def chat_async(self, message: str, context: str = "") -> NeiraResponse:
        """
        Отправить сообщение в чат (асинхронно)
        """
        return await self._post_async("/chat", {
            "message": message,
            "context": context,
            "user_id": self.user_id
        })
    
    def explain(self, code: str, language: str = "", filename: str = "") -> NeiraResponse:
        """Объяснить код"""
        return self._post_sync("/explain", {
            "code": code,
            "language": language,
            "filename": filename
        })
    
    async def explain_async(self, code: str, language: str = "", filename: str = "") -> NeiraResponse:
        """Объяснить код (асинхронно)"""
        return await self._post_async("/explain", {
            "code": code,
            "language": language,
            "filename": filename
        })
    
    def generate(self, prompt: str, language: str = "python") -> NeiraResponse:
        """Сгенерировать код"""
        return self._post_sync("/generate", {
            "prompt": prompt,
            "language": language
        })
    
    async def generate_async(self, prompt: str, language: str = "python") -> NeiraResponse:
        """Сгенерировать код (асинхронно)"""
        return await self._post_async("/generate", {
            "prompt": prompt,
            "language": language
        })
    
    # ============== Autonomy API ==============
    
    def get_autonomy_stats(self) -> NeiraResponse:
        """Получить статистику автономности"""
        return self._get_sync("/autonomy/stats")
    
    async def get_autonomy_stats_async(self) -> NeiraResponse:
        """Получить статистику автономности (асинхронно)"""
        return await self._get_async("/autonomy/stats")
    
    # ============== Pathway API ==============
    
    def record_feedback(self, query: str, response: str, positive: bool) -> NeiraResponse:
        """
        Записать feedback для обучения pathways
        """
        return self._post_sync("/pathway/feedback", {
            "query": query,
            "response": response,
            "positive": positive,
            "user_id": self.user_id
        })
    
    async def record_feedback_async(self, query: str, response: str, positive: bool) -> NeiraResponse:
        """Записать feedback (асинхронно) - простая версия"""
        return await self._post_async("/pathway/feedback", {
            "query": query,
            "response": response,
            "feedback": "positive" if positive else "negative",
            "user_id": self.user_id
        })
    
    async def send_feedback_async(
        self,
        query: str,
        response: str,
        feedback: str,
        score: float = 0.5,
        user_id: Optional[str] = None,
        source: str = "client"
    ) -> Optional[Dict]:
        """
        Отправить полный feedback на сервер (Phase 2)
        
        Args:
            query: Текст запроса
            response: Текст ответа  
            feedback: 'positive', 'negative', 'neutral'
            score: Оценка 0.0-1.0
            user_id: ID пользователя
            source: Источник (telegram, vscode, etc)
            
        Returns:
            Ответ сервера или None при ошибке
        """
        result = await self._post_async("/pathway/feedback", {
            "query": query,
            "response": response,
            "feedback": feedback,
            "score": score,
            "user_id": user_id or self.user_id,
            "source": source
        })
        
        if result.success:
            return {"success": True, "data": result.data}
        return None
    
    # ============== HTTP Helpers ==============
    
    def _post_sync(self, endpoint: str, data: Dict) -> NeiraResponse:
        """Синхронный POST запрос"""
        if not self._connected and not self.connect():
            return NeiraResponse.error_response("Neira Server недоступен")
        
        try:
            response = requests.post(
                f"{self.server_url}{endpoint}",
                json=data,
                timeout=REQUEST_TIMEOUT
            )
            return NeiraResponse.from_json(response.json())
        except requests.exceptions.Timeout:
            return NeiraResponse.error_response("Timeout запроса к серверу")
        except requests.exceptions.ConnectionError:
            self._connected = False
            return NeiraResponse.error_response("Потеряно соединение с сервером")
        except Exception as e:
            return NeiraResponse.error_response(f"Ошибка запроса: {e}")
    
    def _get_sync(self, endpoint: str) -> NeiraResponse:
        """Синхронный GET запрос"""
        if not self._connected and not self.connect():
            return NeiraResponse.error_response("Neira Server недоступен")
        
        try:
            response = requests.get(
                f"{self.server_url}{endpoint}",
                timeout=REQUEST_TIMEOUT
            )
            return NeiraResponse.from_json(response.json())
        except requests.exceptions.Timeout:
            return NeiraResponse.error_response("Timeout запроса к серверу")
        except requests.exceptions.ConnectionError:
            self._connected = False
            return NeiraResponse.error_response("Потеряно соединение с сервером")
        except Exception as e:
            return NeiraResponse.error_response(f"Ошибка запроса: {e}")
    
    async def _post_async(self, endpoint: str, data: Dict) -> NeiraResponse:
        """Асинхронный POST запрос"""
        if not self._connected and not await self.connect_async():
            return NeiraResponse.error_response("Neira Server недоступен")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}{endpoint}",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                ) as response:
                    json_data = await response.json()
                    return NeiraResponse.from_json(json_data)
        except asyncio.TimeoutError:
            return NeiraResponse.error_response("Timeout запроса к серверу")
        except aiohttp.ClientError:
            self._connected = False
            return NeiraResponse.error_response("Потеряно соединение с сервером")
        except Exception as e:
            return NeiraResponse.error_response(f"Ошибка запроса: {e}")
    
    async def _get_async(self, endpoint: str) -> NeiraResponse:
        """Асинхронный GET запрос"""
        if not self._connected and not await self.connect_async():
            return NeiraResponse.error_response("Neira Server недоступен")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.server_url}{endpoint}",
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                ) as response:
                    json_data = await response.json()
                    return NeiraResponse.from_json(json_data)
        except asyncio.TimeoutError:
            return NeiraResponse.error_response("Timeout запроса к серверу")
        except aiohttp.ClientError:
            self._connected = False
            return NeiraResponse.error_response("Потеряно соединение с сервером")
        except Exception as e:
            return NeiraResponse.error_response(f"Ошибка запроса: {e}")


# ============== Global Instance ==============

_client: Optional[NeiraClient] = None


def get_client(user_id: Optional[str] = None) -> NeiraClient:
    """Получить глобальный экземпляр клиента"""
    global _client
    if _client is None:
        _client = NeiraClient(user_id=user_id)
    elif user_id and _client.user_id != user_id:
        _client.user_id = user_id
    return _client


# ============== Test ==============

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Тест NeiraClient")
    print("=" * 50)
    
    client = get_client(user_id="test_user")
    
    # Проверяем статус
    status = client.get_status()
    print(f"Статус сервера: {'✅ Online' if status.online else '❌ Offline'}")
    
    if status.online:
        print(f"  • Neira ready: {status.neira_ready}")
        print(f"  • Version: {status.version}")
        print(f"  • Uptime: {status.uptime_seconds:.0f}s")
        print(f"  • Requests: {status.requests_processed}")
    else:
        print(f"  • Error: {status.error}")
        
        if AUTO_START_SERVER:
            print("\n🔄 Пробуем подключиться (с автозапуском)...")
            if client.connect():
                print("✅ Подключено!")
                status = client.get_status()
                print(f"  • Neira ready: {status.neira_ready}")
    
    # Тест chat (если подключено)
    if client._connected:
        print("\n" + "=" * 50)
        print("Тест /chat...")
        response = client.chat("Привет! Как дела?")
        if response.success:
            print(f"✅ Ответ: {response.data.get('response', '')[:100]}...")
        else:
            print(f"❌ Ошибка: {response.error}")
    
    print("\n🎉 Тесты завершены!")
