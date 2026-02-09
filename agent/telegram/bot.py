
import logging
import asyncio
from typing import List, Optional
from telegram.ext import Application, ApplicationBuilder
from .auth import TelegramAuth
from .notifier import TelegramNotifier
from .commands import setup_commands

logger = logging.getLogger(__name__)

class TelegramBot:
    """
    Main Telegram Bot Wrapper.
    """
    
    def __init__(self, token: str, allowed_chat_ids: List[str]):
        self.token = token
        self.auth = TelegramAuth(allowed_chat_ids)
        self.application = None
        self.notifier = None
        self.running = False
        self.orchestrator = None # Store reference

    async def initialize(self):
        """Initialize the bot application."""
        if not self.token:
            logger.warning("No Telegram token provided.")
            return

        self.application = ApplicationBuilder().token(self.token).build()
        self.notifier = TelegramNotifier(self)
        
        # Inject orchestrator if set before init
        if self.orchestrator:
             self.application.bot_data['orchestrator'] = self.orchestrator
        
        # Register commands
        setup_commands(self.application, self.auth)
        
        await self.application.initialize()
        logger.info("Telegram Bot Initialized.")

    async def start(self):
        """Start polling."""
        if not self.application:
            return
            
        self.running = True
        logger.info("Starting Telegram Polling...")
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop(self):
        """Stop the bot."""
        if not self.application:
            return
            
        self.running = False
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("Telegram Bot Stopped.")

    def register_handlers(self):
        """Re-register handlers (if needed)."""
        if self.application:
             setup_commands(self.application, self.auth)

    async def handle_message(self, update):
        """Manual message handling (webhook mode)."""
        if self.application:
            await self.application.process_update(update)

    async def send_notification(self, text: str):
        """Send a notification."""
        if self.notifier:
            await self.notifier.send_message(text)
            
    async def send_document(self, document_path: str, caption: str = None):
        """Send a document/file."""
        if self.auth and self.application:
            # Broadcast to all allowed users
            for chat_id in self.auth.allowed_chat_ids:
                try:
                    await self.application.bot.send_document(
                        chat_id=chat_id,
                        document=open(document_path, 'rb'),
                        caption=caption
                    )
                except Exception as e:
                    logger.error(f"Failed to send document to {chat_id}: {e}")

    # Webhook support methods
    def setup_webhook(self, url: str):
        pass # Placeholder
        
    def handle_webhook(self, update_json: dict):
        pass # Placeholder

    def set_orchestrator(self, orchestrator):
        """Link to the main agent orchestrator."""
        self.orchestrator = orchestrator
        if self.application:
            self.application.bot_data['orchestrator'] = orchestrator

    def get_status(self):
        return "Running" if self.running else "Stopped"
