"""
Краткая инструкция для Нейры: как создавать многопользовательские игры
"""

MULTIPLAYER_PATTERN = """
# Паттерн создания многопользовательской игры

## Компоненты
1. **WebSocket Server** (Python) — синхронизация состояния
2. **HTML Client** (ui_code_cell) — игровой интерфейс
3. **GameRoom** — управление игроками и состоянием

## Server (multiplayer_server.py)

```python
import asyncio
import json
from starlette.applications import Starlette
from starlette.websockets import WebSocket
import uvicorn

class GameRoom:
    def __init__(self):
        self.players = {}  # {player_id: {name, position, score}}
        self.artifacts = []  # [{x, y, type}]
        self.connections = {}  # {player_id: websocket}
    
    async def broadcast(self, message: dict):
        '''Отправка всем подключенным игрокам'''
        for ws in self.connections.values():
            await ws.send_json(message)
    
    async def handle_join(self, player_id: str, name: str, ws: WebSocket):
        '''Добавление нового игрока'''
        self.players[player_id] = {
            'name': name,
            'x': random.randint(0, grid_size-1),
            'y': random.randint(0, grid_size-1),
            'score': 0
        }
        self.connections[player_id] = ws
        await self.broadcast({
            'action': 'player_joined',
            'player_id': player_id,
            'player': self.players[player_id]
        })

app = Starlette()

@app.websocket_route('/game')
async def game_endpoint(websocket: WebSocket):
    await websocket.accept()
    room_id = await websocket.receive_text()
    # Обработка сообщений...

uvicorn.run(app, host='0.0.0.0', port=8003)
```

## Client (HTML + WebSocket)

```javascript
// Подключение к серверу
const ws = new WebSocket('ws://localhost:8003/game');

ws.onopen = () => {
    ws.send(JSON.stringify({
        action: 'join',
        player_id: playerId,
        name: playerName,
        room_id: roomId
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    switch(data.action) {
        case 'player_joined':
            addPlayer(data.player_id, data.player);
            break;
        case 'player_moved':
            updatePlayerPosition(data.player_id, data.x, data.y);
            break;
        case 'chat':
            displayMessage(data.player_name, data.message);
            break;
    }
};

// Отправка движения
function move(direction) {
    ws.send(JSON.stringify({
        action: 'move',
        direction: direction
    }));
}
```

## UI Structure

```html
<div class="game-container">
    <!-- Игровое поле -->
    <div class="game-grid" id="gameGrid"></div>
    
    <!-- Список игроков -->
    <div class="players-panel">
        <h3>Игроки онлайн:</h3>
        <div id="playersList"></div>
    </div>
    
    <!-- Чат -->
    <div class="chat-panel">
        <div class="messages" id="messages"></div>
        <input type="text" id="chatInput" placeholder="Сообщение..." />
    </div>
</div>
```

## Ключевые принципы

### 1. Server Authoritative
- Клиент отправляет намерение (хочу двигаться)
- Сервер валидирует и обновляет состояние
- Сервер делает broadcast нового состояния

### 2. Broadcast Pattern
```python
async def broadcast(self, message):
    for ws in self.connections.values():
        try:
            await ws.send_json(message)
        except:
            # Удалить отключенного игрока
            pass
```

### 3. Real-time Sync
- При любом действии игрока → broadcast всем
- События: join, leave, move, collect, chat

## Типичные action types

```python
ACTIONS = {
    'join': handle_join,      # Вход игрока
    'leave': handle_leave,    # Выход игрока
    'move': handle_move,      # Движение
    'collect': handle_collect,# Сбор предмета
    'chat': handle_chat,      # Сообщение в чат
}
```

## Локальная сеть

Для игры по LAN:
1. Сервер слушает `0.0.0.0` (все интерфейсы)
2. Клиенты подключаются к `ws://SERVER_IP:8003/game`
3. Убедиться, что firewall разрешает порт

## Checklist создания multiplayer игры

- [ ] Создать GameRoom класс с players/artifacts
- [ ] Реализовать WebSocket endpoint
- [ ] Добавить broadcast метод
- [ ] Создать HTML клиент с WebSocket подключением
- [ ] Реализовать обработку join/leave/move
- [ ] Добавить UI для списка игроков
- [ ] Добавить chat panel
- [ ] Тестировать с 2+ клиентами

## Использование в Neira

Когда пользователь просит "создай многопользовательскую игру":
1. Использовать `ui_code_cell` для HTML клиента
2. Предоставить Python сервер код (multiplayer_server.py)
3. Объяснить, как запустить: `python multiplayer_server.py`
4. Открыть HTML в нескольких браузерах для теста
"""

print(MULTIPLAYER_PATTERN)

if __name__ == "__main__":
    print("✅ Паттерн multiplayer игр готов для Нейры")
    print("📚 Примеры добавлены в training_dataset.jsonl")
    print("🎮 Игра harry_potter_multiplayer.html готова к тесту")
