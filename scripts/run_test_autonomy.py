# -*- coding: utf-8 -*-
"""Скрипт запуска тестов autonomy_engine"""
import os
import sys

# Определяем путь к директории скрипта
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
sys.path.insert(0, script_dir)

# Запускаем тест
if __name__ == "__main__":
    print(f"Working directory: {os.getcwd()}")
    print(f"Python: {sys.executable}")
    print("-" * 50)
    
    # Импортируем и запускаем тесты
    import autonomy_engine
