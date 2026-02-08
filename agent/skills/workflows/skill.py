"""
Workflow Skill - Macro/task automation with skill-aware steps.

Provides:
- YAML-based workflow definitions
- Parameterized workflows
- Conditional branching
- Multi-step task execution
- Named workflow storage

IMPORTANT: Workflows call SKILLS, not TOOLS.
This keeps workflows stable even when skill internals change.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    skill: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    save_as: Optional[str] = None  # Save result to context variable
    condition: Optional[str] = None  # Only execute if condition is true
    on_error: str = "stop"  # stop, continue, retry


@dataclass 
class Workflow:
    """A complete workflow definition."""
    name: str
    description: str = ""
    trigger: Optional[str] = None  # Natural language trigger
    steps: List[WorkflowStep] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)  # Default parameters


class WorkflowSkill(BaseSkill):
    """
    Workflow execution and management skill.
    
    Actions:
    - run: Execute a workflow by name
    - list: List available workflows
    - create: Create a new workflow
    - delete: Delete a workflow
    - show: Show workflow details
    
    Workflows are stored in: agent/data/workflows/*.yaml
    """
    
    WORKFLOW_DIR = Path("agent/data/workflows")
    
    def __init__(self, skill_router=None):
        super().__init__()
        self._workflows: Dict[str, Workflow] = {}
        self._skill_router = skill_router  # Injected for executing skill actions
    
    def set_router(self, router):
        """Set the skill router for executing steps."""
        self._skill_router = router
    
    @property
    def name(self) -> str:
        return "workflow"
    
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="workflow",
            version="1.0.0",
            description="Macro/task automation with skill-aware steps",
            actions=["run", "list", "create", "delete", "show", "dry_run_workflow"],
            requires=[],
            permissions=["workflows"]
        )
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """Load all workflow definitions."""
        try:
            self.WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
            self._load_workflows()
            super().on_load()
            self.logger.info(f"Workflow skill loaded. {len(self._workflows)} workflows available.")
        except Exception as e:
            self.logger.error(f"Failed to initialize workflow skill: {e}")
            self._health = SkillHealth.DEGRADED
    
    def _load_workflows(self) -> None:
        """Load all .yaml workflow files."""
        for yaml_file in self.WORKFLOW_DIR.glob("*.yaml"):
            try:
                workflow = self._parse_workflow_file(yaml_file)
                if workflow:
                    self._workflows[workflow.name] = workflow
                    self.logger.debug(f"Loaded workflow: {workflow.name}")
            except Exception as e:
                self.logger.error(f"Failed to load workflow {yaml_file}: {e}")
    
    def _parse_workflow_file(self, path: Path) -> Optional[Workflow]:
        """Parse a YAML workflow file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        if not data:
            return None
        
        steps = []
        for step_data in data.get("steps", []):
            step = WorkflowStep(
                skill=step_data.get("skill", ""),
                action=step_data.get("action", ""),
                params=step_data.get("params", {}),
                save_as=step_data.get("save_as"),
                condition=step_data.get("condition"),
                on_error=step_data.get("on_error", "stop")
            )
            steps.append(step)
        
        return Workflow(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            trigger=data.get("trigger"),
            steps=steps,
            params=data.get("params", {})
        )
    
    def on_unload(self) -> None:
        """Cleanup."""
        super().on_unload()
    
    # ==================== INTENT MATCHING ====================
    
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill can handle the intent."""
        intent_lower = intent.lower()
        
        # Check for workflow triggers
        for wf in self._workflows.values():
            if wf.trigger and wf.trigger.lower() in intent_lower:
                return 0.95
        
        # General workflow patterns
        patterns = [
            "run workflow", "execute workflow", "start workflow",
            "run routine", "run macro", "execute macro",
            "morning routine", "daily routine"
        ]
        
        for pattern in patterns:
            if pattern in intent_lower:
                return 0.85
        
        return 0.0
    
    # ==================== EXECUTION ====================
    
    def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Execute a workflow action."""
        
        handlers = {
            "run": self._action_run,
            "list": self._action_list,
            "create": self._action_create,
            "delete": self._action_delete,
            "show": self._action_show,
            "dry_run_workflow": self._action_dry_run,
        }
        
        handler = handlers.get(action)
        if not handler:
            # Try to match workflow by trigger
            handler = self._match_by_trigger(action)
            if handler:
                return handler(params, context or {})
            return SkillResult(success=False, error=f"Unknown action: {action}")
        
        return handler(params, context or {})
    
    def _match_by_trigger(self, intent: str):
        """Try to match intent to a workflow trigger."""
        intent_lower = intent.lower()
        for wf in self._workflows.values():
            if wf.trigger and wf.trigger.lower() in intent_lower:
                def run_matched(params, context):
                    params["name"] = wf.name
                    return self._action_run(params, context)
                return run_matched
        return None
    
    # ==================== ACTIONS ====================
    
    def _action_run(self, params: Dict, context: Dict) -> SkillResult:
        """Execute a workflow by name."""
        name = params.get("name")
        if not name:
            return SkillResult(success=False, error="Workflow name required")
        
        if name not in self._workflows:
            return SkillResult(success=False, error=f"Workflow not found: {name}")
        
        if not self._skill_router:
            return SkillResult(success=False, error="Skill router not available")
        
        workflow = self._workflows[name]
        
        # Merge default params with provided params
        run_params = {**workflow.params, **params}
        run_context = {**context, **run_params}
        
        results = []
        for i, step in enumerate(workflow.steps):
            self.logger.info(f"Executing step {i+1}/{len(workflow.steps)}: {step.skill}.{step.action}")
            
            # Check condition
            if step.condition:
                if not self._evaluate_condition(step.condition, run_context):
                    self.logger.info(f"Skipping step (condition false): {step.condition}")
                    continue
            
            # Interpolate params with context
            step_params = self._interpolate_params(step.params, run_context)
            
            # Execute via router
            try:
                result = self._skill_router.execute_skill_action(
                    step.skill, 
                    step.action, 
                    step_params
                )
                
                results.append({
                    "step": f"{step.skill}.{step.action}",
                    "success": result.success,
                    "message": result.result.message if result.result else ""
                })
                
                # Save result if requested
                if step.save_as and result.result and result.result.data:
                    run_context[step.save_as] = result.result.data
                
                # Handle errors
                if not result.success:
                    if step.on_error == "stop":
                        return SkillResult(
                            success=False,
                            data={"results": results, "failed_at": i+1},
                            error=f"Workflow stopped at step {i+1}: {result.error}"
                        )
                    # continue: just move on
                    
            except Exception as e:
                if step.on_error == "stop":
                    return SkillResult(
                        success=False,
                        data={"results": results},
                        error=f"Step {i+1} failed: {e}"
                    )
        
        return SkillResult(
            success=True,
            data={"results": results},
            message=f"Workflow '{name}' completed successfully",
            context_updates=run_context
        )
    
    def _evaluate_condition(self, condition: str, context: Dict) -> bool:
        """Evaluate a condition expression."""
        try:
            # Simple variable check: "{{variable}}"
            if condition.startswith("{{") and condition.endswith("}}"):
                var_name = condition[2:-2].strip()
                return bool(context.get(var_name))
            
            # Expression evaluation (be careful with this in production!)
            return eval(condition, {"__builtins__": {}}, context)
        except:
            return False
    
    def _interpolate_params(self, params: Dict, context: Dict) -> Dict:
        """Replace {{variable}} placeholders with context values."""
        result = {}
        for key, value in params.items():
            if isinstance(value, str) and "{{" in value:
                # Replace all {{var}} with context values
                for ctx_key, ctx_value in context.items():
                    value = value.replace(f"{{{{{ctx_key}}}}}", str(ctx_value))
                result[key] = value
            else:
                result[key] = value
        return result
    
    def _action_list(self, params: Dict, context: Dict) -> SkillResult:
        """List all available workflows."""
        workflows_info = [
            {
                "name": wf.name,
                "description": wf.description,
                "trigger": wf.trigger,
                "steps": len(wf.steps)
            }
            for wf in self._workflows.values()
        ]
        
        return SkillResult(
            success=True,
            data={"workflows": workflows_info},
            message=f"Found {len(workflows_info)} workflows"
        )
    
    def _action_create(self, params: Dict, context: Dict) -> SkillResult:
        """Create a new workflow."""
        name = params.get("name")
        description = params.get("description", "")
        trigger = params.get("trigger")
        steps = params.get("steps", [])
        
        if not name:
            return SkillResult(success=False, error="Workflow name required")
        
        # Build YAML content
        workflow_data = {
            "name": name,
            "description": description,
            "trigger": trigger,
            "steps": steps
        }
        
        # Save to file
        file_path = self.WORKFLOW_DIR / f"{name}.yaml"
        with open(file_path, 'w') as f:
            yaml.dump(workflow_data, f, default_flow_style=False)
        
        # Reload
        workflow = self._parse_workflow_file(file_path)
        if workflow:
            self._workflows[name] = workflow
        
        return SkillResult(
            success=True,
            data={"path": str(file_path)},
            message=f"Created workflow: {name}"
        )
    
    def _action_delete(self, params: Dict, context: Dict) -> SkillResult:
        """Delete a workflow."""
        name = params.get("name")
        if not name or name not in self._workflows:
            return SkillResult(success=False, error=f"Workflow not found: {name}")
        
        file_path = self.WORKFLOW_DIR / f"{name}.yaml"
        if file_path.exists():
            file_path.unlink()
        
        del self._workflows[name]
        
        return SkillResult(success=True, message=f"Deleted workflow: {name}")
    
    def _action_show(self, params: Dict, context: Dict) -> SkillResult:
        """Show workflow details."""
        name = params.get("name")
        if not name or name not in self._workflows:
            return SkillResult(success=False, error=f"Workflow not found: {name}")
        
        wf = self._workflows[name]
        steps_info = [
            {"skill": s.skill, "action": s.action, "params": s.params}
            for s in wf.steps
        ]
        
        return SkillResult(
            success=True,
            data={
                "name": wf.name,
                "description": wf.description,
                "trigger": wf.trigger,
                "steps": steps_info
            },
            message=f"Workflow '{name}' has {len(wf.steps)} steps"
        )
    
    def _action_dry_run(self, params: Dict, context: Dict) -> SkillResult:
        """Preview workflow execution without actually running."""
        name = params.get("name")
        if not name or name not in self._workflows:
            return SkillResult(success=False, error=f"Workflow not found: {name}")
        
        wf = self._workflows[name]
        preview = []
        
        for i, step in enumerate(wf.steps):
            dry_run_text = f"Step {i+1}: Would call {step.skill}.{step.action}"
            if step.params:
                dry_run_text += f" with {step.params}"
            if step.condition:
                dry_run_text += f" (if {step.condition})"
            preview.append(dry_run_text)
        
        return SkillResult(
            success=True,
            data={"preview": preview},
            message="\n".join(preview)
        )
    
    # ==================== HEALTH ====================
    
    def health(self) -> SkillHealth:
        """Check workflow skill health."""
        if not self._loaded:
            return SkillHealth.UNAVAILABLE
        if not self._skill_router:
            return SkillHealth.DEGRADED
        return SkillHealth.READY
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """Preview workflow action."""
        if action == "run":
            name = params.get("name", "unknown")
            wf = self._workflows.get(name)
            if wf:
                return f"Would run workflow '{name}' with {len(wf.steps)} steps"
            return f"Workflow '{name}' not found"
        
        return f"Would execute workflow.{action}"
