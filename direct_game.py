"""
Direct Harry Potter game generation (no WebSocket)
"""
import sys
sys.path.insert(0, "f:/Нейронки/prototype")

from ui_code_cell import UICodeCell

# Создаём UICodeCell
cell = UICodeCell()

print("Generating Harry Potter game...")
print("="*80)

# Генерируем игру
keywords = [
    "игра", "гарри поттер", "аркада", "квест", "UI", "управление",
    "клавиши", "WASD", "хогвартс", "артефакты", "чат", "нейра"
]

result = cell.generate_ui(
    keywords=keywords,
    description="Мини-игра в стиле Гарри Поттера с UI, управлением и чатом"
)

if result.success:
    filename = "harry_potter_game_direct.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(result.artifact)
    
    print(f"\nSUCCESS!")
    print(f"File saved: {filename}")
    print(f"Size: {len(result.artifact)} bytes")
    print(f"\nOpening in browser...")
    
    import os
    os.system(f"start {filename}")
    
    print("\nYou can play now!")
else:
    print(f"\nERROR: {result.metadata.get('error', 'Unknown error')}")
