"""
Telegram Skill - Two-way communication via Telegram Bot.
"""

import logging
import asyncio
import os
from typing import Dict, Any, Optional, List
from telegram import Bot
from telegram.error import TelegramError

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth

class TelegramSkill(BaseSkill):
    """
    Communicates via Telegram Bot API.
    
    Actions:
    - send_message: Send text to user.
    - send_photo: Send image/screenshot.
    - check_messages: Get recent updates (polling).
    """

    def __init__(self):
        super().__init__()
        self._bot: Optional[Bot] = None
        self._chat_id: Optional[str] = None
        self._token: Optional[str] = None
        self._last_update_id = 0

    @property
    def name(self) -> str:
        return "telegram"

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="telegram",
            version="1.0.0",
            description="Telegram Bot Integration for alerts and control.",
            actions=["send_message", "send_photo", "check_messages"],
            requires=["python-telegram-bot"],
            permissions=["network"]
        )

    def on_load(self) -> None:
        """Initialize Telegram Bot."""
        self._token = os.environ.get("TELEGRAM_TOKEN")
        self._chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        
        if self._token:
            try:
                self._bot = Bot(token=self._token)
                self.logger.info("Telegram Bot initialized.")
                # Verify token by getting me
                # Note: synchronous run in async context might be tricky, 
                # but BaseSkill.on_load is sync. We'll verify lazily or use asyncio.run
            except Exception as e:
                self.logger.error(f"Failed to init Telegram Bot: {e}")
        else:
            self.logger.warning("TELEGRAM_TOKEN not found in environment.")

        super().on_load()

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        intent_lower = intent.lower()
        if any(x in intent_lower for x in ["telegram", "send message to me", "message me", "check telegram"]):
            return 0.95
        return 0.0

    def execute(self, action: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        if action == "send_message":
            return self._send_message(params, context)
        elif action == "send_photo":
            return self._send_photo(params)
        elif action == "check_messages":
            return self._check_messages(params)
        return SkillResult(success=False, error=f"Unknown action: {action}")

    def _send_message(self, params: Dict, context: Optional[Dict] = None) -> SkillResult:
        if not self._bot:
            return SkillResult(success=False, error="Telegram Bot not configured. Set TELEGRAM_TOKEN.")
        
        # Determine chat_id: param > env > error
        chat_id = params.get("chat_id") or self._chat_id
        # If we don't know who to send to, we can't send.
        # But maybe the user Sent US a message first? We can grab chat_id from updates if missing.
        if not chat_id:
             return SkillResult(success=False, error="No chat_id provided and TELEGRAM_CHAT_ID not set. Send a message to the bot first and run 'check_messages'.")

        text = params.get("message") or params.get("text") or ""
        
        # If use_previous_result is set, append content from previous step
        if params.get("use_previous_result") and context:
            prev_result = context.get("previous_result")
            if prev_result:
                # Get content from previous step
                if isinstance(prev_result, dict):
                    # If previous result is from scrape, get "content"
                    if "content" in prev_result:
                        content = prev_result.get("content")
                    # If previous result is from write_file, read the file
                    elif "path" in prev_result:
                        try:
                            file_path = prev_result.get("path")
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except Exception as e:
                            content = f"[Could not read file: {e}]"
                    else:
                        content = str(prev_result)
                else:
                    content = str(prev_result)
                
                # Truncate if too long for Telegram (4096 char limit)
                if len(content) > 3500:
                    content = content[:3500] + "\n\n... [truncated]"
                
                text = f"{text}\n\n{content}" if text else content
        
        if not text:
            return SkillResult(success=False, error="No message text provided.")

        try:
            # Use httpx for synchronous context (works in both sync and async)
            import httpx
            
            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text
            }
            
            response = httpx.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                return SkillResult(success=True, message=f"Sent to {chat_id}")
            else:
                return SkillResult(success=False, error=f"Telegram API error: {response.text}")
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _send_photo(self, params: Dict) -> SkillResult:
        if not self._bot:
            return SkillResult(success=False, error="Telegram Bot not configured.")
        
        chat_id = params.get("chat_id") or self._chat_id
        if not chat_id:
             return SkillResult(success=False, error="No chat_id configured.")

        path = params.get("path")
        if not path:
             return SkillResult(success=False, error="No image path provided.")

        try:
            with open(path, 'rb') as f:
                await self._bot.send_photo(chat_id=chat_id, photo=f)
            return SkillResult(success=True, message="Photo sent.")
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _check_messages(self, params: Dict) -> SkillResult:
        """Manually poll for updates."""
        if not self._bot:
            return SkillResult(success=False, error="Bot not init.")

        try:
            updates = await self._bot.get_updates(offset=self._last_update_id + 1)
            
            messages = []
            for u in updates:
                self._last_update_id = u.update_id
                if u.message and u.message.text:
                    # Get sender name - prefer username or first_name
                    sender = u.message.chat.username or u.message.chat.first_name or "User"
                    # Auto-capture chat_id if not set!
                    if not self._chat_id:
                        self._chat_id = str(u.message.chat_id)
                        self.logger.info(f"Learned Chat ID: {self._chat_id}") # Should save this persistently
                    
                    messages.append(f"{sender}: {u.message.text}")

            if messages:
                return SkillResult(
                    success=True, 
                    data={"messages": messages, "learned_chat_id": self._chat_id},
                    message=f"Received {len(messages)} message(s):\n" + "\n".join(messages)
                )
            return SkillResult(success=True, message="No new messages.")

        except Exception as e:
            return SkillResult(success=False, error=str(e))

    def health(self) -> SkillHealth:
        return SkillHealth.READY if self._bot else SkillHealth.DEGRADED
