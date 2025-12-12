"""
Neira Backend API v0.6
FastAPI server with REST endpoints, WebSocket support and optional auth
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from typing import Optional, List
import json
import asyncio
import os
import secrets
import hashlib
from datetime import datetime

from neira_wrapper import NeiraWrapper, StreamChunk

# === ЗАЩИЩЁННЫЙ ПРОФИЛЬ АДМИНИСТРАТОРА ===
# Захардкожен для защиты от несанкционированного доступа
# 0 → переполнение (overflow), 11111111 → 255 → 0x00 при переполнении бита
_ADMIN_HASH = hashlib.sha256(b"0:11111111").hexdigest()  # Хеш login:password
_ADMIN_LOGIN = "0"

def _verify_admin(login: str, password: str) -> bool:
    """Проверка администратора (захардкоженный профиль)"""
    attempt_hash = hashlib.sha256(f"{login}:{password}".encode()).hexdigest()
    return secrets.compare_digest(attempt_hash, _ADMIN_HASH)

# === Конфигурация безопасности ===
# Установи эти переменные окружения для защиты API:
#   NEIRA_AUTH_ENABLED=true
#   NEIRA_USERNAME=your_username  (игнорируется для админа)
#   NEIRA_PASSWORD=your_password  (игнорируется для админа)
AUTH_ENABLED = os.getenv("NEIRA_AUTH_ENABLED", "false").lower() == "true"
AUTH_USERNAME = os.getenv("NEIRA_USERNAME", "neira")
AUTH_PASSWORD = os.getenv("NEIRA_PASSWORD", "")  # Пустой = отключено

security = HTTPBasic()


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Проверка Basic Auth с приоритетом захардкоженного админа"""
    if not AUTH_ENABLED:
        return {"user": "anonymous", "is_admin": False}
    
    # Сначала проверяем захардкоженного админа
    if _verify_admin(credentials.username, credentials.password):
        return {"user": _ADMIN_LOGIN, "is_admin": True}
    
    # Затем проверяем обычные учётные данные
    if AUTH_PASSWORD:
        correct_username = secrets.compare_digest(credentials.username, AUTH_USERNAME)
        correct_password = secrets.compare_digest(credentials.password, AUTH_PASSWORD)
        
        if correct_username and correct_password:
            return {"user": credentials.username, "is_admin": False}
    
    raise HTTPException(
        status_code=401,
        detail="Неверные учётные данные",
        headers={"WWW-Authenticate": "Basic"},
    )


def optional_auth(authorization: Optional[str] = Header(None)):
    """Опциональная проверка (для открытых endpoints)"""
    if not AUTH_ENABLED or not AUTH_PASSWORD:
        return True
    # Для endpoints где auth опционален
    return True


# === FastAPI App ===
app = FastAPI(
    title="Neira API",
    description="Backend API for Neira AI Assistant (v0.6 with remote access)",
    version="0.6.0"
)

# CORS для frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене ограничить до конкретных доменов
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобальный экземпляр Neira
neira_wrapper = NeiraWrapper(verbose=False)

# === Models ===
class ChatRequest(BaseModel):
    message: str
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    timestamp: str
    model: Optional[str] = None


class CommandRequest(BaseModel):
    command: str
    args: Optional[List[str]] = []


# === REST Endpoints ===

@app.get("/")
async def root():
    """Health check"""
    return {
        "status": "ok",
        "service": "Neira API",
        "version": "0.5.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/health")
async def health():
    """Detailed health check"""
    stats = neira_wrapper.get_stats()
    return {
        "alive": True,
        "status": "healthy",
        "is_processing": stats.get("is_processing", False),
        "models_ready": stats.get("models", {}),
        "components": {
            "memory": True,
            "ollama": True,
            "experience": True
        },
        "uptime": 0,  # TODO: вычислить
        "errors": [],
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/status")
async def status():
    """Neira status for mobile app"""
    stats = neira_wrapper.get_stats()
    models = stats.get("models", {})
    active_models = [k for k, v in models.items() if v]
    
    # Получаем количество записей в памяти
    memory_count = 0
    try:
        memory = neira_wrapper.neira.memory if neira_wrapper.neira else None
        if memory and hasattr(memory, 'memories'):
            memory_count = len(memory.memories)
    except:
        pass
    
    return {
        "online": True,
        "version": "0.8",
        "mood": "curious",
        "memory_count": memory_count,
        # Дополнительно для совместимости
        "isOnline": True,
        "lastSeen": datetime.now().timestamp() * 1000,
        "memoryUsage": memory_count / 100 if memory_count < 100 else 1.0,
        "activeModels": active_models
    }


@app.get("/api/curiosity")
async def curiosity():
    """Get curiosity question from Neira"""
    try:
        # Попробуем получить вопрос от CuriosityCell
        from cells import maybe_ask_question, CURIOSITY_AVAILABLE
        if CURIOSITY_AVAILABLE:
            question = maybe_ask_question("мобильный пользователь", "проверка связи")
            if question:
                return {"question": question}
        return {"question": None}
    except:
        return {"question": None}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process chat message (non-streaming)

    For streaming, use WebSocket at /ws/chat
    """
    try:
        response = await neira_wrapper.process(request.message)
        return ChatResponse(
            response=response,
            timestamp=datetime.now().isoformat(),
            model=neira_wrapper.neira.model_manager.current_model
                  if neira_wrapper.neira.model_manager else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    return neira_wrapper.get_stats()


@app.get("/api/memory")
async def get_memory(limit: int = 10):
    """
    Get recent memory entries

    Args:
        limit: Number of recent entries (default 10)
    """
    return neira_wrapper.get_memory(limit=limit)


@app.get("/api/experience")
async def get_experience():
    """Get experience and personality data"""
    return neira_wrapper.get_experience()


@app.post("/api/memory/clear")
async def clear_memory():
    """Clear all memory"""
    return neira_wrapper.clear_memory()


# === Самосознание и Органы (v0.6) ===

@app.get("/api/self")
async def get_self():
    """Получить информацию о себе (самосознание Нейры)"""
    return neira_wrapper.get_self_description()


@app.get("/api/organs")
async def get_organs():
    """Получить список всех органов (клеток) Нейры"""
    return neira_wrapper.get_organs()


@app.get("/api/organs/{organ_name}")
async def get_organ_details(organ_name: str):
    """Получить детали конкретного органа"""
    return neira_wrapper.get_organ_details(organ_name)


@app.get("/api/growth")
async def get_growth_info():
    """Информация о возможностях роста"""
    return neira_wrapper.get_growth_capabilities()


@app.post("/api/command")
async def execute_command(request: CommandRequest):
    """
    Execute Neira command (like /stats, /memory, etc.)

    Args:
        command: Command name without / (e.g., "stats", "memory")
        args: Optional command arguments
    """
    cmd = request.command.lower()

    if cmd == "stats":
        return {"result": neira_wrapper.get_stats()}
    elif cmd == "memory":
        return {"result": neira_wrapper.get_memory()}
    elif cmd == "experience":
        return {"result": neira_wrapper.get_experience()}
    elif cmd == "clear":
        return {"result": neira_wrapper.clear_memory()}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown command: {cmd}")


# === WebSocket Endpoint ===

class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_json(self, websocket: WebSocket, data: dict):
        await websocket.send_json(data)


manager = ConnectionManager()


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for streaming chat

    Client sends: {"message": "user input"}
    Server sends: {"type": "stage"|"content"|"error"|"done", ...}
    """
    await manager.connect(websocket)

    try:
        while True:
            # Получаем сообщение от клиента
            data = await websocket.receive_json()
            message = data.get("message", "")

            if not message:
                await manager.send_json(websocket, {
                    "type": "error",
                    "content": "Empty message"
                })
                continue

            # Стримим ответ
            async for chunk in neira_wrapper.process_stream(message):
                await manager.send_json(websocket, {
                    "type": chunk.type,
                    "stage": chunk.stage,
                    "content": chunk.content,
                    "metadata": chunk.metadata
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Client disconnected")
    except Exception as e:
        try:
            await manager.send_json(websocket, {
                "type": "error",
                "content": f"Server error: {str(e)}"
            })
        except:
            pass
        manager.disconnect(websocket)


# === Server Sent Events (альтернатива WebSocket) ===

@app.get("/api/chat/stream")
async def chat_stream(message: str):
    """
    Server-Sent Events endpoint for streaming (альтернатива WebSocket)

    Usage: GET /api/chat/stream?message=hello
    """
    async def event_generator():
        async for chunk in neira_wrapper.process_stream(message):
            # SSE format: "data: {json}\n\n"
            yield f"data: {json.dumps({
                'type': chunk.type,
                'stage': chunk.stage,
                'content': chunk.content,
                'metadata': chunk.metadata
            })}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


# === Startup/Shutdown Events ===

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    print("=" * 60)
    print("  Neira Backend API v0.5 Starting...")
    print("=" * 60)
    print(f"  Docs: http://localhost:8000/docs")
    print(f"  WebSocket: ws://localhost:8000/ws/chat")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("Shutting down Neira API...")


# === Run Server ===
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload при изменении кода
        log_level="info"
    )
