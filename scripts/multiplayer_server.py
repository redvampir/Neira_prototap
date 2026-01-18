"""
Harry Potter Multiplayer Game Server
WebSocket server for local network multiplayer
"""
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute, Route
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.responses import FileResponse
import json
import asyncio
from typing import Dict, Set, List
import random
import os

# Импорт Neira бота
try:
    from neira_game_bot import NeiraGameBot
    NEIRA_AVAILABLE = True
except ImportError:
    NEIRA_AVAILABLE = False
    print("⚠️  Neira bot не доступен (llm_providers не найден)")

# Game state
class GameRoom:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.players: Dict[str, dict] = {}  # player_id -> {name, x, y, score, color}
        self.artifacts: List[dict] = []  # [{x, y, icon, collected}]
        self.connections: Dict[str, WebSocket] = {}  # player_id -> websocket
        self.grid_size = 15
        self.neira_bot = None  # AI персонаж
        self.init_artifacts()
        self.init_neira()
    
    def init_neira(self):
        """Инициализирует Neira бота"""
        if NEIRA_AVAILABLE:
            self.neira_bot = NeiraGameBot(self)
            print(f"✅ Neira bot активирована в комнате {self.room_id}")
        else:
            print(f"⚠️  Neira bot недоступна в комнате {self.room_id}")
    
    def init_artifacts(self):
        icons = ['🪄', '🔮', '📚', '🧙', '⚗️', '🦉', '🐍', '🦁']
        self.artifacts = []
        for i in range(8):
            x = random.randint(0, self.grid_size - 1)
            y = random.randint(0, self.grid_size - 1)
            self.artifacts.append({
                'id': i,
                'x': x,
                'y': y,
                'icon': icons[i],
                'collected': False,
                'collected_by': None
            })
    
    def add_player(self, player_id: str, name: str, ws: WebSocket):
        colors = ['#8a2be2', '#ff6347', '#32cd32', '#ffd700', '#00bfff']
        color = colors[len(self.players) % len(colors)]
        
        # Random spawn position
        x = random.randint(0, self.grid_size - 1)
        y = random.randint(0, self.grid_size - 1)
        
        self.players[player_id] = {
            'id': player_id,
            'name': name,
            'x': x,
            'y': y,
            'score': 0,
            'color': color
        }
        self.connections[player_id] = ws
        
        # Neira приветствует нового игрока
        if self.neira_bot:
            asyncio.create_task(self.neira_bot.on_player_joined(name))
    
    def remove_player(self, player_id: str):
        if player_id in self.players:
            del self.players[player_id]
        if player_id in self.connections:
            del self.connections[player_id]
    
    def move_player(self, player_id: str, direction: str) -> dict:
        if player_id not in self.players:
            return {'error': 'Player not found'}
        
        player = self.players[player_id]
        old_x, old_y = player['x'], player['y']
        
        if direction == 'up':
            player['y'] = max(0, player['y'] - 1)
        elif direction == 'down':
            player['y'] = min(self.grid_size - 1, player['y'] + 1)
        elif direction == 'left':
            player['x'] = max(0, player['x'] - 1)
        elif direction == 'right':
            player['x'] = min(self.grid_size - 1, player['x'] + 1)
        
        # Check artifact collision
        collected_artifact = None
        for artifact in self.artifacts:
            if not artifact['collected'] and artifact['x'] == player['x'] and artifact['y'] == player['y']:
                artifact['collected'] = True
                artifact['collected_by'] = player_id
                player['score'] += 100
                collected_artifact = artifact
                
                # Neira поздравляет со сбором артефакта
                if self.neira_bot:
                    remaining = len([a for a in self.artifacts if not a['collected']])
                    asyncio.create_task(
                        self.neira_bot.on_artifact_collected(
                            player['name'], 
                            artifact['icon'], 
                            remaining
                        )
                    )
                
                break
        
        return {
            'player_id': player_id,
            'old_pos': {'x': old_x, 'y': old_y},
            'new_pos': {'x': player['x'], 'y': player['y']},
            'artifact': collected_artifact
        }
    
    def get_state(self) -> dict:
        return {
            'players': list(self.players.values()),
            'artifacts': self.artifacts,
            'grid_size': self.grid_size
        }
    
    async def broadcast(self, message: dict, exclude: str = None):
        disconnected = []
        for player_id, ws in self.connections.items():
            if player_id != exclude:
                try:
                    await ws.send_json(message)
                except:
                    disconnected.append(player_id)
        
        # Cleanup disconnected
        for player_id in disconnected:
            self.remove_player(player_id)

# Global rooms
rooms: Dict[str, GameRoom] = {}

async def multiplayer_game(websocket: WebSocket):
    await websocket.accept()
    
    player_id = None
    room_id = None
    
    try:
        # Wait for join message
        data = await websocket.receive_json()
        
        if data.get('action') != 'join':
            await websocket.send_json({'error': 'First message must be join'})
            return
        
        player_id = data.get('player_id', f"player_{random.randint(1000, 9999)}")
        player_name = data.get('player_name', f"Wizard {random.randint(1, 99)}")
        room_id = data.get('room_id', 'default')
        
        # Create or join room
        if room_id not in rooms:
            rooms[room_id] = GameRoom(room_id)
        
        room = rooms[room_id]
        room.add_player(player_id, player_name, websocket)
        
        # Send initial state
        await websocket.send_json({
            'type': 'joined',
            'player_id': player_id,
            'state': room.get_state()
        })
        
        # Notify others
        await room.broadcast({
            'type': 'player_joined',
            'player': room.players[player_id]
        }, exclude=player_id)
        
        # Message loop
        while True:
            data = await websocket.receive_json()
            action = data.get('action')
            
            if action == 'move':
                direction = data.get('direction')
                result = room.move_player(player_id, direction)
                
                # Broadcast movement
                await room.broadcast({
                    'type': 'player_moved',
                    'data': result
                })
                
                # Send updated state to mover
                await websocket.send_json({
                    'type': 'state_update',
                    'state': room.get_state()
                })
            
            elif action == 'chat':
                message = data.get('message', '')
                player_name = room.players[player_id]['name']
                
                # Broadcast сообщения
                await room.broadcast({
                    'type': 'chat_message',
                    'player_id': player_id,
                    'player_name': player_name,
                    'message': message
                })
                
                # Neira может ответить
                if room.neira_bot:
                    asyncio.create_task(
                        room.neira_bot.respond_to_chat(player_name, message)
                    )
            
            elif action == 'get_state':
                await websocket.send_json({
                    'type': 'state_update',
                    'state': room.get_state()
                })
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        if room_id and room_id in rooms:
            room = rooms[room_id]
            if player_id:
                room.remove_player(player_id)
                await room.broadcast({
                    'type': 'player_left',
                    'player_id': player_id
                })
            
            # Remove empty rooms
            if len(room.players) == 0:
                del rooms[room_id]

async def homepage(request):
    """Раздаёт HTML страницу игры"""
    html_file = os.path.join(os.path.dirname(__file__), 'harry_potter_mobile.html')
    if os.path.exists(html_file):
        return FileResponse(html_file)
    else:
        return FileResponse('harry_potter_multiplayer.html')

app = Starlette(
    routes=[
        Route("/", homepage),
        WebSocketRoute("/game", multiplayer_game),
    ]
)

if __name__ == "__main__":
    import uvicorn
    print("="*60)
    print("Harry Potter Multiplayer Server")
    print("="*60)
    print("Server: ws://localhost:8003/game")
    print("Open harry_potter_multiplayer.html in multiple browsers!")
    print("="*60)
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")
