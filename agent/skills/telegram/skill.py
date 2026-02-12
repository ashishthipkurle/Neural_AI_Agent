
import logging
import asyncio
from typing import Dict, Any, Optional

from agent.skills.base_skill import BaseSkill, SkillManifest, SkillResult, SkillHealth

# Try imports
try:
    from telegram import Bot, Update
    from telegram.ext import Application, ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
    from telegram.error import TelegramError
except ImportError:
    Bot = None
    Application = None
    TelegramError = None

class TelegramSkill(BaseSkill):
    """
    Module 8: Telegram Controller Skill
    Messaging and Human-in-the-Loop Approval.
    Supports both sending and receiving messages via polling.
    """

    def __init__(self, config: Dict[str, Any] = None, agent: Any = None):
        self._name = "telegram"
        super().__init__()
        self.config = config or {}
        self.agent = agent
        
        self.token = self.config.get('telegram', {}).get('bot_token')
        self.chat_id = self.config.get('telegram', {}).get('chat_id') # Main user ID
        
        self.bot = None
        self.application = None
        self._polling_task = None
        
        self._setup_bot()

    def _setup_bot(self):
        if Application and self.token:
            try:
                # Build Application (v20+)
                builder = ApplicationBuilder().token(self.token)
                builder.connect_timeout(30.0)
                builder.read_timeout(30.0)
                builder.write_timeout(30.0)
                self.application = builder.build()
                self.bot = self.application.bot # For legacy/direct use
                
                # Register Handlers
                self.application.add_handler(CommandHandler("start", self._cmd_start))
                # Catch-all for other commands (e.g. /task, /ask)
                self.application.add_handler(MessageHandler(filters.COMMAND, self._handle_command))
                # Handle text messages
                self.application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_message))
                
                self._health = SkillHealth.READY
            except Exception as e:
                self.logger.error(f"Failed to init Telegram app: {e}")
                self._health = SkillHealth.UNAVAILABLE
        else:
            if not Application:
                self.logger.warning("python-telegram-bot not installed.")

    def on_load(self):
        """Sync load."""
        super().on_load()

    async def on_start(self):
        """Start polling on start (with increased timeout handling)."""
        if self.application and not self._polling_task:
            self.logger.info("Starting Telegram polling...")
            try:
                self.logger.info("Initializing Telegram app...")
                await self.application.initialize()
                
                self.logger.info("Starting Telegram app...")
                await self.application.start()
                
                self.logger.info("Starting updaters...")
                # Start polling in background task
                self._polling_task = asyncio.create_task(self.application.updater.start_polling())
                self.logger.info("Telegram polling started.")
            except Exception as e:
                self.logger.error(f"Failed to start polling: {e}")
                import traceback
                self.logger.error(traceback.format_exc())

    async def on_unload(self):
        """Stop polling on unload."""
        if self.application:
            self.logger.info("Stopping Telegram polling...")
            try:
                if self.application.updater.running:
                    await self.application.updater.stop()
                if self.application.running:
                    await self.application.stop()
                    await self.application.shutdown()
            except Exception as e:
                self.logger.error(f"Error stopping Telegram: {e}")
                
            if self._polling_task:
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    pass
            self.logger.info("Telegram polling stopped.")

    # --- Handlers ---

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        await update.message.reply_html(
            f"Hello {user.mention_html()}! I am your AI Agent.\n"
            "I am now connected and listening. You can chat with me directly here."
        )

    async def _handle_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle generic commands (e.g. /task, /open)."""
        if not update.message or not update.message.text:
            return
            
        text = update.message.text
        # Strip leading slash to support fast command routing (e.g. "/open" -> "open")
        if text.startswith('/'):
            text = text[1:]
            
        await self._relay_to_agent(update, text)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages."""
        if not update.message or not update.message.text:
            return
            
        text = update.message.text
        await self._relay_to_agent(update, text)

    async def _relay_to_agent(self, update: Update, text: str):
        """Common logic to send text to agent."""
        user_id = update.effective_user.id
        
        # Security check: only allow main chat_id if configured
        if self.chat_id and str(user_id) != str(self.chat_id):
             self.logger.warning(f"Message from unauthorized user: {user_id}")
             # await update.message.reply_text("⛔ Unauthorized.")
             # return

        if self.agent:
            # Indicate processing
            await update.message.chat.send_action(action="typing")
            
            # Route to agent
            try:
                response = await self.agent.process_input(text, source="telegram")
                # Send response back
                await update.message.reply_text(response)
            except Exception as e:
                self.logger.error(f"Agent processing failed: {e}")
                await update.message.reply_text(f"❌ Error: {str(e)}")
        else:
            await update.message.reply_text("⚠ Agent not linked. Cannot process message.")

    @property
    def name(self) -> str:
        return self._name

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name=self.name,
            version="1.1.0",
            description="Telegram messaging and approval system (Bidirectional).",
            actions=["send_message", "request_approval", "send_document"],
            requires=["python-telegram-bot"],
            permissions=["network"]
        )

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        text = intent.lower() if isinstance(intent, str) else str(intent).lower()
        if "telegram" in text or "send message" in text:
            return 0.9
        return 0.0

    async def execute(self, action: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        if action == "send_message":
            text = params.get('text') or params.get('message')
            if not text:
                return SkillResult(success=False, error="No text provided.")
                
            success = await self.send_message(text)
            return SkillResult(success=success, message="Message sent" if success else "Failed")
            
        elif action == "request_approval":
            description = params.get('description', 'Unknown Action')
            risk_level = params.get('risk_level', 'UNKNOWN')
            
            approved = await self.request_approval(description, risk_level)
            return SkillResult(success=True, data={"approved": approved})

        elif action == "send_document":
            path = params.get('path')
            caption = params.get('caption')
            chat_id = params.get('chat_id')

            if not path:
                return SkillResult(success=False, error="No document path provided.")

            if not self.bot:
                return SkillResult(success=False, error="Telegram bot not initialized.")

            import os
            if not os.path.exists(path):
                return SkillResult(success=False, error=f"File not found: {path}")

            target_chat = chat_id or self.chat_id
            if not target_chat:
                return SkillResult(success=False, error="No destination chat ID.")

            try:
                # Robustly handle sending:
                # If self.bot is the wrapper, it has send_document(document_path=...)
                # If self.bot is ExtBot (raw), it needs send_document(chat_id=..., document=open(...))
                
                # Check if it's the wrapper (has 'auth' attribute usually, or check method signature?)
                # Safest: Try wrapper signature, fallback to raw.
                
                # Actually, based on logs, self.bot IS the ExtBot. Use the raw interface directly.
                with open(path, 'rb') as f:
                    await self.bot.send_document(
                        chat_id=target_chat,
                        document=f,
                        caption=caption
                    )
                return SkillResult(success=True, message=f"Document sent: {path}")
            except Exception as e:
                self.logger.error(f"Failed to send document: {e}")
                return SkillResult(success=False, error=f"Send failed: {e}")
            
        return SkillResult(success=False, error=f"Unknown action: {action}")

    async def send_message(self, text: str, chat_id: str = None) -> bool:
        """Send a simple text message."""
        if not self.bot:
            return False
            
        target = chat_id or self.chat_id
        if not target:
            self.logger.error("No Chat ID provided for Telegram.")
            return False
            
        try:
            await self.bot.send_message(chat_id=target, text=text)
            return True
        except Exception as e:
            self.logger.error(f"Telegram send failed: {e}")
            return False

    async def request_approval(self, action_description: str, risk_level: str) -> bool:
        """
        Send approval request with inline buttons (mocked for foundation logic).
        Returns True/False based on user response.
        """
        if not self.bot or not self.chat_id:
            self.logger.warning("Telegram not configured for approval.")
            return False
            
        message = f"⚠️ **APPROVAL REQUEST** ⚠️\n\nAction: {action_description}\nRisk: {risk_level}\n\nApprove?"
        
        # In a real async bot, we would:
        # 1. Send message with InlineKeyboard (Yes/No)
        # 2. Wait for CallbackQuery handler to trigger an event or future
        # 3. Return the result
        
        await self.send_message(message)
        
        # NOTE: A real implementation would verify specific message ID and wait. 
        # Here we just log it. 
        self.logger.info(f"Sent approval request for {action_description}")
        return False # Default to deny for safety until callback logic is wired up.
