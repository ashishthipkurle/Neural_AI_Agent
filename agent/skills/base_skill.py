"""
Skill System - Base Classes and Types

This module defines the foundational contracts for all skills in the agent.
Skills are stateful modules with lifecycle hooks, not stateless tool wrappers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import logging


class SkillHealth(Enum):
    """Health status of a skill."""
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class SkillResult:
    """Result of a skill action execution."""
    success: bool
    data: Any = None
    message: str = ""
    error: Optional[str] = None
    
    # For chaining / context passing
    context_updates: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class SkillManifest:
    """Metadata about a skill."""
    name: str
    version: str
    description: str
    actions: List[str]  # List of action names this skill supports
    requires: List[str] = field(default_factory=list)  # Python packages required
    permissions: List[str] = field(default_factory=list)  # e.g., "network", "filesystem", "cookies"


class BaseSkill(ABC):
    """
    Abstract base class for all skills.
    
    Skills are STATEFUL modules with:
    - Lifecycle hooks (on_load, on_unload)
    - Intent matching (can_handle)
    - Action execution (execute)
    - Health monitoring (health)
    - Dry-run capability (dry_run)
    
    IMPORTANT: Router routes to SKILLS, not tools.
    Tools are private implementation details within skills.
    """
    

    def __init__(self):
        self.logger = logging.getLogger(f"Skill.{self.name}")
        self._loaded = False
        self._health = SkillHealth.UNAVAILABLE
        self.learning_manager = None # Injected later
        
    def inject_learning_manager(self, manager: Any) -> None:
        """Inject learning manager dependency."""
        self.learning_manager = manager

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill name (e.g., 'browser', 'desktop', 'memory')."""
        pass
    
    @property
    @abstractmethod
    def manifest(self) -> SkillManifest:
        """Return skill metadata."""
        pass
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """
        Called when the skill is loaded.
        
        Use this to:
        - Initialize expensive resources (Playwright browser, model loading)
        - Load persisted state (indexes, caches)
        - Register OS hooks if needed
        
        Override in subclass. Call super().on_load() at the end.
        """
        self._loaded = True
        self._health = SkillHealth.READY
        self.logger.info(f"Skill '{self.name}' loaded.")
    
    def on_unload(self) -> None:
        """
        Called when the skill is unloaded/shutdown.
        
        Use this to:
        - Close connections
        - Save state
        - Release resources
        
        Override in subclass. Call super().on_unload() at the end.
        """
        self._loaded = False
        self._health = SkillHealth.UNAVAILABLE
        self.logger.info(f"Skill '{self.name}' unloaded.")
    
    # ==================== INTENT MATCHING ====================
    
    @abstractmethod
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """
        Check if this skill can handle the given intent.
        
        Args:
            intent: Natural language intent or action name
            context: Optional execution context
            
        Returns:
            Confidence score 0.0-1.0. Higher = more confident.
            Return 0.0 if cannot handle.
            
        LEARNING ENHANCEMENT:
        This method will be intercepted by PatternRecognizer in the future to improve matching.
        """
        pass
    
    def get_actions(self) -> List[str]:
        """Return list of supported action names."""
        return self.manifest.actions
    
    # ==================== EXECUTION ====================
    
    @abstractmethod
    def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """
        Execute an action within this skill.
        
        Args:
            action: Action name (must be in manifest.actions)
            params: Action parameters
            context: Execution context (user info, previous results, etc.)
            
        Returns:
            SkillResult with success status, data, and any context updates.
        """
        pass
        
    async def execute_wrapper(self, action: str, params: Dict[str, Any], context: dict = None) -> SkillResult:
        """
        Wrapper to handle learning hooks. Call THIS instead of execute() directly.
        """
        import time
        
        # 1. Before Hook
        context = self.before_execution(context or {})
        start_time = time.time()
        
        try:
            # 2. Execute
            # Check if execute is async, if not wrap it
            import inspect
            if inspect.iscoroutinefunction(self.execute):
                result = await self.execute(action, params, context)
            else:
                result = self.execute(action, params, context)
                
            duration = time.time() - start_time
            
            # 3. After Hook
            self.after_execution(result, True, duration, action, params, context)
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            self.after_execution(None, False, duration, action, params, context, error=str(e))
            raise e

    # ==================== LEARNING HOOKS ====================

    def before_execution(self, context: dict) -> dict:
        """
        Called before execution.
        Can modify context based on learned strategies.
        """
        if self.learning_manager:
            # Inject best strategy if available
            strategy = self.learning_manager.strategy_optimizer.select_strategy(self.name, context)
            context['strategy'] = strategy
            
            # Inject optimal parameters if available
            # params = ... (would require params arg here, skipping for now)
            pass
        return context

    def after_execution(self, result: Any, success: bool, duration: float, 
                       action: str, params: dict, context: dict, error: str = None) -> None:
        """
        Called after execution.
        Logs experience to LearningManager.
        """
        if self.learning_manager:
            outcome = {}
            if result and hasattr(result, 'data'):
                outcome = {'data_summary': str(result.data)[:100]}
            
            self.learning_manager.record_experience(
                skill_name=self.name,
                action=action,
                context={**context, 'params': params},
                outcome=outcome,
                success=success,
                duration=duration,
                error_message=error
            )
            
            if success:
                self.self_improve()

    def get_proficiency(self) -> float:
        """Get current proficiency score."""
        if self.learning_manager:
            return self.learning_manager.skill_registry.get_proficiency(self.name)
        return 0.0

    def self_improve(self) -> None:
        """
        Apply learned optimizations.
        """
        if self.learning_manager:
            # Check for best practices or parameter tuning
            # This is where the skill would update its internal config based on learning
            pass

    # ==================== HEALTH & DRY-RUN ====================
    
    def health(self) -> SkillHealth:
        """
        Return current health status.
        
        Override to add custom health checks (e.g., check if Playwright is responsive).
        """
        return self._health
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """
        Preview what would happen without actually executing.
        
        Returns a human-readable description of the planned action.
        
        Override in subclass for accurate previews.
        """
        return f"[DRY-RUN] Would execute '{self.name}.{action}' with params: {params}"
    
    # ==================== UTILITIES ====================
    
    def is_loaded(self) -> bool:
        """Check if skill is currently loaded."""
        return self._loaded
    
    def __repr__(self) -> str:
        return f"<Skill:{self.name} health={self.health().value}>"

