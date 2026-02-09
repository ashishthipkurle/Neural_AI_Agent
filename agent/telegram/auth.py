
import logging
from typing import List, Callable
from functools import wraps

logger = logging.getLogger(__name__)

class TelegramAuth:
    """
    Handles user authentication and authorization for Telegram commands.
    """
    
    def __init__(self, allowed_chat_ids: List[str]):
        self.allowed_chat_ids = set(str(cid) for cid in allowed_chat_ids)
        self.admin_users = {} # chat_id -> username
        
    def is_authorized(self, chat_id: str) -> bool:
        """Check if a chat ID is authorized."""
        return str(chat_id) in self.allowed_chat_ids
        
    def add_authorized_user(self, chat_id: str, username: str) -> None:
        """Add a new authorized user (runtime)."""
        self.allowed_chat_ids.add(str(chat_id))
        self.admin_users[str(chat_id)] = username
        logger.info(f"Authorized new user: {username} ({chat_id})")
        
    def require_auth(self, func: Callable) -> Callable:
        """Decorator to require authorization for command handlers."""
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            chat_id = str(update.effective_chat.id)
            if not self.is_authorized(chat_id):
                logger.warning(f"Unauthorized access attempt from {chat_id}")
                await update.message.reply_text("⛔ Unauthorized access.")
                return
            return await func(update, context, *args, **kwargs)
        return wrapper
        
    def get_authorized_users(self) -> List[str]:
        """Return list of authorized chat IDs."""
        return list(self.allowed_chat_ids)
        
    def revoke_access(self, chat_id: str) -> None:
        """Remove authorization."""
        if str(chat_id) in self.allowed_chat_ids:
            self.allowed_chat_ids.remove(str(chat_id))
            if str(chat_id) in self.admin_users:
                del self.admin_users[str(chat_id)]
