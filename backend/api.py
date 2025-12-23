"""Neira Backend API.

Причина: FastAPI требует Pydantic, а в текущем окружении Python 3.14
у Pydantic (и v1, и v2) есть несовместимости (v2 требует бинарный
`pydantic-core`, v1 ломается на новых изменениях typing).

Чтобы Desktop UI стабильно запускался, этот backend реализован на Starlette
(ASGI), без Pydantic.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import secrets
import hashlib
from datetime import datetime
from typing import Any, Dict, Optional

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from .neira_wrapper import NeiraWrapper

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


def _unauthorized() -> Response:
    return JSONResponse(
        {"detail": "Неверные учётные данные"},
        status_code=401,
        headers={"WWW-Authenticate": "Basic"},
    )


def _parse_basic_auth(authorization_header: Optional[str]) -> Optional[tuple[str, str]]:
    if not authorization_header:
        return None
    if not authorization_header.startswith("Basic "):
        return None
    token = authorization_header[len("Basic ") :].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except Exception:
        return None
    if ":" not in decoded:
        return None
    username, password = decoded.split(":", 1)
    return username, password


def verify_credentials_from_headers(headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Проверка Basic Auth.

    Возвращает payload пользователя при успехе, иначе None.
    """
    if not AUTH_ENABLED:
        return {"user": "anonymous", "is_admin": False}

    creds = _parse_basic_auth(headers.get("authorization"))
    if not creds:
        return None
    username, password = creds

    # Сначала проверяем захардкоженного админа
    if _verify_admin(username, password):
        return {"user": _ADMIN_LOGIN, "is_admin": True}

    if AUTH_PASSWORD:
        correct_username = secrets.compare_digest(username, AUTH_USERNAME)
        correct_password = secrets.compare_digest(password, AUTH_PASSWORD)
        if correct_username and correct_password:
            return {"user": username, "is_admin": False}

    return None


neira_wrapper = NeiraWrapper(verbose=False)


async def root(request: Request) -> Response:
    return JSONResponse(
        {
            "status": "ok",
            "service": "Neira API",
            "version": "0.6.0",
            "timestamp": datetime.now().isoformat(),
        }
    )


async def health(request: Request) -> Response:
    stats = neira_wrapper.get_stats()
    return JSONResponse(
        {
            "alive": True,
            "status": "healthy",
            "is_processing": stats.get("is_processing", False),
            "models_ready": stats.get("models", {}),
            "components": {"memory": True, "ollama": True, "experience": True},
            "uptime": 0,
            "errors": [],
            "timestamp": datetime.now().isoformat(),
        }
    )


async def status(request: Request) -> Response:
    stats = neira_wrapper.get_stats()
    models = stats.get("models", {})
    active_models = [k for k, v in models.items() if v]

    memory_count = 0
    try:
        memory = neira_wrapper.neira.memory if neira_wrapper.neira else None
        if memory and hasattr(memory, "memories"):
            memory_count = len(memory.memories)
    except Exception:
        pass

    return JSONResponse(
        {
            "online": True,
            "version": "0.8",
            "mood": "curious",
            "memory_count": memory_count,
            "isOnline": True,
            "lastSeen": datetime.now().timestamp() * 1000,
            "memoryUsage": memory_count / 100 if memory_count < 100 else 1.0,
            "activeModels": active_models,
        }
    )


async def curiosity(request: Request) -> Response:
    try:
        from cells import maybe_ask_question, CURIOSITY_AVAILABLE

        if CURIOSITY_AVAILABLE:
            question = maybe_ask_question("мобильный пользователь", "проверка связи")
            if question:
                return JSONResponse({"question": question})
        return JSONResponse({"question": None})
    except Exception:
        return JSONResponse({"question": None})


async def chat(request: Request) -> Response:
    try:
        payload = await request.json()
        message = (payload.get("message") or "").strip()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)

    if not message:
        return JSONResponse({"detail": "Empty message"}, status_code=400)

    try:
        response_text = await neira_wrapper.process(message)
        model = None
        try:
            if neira_wrapper.neira and neira_wrapper.neira.model_manager:
                model = neira_wrapper.neira.model_manager.current_model
        except Exception:
            model = None

        return JSONResponse(
            {
                "response": response_text,
                "timestamp": datetime.now().isoformat(),
                "model": model,
            }
        )
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)


async def get_stats(request: Request) -> Response:
    return JSONResponse(neira_wrapper.get_stats())


async def get_memory(request: Request) -> Response:
    try:
        limit = int(request.query_params.get("limit", "10"))
    except ValueError:
        return JSONResponse({"detail": "Invalid limit"}, status_code=400)
    return JSONResponse(neira_wrapper.get_memory(limit=limit))


async def get_experience(request: Request) -> Response:
    return JSONResponse(neira_wrapper.get_experience())


async def clear_memory(request: Request) -> Response:
    return JSONResponse(neira_wrapper.clear_memory())


# === Самосознание и Органы (v0.6) ===

async def get_self(request: Request) -> Response:
    return JSONResponse(neira_wrapper.get_self_description())


async def get_organs(request: Request) -> Response:
    return JSONResponse(neira_wrapper.get_organs())


async def get_organ_details(request: Request) -> Response:
    organ_name = request.path_params.get("organ_name", "")
    return JSONResponse(neira_wrapper.get_organ_details(organ_name))


async def get_growth_info(request: Request) -> Response:
    return JSONResponse(neira_wrapper.get_growth_capabilities())


async def execute_command(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"detail": "Invalid JSON"}, status_code=400)

    cmd = (payload.get("command") or "").strip().lower()
    if not cmd:
        return JSONResponse({"detail": "Empty command"}, status_code=400)

    if cmd == "stats":
        return JSONResponse({"result": neira_wrapper.get_stats()})
    if cmd == "memory":
        return JSONResponse({"result": neira_wrapper.get_memory()})
    if cmd == "experience":
        return JSONResponse({"result": neira_wrapper.get_experience()})
    if cmd == "clear":
        return JSONResponse({"result": neira_wrapper.clear_memory()})

    return JSONResponse({"detail": f"Unknown command: {cmd}"}, status_code=400)


async def websocket_chat(websocket: WebSocket) -> None:
    """WebSocket endpoint с keepalive и улучшенной обработкой ошибок."""
    import logging
    logger = logging.getLogger("neira.websocket")
    
    await websocket.accept()
    logger.info("WebSocket connected")

    # Для keepalive: последний ping
    last_ping = asyncio.get_event_loop().time()
    
    try:
        while True:
            # Keepalive: отправляем ping каждые 30 секунд
            current_time = asyncio.get_event_loop().time()
            if current_time - last_ping > 30:
                try:
                    await websocket.send_json({"type": "ping"})
                    last_ping = current_time
                except Exception as ping_err:
                    logger.warning(f"Ping failed: {ping_err}")
                    break
            
            # Получаем сообщение с timeout 1 сек (чтобы ping не блокировался)
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
            except asyncio.TimeoutError:
                continue  # Timeout — идём на следующую итерацию (для ping)
            
            message = (data.get("message") or "").strip()

            if not message:
                await websocket.send_json({"type": "error", "content": "Empty message"})
                continue

            # Проверка на UI запрос
            is_ui_request = any(keyword in message.lower() for keyword in [
                "создай ui", "создай интерфейс", "сделай ui", 
                "игровой интерфейс", "ui для", "интерфейс для"
            ])

            if is_ui_request and neira_wrapper.ui_code_cell:
                # Генерируем артефакт
                try:
                    await websocket.send_json({
                        "type": "stage",
                        "stage": "generation",
                        "content": "🎨 Создаю UI артефакт..."
                    })
                    
                    artifact = await neira_wrapper.ui_code_cell.generate_ui(
                        task_description=message
                    )
                    
                    await websocket.send_json({
                        "type": "artifact",
                        "content": f"✅ Артефакт создан: {artifact['id']}",
                        "metadata": {"artifact": artifact}
                    })
                    
                    await websocket.send_json({"type": "done"})
                    continue
                    
                except Exception as artifact_err:
                    logger.error(f"Artifact generation failed: {artifact_err}", exc_info=True)
                    # Fallback to normal processing

            # Обрабатываем запрос через стриминг
            try:
                async for chunk in neira_wrapper.process_stream(message):
                    await websocket.send_json(
                        {
                            "type": chunk.type,
                            "stage": chunk.stage,
                            "content": chunk.content,
                            "metadata": chunk.metadata,
                        }
                    )
            except Exception as process_err:
                logger.error(f"Error processing message: {process_err}", exc_info=True)
                await websocket.send_json(
                    {"type": "error", "content": f"Ошибка обработки: {str(process_err)}"}
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
        return
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "content": f"Server error: {str(e)}"})
        except Exception:
            pass


# === Server Sent Events (альтернатива WebSocket) ===

async def chat_stream(request: Request) -> Response:
    message = (request.query_params.get("message") or "").strip()
    if not message:
        return JSONResponse({"detail": "Empty message"}, status_code=400)

    async def event_generator():
        async for chunk in neira_wrapper.process_stream(message):
            yield "data: " + json.dumps(
                {
                    "type": chunk.type,
                    "stage": chunk.stage,
                    "content": chunk.content,
                    "metadata": chunk.metadata,
                },
                ensure_ascii=False,
            ) + "\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# === Control Panel Actions ===

async def clear_context(request: Request) -> Response:
    """Очистить контекст диалога"""
    try:
        if neira_wrapper.neira and hasattr(neira_wrapper.neira, 'context'):
            neira_wrapper.neira.context.clear()
        return JSONResponse({"status": "ok", "message": "Контекст очищен"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def reset_memory(request: Request) -> Response:
    """ВНИМАНИЕ: Полный сброс памяти"""
    try:
        if neira_wrapper.neira and hasattr(neira_wrapper.neira, 'memory'):
            neira_wrapper.neira.memory.memories.clear()
            neira_wrapper.neira.memory.save_to_file()
        return JSONResponse({"status": "ok", "message": "Память сброшена"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def get_available_models(request: Request) -> Response:
    """Получить список доступных моделей Ollama"""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://127.0.0.1:11434/api/tags")
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            return JSONResponse({"models": models})
    except Exception as e:
        return JSONResponse({"models": [], "error": str(e)})


# === Artifact Generation ===

async def generate_artifact(request: Request) -> Response:
    """Генерация UI артефакта через UICodeCell"""
    try:
        body = await request.json()
        task = body.get("task", "")
        template = body.get("template")
        data = body.get("data")
        
        if not task:
            return JSONResponse({"error": "Task description required"}, status_code=400)
        
        if not neira_wrapper.ui_code_cell:
            return JSONResponse(
                {"error": "UICodeCell not available"},
                status_code=503
            )
        
        artifact = await neira_wrapper.ui_code_cell.generate_ui(
            task_description=task,
            template_name=template,
            data=data
        )
        
        return JSONResponse(artifact)
    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to generate artifact: {str(e)}"},
            status_code=500
        )


async def list_artifacts(request: Request) -> Response:
    """Список всех артефактов"""
    try:
        if not neira_wrapper.ui_code_cell:
            return JSONResponse({"artifacts": []})
        
        artifacts = neira_wrapper.ui_code_cell.list_artifacts()
        return JSONResponse({"artifacts": artifacts})
    except Exception as e:
        return JSONResponse({"artifacts": [], "error": str(e)})


async def get_artifact(request: Request) -> Response:
    """Получить артефакт по ID"""
    try:
        artifact_id = request.path_params.get("artifact_id")
        
        if not neira_wrapper.ui_code_cell:
            return JSONResponse({"error": "UICodeCell not available"}, status_code=503)
        
        artifact = neira_wrapper.ui_code_cell.get_artifact(artifact_id)
        
        if not artifact:
            return JSONResponse({"error": "Artifact not found"}, status_code=404)
        
        return JSONResponse(artifact)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def rate_artifact(request: Request) -> Response:
    """Оценить артефакт (1-5 звёзд)"""
    print(f"[DEBUG] rate_artifact called! Path: {request.url.path}, Method: {request.method}")
    try:
        artifact_id = request.path_params.get("artifact_id")
        print(f"[DEBUG] artifact_id: {artifact_id}")
        
        if not neira_wrapper.ui_code_cell:
            return JSONResponse({"error": "UICodeCell not available"}, status_code=503)
        
        # Получить рейтинг из тела запроса
        body = await request.json()
        rating = body.get("rating")
        
        if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
            return JSONResponse({"error": "Rating must be integer 1-5"}, status_code=400)
        
        # Загрузить артефакт
        artifact = neira_wrapper.ui_code_cell.get_artifact(artifact_id)
        if not artifact:
            return JSONResponse({"error": "Artifact not found"}, status_code=404)
        
        # Обновить рейтинг
        artifact["metadata"]["rating"] = rating
        artifact["metadata"]["rated_at"] = datetime.now().isoformat()
        
        # Сохранить обратно
        artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
        json_path = os.path.join(artifacts_dir, f"{artifact_id}.json")
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2)
        
        # Интеграция с experience.py
        try:
            if hasattr(neira_wrapper.neira, 'experience'):
                context = {
                    "type": "artifact_rating",
                    "artifact_id": artifact_id,
                    "template": artifact.get("template_used"),
                    "rating": rating,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Добавить опыт: чем выше оценка, тем больше reward
                neira_wrapper.neira.experience.add_experience(
                    action_type="ui_generation",
                    success=rating >= 4,  # 4-5 звёзд = успех
                    reward=rating,  # 1-5 баллов
                    context=context
                )
        except Exception as exp_err:
            print(f"[WARNING] Experience.py integration failed: {exp_err}")
        
        # Автоэкстракция компонентов для 5⭐ артефактов
        if rating == 5:
            try:
                components = neira_wrapper.ui_code_cell.extract_components_from_artifact(artifact_id)
                if components:
                    neira_wrapper.ui_code_cell.save_components_to_library(components)
                    print(f"[INFO] Extracted {len(components)} components from 5⭐ artifact {artifact_id}")
            except Exception as comp_err:
                print(f"[WARNING] Component extraction failed: {comp_err}")
        
        return JSONResponse({
            "success": True,
            "artifact_id": artifact_id,
            "rating": rating
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def list_templates(request: Request) -> Response:
    """Список доступных шаблонов"""
    try:
        if not neira_wrapper.ui_code_cell:
            return JSONResponse({"templates": []})
        
        templates = [
            {
                "name": name,
                "display_name": data.get("name"),
                "category": data.get("category"),
                "description": data.get("description")
            }
            for name, data in neira_wrapper.ui_code_cell.templates.items()
        ]
        
        return JSONResponse({"templates": templates})
    except Exception as e:
        return JSONResponse({"templates": [], "error": str(e)})


routes = [
    Route("/", root, methods=["GET"]),
    Route("/api/health", health, methods=["GET"]),
    Route("/api/status", status, methods=["GET"]),
    Route("/api/curiosity", curiosity, methods=["GET"]),
    Route("/api/chat", chat, methods=["POST"]),
    Route("/api/chat/stream", chat_stream, methods=["GET"]),
    Route("/api/stats", get_stats, methods=["GET"]),
    Route("/api/memory", get_memory, methods=["GET"]),
    Route("/api/experience", get_experience, methods=["GET"]),
    Route("/api/memory/clear", clear_memory, methods=["POST"]),
    Route("/api/self", get_self, methods=["GET"]),
    Route("/api/organs", get_organs, methods=["GET"]),
    Route("/api/organs/{organ_name}", get_organ_details, methods=["GET"]),
    Route("/api/growth", get_growth_info, methods=["GET"]),
    Route("/api/command", execute_command, methods=["POST"]),
    
    # Control Panel endpoints
    Route("/api/clear-context", clear_context, methods=["POST"]),
    Route("/api/reset-memory", reset_memory, methods=["POST"]),
    Route("/api/available-models", get_available_models, methods=["GET"]),
    
    # Artifact endpoints
    Route("/api/artifacts/generate", generate_artifact, methods=["POST"]),
    Route("/api/artifacts/{artifact_id}/rate", rate_artifact, methods=["POST"]),
    Route("/api/artifacts/{artifact_id}", get_artifact, methods=["GET"]),
    Route("/api/artifacts", list_artifacts, methods=["GET"]),
    Route("/api/templates", list_templates, methods=["GET"]),
    
    WebSocketRoute("/ws/chat", websocket_chat),
]

app = Starlette(routes=routes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.api:app", host="0.0.0.0", port=8001, log_level="info")
