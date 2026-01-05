#!/usr/bin/env python3
"""
Neira Launcher — Единая точка входа для всех режимов работы.

Использование:
    python neira.py telegram     # Telegram бот
    python neira.py server       # HTTP/WebSocket сервер
    python neira.py cli          # Консольный режим
    python neira.py test         # Запуск тестов
    python neira.py status       # Проверка статуса систем
    
Опции:
    --port PORT         Порт для сервера (по умолчанию 8765)
    --verbose, -v       Подробный вывод
    --help, -h          Справка
"""

import argparse
import sys
import os

# Фикс кодировки для Windows консоли
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from pathlib import Path

# Добавляем корень проекта в PATH
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))


def run_telegram():
    """Запуск Telegram бота."""
    print("🚀 Запуск Telegram бота...")
    from telegram_bot import main
    main()


def run_server(port: int = 8765, modules: str = "all"):
    """Запуск HTTP/WebSocket сервера."""
    print(f"🌐 Запуск сервера на порту {port}...")
    os.environ.setdefault("NEIRA_PORT", str(port))
    os.environ.setdefault("NEIRA_SERVICE_MODE", modules)
    from neira_server import start_server
    start_server()


def run_cli():
    """Консольный режим общения."""
    print("💬 Консольный режим (Ctrl+C для выхода)")
    print("=" * 50)
    
    try:
        from main import Neira
        neira = Neira()
        
        while True:
            try:
                user_input = input("\n👤 Вы: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ('выход', 'exit', 'quit', 'q'):
                    print("👋 До свидания!")
                    break
                    
                response = neira.process(user_input)
                print(f"\n🧠 Нейра: {response}")
                
            except KeyboardInterrupt:
                print("\n👋 До свидания!")
                break
                
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("   Попробуйте: pip install -r requirements.txt")
        sys.exit(1)


def run_tests(pattern: str = "", verbose: bool = False):
    """Запуск тестов."""
    import subprocess
    
    cmd = ["python", "-m", "pytest", "tests/"]
    if verbose:
        cmd.append("-v")
    if pattern:
        cmd.extend(["-k", pattern])
    cmd.extend(["--tb=short", "-m", "not slow"])
    
    print(f"🧪 Запуск: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT_DIR)


def show_status():
    """Показать статус всех систем."""
    print("📊 Статус систем Neira")
    print("=" * 50)
    
    # LLM
    print("\n🤖 LLM Providers:")
    try:
        from llm_providers import create_default_manager
        manager = create_default_manager()
        if manager and manager.providers:
            for p in manager.providers:
                status = "✅" if p.available else "❌"
                print(f"   {status} {p.get_provider_type().value}: {p.model}")
        else:
            print("   ⚠️ Нет доступных провайдеров")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Память
    print("\n💾 Memory System:")
    try:
        from memory_system import MemorySystem
        ms = MemorySystem(".")
        stats = ms.get_stats()
        print(f"   📚 Long-term: {stats['long_term']} записей")
        print(f"   📝 Short-term: {stats['short_term']} записей")
        print(f"   🔄 Pending validation: {stats['pending_validation']}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Органы
    print("\n🧬 Organ System:")
    try:
        from unified_organ_system import get_organ_system
        system = get_organ_system()
        print(f"   Активных органов: {len(system.organs)}")
        for oid, organ in list(system.organs.items())[:5]:
            print(f"   • {organ.name}")
        if len(system.organs) > 5:
            print(f"   ... и ещё {len(system.organs) - 5}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Neural Pathways
    print("\n🧠 Neural Pathways:")
    try:
        from neural_pathways import NeuralPathwaySystem
        pathways = NeuralPathwaySystem()
        print(f"   Загружено: {len(pathways.pathways)} pathways")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print("\n" + "=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Neira — Единый лаунчер",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "mode",
        choices=["telegram", "server", "cli", "test", "status"],
        nargs="?",
        default="status",
        help="Режим работы"
    )
    
    parser.add_argument("--port", "-p", type=int, default=8765, help="Порт сервера")
    parser.add_argument("--modules", "-m", default="all", help="Модули сервера")
    parser.add_argument("--verbose", "-v", action="store_true", help="Подробный вывод")
    parser.add_argument("--pattern", "-k", default="", help="Паттерн для тестов")
    
    args = parser.parse_args()
    
    print("\n=== NEIRA LAUNCHER ===")
    
    if args.mode == "telegram":
        run_telegram()
    elif args.mode == "server":
        run_server(args.port, args.modules)
    elif args.mode == "cli":
        run_cli()
    elif args.mode == "test":
        run_tests(args.pattern, args.verbose)
    elif args.mode == "status":
        show_status()


if __name__ == "__main__":
    main()
