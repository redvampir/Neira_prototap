#!/usr/bin/env python3
"""
Проверка статуса Telegram бота Neira
"""
import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot

async def check_bot_status():
    load_dotenv()
    token = os.getenv('TELEGRAM_BOT_TOKEN')

    if not token:
        print('❌ TELEGRAM_BOT_TOKEN не найден в .env')
        return

    try:
        bot = Bot(token=token)
        info = await bot.get_me()
        print('✅ Бот подключен к Telegram API')
        print(f'📱 Имя: {info.first_name}')
        print(f'👤 Username: @{info.username}')
        print(f'🆔 ID: {info.id}')
        print('🚀 Бот готов к работе!')
    except Exception as e:
        print(f'❌ Ошибка подключения: {e}')

if __name__ == '__main__':
    asyncio.run(check_bot_status())