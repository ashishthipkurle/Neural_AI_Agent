from typing import Dict, Any, Callable
from agent.core.intent import Intent
import logging
from agent.tools.os_tools import OSTools
from agent.tools.math_tools import MathTools
from agent.tools.code_executor import CodeExecutor
from agent.tools.vision_tools import VisionTools
from agent.tools.memory_tools import MemoryTools
from agent.tools.web_search import WebSearchTool 
from agent.tools.browser_tools import BrowserTools
from agent.tools.market_tools import MarketTools
from agent.automation.scheduler import TaskScheduler

class ToolRouter:
    """
    Registry for tools and responsible for routing intents to the correct tool.
    """
    def __init__(self):
        self.tools: Dict[str, Any] = {}
        self.logger = logging.getLogger("ToolRouter")
        
        # Initialize components
        self._init_tools()

    def _init_tools(self):
        self.os_tools = OSTools()
        self.math_tools = MathTools()
        self.code_executor = CodeExecutor()
        self.vision_tools = VisionTools()
        self.memory_tools = MemoryTools()
        self.web_tools = WebSearchTool() 
        self.browser_tools = BrowserTools()
        self.market_tools = MarketTools()
        self.scheduler = TaskScheduler() # Re-added scheduler initialization

        # Chat
        self.register_tool("chat_tool", self._chat_tool)
        
        # OS Tools
        self.register_tool("read_file", self.os_tools.read_file)
        self.register_tool("write_file", self.os_tools.write_file)
        self.register_tool("launch_app", self.os_tools.launch_app)
        
        # Math Tools
        self.register_tool("calculate", self.math_tools.calculate)
        
        # Code Tools
        self.register_tool("execute_code", self.code_executor.execute_code)
        
        # Vision Tools (Unified)
        self.register_tool("describe_image", self.vision_tools.describe_image)
        self.register_tool("capture_screen", self.vision_tools.capture_screen)
        self.register_tool("detect_faces", self.vision_tools.detect_faces)
        self.register_tool("recognize_faces", self.vision_tools.recognize_faces)
        self.register_tool("register_face", self.vision_tools.register_face)
        self.register_tool("forget_face", self.vision_tools.forget_face)
        self.register_tool("start_surveillance", self.vision_tools.start_surveillance)
        self.register_tool("stop_surveillance", self.vision_tools.stop_surveillance)
        
        # Memory Tools
        self.register_tool("store_memory", self.memory_tools.store_memory)
        self.register_tool("search_memory", self.memory_tools.search_memory)


        # Web Tools
        self.register_tool("search_online", self.web_tools.search)
        self.register_tool("browser_navigate", self.browser_tools.navigate_to)
        self.register_tool("browser_read", self.browser_tools.read_content)
        self.register_tool("browser_close", self.browser_tools.close_browser)

        # Market Analysis Tools
        self.register_tool("analyze_chart", self.market_tools.analyze_chart)
        self.register_tool("analyze_screen_chart", self.market_tools.analyze_screen_chart)

        # Input Automation
        self.register_tool("move_mouse", self.os_tools.move_mouse)
        self.register_tool("click_mouse", self.os_tools.click_mouse)
        self.register_tool("type_text", self.os_tools.type_text)
        self.register_tool("press_key", self.os_tools.press_key)

        # Automation
        self.register_tool("schedule_task", self._schedule_wrapper)

        # Telegram Tools (Dynamic)
        try:
            from agent.skills.telegram.skill import TelegramSkill
            self._telegram_skill = TelegramSkill()
            self._telegram_skill.on_load()
            self.register_tool("telegram_check_messages", self._telegram_check_messages)
            self.register_tool("telegram_send_message", self._telegram_send_message)
        except Exception as e:
            self.logger.warning(f"Telegram skill not available: {e}")
            self._telegram_skill = None

        # Mission Control (Dynamic)
        try:
            from agent.skills.mission.skill import MissionControlSkill
            self._mission_skill = MissionControlSkill()
            self._mission_skill.on_load()
            self._mission_skill.set_skill_router(self)  # Inject router
            self.register_tool("start_mission", self._start_mission)
        except Exception as e:
            self.logger.warning(f"Mission skill not available: {e}")
            self._mission_skill = None

    def _chat_tool(self, message: str = "Request processed.") -> str:
        return f"Agent: {message}"

    def _schedule_wrapper(self, interval: int, unit: str, action_type: str, action_params: dict) -> str:
        """
        Wraps the scheduler to allow scheduling specific tool calls.
        """
        # Define the job to run
        def job():
            self.logger.info(f"Executing scheduled job: {action_type}")
            # We need to route this safely. For now, we support 'monitor_stream' as the primary background job.
            if action_type == "monitor_stream":
                self.cctv_tools.monitor_stream(**action_params)
            elif action_type == "chat":
                 print(f"[Scheduled Alert]: {action_params.get('message')}")

        return self.scheduler.add_job(interval, unit, job)

    async def _telegram_check_messages(self) -> str:
        """Wrapper for telegram check_messages."""
        if not self._telegram_skill:
            return "Telegram skill not loaded."
        result = await self._telegram_skill.execute("check_messages", {})
        return result.message if result.success else f"Error: {result.error}"

    async def _telegram_send_message(self, message: str = "Hello from Agent") -> str:
        """Wrapper for telegram send_message."""
        if not self._telegram_skill:
            return "Telegram skill not loaded."
        result = self._telegram_skill.execute("send_message", {"message": message})
        return result.message if result.success else f"Error: {result.error}"

    async def _start_mission(self, goal: str) -> str:
        """Wrapper for mission start_mission."""
        if not self._mission_skill:
            return "Mission skill not loaded."
        result = await self._mission_skill.execute("start_mission", {"goal": goal})
        return result.message if result.success else f"Error: {result.error}"

    def set_skill_router(self, router):
        """Link to Clowbot-class SkillRouter."""
        self._clowbot_skill_router = router
        # Also update Mission Skill's router link
        if self._mission_skill:
             self._mission_skill.set_skill_router(self)

    # Method for MissionControlSkill to call other skills
    async def execute_skill_action(self, skill_name: str, action: str, params: dict, context: dict = None):
        """Execute a skill action by name (for MissionControlSkill)."""
        from agent.skills.base_skill import SkillResult
        
        # 1. Handle Clowbot-class Skills (like Planning, Browser, Desktop)
        if hasattr(self, '_clowbot_skill_router') and self._clowbot_skill_router:
            return await self._clowbot_skill_router.execute_skill_action(skill_name, action, params, context)
        
        # 2. Map skill names to tool names for internal tools
        tool_mapping = {
            ("telegram", "send_message"): "telegram_send_message",
            ("telegram", "check_messages"): "telegram_check_messages",
        }
        
        tool_key = (skill_name, action)
        tool_name = tool_mapping.get(tool_key)
        
        if tool_name and tool_name in self.tools:
            try:
                handler = self.tools[tool_name]
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**params)
                else:
                    result = handler(**params)
                return SkillResult(success=True, message=str(result))
            except Exception as e:
                return SkillResult(success=False, error=str(e))
        
        # Fallback: try to find handler directly
        handler = self.tools.get(action)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**params)
                else:
                    result = handler(**params)
                return SkillResult(success=True, message=str(result))
            except Exception as e:
                return SkillResult(success=False, error=str(e))
        
        return SkillResult(success=False, error=f"Skill action not found: {skill_name}.{action}")

    def register_tool(self, tool_name: str, handler: Callable):
        """
        Registers a tool handler function.
        """
        self.tools[tool_name] = handler
        self.logger.info(f"Registered tool: {tool_name}")

    def route(self, intent: Intent) -> Any:
        """
        Routes the intent to the appropriate tool.
        """
        if not intent.tool_name:
            return f"No tool specified for action: {intent.action}"

        handler = self.tools.get(intent.tool_name)
        if not handler:
            return f"Tool not found: {intent.tool_name}"

        try:
            self.logger.info(f"Executing tool {intent.tool_name} with params {intent.parameters}")
            
            # Robust Parameter Filtering: Only pass args defined in the function signature
            import inspect
            sig = inspect.signature(handler)
            valid_params = {}
            missing_params = []
            
            for name, param in sig.parameters.items():
                if name in intent.parameters:
                    valid_params[name] = intent.parameters[name]
                elif param.default == inspect.Parameter.empty and param.kind != inspect.Parameter.VAR_KEYWORD:
                    missing_params.append(name)
            
            # Use 'kwargs' if the function accepts **kwargs
            if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                valid_params.update(intent.parameters) # Pass everything
            
            if missing_params:
                return f"Error: Missing required parameters for {intent.tool_name}: {', '.join(missing_params)}"

            return handler(**valid_params)
        except Exception as e:
            self.logger.error(f"Error executing tool {intent.tool_name}: {e}")
            return f"Error: {str(e)}"
