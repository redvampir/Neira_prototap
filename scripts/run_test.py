import subprocess
import sys
import os

# Получаем текущую директорию скрипта
script_dir = os.path.dirname(os.path.abspath(__file__))
test_file = os.path.join(script_dir, 'test_selfaware_module.py')

# Запускаем тест
result = subprocess.run([sys.executable, test_file], cwd=script_dir)
sys.exit(result.returncode)
