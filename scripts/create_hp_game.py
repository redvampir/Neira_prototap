"""
Harry Potter Game - Manual Generation
"""

# Создаём HTML с Harry Potter тематикой
html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Harry Potter: Hogwarts Adventure</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Georgia', serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #0f3460 50%, #16213e 100%);
            color: #f0f0f0;
            overflow: hidden;
        }}
        
        .game-container {{
            display: flex;
            height: 100vh;
            padding: 20px;
            gap: 20px;
        }}
        
        .game-area {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}
        
        .header {{
            background: rgba(25, 25, 45, 0.9);
            padding: 15px 25px;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            border: 2px solid rgba(255, 215, 0, 0.3);
        }}
        
        .header h1 {{
            color: #ffd700;
            font-size: 32px;
            text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
        }}
        
        .stats {{
            display: flex;
            gap: 30px;
            margin-top: 10px;
        }}
        
        .stat {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .stat-label {{
            color: #a0a0a0;
        }}
        
        .stat-value {{
            color: #ffd700;
            font-weight: bold;
            font-size: 20px;
        }}
        
        .game-field {{
            flex: 1;
            background: rgba(15, 15, 30, 0.8);
            border-radius: 10px;
            padding: 20px;
            position: relative;
            box-shadow: inset 0 0 30px rgba(0,0,0,0.7);
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(10, 1fr);
            gap: 2px;
            height: 100%;
            max-height: 600px;
            max-width: 600px;
            margin: 0 auto;
        }}
        
        .cell {{
            background: rgba(30, 30, 50, 0.6);
            border: 1px solid rgba(100, 100, 150, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
        }}
        
        .cell:hover {{
            background: rgba(50, 50, 80, 0.8);
            border-color: rgba(255, 215, 0, 0.5);
        }}
        
        .cell.player {{
            background: rgba(138, 43, 226, 0.8);
            box-shadow: 0 0 15px rgba(138, 43, 226, 0.6);
        }}
        
        .cell.artifact {{
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.1); }}
        }}
        
        .chat-panel {{
            width: 350px;
            background: rgba(25, 25, 45, 0.9);
            border-radius: 10px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            border: 2px solid rgba(255, 215, 0, 0.3);
        }}
        
        .chat-header {{
            color: #ffd700;
            font-size: 20px;
            font-weight: bold;
            text-align: center;
            padding-bottom: 10px;
            border-bottom: 2px solid rgba(255, 215, 0, 0.3);
        }}
        
        .chat-messages {{
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            background: rgba(15, 15, 30, 0.6);
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        
        .message {{
            padding: 10px 15px;
            border-radius: 8px;
            max-width: 90%;
        }}
        
        .message.neira {{
            background: rgba(138, 43, 226, 0.3);
            align-self: flex-start;
            border-left: 3px solid #8a2be2;
        }}
        
        .message.player {{
            background: rgba(255, 215, 0, 0.2);
            align-self: flex-end;
            border-right: 3px solid #ffd700;
        }}
        
        .chat-input {{
            display: flex;
            gap: 10px;
        }}
        
        .chat-input input {{
            flex: 1;
            padding: 12px;
            background: rgba(15, 15, 30, 0.6);
            border: 2px solid rgba(255, 215, 0, 0.3);
            border-radius: 8px;
            color: #f0f0f0;
            font-size: 14px;
        }}
        
        .chat-input input:focus {{
            outline: none;
            border-color: #ffd700;
        }}
        
        .chat-input button {{
            padding: 12px 20px;
            background: linear-gradient(135deg, #8a2be2 0%, #6a1bb2 100%);
            border: none;
            border-radius: 8px;
            color: white;
            cursor: pointer;
            font-weight: bold;
            transition: transform 0.2s;
        }}
        
        .chat-input button:hover {{
            transform: scale(1.05);
        }}
        
        .controls {{
            text-align: center;
            color: #a0a0a0;
            font-size: 14px;
            margin-top: 10px;
        }}
        
        .artifact-info {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(25, 25, 45, 0.95);
            padding: 15px;
            border-radius: 8px;
            border: 2px solid rgba(255, 215, 0, 0.4);
            max-width: 250px;
        }}
        
        .artifact-info h3 {{
            color: #ffd700;
            margin-bottom: 8px;
        }}
        
        .artifact-list {{
            display: flex;
            flex-direction: column;
            gap: 5px;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="game-container">
        <div class="game-area">
            <div class="header">
                <h1>⚡ Hogwarts Adventure ⚡</h1>
                <div class="stats">
                    <div class="stat">
                        <span class="stat-label">Score:</span>
                        <span class="stat-value" id="score">0</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Artifacts:</span>
                        <span class="stat-value" id="artifacts">0/5</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Moves:</span>
                        <span class="stat-value" id="moves">0</span>
                    </div>
                </div>
            </div>
            
            <div class="game-field">
                <div class="grid" id="grid"></div>
                <div class="controls">
                    Use WASD or Arrow Keys to move • Collect all artifacts!
                </div>
                
                <div class="artifact-info">
                    <h3>Magical Artifacts</h3>
                    <div class="artifact-list" id="artifactList">
                        <div>🪄 Elder Wand</div>
                        <div>🔮 Crystal Ball</div>
                        <div>📚 Spellbook</div>
                        <div>🧙 Sorting Hat</div>
                        <div>⚗️ Potion</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="chat-panel">
            <div class="chat-header">💬 Chat with Neira</div>
            <div class="chat-messages" id="chatMessages">
                <div class="message neira">
                    Welcome to Hogwarts! I'm Neira, your magical guide. Collect all 5 artifacts to complete your quest. Ask me anything!
                </div>
            </div>
            <div class="chat-input">
                <input type="text" id="chatInput" placeholder="Ask Neira..." />
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>
    
    <script>
        const GRID_SIZE = 10;
        const ARTIFACTS_ICONS = ['🪄', '🔮', '📚', '🧙', '⚗️'];
        
        let player = {{ x: 0, y: 0 }};
        let artifacts = [];
        let collected = 0;
        let score = 0;
        let moves = 0;
        
        function init() {{
            createGrid();
            placeArtifacts();
            updateUI();
            
            document.addEventListener('keydown', handleKeyPress);
        }}
        
        function createGrid() {{
            const grid = document.getElementById('grid');
            for (let y = 0; y < GRID_SIZE; y++) {{
                for (let x = 0; x < GRID_SIZE; x++) {{
                    const cell = document.createElement('div');
                    cell.className = 'cell';
                    cell.dataset.x = x;
                    cell.dataset.y = y;
                    grid.appendChild(cell);
                }}
            }}
            updatePlayerPosition();
        }}
        
        function placeArtifacts() {{
            artifacts = [];
            for (let i = 0; i < 5; i++) {{
                let x, y;
                do {{
                    x = Math.floor(Math.random() * GRID_SIZE);
                    y = Math.floor(Math.random() * GRID_SIZE);
                }} while ((x === player.x && y === player.y) || artifacts.some(a => a.x === x && a.y === y));
                
                artifacts.push({{ x, y, icon: ARTIFACTS_ICONS[i], collected: false }});
            }}
            updateArtifacts();
        }}
        
        function handleKeyPress(e) {{
            const key = e.key.toLowerCase();
            let newX = player.x;
            let newY = player.y;
            
            if (key === 'w' || key === 'arrowup') newY = Math.max(0, player.y - 1);
            if (key === 's' || key === 'arrowdown') newY = Math.min(GRID_SIZE - 1, player.y + 1);
            if (key === 'a' || key === 'arrowleft') newX = Math.max(0, player.x - 1);
            if (key === 'd' || key === 'arrowright') newX = Math.min(GRID_SIZE - 1, player.x + 1);
            
            if (newX !== player.x || newY !== player.y) {{
                player.x = newX;
                player.y = newY;
                moves++;
                checkArtifactCollision();
                updatePlayerPosition();
                updateUI();
            }}
        }}
        
        function checkArtifactCollision() {{
            artifacts.forEach(artifact => {{
                if (!artifact.collected && artifact.x === player.x && artifact.y === player.y) {{
                    artifact.collected = true;
                    collected++;
                    score += 100;
                    
                    addMessage(`You found the ${{artifact.icon}}! +100 points`, 'neira');
                    
                    if (collected === 5) {{
                        setTimeout(() => {{
                            addMessage('Congratulations! You collected all artifacts! 🎉', 'neira');
                        }}, 500);
                    }}
                }}
            }});
        }}
        
        function updatePlayerPosition() {{
            document.querySelectorAll('.cell').forEach(cell => {{
                cell.classList.remove('player');
                const x = parseInt(cell.dataset.x);
                const y = parseInt(cell.dataset.y);
                if (x === player.x && y === player.y) {{
                    cell.classList.add('player');
                    cell.textContent = '🧙';
                }}
            }});
        }}
        
        function updateArtifacts() {{
            artifacts.forEach(artifact => {{
                if (!artifact.collected) {{
                    const cell = document.querySelector(`.cell[data-x="${{artifact.x}}"][data-y="${{artifact.y}}"]`);
                    if (cell) {{
                        cell.textContent = artifact.icon;
                        cell.classList.add('artifact');
                    }}
                }}
            }});
        }}
        
        function updateUI() {{
            document.getElementById('score').textContent = score;
            document.getElementById('artifacts').textContent = `${{collected}}/5`;
            document.getElementById('moves').textContent = moves;
            updateArtifacts();
        }}
        
        function sendMessage() {{
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            if (!message) return;
            
            addMessage(message, 'player');
            input.value = '';
            
            // Simple Neira responses
            setTimeout(() => {{
                const responses = [
                    'Keep exploring! Magic awaits around every corner.',
                    `You've collected ${{collected}} artifacts so far!`,
                    'Try moving towards the glowing artifacts!',
                    'The artifacts are scattered across Hogwarts. Good luck!',
                    `Great progress! Only ${{5 - collected}} artifacts left!`
                ];
                addMessage(responses[Math.floor(Math.random() * responses.length)], 'neira');
            }}, 500);
        }}
        
        function addMessage(text, sender) {{
            const messagesDiv = document.getElementById('chatMessages');
            const message = document.createElement('div');
            message.className = `message ${{sender}}`;
            message.textContent = text;
            messagesDiv.appendChild(message);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }}
        
        document.getElementById('chatInput').addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') sendMessage();
        }});
        
        init();
    </script>
</body>
</html>
"""

# Сохраняем
filename = "harry_potter_game.html"
with open(filename, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Harry Potter game created: {filename}")
print(f"Size: {len(html)} bytes")
print("\nOpening in browser...")

import os
os.system(f"start {filename}")

print("\nGame features:")
print("- 10x10 grid game field")
print("- WASD or Arrow keys to move")
print("- 5 magical artifacts to collect")
print("- Score counter and stats")
print("- Live chat with Neira")
print("- Harry Potter theme")
print("\nYou can play now!")
