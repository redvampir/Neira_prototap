"""Генератор shim-файлов: создает в корне файлы-обёртки для модулей в папке scripts/

Запуск:
    python tools/create_shims.py
"""
from pathlib import Path

ROOT = Path('.').resolve()
SCRIPTS = ROOT / 'scripts'

if not SCRIPTS.exists():
    print('Папка scripts/ не найдена')
    raise SystemExit(1)

count = 0
for p in sorted(SCRIPTS.glob('*.py')):
    name = p.stem
    shim_path = ROOT / f"{name}.py"
    if shim_path.exists():
        # не перезаписываем существующие файлы
        continue
    content = f"""# Auto-generated shim for backward compatibility
# This file re-exports symbols from scripts.{name}
try:
    from scripts.{name} import *
except Exception:
    # Keep import-time errors visible for debugging
    raise
"""
    shim_path.write_text(content, encoding='utf-8')
    count += 1

print(f"Created {count} shims")
