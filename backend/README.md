# Neira Backend API

REST API + WebSocket сервер для Neira AI Assistant.

Backend реализован на **Starlette (ASGI)** и запускается через **Uvicorn**.
Это сделано специально, чтобы не зависеть от Pydantic/FastAPI в окружениях,
где пакеты с бинарными расширениями могут не импортироваться (например, Python 3.14).

## Установка

```bash
# Установить зависимости
pip install -r requirements.txt
```

## Запуск

Важно: запускать нужно **из корня репозитория**, чтобы работали импорты:

```bash
uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Если порт `8000` занят (часто на Windows), используйте `8001`:

```bash
uvicorn backend.api:app --host 127.0.0.1 --port 8001
```

Быстрый рестарт Desktop UI на `8001`:

```powershell
./restart_desktop_8001.ps1
```

### Docker (будущее)
```bash
docker-compose up
```

После запуска доступно:
- **REST API**: http://localhost:8000/api/...
- **WebSocket**: ws://localhost:8000/ws/chat

---

## API Endpoints

### REST API

#### `GET /`
Health check
```bash
curl http://localhost:8000/
```

#### `GET /api/health`
Detailed health status
```bash
curl http://localhost:8000/api/health
```

#### `POST /api/chat`
Process message (non-streaming)
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Привет, Нейра!"}'
```

Response:
```json
{
  "response": "Привет! Чем могу помочь?",
  "timestamp": "2024-12-09T10:30:00",
  "model": "reason"
}
```

#### `GET /api/stats`
Get system statistics
```bash
curl http://localhost:8000/api/stats
```

Response:
```json
{
  "timestamp": "2024-12-09T10:30:00",
  "is_processing": false,
  "models": {
    "local": {
      "code": true,
      "reason": true,
      "personality": false
    },
    "cloud": {
      "code": true,
      "universal": true,
      "vision": false
    }
  },
  "model_manager": {
    "current_model": "reason",
    "switches": 15,
    "loaded_models": ["ministral-3:3b"],
    "max_vram_gb": 8.0
  },
  "memory": {
    "total": 42,
    "session_context": 10
  },
  "experience": {
    "total": 25,
    "avg_score": 8.5
  }
}
```

#### `GET /api/memory?limit=10`
Get recent memory entries
```bash
curl http://localhost:8000/api/memory?limit=5
```

#### `GET /api/experience`
Get experience and personality data
```bash
curl http://localhost:8000/api/experience
```

#### `POST /api/memory/clear`
Clear all memory
```bash
curl -X POST http://localhost:8000/api/memory/clear
```

---

### WebSocket API

#### `ws://localhost:8000/ws/chat`
Real-time streaming chat

**Client → Server** (JSON):
```json
{
  "message": "Напиши функцию для сортировки"
}
```

**Server → Client** (JSON stream):
```json
{"type": "stage", "stage": "analysis", "content": "Анализирую запрос..."}
{"type": "stage", "stage": "planning", "content": "Составляю план..."}
{"type": "stage", "stage": "execution", "content": "Выполняю..."}
{"type": "content", "content": "Вот функция сортировки..."}
{"type": "done", "content": "Готово"}
```

**Пример клиента (Python)**:
```python
import asyncio
import websockets
import json

async def test_chat():
    uri = "ws://localhost:8000/ws/chat"
    async with websockets.connect(uri) as websocket:
        # Отправляем сообщение
        await websocket.send(json.dumps({
            "message": "Привет, Нейра!"
        }))

        # Получаем стрим ответов
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            print(f"[{data['type']}] {data.get('content', '')}")

            if data['type'] == 'done':
                break

asyncio.run(test_chat())
```

**Пример клиента (JavaScript)**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onopen = () => {
  ws.send(JSON.stringify({ message: 'Привет!' }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`[${data.type}] ${data.content}`);

  if (data.type === 'done') {
    ws.close();
  }
};
```

---

### Server-Sent Events (SSE)

#### `GET /api/chat/stream?message=hello`
Alternative to WebSocket (one-way streaming)

**Пример (curl)**:
```bash
curl -N http://localhost:8000/api/chat/stream?message=Привет
```

**Пример (JavaScript)**:
```javascript
const eventSource = new EventSource(
  'http://localhost:8000/api/chat/stream?message=Привет'
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.content);

  if (data.type === 'done') {
    eventSource.close();
  }
};
```

---

## Архитектура

```
┌─────────────────────────────────────┐
│         Frontend (React)            │
└─────────────────────────────────────┘
            │ HTTP/WebSocket
            ↓
┌─────────────────────────────────────┐
│      FastAPI (api.py)               │
│  - REST endpoints                   │
│  - WebSocket handler                │
│  - SSE streaming                    │
└─────────────────────────────────────┘
            │
            ↓
┌─────────────────────────────────────┐
│   NeiraWrapper (neira_wrapper.py)   │
│  - Async interface                  │
│  - Streaming support                │
│  - Stats/Memory API                 │
└─────────────────────────────────────┘
            │
            ↓
┌─────────────────────────────────────┐
│     Neira Core (../main.py)         │
│  - ModelManager                     │
│  - Memory/Experience                │
│  - Cells (Analyzer, Executor, etc)  │
└─────────────────────────────────────┘
```

---

## Тестирование

### 1. Health Check
```bash
curl http://localhost:8000/api/health
```

### 2. Chat (REST)
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Как дела?"}'
```

### 3. Stats
```bash
curl http://localhost:8000/api/stats | jq
```

### 4. WebSocket (Python)
```python
# test_websocket.py
import asyncio
import websockets
import json

async def main():
    async with websockets.connect("ws://localhost:8000/ws/chat") as ws:
        await ws.send(json.dumps({"message": "Тест"}))
        async for msg in ws:
            data = json.loads(msg)
            print(f"{data['type']}: {data.get('content', '')}")
            if data['type'] == 'done':
                break

asyncio.run(main())
```

---

## Развёртывание

### systemd service
```ini
# /etc/systemd/system/neira-api.service
[Unit]
Description=Neira Backend API
After=network.target

[Service]
Type=simple
User=neira
WorkingDirectory=/path/to/Neira_prototap/backend
ExecStart=/usr/bin/uvicorn api:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### nginx reverse proxy
```nginx
server {
    listen 80;
    server_name neira.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

---

## Следующий шаг

После запуска backend можно:
1. Тестировать через curl/Postman
2. Начать разработку Frontend (React)
3. Интегрировать с Electron для desktop app

**Документация API**: http://localhost:8000/docs
