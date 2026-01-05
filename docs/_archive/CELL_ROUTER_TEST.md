# Cell Router Testing Guide

## Что было сделано

### 1. Fine-tuned модель `neira-cell-router:latest`
- **Dataset**: `training_dataset.jsonl` (25 примеров)
- **Base model**: `ministral-3:3b`
- **System prompt**: Enhanced с описанием Cell Registry и правил использования

### 2. Интеграция
- `cells.py`: MODEL_REASON → `neira-cell-router:latest`
- `llm_providers.py`: Default provider → `neira-cell-router:latest`
- `model_manager.py`: MODELS registry обновлён
- `main.py`: MODEL_REASON constant обновлён

### 3. Cell Router System
- `cell_router.py`: Intent detection + cell selection
- `ui_code_cell.py`: 4 templates loaded (rpg_inventory, platformer_hud, puzzle_board, tictactoe)
- `backend/neira_wrapper.py`: Интеграция Cell Router в процесс обработки

## Как тестировать

### Шаг 1: Запустить WebSocket Backend

```bash
chcp 65001
python -m backend.api
```

Ожидаемый output:
```
✅ UICodeCell импортирован
✅ CellRouter импортирован
🧬 Cell Router инициализирован
🎨 UICodeCell инициализирован
   Templates loaded: ['rpg_inventory', 'platformer_hud', 'puzzle_board', 'tictactoe']
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Шаг 2: Открыть test_websocket.html в браузере

```bash
start test_websocket.html
```

Или вручную: открыть файл `f:\Нейронки\prototype\test_websocket.html` через **File → Open File** в браузере.

### Шаг 3: Тестировать TicTacToe Request

1. **Нажать кнопку "🔌 Подключиться"**
   - Status должен стать "Connected"

2. **Нажать кнопку "📤 Создать TicTacToe"**
   - Отправит запрос: `"Создай интерфейс для игры в крестики-нолики"`

3. **Наблюдать за логами**:
   - `📥 chunk`: Streaming chunks от модели
   - `📥 artifact`: HTML artifact с TicTacToe UI
   - Автоматически откроется артефакт в новом окне

### Ожидаемое поведение

#### ✅ Правильно (Cell Router работает):
```
[CELL:ui_code_cell] Создаю интерфейс для крестиков-ноликов...
```
→ UICodeCell генерирует HTML с template `tictactoe`

#### ❌ Неправильно (модель игнорирует директиву):
```
[CELL:ui_code_cell] Создаю интерфейс...
```python
import tkinter as tk
# ... full Python implementation ...
```
→ Модель генерирует код вместо использования клетки

## Проверка логов в терминале

В терминале где запущен `python -m backend.api` должны появиться:

```
[process_stream] Checking for cell routing...
[process_stream] Cell Router decided: should_use=True, cell_name='ui_code_cell'
[UICodeCell.generate_ui] 🎨 Generating UI with keywords: интерфейс, игра, крестики-нолики
[UICodeCell._select_template] Template 'tictactoe' selected (score=3)
```

## Debug режим

Если нужно увидеть больше деталей:

```python
# В backend/neira_wrapper.py
verbose = True  # Раскомментировать debug логи
```

Перезапустить backend:
```bash
chcp 65001
python -m backend.api
```

## Fallback тестирование (без WebSocket)

Если WebSocket не работает, можно протестировать модель напрямую:

```bash
ollama run neira-cell-router:latest "Создай интерфейс для игры в крестики-нолики"
```

Ожидаемый output:
```
[CELL:ui_code_cell] Создаю интерфейс для игры в крестики-нолики с использованием template 'tictactoe'...
```

**Проблема**: Модель также генерирует Python код после директивы (Ollama ограничение system prompt).

**Решение**: Cell Router в `neira_wrapper.py` обрезает response после директивы `[CELL:...]` и передаёт управление UICodeCell.

## Статус

- ✅ Fine-tuning модели завершён
- ✅ Интеграция Cell Router + UICodeCell работает
- ✅ WebSocket backend запускается без ошибок
- ⚠️ Модель генерирует код после `[CELL:...]` (ожидаемо, Cell Router обрабатывает)
- 🔲 Тестирование end-to-end через WebSocket (требуется ручная проверка)

## Next Steps

1. **Протестировать через test_websocket.html**
2. **Проверить что артефакт генерируется корректно**
3. **Проверить resonance адаптацию CSS** (0-1 scale)
4. **Расширить templates** (если нужно)
5. **Добавить больше примеров в training_dataset.jsonl** (улучшение fine-tuning)
