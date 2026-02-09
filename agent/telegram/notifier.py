
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Helper to send notifications via Telegram.
    """
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        
    async def send_message(self, text: str, chat_id: str = None) -> bool:
        """Send a simple text message."""
        if not self.bot: return False
        try:
            # If no specific chat_id, broadcast to all authorized
            if not chat_id:
                for cid in self.bot.auth.get_authorized_users():
                    await self.bot.application.bot.send_message(chat_id=cid, text=text)
            else:
                await self.bot.application.bot.send_message(chat_id=chat_id, text=text)
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    async def send_file(self, file_path: str, caption: str = None, chat_id: str = None) -> bool:
        """Send a file/document."""
        if not self.bot: return False
        try:
            with open(file_path, 'rb') as f:
                if not chat_id:
                    for cid in self.bot.auth.get_authorized_users():
                        await self.bot.application.bot.send_document(chat_id=cid, document=f, caption=caption)
                else:
                    await self.bot.application.bot.send_document(chat_id=chat_id, document=f, caption=caption)
            return True
        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            return False

    async def send_screenshot(self, image_path: str, chat_id: str = None) -> bool:
        """Send a photo/screenshot."""
        if not self.bot: return False
        try:
            with open(image_path, 'rb') as f:
                if not chat_id:
                    for cid in self.bot.auth.get_authorized_users():
                        await self.bot.application.bot.send_photo(chat_id=cid, photo=f, caption="Screenshot")
                else:
                    await self.bot.application.bot.send_photo(chat_id=chat_id, photo=f, caption="Screenshot")
            return True
        except Exception as e:
            logger.error(f"Failed to send screenshot: {e}")
            return False

    async def notify_task_complete(self, task_id: str, result: str) -> None:
        """Standard notification for task completion."""
        msg = f"✅ Task Completed: {task_id}\n\nResult: {str(result)[:500]}"
        await self.send_message(msg)

    async def notify_task_failed(self, task_id: str, error: str) -> None:
        """Standard notification for task failure."""
        msg = f"❌ Task Failed: {task_id}\n\nError: {error}"
        await self.send_message(msg)

    async def send_progress_update(self, task_id: str, progress: int) -> None:
        """Standard notification for progress."""
        # Only notify on significant steps to avoid spam
        if progress % 25 == 0:
            msg = f"🔄 Task {task_id} Progress: {progress}%"
            await self.send_message(msg)
            
    async def notify_learning_achievement(self, skill: str, level: float) -> None:
        """Notify on skill upgrade."""
        msg = f"🎓 Skill Leveled Up: {skill} -> {level:.2f}"
        await self.send_message(msg)
