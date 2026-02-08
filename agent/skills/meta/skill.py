"""
Meta Skill - Agent introspection and capability discovery.

Provides:
- Skill/action listing ("What can you do?")
- Capability explanations
- Self-diagnostics
- Pattern learning (save user commands as workflows)
- Confidence estimation
"""

import logging
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth


class MetaSkill(BaseSkill):
    """
    Self-awareness and user assistance skill.
    
    Actions:
    - list_skills: List all available skills
    - explain: Explain a skill or action
    - status: Get system status
    - health: Check all skill health
    - learn: Learn a pattern from user behavior
    - suggest: Suggest next actions
    - help: Get contextual help
    """
    
    def __init__(self):
        super().__init__()
        self._skill_router = None
        self._learned_patterns: List[Dict] = []
        self._command_history: List[Dict] = []
    
    @property
    def name(self) -> str:
        return "meta"
    
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="meta",
            version="1.0.0",
            description="Agent introspection and capability discovery",
            actions=[
                "list_skills", "explain", "status", "health",
                "learn", "suggest", "help", "capabilities"
            ],
            requires=[],
            permissions=["skills"]
        )
    
    def set_skill_router(self, router):
        """Inject skill router for introspection."""
        self._skill_router = router
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """Initialize meta skill."""
        super().on_load()
        self.logger.info("Meta skill loaded")
    
    def on_unload(self) -> None:
        """Cleanup."""
        super().on_unload()
    
    # ==================== INTENT MATCHING ====================
    
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill can handle the intent."""
        intent_lower = intent.lower()
        
        # Direct meta questions
        if any(x in intent_lower for x in [
            "what can you do", "your capabilities", "your skills",
            "help me", "how do i", "list skills", "show skills"
        ]):
            return 0.95
        
        # System status
        if any(x in intent_lower for x in ["system status", "health check", "diagnostics"]):
            return 0.9
        
        # Learning
        if any(x in intent_lower for x in ["learn this", "remember how", "create shortcut"]):
            return 0.85
        
        return 0.0
    
    # ==================== EXECUTION ====================
    
    def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Execute a meta action."""
        
        handlers = {
            "list_skills": self._action_list_skills,
            "explain": self._action_explain,
            "status": self._action_status,
            "health": self._action_health,
            "learn": self._action_learn,
            "suggest": self._action_suggest,
            "help": self._action_help,
            "capabilities": self._action_capabilities,
        }
        
        handler = handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")
        
        try:
            return handler(params, context or {})
        except Exception as e:
            self.logger.error(f"Meta action '{action}' failed: {e}")
            return SkillResult(success=False, error=str(e))
    
    # ==================== ACTIONS ====================
    
    def _action_list_skills(self, params: Dict, context: Dict) -> SkillResult:
        """List all available skills."""
        if not self._skill_router:
            return SkillResult(success=False, error="Skill router not available")
        
        skills = self._skill_router.list_skills()
        
        formatted = []
        for skill in skills:
            status_icon = "✅" if skill.get("health") == "ready" else "⚠️"
            formatted.append(f"{status_icon} **{skill['name']}** - {skill.get('description', 'No description')}")
        
        return SkillResult(
            success=True,
            data={"skills": skills},
            message="Available skills:\n" + "\n".join(formatted)
        )
    
    def _action_explain(self, params: Dict, context: Dict) -> SkillResult:
        """Explain a skill or action."""
        skill_name = params.get("skill", "")
        action_name = params.get("action", "")
        
        if not self._skill_router:
            return SkillResult(success=False, error="Skill router not available")
        
        skill = self._skill_router.skill_loader.get_skill(skill_name)
        if not skill:
            return SkillResult(success=False, error=f"Skill not found: {skill_name}")
        
        manifest = skill.manifest
        
        if action_name:
            # Explain specific action
            if action_name in manifest.actions:
                # Try to get docstring or description
                method = getattr(skill, f"_action_{action_name}", None)
                doc = method.__doc__ if method else f"Execute {action_name}"
                
                return SkillResult(
                    success=True,
                    data={"skill": skill_name, "action": action_name},
                    message=f"**{skill_name}.{action_name}**\n{doc or 'No description available'}"
                )
            return SkillResult(success=False, error=f"Action not found: {action_name}")
        
        # Explain skill
        return SkillResult(
            success=True,
            data={
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "actions": manifest.actions,
                "permissions": manifest.permissions
            },
            message=f"""**{manifest.name}** v{manifest.version}
{manifest.description}

Actions: {', '.join(manifest.actions)}
Requires: {', '.join(manifest.permissions) or 'None'}"""
        )
    
    def _action_status(self, params: Dict, context: Dict) -> SkillResult:
        """Get system status."""
        import psutil
        
        status = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "uptime": time.time() - psutil.boot_time(),
            "skills_loaded": 0,
            "skills_healthy": 0,
        }
        
        if self._skill_router:
            skills = self._skill_router.list_skills()
            status["skills_loaded"] = len(skills)
            status["skills_healthy"] = sum(1 for s in skills if s.get("health") == "ready")
        
        return SkillResult(
            success=True,
            data=status,
            message=f"""System Status:
• CPU: {status['cpu_percent']:.1f}%
• Memory: {status['memory_percent']:.1f}%
• Skills: {status['skills_healthy']}/{status['skills_loaded']} healthy"""
        )
    
    def _action_health(self, params: Dict, context: Dict) -> SkillResult:
        """Check all skill health."""
        if not self._skill_router:
            return SkillResult(success=False, error="Skill router not available")
        
        skills = self._skill_router.list_skills()
        
        report = []
        for skill in skills:
            health = skill.get("health", "unknown")
            icon = {"ready": "✅", "degraded": "⚠️", "unavailable": "❌"}.get(health, "❓")
            report.append(f"{icon} {skill['name']}: {health}")
        
        unhealthy = [s for s in skills if s.get("health") != "ready"]
        
        return SkillResult(
            success=True,
            data={"skills": skills, "unhealthy": len(unhealthy)},
            message="Health Report:\n" + "\n".join(report)
        )
    
    def _action_learn(self, params: Dict, context: Dict) -> SkillResult:
        """Learn a pattern from user behavior."""
        pattern_name = params.get("name", "")
        trigger = params.get("trigger", "")
        steps = params.get("steps", [])
        
        if not pattern_name:
            return SkillResult(success=False, error="Pattern name required")
        
        # If no steps provided, try to learn from recent history
        if not steps and self._command_history:
            steps = [
                {"skill": cmd["skill"], "action": cmd["action"], "params": cmd.get("params", {})}
                for cmd in self._command_history[-5:]
            ]
        
        if not steps:
            return SkillResult(success=False, error="No steps to learn")
        
        pattern = {
            "name": pattern_name,
            "trigger": trigger,
            "steps": steps,
            "created_at": time.time()
        }
        
        self._learned_patterns.append(pattern)
        
        # Could save to workflows skill here
        return SkillResult(
            success=True,
            data={"pattern": pattern},
            message=f"Learned pattern '{pattern_name}' with {len(steps)} steps"
        )
    
    def _action_suggest(self, params: Dict, context: Dict) -> SkillResult:
        """Suggest next actions based on context."""
        current_context = params.get("context", "")
        
        suggestions = []
        
        # Time-based suggestions
        hour = time.localtime().tm_hour
        if 6 <= hour < 9:
            suggestions.append({
                "action": "Run morning routine",
                "skill": "workflow",
                "command": "run morning_routine"
            })
        elif 17 <= hour < 19:
            suggestions.append({
                "action": "Check daily summary",
                "skill": "memory",
                "command": "summarize today"
            })
        
        # Context-based suggestions
        if "browser" in current_context.lower():
            suggestions.append({
                "action": "Take a screenshot",
                "skill": "vision",
                "command": "screenshot"
            })
        
        if not suggestions:
            suggestions = [
                {"action": "Check system status", "command": "status"},
                {"action": "List capabilities", "command": "what can you do"},
                {"action": "Run a workflow", "command": "list workflows"},
            ]
        
        return SkillResult(
            success=True,
            data={"suggestions": suggestions},
            message="Suggestions:\n" + "\n".join([f"• {s['action']}" for s in suggestions])
        )
    
    def _action_help(self, params: Dict, context: Dict) -> SkillResult:
        """Get contextual help."""
        topic = params.get("topic", "general")
        
        help_topics = {
            "general": """**Neural Agent Help**

I'm your AI assistant with advanced automation capabilities.

**Quick Commands:**
• "Open [app]" - Launch an application
• "Go to [website]" - Navigate browser
• "Remember [fact]" - Store in memory
• "What can you do?" - List capabilities

**Skills Available:**
• Browser, Desktop, Memory, Voice, Vision
• Workflows, Integrations, Planning, Knowledge

Say "explain [skill]" for details on any skill.""",

            "browser": """**Browser Skill**

Navigate the web and automate web interactions.

Examples:
• "Go to gmail.com"
• "Click the login button"
• "Fill the email field with [email]"
• "Take a screenshot"
• "Scrape this page"

Sessions persist cookies for authentication.""",

            "desktop": """**Desktop Skill**

Control applications and automate desktop tasks.

Examples:
• "Open Spotify"
• "Close Notepad"
• "Type 'Hello World'"
• "Press Ctrl+S"
• "Set volume to 50%"
• "Take a screenshot\"""",

            "workflow": """**Workflow Skill**

Create and run multi-step automations.

Examples:
• "Run morning routine"
• "List workflows"
• "Create workflow [name]"

Workflows are YAML files in agent/data/workflows/"""
        }
        
        help_text = help_topics.get(topic.lower(), help_topics["general"])
        
        return SkillResult(
            success=True,
            data={"topic": topic},
            message=help_text
        )
    
    def _action_capabilities(self, params: Dict, context: Dict) -> SkillResult:
        """List all capabilities in user-friendly format."""
        capabilities = {
            "🌐 Web Automation": [
                "Navigate to websites",
                "Click, type, fill forms",
                "Scrape content",
                "Take screenshots",
                "Manage login sessions"
            ],
            "🖥️ Desktop Control": [
                "Launch/close applications",
                "Keyboard shortcuts",
                "Mouse automation",
                "Volume control",
                "Clipboard access"
            ],
            "🧠 Memory & Knowledge": [
                "Remember facts and preferences",
                "Semantic search",
                "Document Q&A (RAG)",
                "PDF ingestion"
            ],
            "🎤 Voice & Vision": [
                "Text-to-speech",
                "Speech-to-text",
                "Screen capture",
                "OCR text extraction",
                "Image analysis"
            ],
            "⚙️ Automation": [
                "Multi-step workflows",
                "Task planning",
                "Conditional execution",
                "API integrations"
            ],
            "🔌 Integrations": [
                "Spotify control",
                "GitHub issues/PRs",
                "Notion pages",
                "Discord webhooks"
            ]
        }
        
        message = "**What I Can Do**\n\n"
        for category, items in capabilities.items():
            message += f"{category}\n"
            for item in items:
                message += f"  • {item}\n"
            message += "\n"
        
        return SkillResult(
            success=True,
            data={"capabilities": capabilities},
            message=message
        )
    
    def record_command(self, skill: str, action: str, params: Dict):
        """Record a command for learning."""
        self._command_history.append({
            "skill": skill,
            "action": action,
            "params": params,
            "timestamp": time.time()
        })
        # Keep last 50
        if len(self._command_history) > 50:
            self._command_history = self._command_history[-50:]
    
    # ==================== HEALTH ====================
    
    def health(self) -> SkillHealth:
        """Check meta skill health."""
        if not self._loaded:
            return SkillHealth.UNAVAILABLE
        if not self._skill_router:
            return SkillHealth.DEGRADED
        return SkillHealth.READY
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """Preview meta action."""
        if action == "explain":
            return f"Would explain: {params.get('skill', 'unknown')}"
        return f"Would execute meta.{action}"
