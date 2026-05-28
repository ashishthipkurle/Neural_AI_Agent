
import logging
import asyncio
from typing import Optional, Dict, Any
from agent.learning.manager import LearningManager
from agent.tasks.manager import TaskManager
from agent.telegram.bot import TelegramBot

logger = logging.getLogger(__name__)

class SkillExecutorMap(dict):
    """Dynamic map that returns an executor for any skill name."""
    def __init__(self, orchestrator):
        self.orch = orchestrator
        
    def get(self, skill_name, default=None):
        # Verify skill exists
        if self.orch.agent._skill_router:
             # This check depends on SkillRouter structure. 
             # For now, we trust the orchestration or check if loaded.
             pass
        
        async def executor(task_id: str, params: dict):
            return await self.orch.execute_skill(skill_name, params, task_id)
            
        return executor

class LearningOrchestrator:
    """
    Wraps the NeuralAgent to inject Learning, Task Management, and Telegram support.
    Acts as the central nervous system enhancement.
    """
    
    def __init__(self, neural_agent, config: dict):
        self.agent = neural_agent
        self.config = config
        
        # Initialize Subsystems
        self.learning_manager = LearningManager(config)
        self.task_manager = TaskManager(config)
        
        self.telegram_bot = None
        if config.get('telegram', {}).get('enabled', False):
            token = config.get('telegram', {}).get('bot_token')
            allowed_users = config.get('telegram', {}).get('allowed_users', [])
            self.telegram_bot = TelegramBot(token, allowed_users)
            self.telegram_bot.set_orchestrator(self)
            
    async def start(self):
        """Start all background services."""
        if self.telegram_bot:
            await self.telegram_bot.initialize()
            await self.telegram_bot.start()
            
            # Inject Telegram Bot into Skill
            if hasattr(self.agent, '_skill_router') and self.agent._skill_router:
                 telegram_skill = self.agent._skill_router.skill_loader.get('telegram')
                 if telegram_skill and hasattr(telegram_skill, 'inject_bot'):
                     telegram_skill.inject_bot(self.telegram_bot)
            
        # Start Task Scheduler
        asyncio.create_task(self.task_manager.scheduler.start())
        
        # Start Task Executor Loop
        asyncio.create_task(self._task_loop())
        
        logger.info("LearningOrchestrator Services Started.")

    async def _task_loop(self):
        """Run the task execution loop."""
        skill_map = SkillExecutorMap(self)
        try:
            await self.task_manager.execute_pending_tasks(skill_map)
        except Exception as e:
            logger.error(f"Task Execution Loop Failed: {e}")

    async def stops(self):
        """Stop all services."""
        if self.telegram_bot:
            await self.telegram_bot.stop()
        
        self.task_manager.scheduler.stop()

    async def process_input(self, user_input: str, image_data: str = None, source: str = "desktop") -> str:
        """
        Wrapper around agent.process_input to intercept and learn.
        """
        start_time = asyncio.get_event_loop().time()
        
        # 1. Pre-process (Intent Learning?)
        
        # 2. Execute via Agent — forward source so Telegram isolation works
        response = await self.agent.process_input(user_input, source=source, image_data=image_data)
        
        # 3. Log Experience (High Level)
        # This is tricky because process_input might fire multiple skills
        # We ideally want the skills themselves to log via BaseSkill hooks
        
        duration = asyncio.get_event_loop().time() - start_time
        
        # Notify Telegram if critical
        if self.telegram_bot and "error" in response.lower():
             await self.telegram_bot.send_notification(f"⚠️ Agent Error during execution: {response[:100]}")
             
        return response

    async def execute_skill(self, skill_name: str, params: dict, task_id: str = None) -> Any:
        """
        Direct skill execution (used by Task Manager).
        """
        # Find skill in agent
        skill = None
        if hasattr(self.agent, '_skill_router') and self.agent._skill_router:
            # Check skill_loader
            if hasattr(self.agent._skill_router, 'skill_loader'):
                 skill = self.agent._skill_router.skill_loader.get(skill_name)
        
        if not skill:
            raise ValueError(f"Skill {skill_name} not found")
            
        # Execute with Learning Context
        # We pass task_id in context if possible. BaseSkill execute accepts context.
        context = {"task_id": task_id}
        
        # BaseSkill.execute -> which calls execute_wrapper automatically? 
        # No, we must call execute_wrapper to get learning.
        # But BaseSkill exposes 'execute', 'execute_wrapper' is internal?
        # Check base_skill.py. Usually execute_wrapper calls execute.
        # But if we call execute() directly, we skip hooks?
        # Yes. We should call execute_wrapper if available.
        
        if hasattr(skill, 'execute_wrapper'):
             # We need to figure out 'action' vs 'params'.
             # Params usually contains 'action' or the Task stores 'action'?
             # Task model has 'skill_name' but NOT 'action'. 
             # It implies the task IS the action?
             # Or params must contain "action".
             
             action = params.pop("action", "default")
             return await skill.execute_wrapper(action, params, context)
        else:
             return await skill.execute(params)

    def notify_user(self, message: str, type: str = "info"):
        """Unified notification (Desktop + Telegram)."""
        # Desktop (via Agent's method if available or WebSocket)
        pass 
        
        # Telegram
        if self.telegram_bot:
            asyncio.create_task(self.telegram_bot.send_notification(message))

    def run_background_maintenance(self):
        """Periodic maintenance."""
        self.learning_manager.run_periodic_analysis()
        self.learning_manager.cleanup_old_data()
