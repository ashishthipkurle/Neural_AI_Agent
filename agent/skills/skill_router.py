"""
Skill Router - Routes intents to skills (NOT to tools).

This is the primary entry point for skill execution.
The router:
1. Receives intents from the agent
2. Selects the best skill to handle the intent
3. Delegates execution to the skill
4. Returns results

IMPORTANT: Tools are private to skills. Router never touches tools directly.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .base_skill import BaseSkill, SkillResult, SkillHealth
from .skill_loader import SkillLoader


@dataclass
class SkillPlan:
    """A planned action to be executed by a skill."""
    skill: str
    action: str
    params: Dict[str, Any]


@dataclass
class ExecutionResult:
    """Result of executing a skill plan or intent."""
    success: bool
    skill_name: str
    action: str
    result: SkillResult
    error: Optional[str] = None


class SkillRouter:
    """
    Routes intents to the appropriate skill for execution.
    
    This replaces the old ToolRouter approach where the router
    directly called tools. Now:
    
    Intent -> SkillRouter -> Skill -> (internal tools)
    """
    
    def __init__(self, skill_loader: Optional[SkillLoader] = None):
        self.logger = logging.getLogger("SkillRouter")
        self.skill_loader = skill_loader or SkillLoader()
        
        # Execution context that persists across calls
        self._context: Dict[str, Any] = {}

    @property
    def skills(self) -> Dict[str, BaseSkill]:
        """Alias for skill_loader.get_all() for backward compatibility."""
        return self.skill_loader.get_all()
    
    def initialize(self) -> None:
        """Initialize the router and load all skills."""
        self.logger.info("Initializing SkillRouter...")
        self.skill_loader.discover()
        self.skill_loader.load_all()
        
        # Inject self into skills that need the router
        for name, skill in self.skill_loader.get_all().items():
            if hasattr(skill, 'set_skill_router'):
                skill.set_skill_router(self)
                self.logger.info(f"Injected SkillRouter into skill: {name}")
        
        self.logger.info(f"Loaded {len(self.skill_loader.get_all())} skills.")
    
    def shutdown(self) -> None:
        """Shutdown and cleanup all skills."""
        self.logger.info("Shutting down SkillRouter...")
        self.skill_loader.unload_all()
    
    # ==================== INTENT ROUTING ====================
    
    async def route_intent(self, intent: str, params: Optional[Dict] = None) -> ExecutionResult:
        """
        Route a natural language intent to the best skill.
        
        Args:
            intent: Natural language intent or "skill.action" format
            params: Optional parameters for the action
            
        Returns:
            ExecutionResult with the outcome
        """
        params = params or {}
        
        # Check if intent is in "skill.action" format
        if "." in intent and not " " in intent:
            parts = intent.split(".", 1)
            return await self.execute_skill_action(parts[0], parts[1], params)
        
        # Otherwise, find best skill to handle the intent
        skill = self.skill_loader.get_skill_for_intent(intent)
        
        if not skill:
            return ExecutionResult(
                success=False,
                skill_name="none",
                action="route",
                result=SkillResult(success=False, error=f"No skill found to handle: {intent}"),
                error=f"No skill found to handle: {intent}"
            )
        
        # Let the skill determine the action from the intent
        return await self._execute_skill_with_intent(skill, intent, params)
    
    async def _execute_skill_with_intent(
        self, 
        skill: BaseSkill, 
        intent: str, 
        params: Dict[str, Any]
    ) -> ExecutionResult:
        """Execute a skill with a natural language intent."""
        try:
            # Skill interprets the intent and executes
            # The skill's execute() should parse the intent if action isn't specified
            import asyncio
            if asyncio.iscoroutinefunction(skill.execute):
                result = await skill.execute(
                    action=intent,  # Skill will interpret this
                    params=params,
                    context=self._context
                )
            else:
                result = skill.execute(
                    action=intent,  # Skill will interpret this
                    params=params,
                    context=self._context
                )
            
            # Update context with any updates from the skill
            self._context.update(result.context_updates)
            
            return ExecutionResult(
                success=result.success,
                skill_name=skill.name,
                action=intent,
                result=result
            )
            
        except Exception as e:
            self.logger.error(f"Skill execution failed: {e}")
            return ExecutionResult(
                success=False,
                skill_name=skill.name,
                action=intent,
                result=SkillResult(success=False, error=str(e)),
                error=str(e)
            )
    
    # ==================== EXPLICIT SKILL EXECUTION ====================
    
    async def execute_skill_action(
        self, 
        skill_name: str, 
        action: str, 
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        Execute a specific action on a specific skill.
        
        Used when you know exactly which skill.action to call.
        """
        skill = self.skill_loader.get(skill_name)
        
        if not skill:
            return ExecutionResult(
                success=False,
                skill_name=skill_name,
                action=action,
                result=SkillResult(success=False, error=f"Skill '{skill_name}' not found"),
                error=f"Skill '{skill_name}' not found"
            )
        
        if skill.health() != SkillHealth.READY:
            return ExecutionResult(
                success=False,
                skill_name=skill_name,
                action=action,
                result=SkillResult(success=False, error=f"Skill '{skill_name}' is not ready"),
                error=f"Skill '{skill_name}' health: {skill.health().value}"
            )
        
        # Merge passed context with internal context
        execution_context = {**self._context}
        if context:
            execution_context.update(context)
        
        try:
            import asyncio
            import inspect
            if asyncio.iscoroutinefunction(skill.execute):
                result = await skill.execute(action, params, execution_context)
            else:
                result = skill.execute(action, params, execution_context)
                # Handle case where sync execute returns a coroutine (dynamic dispatch)
                if inspect.isawaitable(result):
                    result = await result
            
            self._context.update(result.context_updates)
            
            return ExecutionResult(
                success=result.success,
                skill_name=skill_name,
                action=action,
                result=result
            )
            
        except Exception as e:
            self.logger.error(f"Skill '{skill_name}.{action}' failed: {e}")
            return ExecutionResult(
                success=False,
                skill_name=skill_name,
                action=action,
                result=SkillResult(success=False, error=str(e)),
                error=str(e)
            )
    
    # ==================== PLAN EXECUTION ====================
    
    async def execute_plan(self, plan: List[SkillPlan]) -> List[ExecutionResult]:
        """
        Execute a sequence of skill actions (from Planner).
        
        Args:
            plan: List of SkillPlan objects
            
        Returns:
            List of ExecutionResult for each step
        """
        results = []
        
        for step in plan:
            self.logger.info(f"Executing plan step: {step.skill}.{step.action}")
            result = await self.execute_skill_action(step.skill, step.action, step.params)
            results.append(result)
            
            # Stop on failure (can be made configurable)
            if not result.success:
                self.logger.warning(f"Plan stopped at step: {step.skill}.{step.action}")
                break
        
        return results
    
    # ==================== INTROSPECTION ====================
    
    def list_skills(self) -> List[Dict[str, Any]]:
        """List all loaded skills with their status."""
        skills = []
        for name, skill in self.skill_loader.get_all().items():
            skills.append({
                "name": name,
                "health": skill.health().value,
                "actions": skill.get_actions(),
                "description": skill.manifest.description
            })
        return skills
    
    def get_context(self) -> Dict[str, Any]:
        """Get current execution context."""
        return self._context.copy()
    
    def clear_context(self) -> None:
        """Clear execution context."""
        self._context.clear()
    
    # ==================== DRY-RUN ====================
    
    def dry_run(self, skill_name: str, action: str, params: Dict[str, Any]) -> str:
        """
        Preview what a skill action would do without executing.
        """
        skill = self.skill_loader.get(skill_name)
        if not skill:
            return f"[DRY-RUN ERROR] Skill '{skill_name}' not found."
        
        return skill.dry_run(action, params)
