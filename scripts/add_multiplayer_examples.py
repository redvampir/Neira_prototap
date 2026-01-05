"""
Добавляет примеры многопользовательских игр в training dataset
"""
import json

examples = [
    {
        "prompt": "Пользователь: Сделай многопользовательскую игру по локальной сети\nКакую клетку использовать?",
        "completion": "Использую ui_code_cell для создания клиентской части (HTML+WebSocket) и предоставлю WebSocket сервер на Python. Обоснование: Многопользовательская игра требует 1) UI интерфейс для клиента 2) WebSocket сервер для синхронизации. Создам game server с rooms, player management, broadcast messages и HTML клиент с WebSocket подключением."
    },
    {
        "prompt": "Система: Запрос содержит keywords: ['multiplayer', 'локальная сеть', 'websocket']\nВыбери подход:",
        "completion": "Подход: WebSocket real-time communication. Создам 1) Starlette WebSocket server с room management 2) HTML client с WebSocket.connect() 3) Broadcast система для синхронизации состояния игры между всеми клиентами. Сервер: ws://localhost:PORT, клиент подключается и отправляет {action: 'join', player_id, room_id}."
    },
    {
        "prompt": "Пользователь: Добавь чат в игру для общения между игроками\nКакую клетку использовать?",
        "completion": "Использую ui_code_cell с интеграцией WebSocket чата. Обоснование: Многопользовательский чат требует real-time messaging. Добавлю chat panel в UI, WebSocket сообщения {action: 'chat', message}, server broadcast всем игрокам. UI: input поле + messages div с автоскроллом."
    },
    {
        "prompt": "Система: Пользователь просит создать multiplayer игру с рейтингом игроков\nПлан действий:",
        "completion": "План: 1) Создам GameRoom с players dict, где ключ - player_id, значение - {name, score, position}. 2) При каждом действии (сбор артефакта, победа) обновляю score и делаю broadcast обновленного рейтинга. 3) В UI добавлю leaderboard panel с сортировкой по score. WebSocket сообщения: {action: 'update_score', player_id, new_score}."
    },
    {
        "prompt": "Пользователь: Как реализовать синхронизацию движения игроков в реальном времени?\nАрхитектурное решение:",
        "completion": "Архитектура: Server authoritative model. Клиент отправляет {action: 'move', direction}, сервер валидирует (проверяет границы, коллизии), обновляет состояние игрока, делает broadcast {action: 'player_moved', player_id, new_x, new_y} всем клиентам. Клиенты обновляют позиции на UI. Интерполация для плавности: клиент рендерит transition CSS при получении новой позиции."
    }
]

# Добавляем примеры в файл
with open('training_dataset.jsonl', 'a', encoding='utf-8') as f:
    for example in examples:
        f.write(json.dumps(example, ensure_ascii=False) + '\n')

print(f"✅ Добавлено {len(examples)} примеров multiplayer игр в training_dataset.jsonl")
