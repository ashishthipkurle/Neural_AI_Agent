"""
Agent Skills System

This package provides a modular skill architecture for the agent.
Skills are stateful modules with lifecycle hooks, not stateless tool wrappers.

Key Concepts:
- Skills: High-level capabilities (browser, desktop, memory, etc.)
- Actions: Specific operations within a skill (browser.login, desktop.launch)
- Tools: Private implementation details within skills (not exposed to router)

Usage:
    from agent.skills import SkillLoader, SkillRouter
    
    router = SkillRouter()
    router.initialize()
    
    # Route an intent to best skill
    result = router.route_intent("open gmail and check unread emails")
    
    # Or call a specific skill action
    result = router.execute_skill_action("browser", "navigate", {"url": "https://gmail.com"})
    
    # Cleanup on shutdown
    router.shutdown()
"""

from .base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth
from .skill_loader import SkillLoader
from .skill_router import SkillRouter, SkillPlan, ExecutionResult

__all__ = [
    # Base classes
    "BaseSkill",
    "SkillResult", 
    "SkillManifest",
    "SkillHealth",
    
    # Loader
    "SkillLoader",
    
    # Router
    "SkillRouter",
    "SkillPlan",
    "ExecutionResult",
]
