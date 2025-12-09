# Desktop UI для Neira — Архитектурный план

## Проблема
Консольный интерфейс неудобен для работы:
- Нет визуализации процессов
- Сложно отслеживать историю
- Нет мониторинга моделей и VRAM
- Неудобно управлять настройками

## Решение: Desktop Application

### Вариант 1: **Web UI** (Рекомендуется)
**Стек**: FastAPI + WebSocket + React/Vue

**Плюсы**:
- Быстрая разработка
- Кроссплатформенность (браузер)
- Можно упаковать в Electron позже
- Легко добавить мобильную версию

**Архитектура**:
```
┌─────────────────────────────────────────┐
│         Frontend (React/Vue)            │
│  - Чат-интерфейс                        │
│  - Панель моделей                       │
│  - Визуализация памяти                  │
└─────────────────────────────────────────┘
            │ WebSocket + REST API
            ↓
┌─────────────────────────────────────────┐
│      Backend (FastAPI)                  │
│  - WebSocket handler                    │
│  - REST endpoints                       │
│  - SSE для стриминга                    │
└─────────────────────────────────────────┘
            │
            ↓
┌─────────────────────────────────────────┐
│        Neira Core (main.py)             │
│  - Существующая логика                  │
│  - ModelManager                         │
│  - Memory/Experience                    │
└─────────────────────────────────────────┘
```

**Файловая структура**:
```
neira_ui/
├── backend/
│   ├── api.py              # FastAPI app
│   ├── websocket.py        # WebSocket handler
│   ├── neira_wrapper.py    # Обёртка над main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chat.tsx           # Чат-интерфейс
│   │   │   ├── ModelMonitor.tsx   # Панель моделей
│   │   │   ├── MemoryView.tsx     # Визуализация памяти
│   │   │   └── Settings.tsx       # Настройки
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

---

### Вариант 2: **PyQt6** (Нативное приложение)
**Стек**: PyQt6 + Python

**Плюсы**:
- Нативный UI
- Прямая интеграция с Python кодом
- Не нужен браузер

**Минусы**:
- Сложнее разработка UI
- Привязка к платформе

---

### Вариант 3: **Electron** (Desktop-первичный)
**Стек**: Electron + React + Python backend

**Плюсы**:
- Настоящее desktop приложение
- Богатая экосистема

**Минусы**:
- Тяжелый (~150MB минимум)
- Двойная упаковка (Node.js + Python)

---

## Рекомендуемый план: Web UI → Electron (опционально)

### Фаза 1: Backend API (FastAPI)

**api.py**:
```python
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from neira_wrapper import NeiraWrapper
import asyncio

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

neira = NeiraWrapper()

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            # Stream response
            async for chunk in neira.process_stream(message):
                await websocket.send_json({
                    "type": "chunk",
                    "content": chunk
                })
    except:
        pass

@app.get("/api/stats")
async def get_stats():
    return neira.get_stats()

@app.get("/api/memory")
async def get_memory():
    return neira.get_memory()

@app.get("/api/models")
async def get_models():
    return neira.get_model_status()
```

**neira_wrapper.py**:
```python
from main import Neira
import asyncio

class NeiraWrapper:
    def __init__(self):
        self.neira = Neira(verbose=False)

    async def process_stream(self, user_input: str):
        """Stream response chunks"""
        # Модифицированная версия process() с yield
        yield {"stage": "analysis", "content": "Анализирую..."}
        # ... остальные этапы

    def get_stats(self):
        return self.neira.cmd_stats()

    def get_memory(self):
        return {
            "total": len(self.neira.memory.memories),
            "recent": [m.to_dict() for m in self.neira.memory.memories[-10:]]
        }
```

---

### Фаза 2: Frontend (React + TypeScript)

**Компоненты**:

1. **Chat.tsx** — основной чат
```tsx
interface Message {
  role: 'user' | 'neira';
  content: string;
  timestamp: string;
}

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const ws = useWebSocket('ws://localhost:8000/ws/chat');

  const sendMessage = () => {
    ws.send(input);
    setMessages(prev => [...prev, {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    }]);
    setInput('');
  };

  // Render chat UI
  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((msg, i) => (
          <Message key={i} {...msg} />
        ))}
      </div>
      <input value={input} onChange={e => setInput(e.target.value)} />
    </div>
  );
}
```

2. **ModelMonitor.tsx** — мониторинг моделей
```tsx
export function ModelMonitor() {
  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: () => fetch('/api/stats').then(r => r.json()),
    refetchInterval: 2000
  });

  return (
    <div className="model-monitor">
      <h3>Model Status</h3>
      <div>Current: {stats?.current_model}</div>
      <div>Switches: {stats?.switches}</div>
      <div>VRAM: {stats?.loaded_models.join(', ')}</div>
    </div>
  );
}
```

3. **MemoryView.tsx** — визуализация памяти
```tsx
export function MemoryView() {
  // График важности воспоминаний
  // Список последних записей
  // Поиск по памяти
}
```

---

### Фаза 3: Стриминг ответов

**Модификация Executor для стриминга**:
```python
# executor.py
async def process_stream(self, input_data: str, plan: str,
                        extra_context: str = ""):
    """Stream output по мере генерации"""
    # Используем streaming Ollama API
    response = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "stream": True},
        stream=True
    )

    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)
            yield chunk.get("response", "")
```

---

## UI Дизайн (Wireframe)

```
┌────────────────────────────────────────────────────────────┐
│  Neira v0.5                    [☁️ cloud_code] [⚙️ Settings] │
├────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────┐  ┌────────────────────────┐   │
│  │     Chat Area           │  │   Model Monitor        │   │
│  │                         │  │  Current: mistral      │   │
│  │  User: Напиши функцию   │  │  Switches: 5           │   │
│  │  Neira: Конечно...      │  │  VRAM: 4.5/8GB         │   │
│  │  [Typing...]            │  │  ┌──────────────────┐  │   │
│  │                         │  │  │ mistral ████░░░  │  │   │
│  │                         │  │  │ code    ░░░░░░░  │  │   │
│  │                         │  │  └──────────────────┘  │   │
│  └─────────────────────────┘  └────────────────────────┘   │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  > Type message...                          [Send]    │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                              │
│  [💾 Memory: 42]  [📖 Experience: 15]  [⚡ Avg: 8.5/10]     │
└────────────────────────────────────────────────────────────┘
```

---

## Roadmap

**v0.6 — Backend API**:
- [ ] FastAPI app с REST endpoints
- [ ] WebSocket для чата
- [ ] Streaming responses
- [ ] API для статистики/памяти

**v0.7 — Базовый Frontend**:
- [ ] React app + Vite
- [ ] Чат-интерфейс
- [ ] Подключение к WebSocket
- [ ] Базовый UI

**v0.8 — Продвинутый UI**:
- [ ] Панель мониторинга моделей
- [ ] Визуализация памяти (графики)
- [ ] Настройки системы
- [ ] Темная/светлая тема

**v0.9 — Упаковка**:
- [ ] Docker образ (backend + frontend)
- [ ] Electron wrapper (опционально)
- [ ] Installers для Windows/Mac/Linux

---

## Технологии

**Backend**:
- FastAPI — API сервер
- WebSocket — real-time коммуникация
- asyncio — асинхронная обработка

**Frontend**:
- React 18 + TypeScript
- Vite — сборщик
- TailwindCSS — стили
- Recharts — графики
- Zustand — state management

**DevOps**:
- Docker Compose — локальная разработка
- GitHub Actions — CI/CD
- nginx — production reverse proxy

---

## Следующий шаг

Хочешь, чтобы я начал реализацию?

**Вариант А**: Сначала Backend API (FastAPI + WebSocket)
**Вариант Б**: Сразу простой Web UI на Flask + Jinja2 (быстрый прототип)
**Вариант В**: PyQt desktop app (нативное приложение)

Скажи, какой путь выбираем, и я начну проектировать детали!
