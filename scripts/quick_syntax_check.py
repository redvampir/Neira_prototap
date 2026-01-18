"""Quick syntax check for selfaware modules."""
import ast
import sys
from pathlib import Path

files = [
    "introspection_cell.py",
    "experience.py", 
    "curiosity_cell.py",
    "memory_system.py",
    "neira_server.py"
]

root = Path(__file__).parent
errors = []

for f in files:
    path = root / f
    if path.exists():
        try:
            ast.parse(path.read_text(encoding='utf-8'))
            print(f"✓ {f}")
        except SyntaxError as e:
            print(f"✗ {f}: {e}")
            errors.append(f)
    else:
        print(f"? {f} not found")

print(f"\n{'All OK!' if not errors else f'Errors: {len(errors)}'}")
sys.exit(len(errors))
