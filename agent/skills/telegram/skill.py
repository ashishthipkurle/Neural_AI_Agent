from typing import Dict, Any, Optional, List
from agent.skills.base_skill import BaseSkill, SkillResult
import logging

class TelegramSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "telegram"

    @property
    def manifest(self):
        from agent.skills.base_skill import SkillManifest
        return SkillManifest(
            name="telegram",
            version="1.0.0",
            description="Telegram integration using shared bot instance.",
            actions=["send_message", "check_messages"],
            permissions=["network"]
        )

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if skill can handle intent."""
        intent = intent.lower()
        if "telegram" in intent or "message" in intent:
            return 0.9
        return 0.0

    def __init__(self):
        # Initialize with None, injected later
        self._bot = None 
        super().__init__()

    def inject_bot(self, bot_instance):
        """Inject the shared TelegramBot instance."""
        self._bot = bot_instance
        # logging.info("Telegram Bot injected into Skill.")

    async def execute(self, action: str, params: Dict[str, Any], context: Dict[str, Any] = None) -> SkillResult:
        if not self._bot:
             return SkillResult(success=False, error="Telegram Bot not active (not injected).")
        
        if action == "send_message":
            msg = params.get("message")
            chat_id = params.get("chat_id")
            # Use notifier from bot
            if self._bot.notifier:
                success = await self._bot.notifier.send_message(msg, chat_id)
                return SkillResult(success=success, message="Message sent" if success else "Failed")
            return SkillResult(success=False, error="Notifier not available")
            
        elif action == "send_document":
            path = params.get("path")
            caption = params.get("caption")
            if self._bot:
                 await self._bot.send_document(path, caption)
                 return SkillResult(success=True, message=f"Document sent: {path}")
            return SkillResult(success=False, error="Bot not active")
            
        elif action == "check_messages":
            return SkillResult(success=True, message="Bot is polling actively.")
            
        else:
            return SkillResult(success=False, error=f"Unknown action: {action}")
