"""
Simple script to send a Telegram message using python-telegram-bot.
"""

import asyncio
from telegram import Bot

async def send_message():
    # Telegram credentials
    token = "8205025100:AAETjiqViw-Pv7wiloRG7wbeu736EgYnLQM"
    chat_id = "6092753706"
    
    # Create bot instance
    bot = Bot(token=token)
    
    try:
        # Send a simple "hi" message
        await bot.send_message(chat_id=chat_id, text="hi")
        print("Message sent successfully!")
    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == "__main__":
    asyncio.run(send_message())