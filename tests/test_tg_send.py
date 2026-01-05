"""Тест отправки сообщения через Telegram бота"""
import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot

async def test_send():
    load_dotenv()
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    bot = Bot(token=token)
    
    # Получаем обновления чтобы узнать chat_id
    updates = await bot.get_updates(limit=5)
    
    if updates:
        chat_id = updates[-1].message.chat.id if updates[-1].message else None
        if chat_id:
            await bot.send_message(chat_id, "🧪 Тест от Claude: Нейра работает через LM Studio!")
            print(f"✅ Сообщение отправлено в чат {chat_id}")
        else:
            print("⚠️ Нет сообщений с chat_id")
    else:
        print("⚠️ Нет обновлений. Отправьте /start боту первыми")

if __name__ == '__main__':
    asyncio.run(test_send())
