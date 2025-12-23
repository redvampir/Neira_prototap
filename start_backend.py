import subprocess
import time
import sys

print("🚀 Запуск backend...")
process = subprocess.Popen(
    [sys.executable, "-m", "backend.api"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
)

print("⏳ Ждём 10 секунд для запуска...")
time.sleep(10)

print("✅ Backend должен быть готов")
print(f"PID: {process.pid}")
print()
print("Теперь запусти: python test_neira_tictactoe.py")
