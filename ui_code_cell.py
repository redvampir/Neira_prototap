"""UI Code Cell — генерация интерфейсов как артефактов.

Философия: Neira не просто создаёт UI, она выражает себя через него.
Каждый артефакт — это её "кожа", проявление внутреннего состояния.
"""

from __future__ import annotations

import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List


class UICodeCell:
    """Ячейка для генерации UI кода (HTML/CSS/JS) как артефактов.
    
    Концепция:
    - Использует шаблоны (templates) как базу
    - LLM дополняет и адаптирует под задачу
    - Результат сохраняется в artifacts/
    - Успешные паттерны запоминаются для обучения
    """
    
    def __init__(self, neira_instance):
        self.name = "UICodeCell"
        self.neira = neira_instance
        self.templates_file = Path("neira_ui_templates.json")
        self.artifacts_dir = Path("artifacts")
        self.artifacts_dir.mkdir(exist_ok=True)
        
        # Загрузить шаблоны или создать дефолтные
        self.templates = self._load_templates()
        
    def _load_templates(self) -> Dict[str, Any]:
        """Загрузить шаблоны или создать базовые игровые."""
        if self.templates_file.exists():
            try:
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.neira.log(f"⚠️ Ошибка загрузки шаблонов: {e}", level="warning")
        
        # Базовые игровые шаблоны
        default_templates = {
            "rpg_inventory": {
                "name": "RPG Inventory",
                "category": "game",
                "description": "Инвентарь для RPG игры с слотами",
                "html": """
<div class="rpg-inventory">
  <div class="inventory-header">
    <h2>⚔️ Инвентарь</h2>
    <div class="gold">💰 <span id="gold">100</span></div>
  </div>
  <div class="inventory-grid" id="inventoryGrid"></div>
</div>""",
                "css": """
.rpg-inventory {
  width: 400px;
  background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
  border: 2px solid #8b7355;
  border-radius: 8px;
  padding: 20px;
  color: #f0e6d2;
  font-family: 'Cinzel', serif;
}
.inventory-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  border-bottom: 1px solid #8b7355;
  padding-bottom: 10px;
}
.inventory-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}
.item-slot {
  width: 60px;
  height: 60px;
  background: #0f0f0f;
  border: 2px solid #4a4a4a;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}
.item-slot:hover {
  border-color: #c9aa71;
  transform: scale(1.05);
}
.item-slot.filled {
  background: linear-gradient(135deg, #2a2a2a, #1a1a1a);
  border-color: #8b7355;
}
.item-icon {
  font-size: 32px;
}
.item-count {
  position: absolute;
  bottom: 2px;
  right: 4px;
  font-size: 12px;
  color: #fff;
  text-shadow: 1px 1px 2px #000;
}""",
                "js": """
const items = [
  { icon: '⚔️', name: 'Меч', count: 1 },
  { icon: '🛡️', name: 'Щит', count: 1 },
  { icon: '🧪', name: 'Зелье', count: 5 },
  { icon: '🔑', name: 'Ключ', count: 1 }
];

function renderInventory() {
  const grid = document.getElementById('inventoryGrid');
  grid.innerHTML = '';
  
  for (let i = 0; i < 20; i++) {
    const slot = document.createElement('div');
    slot.className = 'item-slot';
    
    if (items[i]) {
      slot.classList.add('filled');
      slot.innerHTML = `
        <span class="item-icon">${items[i].icon}</span>
        ${items[i].count > 1 ? `<span class="item-count">${items[i].count}</span>` : ''}
      `;
      slot.title = items[i].name;
    }
    
    grid.appendChild(slot);
  }
}

renderInventory();"""
            },
            
            "platformer_hud": {
                "name": "Platformer HUD",
                "category": "game",
                "description": "HUD для платформера (жизни, монеты, время)",
                "html": """
<div class="platformer-hud">
  <div class="hud-left">
    <div class="lives">
      <span class="label">🫀</span>
      <div class="hearts" id="hearts"></div>
    </div>
    <div class="coins">
      <span class="coin-icon">🪙</span>
      <span id="coinCount">0</span>
    </div>
  </div>
  <div class="hud-center">
    <div class="level">Level <span id="levelNum">1</span></div>
  </div>
  <div class="hud-right">
    <div class="timer">⏱️ <span id="timer">0:00</span></div>
  </div>
</div>""",
                "css": """
.platformer-hud {
  display: flex;
  justify-content: space-between;
  padding: 15px 25px;
  background: linear-gradient(180deg, rgba(0,0,0,0.8) 0%, rgba(0,0,0,0.4) 100%);
  color: white;
  font-family: 'Press Start 2P', monospace;
  font-size: 14px;
  border-bottom: 3px solid #ff6b6b;
}
.hud-left, .hud-right {
  display: flex;
  gap: 20px;
  align-items: center;
}
.lives {
  display: flex;
  align-items: center;
  gap: 8px;
}
.hearts {
  display: flex;
  gap: 4px;
}
.heart {
  font-size: 20px;
  filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.5));
}
.coins {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #ffd700;
}
.level {
  font-size: 16px;
  text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
}
.timer {
  color: #4ecdc4;
}""",
                "js": """
let lives = 3;
let coins = 0;
let seconds = 0;

function renderHearts() {
  const container = document.getElementById('hearts');
  container.innerHTML = '❤️'.repeat(lives);
}

function updateCoins(amount) {
  coins += amount;
  document.getElementById('coinCount').textContent = coins;
}

function startTimer() {
  setInterval(() => {
    seconds++;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    document.getElementById('timer').textContent = 
      `${mins}:${secs.toString().padStart(2, '0')}`;
  }, 1000);
}

renderHearts();
startTimer();

// Demo: собрать монетку через 2 секунды
setTimeout(() => updateCoins(1), 2000);"""
            },
            
            "puzzle_board": {
                "name": "Puzzle Board",
                "category": "game",
                "description": "Игровое поле для головоломки (сетка)",
                "html": """
<div class="puzzle-container">
  <div class="puzzle-header">
    <div class="moves">Ходы: <span id="moves">0</span></div>
    <button class="reset-btn" onclick="resetPuzzle()">🔄 Сброс</button>
  </div>
  <div class="puzzle-board" id="board"></div>
</div>""",
                "css": """
.puzzle-container {
  width: 360px;
  background: #2c3e50;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 8px 16px rgba(0,0,0,0.3);
}
.puzzle-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  color: #ecf0f1;
  font-weight: bold;
}
.reset-btn {
  background: #e74c3c;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.reset-btn:hover {
  background: #c0392b;
}
.puzzle-board {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  background: #34495e;
  padding: 8px;
  border-radius: 8px;
}
.puzzle-tile {
  aspect-ratio: 1;
  background: linear-gradient(135deg, #3498db, #2980b9);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  font-weight: bold;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}
.puzzle-tile:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 8px rgba(0,0,0,0.3);
}
.puzzle-tile.empty {
  background: transparent;
  cursor: default;
}""",
                "js": """
let board = [1, 2, 3, 4, 5, 6, 7, 8, null];
let moves = 0;

function renderBoard() {
  const container = document.getElementById('board');
  container.innerHTML = '';
  
  board.forEach((num, index) => {
    const tile = document.createElement('div');
    tile.className = 'puzzle-tile' + (num === null ? ' empty' : '');
    tile.textContent = num || '';
    tile.onclick = () => moveTile(index);
    container.appendChild(tile);
  });
}

function moveTile(index) {
  const emptyIndex = board.indexOf(null);
  const valid = [
    emptyIndex - 3, // сверху
    emptyIndex + 3, // снизу
    emptyIndex % 3 !== 0 ? emptyIndex - 1 : -1, // слева
    emptyIndex % 3 !== 2 ? emptyIndex + 1 : -1  // справа
  ];
  
  if (valid.includes(index)) {
    [board[index], board[emptyIndex]] = [board[emptyIndex], board[index]];
    moves++;
    document.getElementById('moves').textContent = moves;
    renderBoard();
  }
}

function resetPuzzle() {
  board = [1, 2, 3, 4, 5, 6, 7, 8, null];
  moves = 0;
  document.getElementById('moves').textContent = moves;
  renderBoard();
}

renderBoard();"""
            }
        }
        
        # Сохранить дефолтные шаблоны
        self._save_templates(default_templates)
        return default_templates
    
    def _save_templates(self, templates: Dict[str, Any]) -> None:
        """Сохранить шаблоны в файл."""
        try:
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(templates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.neira.log(f"⚠️ Ошибка сохранения шаблонов: {e}", level="warning")
    
    async def generate_ui(
        self,
        task_description: str,
        template_name: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Генерация UI артефакта.
        
        Args:
            task_description: Описание задачи ("создай интерфейс инвентаря")
            template_name: Имя шаблона (опционально)
            data: Дополнительные данные для шаблона
        
        Returns:
            {
                "html": "...",
                "css": "...",
                "js": "...",
                "artifact_id": "abc123",
                "template_used": "rpg_inventory"
            }
        """
        self.neira.log(f"🎨 UICodeCell: Генерация UI для '{task_description}'")
        
        # 🫀 Resonance-based Generation: читаем heart.resonance
        resonance_level = self._get_resonance()
        self.neira.log(f"🎵 Resonance level: {resonance_level:.2f} (0=консервативно, 1=экспериментально)")
        
        # Выбрать шаблон
        if template_name and template_name in self.templates:
            template = self.templates[template_name]
        else:
            # LLM выбирает подходящий шаблон
            template = await self._select_template(task_description)
        
        if not template:
            return {"error": "Не найден подходящий шаблон"}
        
        # Базовый код из шаблона
        html = template.get("html", "")
        css = template.get("css", "")
        js = template.get("js", "")
        
        # Применить стиль на основе резонанса
        css = self._apply_resonance_style(css, resonance_level)
        
        # LLM адаптирует под задачу (если есть специфика)
        if data or "создай" in task_description.lower():
            adapted = await self._adapt_template(template, task_description, data)
            html = adapted.get("html", html)
            css = adapted.get("css", css)
            js = adapted.get("js", js)
        
        # Создать артефакт
        artifact_id = self._generate_artifact_id(task_description)
        artifact = {
            "id": artifact_id,
            "html": html,
            "css": css,
            "js": js,
            "template_used": template.get("name"),
            "created_at": datetime.now().isoformat(),
            "task": task_description
        }
        
        # Сохранить в artifacts/
        self._save_artifact(artifact)
        
        self.neira.log(f"✅ Артефакт создан: {artifact_id}")
        return artifact
    
    async def _select_template(self, task: str) -> Optional[Dict[str, Any]]:
        """Выбрать подходящий шаблон через LLM."""
        # Простой keyword-based подход (можно заменить на LLM)
        task_lower = task.lower()
        
        if any(word in task_lower for word in ["инвентарь", "inventory", "предметы"]):
            return self.templates.get("rpg_inventory")
        elif any(word in task_lower for word in ["hud", "жизни", "здоровье", "монеты"]):
            return self.templates.get("platformer_hud")
        elif any(word in task_lower for word in ["головоломка", "puzzle", "сетка"]):
            return self.templates.get("puzzle_board")
        
        # Дефолтный шаблон
        return list(self.templates.values())[0] if self.templates else None
    
    async def _adapt_template(
        self,
        template: Dict[str, Any],
        task: str,
        data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Адаптировать шаблон через LLM (TODO: интеграция с моделью)."""
        # Пока возвращаем оригинал, позже добавим LLM
        return {
            "html": template.get("html", ""),
            "css": template.get("css", ""),
            "js": template.get("js", "")
        }
    
    def _get_resonance(self) -> float:
        """Получить текущий уровень резонанса из heart (0-1)."""
        try:
            if hasattr(self.neira, 'heart') and hasattr(self.neira.heart, 'resonance'):
                return self.neira.heart.resonance
        except Exception as e:
            self.neira.log(f"⚠️ Не удалось прочитать heart.resonance: {e}", level="warning")
        return 0.5  # Дефолт: средний резонанс
    
    def _apply_resonance_style(self, css: str, resonance: float) -> str:
        """Адаптировать CSS стиль на основе резонанса.
        
        Логика:
        - resonance < 0.3 (низкий): консервативные цвета (серый, синий)
        - resonance 0.3-0.7 (средний): сбалансированная палитра
        - resonance > 0.7 (высокий): яркие, экспериментальные цвета (золотой, фиолетовый)
        """
        if resonance < 0.3:
            # Консервативный стиль
            css = css.replace("#ffd700", "#7f8c8d")  # Золотой → Серый
            css = css.replace("#ff4444", "#3498db")  # Красный → Синий
        elif resonance > 0.7:
            # Экспериментальный стиль
            css = css.replace("#7f8c8d", "#9b59b6")  # Серый → Фиолетовый
            css = css.replace("#3498db", "#e74c3c")  # Синий → Красный
            # Добавить pulsating анимацию
            if "@keyframes" not in css:
                css += "\n@keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }"
        
        return css
    
    def _generate_artifact_id(self, task: str) -> str:
        """Генерация уникального ID артефакта."""
        timestamp = datetime.now().isoformat()
        raw = f"{task}_{timestamp}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]
    
    def _save_artifact(self, artifact: Dict[str, Any]) -> None:
        """Сохранить артефакт в artifacts/."""
        artifact_file = self.artifacts_dir / f"{artifact['id']}.json"
        try:
            with open(artifact_file, 'w', encoding='utf-8') as f:
                json.dump(artifact, f, ensure_ascii=False, indent=2)
            
            # Также создать HTML файл для превью
            html_file = self.artifacts_dir / f"{artifact['id']}.html"
            full_html = self._build_standalone_html(artifact)
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(full_html)
        except Exception as e:
            self.neira.log(f"⚠️ Ошибка сохранения артефакта: {e}", level="warning")
    
    def _build_standalone_html(self, artifact: Dict[str, Any]) -> str:
        """Собрать полный HTML из артефакта."""
        return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Neira Artifact - {artifact['id']}</title>
  <style>
    body {{
      margin: 0;
      padding: 20px;
      background: #1a1a1a;
      color: #e0e0e0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }}
    {artifact['css']}
  </style>
</head>
<body>
  {artifact['html']}
  <script>
    {artifact['js']}
  </script>
</body>
</html>"""
    
    def list_artifacts(self) -> List[Dict[str, Any]]:
        """Список всех артефактов."""
        artifacts = []
        for file in self.artifacts_dir.glob("*.json"):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    artifacts.append(json.load(f))
            except Exception:
                continue
        return sorted(artifacts, key=lambda x: x.get('created_at', ''), reverse=True)
    
    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Получить артефакт по ID."""
        artifact_file = self.artifacts_dir / f"{artifact_id}.json"
        if artifact_file.exists():
            with open(artifact_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def extract_components_from_artifact(self, artifact_id: str) -> List[Dict[str, Any]]:
        """Извлечь переиспользуемые компоненты из артефакта.
        
        Критерии для автоэкстракции:
        - Артефакт имеет рейтинг 5 звёзд
        - Код содержит CSS классы с уникальными паттернами
        - Есть JS функции с чёткой ответственностью
        - Анимации (@keyframes)
        
        Returns:
            List[Dict]: Список компонентов [{name, html, css, js, tags}]
        """
        artifact = self.get_artifact(artifact_id)
        if not artifact:
            return []
        
        # Проверка рейтинга
        rating = artifact.get("metadata", {}).get("rating", 0)
        if rating < 5:
            return []
        
        components = []
        html = artifact.get("html", "")
        css = artifact.get("css", "")
        js = artifact.get("js", "")
        
        # Паттерн 1: CSS классы с уникальными именами
        import re
        css_classes = re.findall(r'\.([\w-]+)\s*\{([^}]+)\}', css)
        for class_name, class_body in css_classes:
            if len(class_body.strip()) > 30:  # Минимум 30 символов
                components.append({
                    "name": f"css_{class_name}",
                    "type": "css",
                    "code": f".{class_name} {{{class_body}}}",
                    "tags": [artifact.get("template_used", "unknown"), "css"],
                    "extracted_from": artifact_id,
                    "rating": rating
                })
        
        # Паттерн 2: JS функции
        js_functions = re.findall(r'function\s+(\w+)\s*\([^)]*\)\s*\{', js)
        for func_name in js_functions:
            # Извлечь полное тело функции (упрощённо)
            func_start = js.find(f"function {func_name}")
            if func_start != -1:
                components.append({
                    "name": f"js_{func_name}",
                    "type": "js",
                    "code": f"function {func_name}(...) {{ /* см. артефакт {artifact_id} */ }}",
                    "tags": [artifact.get("template_used", "unknown"), "js", "function"],
                    "extracted_from": artifact_id,
                    "rating": rating
                })
        
        # Паттерн 3: Keyframe анимации
        keyframes = re.findall(r'@keyframes\s+([\w-]+)\s*\{([^}]+)\}', css)
        for kf_name, kf_body in keyframes:
            components.append({
                "name": f"anim_{kf_name}",
                "type": "animation",
                "code": f"@keyframes {kf_name} {{{kf_body}}}",
                "tags": ["animation", artifact.get("template_used", "unknown")],
                "extracted_from": artifact_id,
                "rating": rating
            })
        
        return components
    
    def save_components_to_library(self, components: List[Dict[str, Any]]):
        """Сохранить компоненты в библиотеку (neira_ui_components.json)."""
        library_file = Path("neira_ui_components.json")
        
        if library_file.exists():
            with open(library_file, 'r', encoding='utf-8') as f:
                library = json.load(f)
        else:
            library = {
                "components": [],
                "metadata": {
                    "version": "1.0",
                    "created_at": datetime.now().isoformat()
                }
            }
        
        # Добавить новые компоненты (избегая дубликатов по name)
        existing_names = {c["name"] for c in library["components"]}
        for comp in components:
            if comp["name"] not in existing_names:
                library["components"].append(comp)
                existing_names.add(comp["name"])
        
        # Сортировка по рейтингу (лучшие — первыми)
        library["components"].sort(key=lambda x: x.get("rating", 0), reverse=True)
        
        library["metadata"]["last_updated"] = datetime.now().isoformat()
        library["metadata"]["total_components"] = len(library["components"])
        
        with open(library_file, 'w', encoding='utf-8') as f:
            json.dump(library, f, ensure_ascii=False, indent=2)
        
        self.neira.log(f"📚 Добавлено {len(components)} компонентов в библиотеку", level="info")
    
            return {
                "response": f"🎨 Создан артефакт: {result.get('id')}",
                "artifact": result
            }
        return {"response": "UICodeCell готова к работе"}
