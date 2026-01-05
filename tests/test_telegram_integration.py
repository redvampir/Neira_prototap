# -*- coding: utf-8 -*-
"""
Тест интеграции Telegram Bot с Neira Server

Проверяет:
1. Доступность сервера
2. Работу neira_client
3. Статус telegram_bot
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Настройка путей - используем cwd вместо __file__
script_dir = Path(os.getcwd())
sys.path.insert(0, str(script_dir))

# Загрузка .env
from dotenv import load_dotenv
load_dotenv(script_dir / ".env")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


async def test_server_health():
    """Тест 1: Проверка доступности сервера"""
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 1: Проверка сервера Neira")
    print("=" * 60)
    
    try:
        from neira_client import get_client
        client = get_client()
        
        status = await client.get_status()
        
        if status.is_running:
            print(f"✅ Сервер работает на {status.url}")
            print(f"   Version: {status.version}")
            print(f"   Uptime: {status.uptime_seconds}s")
            return True
        else:
            print(f"❌ Сервер недоступен: {status.error}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False


async def test_chat_api():
    """Тест 2: Проверка chat API"""
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 2: Проверка Chat API")
    print("=" * 60)
    
    try:
        from neira_client import get_client
        client = get_client()
        
        # Простой запрос
        response = await client.chat("Привет! Тест интеграции.", user_id="test_user_123")
        
        if response.success:
            print(f"✅ Chat API работает")
            print(f"   Ответ: {response.data.get('response', '')[:100]}...")
            return True
        else:
            print(f"❌ Chat API ошибка: {response.error}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_feedback_api():
    """Тест 3: Проверка Feedback API (Phase 2)"""
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 3: Проверка Feedback API")
    print("=" * 60)
    
    try:
        from neira_client import get_client
        client = get_client()
        
        result = await client.send_feedback_async(
            query="тестовый запрос",
            response="тестовый ответ",
            feedback="positive",
            score=0.9,
            user_id="test_user_123",
            source="telegram_test"
        )
        
        if result and result.get("success"):
            print(f"✅ Feedback API работает")
            actions = result.get("data", {}).get("actions_taken", [])
            print(f"   Actions: {actions}")
            return True
        else:
            print(f"❌ Feedback API ошибка: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_telegram_bot_config():
    """Тест 4: Проверка конфигурации Telegram бота"""
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 4: Конфигурация Telegram Bot")
    print("=" * 60)
    
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN не установлен в .env")
        return False
    
    # Маскируем токен
    masked = token[:10] + "..." + token[-5:]
    print(f"✅ TELEGRAM_BOT_TOKEN найден: {masked}")
    
    # Проверяем формат
    if ":" not in token:
        print("❌ Неверный формат токена")
        return False
    
    bot_id = token.split(":")[0]
    print(f"   Bot ID: {bot_id}")
    
    return True


async def test_telegram_bot_connection():
    """Тест 5: Проверка связи с Telegram API"""
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 5: Связь с Telegram API")
    print("=" * 60)
    
    try:
        import aiohttp
        
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            print("❌ Нет токена")
            return False
        
        url = f"https://api.telegram.org/bot{token}/getMe"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                
                if data.get("ok"):
                    bot_info = data.get("result", {})
                    print(f"✅ Telegram API доступен")
                    print(f"   Bot: @{bot_info.get('username')}")
                    print(f"   Name: {bot_info.get('first_name')}")
                    print(f"   Can join groups: {bot_info.get('can_join_groups')}")
                    return True
                else:
                    print(f"❌ Telegram API ошибка: {data}")
                    return False
                    
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def test_telegram_updates():
    """Тест 6: Проверка очереди обновлений Telegram"""
    print("\n" + "=" * 60)
    print("🧪 ТЕСТ 6: Очередь обновлений Telegram")
    print("=" * 60)
    
    try:
        import aiohttp
        
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            print("❌ Нет токена")
            return False
        
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {"limit": 5, "timeout": 1}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as resp:
                data = await resp.json()
                
                if data.get("ok"):
                    updates = data.get("result", [])
                    print(f"✅ Получено обновлений: {len(updates)}")
                    
                    if updates:
                        for upd in updates[-3:]:
                            msg = upd.get("message", {})
                            text = msg.get("text", "")[:50]
                            user = msg.get("from", {}).get("username", "?")
                            print(f"   - @{user}: {text}")
                    else:
                        print("   (очередь пуста — бот не получал сообщений)")
                    
                    return True
                else:
                    desc = data.get("description", "Unknown error")
                    print(f"❌ Ошибка: {desc}")
                    
                    if "Conflict" in desc:
                        print("   ⚠️ Бот уже запущен в другом процессе!")
                        print("   Решение: остановите другой экземпляр бота")
                    
                    return False
                    
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def main():
    """Запуск всех тестов"""
    print("\n" + "🔬" * 30)
    print("    ДИАГНОСТИКА TELEGRAM ИНТЕГРАЦИИ")
    print("🔬" * 30)
    
    results = {}
    
    # Тест 1: Сервер
    results["server"] = await test_server_health()
    
    # Тест 2: Chat API (только если сервер работает)
    if results["server"]:
        results["chat_api"] = await test_chat_api()
    else:
        results["chat_api"] = False
        print("\n⏭️ Тест Chat API пропущен (сервер недоступен)")
    
    # Тест 3: Feedback API
    if results["server"]:
        results["feedback_api"] = await test_feedback_api()
    else:
        results["feedback_api"] = False
        print("\n⏭️ Тест Feedback API пропущен (сервер недоступен)")
    
    # Тест 4: Конфигурация
    results["tg_config"] = test_telegram_bot_config()
    
    # Тест 5: Telegram API
    results["tg_api"] = await test_telegram_bot_connection()
    
    # Тест 6: Updates
    results["tg_updates"] = await test_telegram_updates()
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ДИАГНОСТИКИ")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "-" * 60)
    
    if all_passed:
        print("🎉 Все тесты пройдены!")
        print("\n📝 Если Telegram бот не отвечает:")
        print("   1. Убедитесь что telegram_bot.py запущен")
        print("   2. Проверьте что нет другого экземпляра бота")
    else:
        print("⚠️ Есть проблемы!")
        
        if not results["server"]:
            print("\n🔧 РЕШЕНИЕ: Запустите сервер")
            print("   python neira_server.py")
        
        if not results.get("tg_updates"):
            print("\n🔧 РЕШЕНИЕ: Запустите Telegram бота")
            print("   python telegram_bot.py")
    
    return all_passed


if __name__ == "__main__":
    asyncio.run(main())
