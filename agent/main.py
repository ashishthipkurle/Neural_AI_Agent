"""
Humanoid Local AI Agent - Main Entry Point

This is the production entry point for the Neural AI Agent.
It initializes all subsystems and starts the main application loop.

CONSTRAINTS (NON-NEGOTIABLE):
- LOCAL execution ONLY
- OFFLINE LLM ONLY
- NO cloud APIs
- EXPLICIT user consent for ALL actions
- FULL audit logging

Author: Antigravity AI
Version: 2.0.0
"""
import asyncio
import logging
import sys
import os
import uuid
from pathlib import Path
from typing import Optional
from agent.core.command_router import CommandRouter # Fast Router
from agent.core.router import ToolRouter # Tool Registry
from agent.skills import SkillRouter # Clowbot-class Skill Router

# Add project root to path (parent of agent/) for 'agent.' imports to work
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    logger_temp = logging.getLogger("NeuralAgent")
    logger_temp.info("Loaded .env file")
except ImportError:
    pass  # dotenv not installed, skip

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("agent.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("NeuralAgent")


def load_config(config_path: str = "agent/config/settings.yaml") -> dict:
    """Load configuration from YAML file."""
    import yaml
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}


class NeuralAgent:
    """
    Main agent class that coordinates all subsystems.
    
    This is the unified entry point for the humanoid AI agent.
    """
    
    def __init__(self, config_path: str = "agent/config/settings.yaml"):
        """Initialize the agent."""
        logger.info("=" * 60)
        logger.info("  NEURAL AI AGENT - Initializing")
        logger.info("=" * 60)
        
        self.config = load_config(config_path)
        self._initialized = False
        
        # External synchronization hooks
        self.sync_broadcast = None
        
        # Core subsystems (lazy initialization)
        self._state_machine = None
        self._consent_gate = None
        self._command_router = None # Core orchestrator router
        self.fast_command_router = CommandRouter() # Fast regex router
        self._skill_router = None # Clowbot-class skill router
        self._rollback_manager = None
        self._llm_runtime = None
        self._audit_logger = None
        self._voice_manager = None
        self._lock_controller = None
        self._short_term_memory = None
        self._short_term_memory = None
        self._long_term_memory = None
        self._history_manager = None
        self.active_conversation_id = None
    
    def _init_core_systems(self):
        """Initialize core orchestration systems."""
        logger.info("Initializing core systems...")
        
        try:
            from agent.core.orchestrator import StateMachine, ConsentGate, CommandRouter, RollbackManager
            from agent.security.audit_log import AuditLogger
            
            self._state_machine = StateMachine()
            self._audit_logger = AuditLogger()
            
            # Extract auto-approval setting
            security_config = self.config.get('security', {})
            auto_approval = security_config.get('auto_approval', False)
            
            self._consent_gate = ConsentGate(auto_approval=auto_approval)
            self._rollback_manager = RollbackManager()
            self._command_router = CommandRouter(
                state_machine=self._state_machine,
                consent_gate=self._consent_gate,
                audit_logger=self._audit_logger
            )
            
            # Initialize ToolRouter and register tools
            self._tool_router = ToolRouter()
            for tool_name, handler in self._tool_router.tools.items():
                self._command_router.register_handler(tool_name, handler)
            
            logger.info(f"✓ Core systems initialized (Registered {len(self._tool_router.tools)} tools)")
            
            # Initialize Skill Router (Clowbot-class)
            try:
                self._skill_router = SkillRouter()
                self._skill_router.initialize()
                skills = self._skill_router.list_skills()
                logger.info(f"✓ Skill Router initialized ({len(skills)} skills loaded)")
                
                # Link to ToolRouter for cross-skill execution
                if hasattr(self._tool_router, 'set_skill_router'):
                    self._tool_router.set_skill_router(self._skill_router)
                    
            except Exception as skill_err:
                logger.warning(f"⚠ Skill Router partial: {skill_err}")
            
            logger.info("✓ Core systems initialized")
        except Exception as e:
            logger.error(f"✗ Core systems failed: {e}")
            raise
    
    def _init_llm(self):
        """Initialize local LLM runtime."""
        logger.info("Initializing LLM runtime...")
        
        try:
            from agent.core.llm import LocalLLMRuntime, LLMBackend
            
            llm_config = self.config.get('llm', {})
            provider = llm_config.get('provider', 'ollama')
            model_name = llm_config.get('model_name', 'phi3:mini')
            
            backend = LLMBackend.OLLAMA if provider == 'ollama' else LLMBackend.LLAMA_CPP
            
            self._llm_runtime = LocalLLMRuntime(
                backend=backend,
                model_name=model_name,
                config=llm_config
            )
            
            if self._llm_runtime.is_available():
                logger.info(f"✓ LLM runtime initialized ({provider}/{model_name})")
            else:
                logger.warning("⚠ LLM runtime not available - ensure Ollama is running")
        except Exception as e:
            logger.error(f"✗ LLM initialization failed: {e}")
    
    def _init_memory(self):
        """Initialize memory systems."""
        logger.info("Initializing memory systems...")
        
        try:
            from agent.memory.short_term import ShortTermMemory
            from agent.memory.vector_store import VectorStore
            from agent.memory.history_manager import HistoryManager
            
            self._short_term_memory = ShortTermMemory()
            self._long_term_memory = VectorStore()
            self._history_manager = HistoryManager()
            
            # Don't auto-create session on startup.
            # Sessions are created lazily when the user sends their first message.
            self.active_conversation_id = None
            
            logger.info("✓ Memory systems initialized")
        except Exception as e:
            logger.warning(f"⚠ Memory initialization partial: {e}")
    
    def _init_security(self):
        """Initialize security systems."""
        logger.info("Initializing security systems...")
        
        try:
            from agent.security.face import FaceCamera, EmbeddingStore, FaceVerifier, LockController, PINFallback
            
            camera = FaceCamera()
            embedding_store = EmbeddingStore()
            pin_fallback = PINFallback(default_pin="1234")  # Default PIN for first use
            
            face_verifier = FaceVerifier(camera, embedding_store)
            
            self._lock_controller = LockController(
                face_verifier=face_verifier,
                pin_fallback=pin_fallback,
                state_machine=self._state_machine,
                audit_logger=self._audit_logger
            )
            
            logger.info("✓ Security systems initialized")
        except Exception as e:
            logger.warning(f"⚠ Security initialization partial: {e}")
    
    def _init_voice(self):
        """Initialize voice systems."""
        logger.info("Initializing voice systems...")
        
        try:
            from agent.voice.voice_manager import VoiceManager, VoiceConfig
            from agent.voice.emotion_controller import EmotionController
            
            voice_config = self.config.get('voice_settings', {})
            
            config = VoiceConfig(
                wake_words=voice_config.get('wake_words', ["hey antigravity", "antigravity", "hii bro", "hey bro"]),
                greeting_message=voice_config.get('greeting', 'Hey there!'),
                confirm_before_action=True,
                voice_speed=voice_config.get('speed', 1.0),
                enable_emotion=True
            )
            
            self._voice_manager = VoiceManager(config=config)
            
            # Apply sync hooks if injected
            if self.sync_broadcast:
                self._voice_manager.on_stt = lambda text: self.sync_broadcast("stt", "user", text)
                self._voice_manager.on_partial = lambda text: self.sync_broadcast("stt", "user", text, partial=True)
                self._voice_manager.on_status = lambda text: self.sync_broadcast("status", "system", text)
            
            logger.info("✓ Voice systems initialized")
        except Exception as e:
            logger.warning(f"⚠ Voice initialization partial: {e}")
    
    def initialize(self):
        """Initialize all agent subsystems."""
        if self._initialized:
            return
        
        try:
            self._init_core_systems()
            self._init_llm()
            self._init_memory()
            self._init_security()
            self._init_voice()
            
            self._initialized = True
            logger.info("=" * 60)
            logger.info("  NEURAL AI AGENT - Ready")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Agent initialization failed: {e}")
            raise
    
    async def process_input(self, user_input: str, image_data: Optional[str] = None) -> str:
        """
        Process user input and return response with full sync.
        
        Flow:
        1. Parse intent
        2. Execute tools with task_ids
        3. Broadcast assistant response and speak
        """
        if not self._initialized:
            return "Agent not initialized. Please wait..."
        
        # Check if locked
        if self._lock_controller and self._lock_controller.is_locked:
            return "Agent is locked. Please authenticate to unlock."
        
        # Add to short-term memory
        # Add to short-term memory
        if self._short_term_memory:
            msg_content = user_input
            if image_data:
                msg_content += " [Image Attached]"
            self._short_term_memory.add_message("user", msg_content)
            
        # PERSISTENCE: Save to History Database
        if self._history_manager:
            if not self.active_conversation_id:
                # Create a new conversation - title will be auto-generated by add_message on first user message
                self.active_conversation_id = self._history_manager.create_conversation(title="New Chat")
            
            self._history_manager.add_message(
                self.active_conversation_id, 
                "user", 
                user_input + (" [Image Attached]" if image_data else "")
            )
        
        # State transitions
        self._state_machine.to_listening("Received input")
        self._state_machine.to_thinking("Processing input")

        # Handle Image Attachment
        if image_data:
            try:
                import base64
                import os
                import time
                
                # Save to temp file
                temp_dir = os.path.join(PROJECT_ROOT, "temp", "uploads")
                os.makedirs(temp_dir, exist_ok=True)
                filename = f"upload_{int(time.time())}.png"
                image_path = os.path.join(temp_dir, filename)
                
                with open(image_path, "wb") as f:
                    # Handle both raw base64 and data URI
                    if "," in image_data:
                        image_data = image_data.split(",")[1]
                    f.write(base64.b64decode(image_data))
                
                logger.info(f"Saved attached image to: {image_path}")
                
                # Append path to input so LLM can see it
                user_input += f" [Image Path: {image_path}]"
                
            except Exception as e:
                logger.error(f"Failed to save image attachment: {e}")
        
        # BUSY LOCK: Start
        if self._voice_manager:
            self._voice_manager.set_busy(True)
        
        # Broadcast Processing State IMMEDIATELY
        task_id = str(uuid.uuid4()) if 'uuid' in sys.modules or 'uuid' in globals() else str(int(asyncio.get_event_loop().time()))
        if self.sync_broadcast:
            self.sync_broadcast("status", "system", "Processing...", task_id)
        
        try:
            # ---------------------------------------------------------
            # FAST PATH: Regex Command Router (Bypass LLM)
            # ---------------------------------------------------------
            if self.fast_command_router and self.fast_command_router.can_handle(user_input):
                logger.info(f"Fast routing command: {user_input}")
                
                # Notify UI processing
                if self.sync_broadcast:
                    self.sync_broadcast("status", "system", "Executing fast command...", task_id)
                
                # Execute
                result = await self.fast_command_router.execute(user_input)
                response_text = result.get("response", "Done.")
                
                # Broadcast Assistant Response
                if self.sync_broadcast:
                    self.sync_broadcast("assistant", "assistant", response_text, task_id)
                
                # Speak (with suppression to avoid double speech)
                if self._voice_manager:
                     await self._voice_manager.speak(response_text, suppress_sync=True)
                
                # Broadcast Task Completion
                if self.sync_broadcast:
                    self.sync_broadcast("status", "system", "Done", task_id)
                    
                # Add to memory
                if self._short_term_memory:
                    self._short_term_memory.add_message("assistant", response_text)
                    
                self._state_machine.to_idle("Fast command complete")
                return response_text
            # ---------------------------------------------------------

            # ---------------------------------------------------------
            # SKILL ROUTER PATH: Clowbot-class skill execution
            # ---------------------------------------------------------
            if self._skill_router:
                # Try to route through skill system first
                skill = self._skill_router.skill_loader.get_skill_for_intent(user_input)
                if skill:
                    logger.info(f"Skill routing: {user_input} -> Skill '{skill.name}'")
                    
                    if self.sync_broadcast:
                        self.sync_broadcast("status", "system", f"Executing via {skill.name} skill...", task_id)
                    
                    result = await self._skill_router.route_intent(user_input)
                    
                    if result.success:
                        response_text = result.result.message or str(result.result.data)
                        
                        # Broadcast Assistant Response
                        if self.sync_broadcast:
                            self.sync_broadcast("assistant", "assistant", response_text, task_id)
                        
                        # Speak
                        if self._voice_manager:
                            await self._voice_manager.speak(response_text, suppress_sync=True)
                        
                        # Broadcast Task Completion
                        if self.sync_broadcast:
                            self.sync_broadcast("status", "system", "Done", task_id)
                        
                        # Add to memory
                        if self._short_term_memory:
                            self._short_term_memory.add_message("assistant", response_text)
                        
                        self._state_machine.to_idle("Skill execution complete")
                        return response_text
            # ---------------------------------------------------------

            # Parse intent
            from agent.core.intent import IntentParser
            parser = IntentParser(self.config)
            intents = parser.parse(user_input)
            
            response = None
            
            # 1. ACKNOWLEDGE (Sync)
            if any(intent.action != "chat" for intent in intents):
                if self._voice_manager:
                    # VoiceManager.acknowledge now calls on_status(sync_broadcast)
                    await self._voice_manager.acknowledge()
            
            for intent in intents:
                logger.info(f"Intent: {intent.action} -> {intent.parameters}")
                
                # Execute actions - PROGRESS (Sync via on_status in handlers or here)
                if intent.action == "launch_app" and intent.parameters.get("app_name"):
                    app_name = intent.parameters["app_name"]
                    extra_args = intent.parameters.get("extra_args") # e.g. URL for browser
                    if self.sync_broadcast:
                        self.sync_broadcast("status", "system", f"Opening {app_name}", task_id)
                    response = await self._execute_launch_app(app_name, extra_args)
                    
                elif intent.action == "browser_navigate" and intent.parameters.get("url"):
                    url = intent.parameters["url"]
                    if self.sync_broadcast:
                        self.sync_broadcast("status", "system", f"Navigating to {url}", task_id)
                    response = await self._execute_browser(url)
                    
                elif intent.action == "type_text" and intent.parameters.get("text"):
                    response = await self._execute_type(intent.parameters["text"])
                    
                elif intent.action == "press_key" and intent.parameters.get("key"):
                    response = await self._execute_keypress(intent.parameters["key"])
                    
                elif intent.action == "capture_screen":
                    response = await self._execute_screenshot()
                
                elif intent.action == "telegram_gui_send":
                    # Route to DesktopSkill for GUI-based Telegram messaging
                    contact = intent.parameters.get("contact", "")
                    message = intent.parameters.get("message", "")
                    if self.sync_broadcast:
                        self.sync_broadcast("status", "system", f"Opening Telegram to message {contact}...", task_id)
                    
                    if self._skill_router:
                        result = await self._skill_router.execute_skill_action(
                            "desktop", "telegram_gui_send", 
                            {"contact": contact, "message": message}
                        )
                        response = result.result.message if result.success else f"Failed: {result.error}"
                    else:
                        response = "Desktop skill not available"
                    
                elif intent.action in ["chat", "chat_tool", "unknown"]:
                    # These will be handled by LLM response unification below
                    pass
                
                else:
                    # Command Router execution
                    if self._command_router:
                        handler = self._command_router.get_handler(intent.action)
                        if handler:
                            if self.sync_broadcast:
                                self.sync_broadcast("status", "system", f"Executing {intent.action}", task_id)
                            result = await self._command_router.route(intent.action, intent.parameters)
                            raw_response = str(result.result) if result.success else result.error
                            
                            # SYNTHESIS: If search tool, feed back to LLM for natural response
                            if intent.action in ["search_online", "search_memory"] and result.success:
                                # Truncate to prevent context overflow
                                truncated = raw_response[:2000] if len(raw_response) > 2000 else raw_response
                                
                                synthesis_prompt = f"""User Question: {user_input}

Search Results:
{truncated}

Based ONLY on the search results above, provide a direct answer to the user's question.
Be concise (1-3 sentences). If a specific name or fact is mentioned, state it clearly.
Do NOT say "according to the search results" - just answer directly."""

                                response = await self._chat_with_llm(synthesis_prompt)
                            else:
                                response = raw_response
            
            # 2. CONVERSION / ASSISTANT RESPONSE
            if not response:
                if image_data:
                    response = await self._chat_with_llm(user_input, images=[image_data])
                else:
                    response = await self._chat_with_llm(user_input)

            # UNIFIED SYNC: Broadcast assistant event AND Speak
            if self.sync_broadcast:
                self.sync_broadcast("assistant", "assistant", response, task_id)
            
            if self._voice_manager:
                # speak is a consumer here because we already broadcasted
                await self._voice_manager.speak(response, suppress_sync=True)
            
            # CONFIRM COMPLETION (Sync)
            if any(intent.action != "chat" for intent in intents):
                if self.sync_broadcast:
                    self.sync_broadcast("status", "system", "Done", task_id)

            # Add response to memory
            if self._short_term_memory:
                self._short_term_memory.add_message("assistant", response)
                
            # PERSISTENCE: Save Assistant Response
            if self._history_manager and self.active_conversation_id:
                self._history_manager.add_message(self.active_conversation_id, "assistant", response)
            
            self._state_machine.to_idle("Response complete")
            return response
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            if self.sync_broadcast:
                self.sync_broadcast("error", "system", str(e))
            if self._voice_manager:
                await self._voice_manager.speak(f"I encountered an error: {e}", suppress_sync=True)
            self._state_machine.to_error(str(e))
            self._state_machine.recover()
            return f"I encountered an error: {e}"
        finally:
            # BUSY LOCK: Release
            if self._voice_manager:
                self._voice_manager.set_busy(False)
    
    async def _execute_launch_app(self, app_name: str, extra_args: str = None) -> str:
        """Execute launch_app tool."""
        try:
            from agent.tools.os_tools import OSTools
            os_tools = OSTools()
            result = os_tools.launch_app(app_name, extra_args)
            logger.info(f"Launch app result: {result}")
            return f"Done! I've opened {app_name} for you."
        except Exception as e:
            logger.error(f"Launch app error: {e}")
            return f"Sorry, I couldn't open {app_name}: {e}"
    
    async def _execute_browser(self, url: str) -> str:
        """Execute browser navigation using system default browser."""
        try:
            import webbrowser
            import subprocess
            
            if not url.startswith("http"):
                url = "https://" + url
            
            # Use webbrowser module for reliable cross-platform URL opening
            webbrowser.open(url)
            return f"Opened {url} in the browser."
        except Exception as e:
            logger.error(f"Browser error: {e}")
            return f"Sorry, I couldn't open {url}: {e}"
    
    async def _execute_type(self, text: str) -> str:
        """Execute typing."""
        try:
            from agent.tools.os_tools import OSTools
            os_tools = OSTools()
            os_tools.type_text(text)
            return f"Typed: {text}"
        except Exception as e:
            return f"Typing failed: {e}"
    
    async def _execute_keypress(self, key: str) -> str:
        """Execute key press."""
        try:
            from agent.tools.os_tools import OSTools
            os_tools = OSTools()
            os_tools.press_key(key)
            return f"Pressed {key}"
        except Exception as e:
            return f"Key press failed: {e}"
    
    async def _execute_screenshot(self) -> str:
        """Execute screenshot capture."""
        try:
            from agent.vision.screen_capture import ScreenCapture
            capture = ScreenCapture()
            path = capture.capture()
            return f"Screenshot saved to: {path}"
        except Exception as e:
            return f"Screenshot failed: {e}"

    async def _execute_search(self, query: str) -> str:
        """Execute web search."""
        try:
            from agent.tools.web_search import WebSearchTool
            search_tool = WebSearchTool()
            return search_tool.search(query)
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Search failed: {e}"
    
    async def _chat_with_llm(self, user_input: str, images: Optional[list] = None) -> str:
        """Generate LLM response for chat."""
        if self._llm_runtime and self._llm_runtime.is_available():
            system_prompt = self.config.get('system_prompt', "You are a helpful AI assistant.")
            
            # Inject Performance Stats into System Prompt (so LLM knows its speed)
            if hasattr(self._llm_runtime, 'last_tps') and self._llm_runtime.last_tps > 0:
                system_prompt += f"\n\n[SYSTEM STATUS] Current Generation Speed: {self._llm_runtime.last_tps:.2f} tokens/second."
                
            return self._llm_runtime.chat(system_prompt, user_input, images=images)
        return "LLM not available. Please ensure Ollama is running."
    
    async def run_cli(self):
        """Run agent in CLI mode."""
        print("\n" + "=" * 60)
        print("  NEURAL AI AGENT - CLI Mode")
        print("  Type 'quit' or 'exit' to stop")
        print("  Type 'lock' to lock the agent")
        print("=" * 60 + "\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit']:
                    print("Goodbye!")
                    break
                
                if user_input.lower() == 'lock':
                    if self._lock_controller:
                        self._lock_controller.lock("User requested")
                        print("Agent: I'm now locked. Authenticate to continue.")
                    continue
                
                response = await self.process_input(user_input)
                print(f"Agent: {response}\n")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    async def load_context(self, conversation_id: str):
        """Load a specific conversation context."""
        if not self._history_manager:
            return False
            
        messages = self._history_manager.get_messages(conversation_id)
        if not messages:
            logger.warning(f"No messages found for conversation {conversation_id}")
            # Still set it active, maybe it's new
            self.active_conversation_id = conversation_id
            if self._short_term_memory:
                self._short_term_memory.clear()
            return True
            
        # Switch active ID
        self.active_conversation_id = conversation_id
        
        # Populate Short Term Memory for LLM Context
        if self._short_term_memory:
            self._short_term_memory.clear()
            for msg in messages:
                # Map role to memory types if needed, but 'user'/'assistant' are standard
                self._short_term_memory.add_message(msg['role'], msg['content'])
        
        logger.info(f"Loaded context for conversation {conversation_id} ({len(messages)} messages)")
        return True

    def shutdown(self):
        """Gracefully shutdown the agent."""
        logger.info("Shutting down agent...")
        
        # Shutdown skill router (cleanup browser sessions, etc.)
        if self._skill_router:
            try:
                self._skill_router.shutdown()
                logger.info("✓ Skill router shutdown complete")
            except Exception as e:
                logger.warning(f"Skill router shutdown error: {e}")
        
        if self._lock_controller:
            self._lock_controller.stop_presence_monitoring()
        
        if self._audit_logger:
            self._audit_logger.log(
                event_type="system",
                action="shutdown",
                description="Agent shutdown initiated"
            )
        
        logger.info("Agent shutdown complete.")


def main():
    """Main entry point."""
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description="Neural AI Agent")
    parser.add_argument("--config", default="agent/config/settings.yaml", help="Config file path")
    parser.add_argument("--mode", choices=["cli", "api"], default="api", help="Run mode (default: api)")
    parser.add_argument("--port", type=int, default=8000, help="API port")
    args = parser.parse_args()
    
    # Create and initialize agent
    agent = NeuralAgent(config_path=args.config)
    
    try:
        agent.initialize()
        
        if args.mode == "cli":
            # Use nest_asyncio to allow nested event loops (Playwright creates one during init)
            try:
                import nest_asyncio
                nest_asyncio.apply()
            except ImportError:
                pass  # If not available, try anyway
            asyncio.run(agent.run_cli())
            
        elif args.mode == "api":
            # API mode - start FastAPI server
            logger.info(f"API mode - starting server on port {args.port}...")
            # We use uvicorn to run our FastAPI app defined in agent.api_server
            uvicorn.run(
                "agent.api_server:app",
                host="0.0.0.0",
                port=args.port,
                reload=False,  # Reload disabled for production use
                log_level="info"
            )
        
    except KeyboardInterrupt:
        pass
    finally:
        agent.shutdown()


if __name__ == "__main__":
    main()

