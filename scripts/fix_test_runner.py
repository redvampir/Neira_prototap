"""
ИЗОЛИРОВАННОЕ решение проблемы падающего теста

Проблема: Python импортирует все модули из prototype/ при запуске любого скрипта
Решение: Использовать ВНЕШНИЙ тест БЕЗ Python

Варианты тестирования:
1. Браузер: file://F:/Нейронки/prototype/test_websocket.html
2. curl + jq:
   curl -X POST http://localhost:8001/api/ui/generate \\
     -H "Content-Type: application/json" \\
     -d '{"task":"Создай интерфейс для игры в крестики-нолики 3x3"}'

3. PowerShell WebSocket (чистый, без Python):
   См. test_tictactoe.bat

РЕШЕНИЕ ПАДАЮЩЕГО BACKEND:
- Backend использует singleton NeiraWrapper
- При импорте любого Python файла в prototype/ происходит:
  1. sys.path.insert(0, "F:\\Нейронки\\prototype")  
  2. Import neira_wrapper → создаётся экземпляр
  3. Backend видит конфликт → shutdown

FIX:
- Вынести test скрипты в отдельную папку tests/ ВНЕ prototype
- Или использовать non-Python тесты (HTML, curl, Postman)
"""

import subprocess
import time
from pathlib import Path

def start_backend():
    """Запустить backend в отдельном процессе."""
    print("🚀 Запускаем backend...")
    
    # Запускаем в новом окне PowerShell
    subprocess.Popen(
        ["powershell", "-NoExit", "-Command", "python -m backend.api"],
        cwd=Path(__file__).parent,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    print("⏳ Ждём инициализации (10 сек)...")
    time.sleep(10)
    print("✅ Backend должен быть готов")

def open_test_page():
    """Открыть HTML тест в браузере."""
    test_html = Path(__file__).parent / "test_websocket.html"
    
    if not test_html.exists():
        print(f"❌ Файл не найден: {test_html}")
        return
    
    print(f"🌐 Открываю тест: {test_html}")
    subprocess.Popen(["cmd", "/c", "start", str(test_html)], shell=True)
    
    print("""
✅ HTML тест открыт в браузере!

Инструкция:
1. Нажмите "🔌 Подключиться"
2. Нажмите "📤 Создать TicTacToe"  
3. Смотрите логи в браузере
4. Артефакт откроется автоматически

Backend логи смотрите в отдельном окне PowerShell.
""")

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 ИСПРАВЛЕНИЕ ПАДАЮЩЕГО ТЕСТА")
    print("=" * 60)
    print()
    
    choice = input("1️⃣  Запустить backend\n2️⃣  Открыть HTML тест\n3️⃣  Всё вместе\n\nВыбор: ")
    
    if choice == "1":
        start_backend()
    elif choice == "2":
        open_test_page()
    elif choice == "3":
        start_backend()
        open_test_page()
    else:
        print("❌ Неверный выбор")
