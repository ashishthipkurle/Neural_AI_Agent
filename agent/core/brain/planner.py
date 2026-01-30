"""
Planner Module - Decomposes user goals into actionable steps.

This module handles goal decomposition, task planning, and action sequencing.
It creates structured plans that the orchestrator can execute step-by-step.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class TaskPriority(Enum):
    """Priority levels for planned tasks."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class TaskStatus(Enum):
    """Execution status of a planned task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass
class PlannedTask:
    """Represents a single actionable task in a plan."""
    id: str
    action: str
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    requires_confirmation: bool = False
    is_destructive: bool = False
    estimated_duration_seconds: float = 1.0
    dependencies: List[str] = field(default_factory=list)
    reasoning: str = ""
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


@dataclass
class ExecutionPlan:
    """Complete execution plan for a user goal."""
    id: str
    goal: str
    tasks: List[PlannedTask] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    total_estimated_duration: float = 0.0
    
    def add_task(self, task: PlannedTask) -> None:
        """Add a task to the plan and update duration estimate."""
        self.tasks.append(task)
        self.total_estimated_duration += task.estimated_duration_seconds
    
    def get_next_pending_task(self) -> Optional[PlannedTask]:
        """Get the next task that is pending and has no blocked dependencies."""
        completed_ids = {t.id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        for task in self.tasks:
            if task.status == TaskStatus.PENDING:
                deps_satisfied = all(dep in completed_ids for dep in task.dependencies)
                if deps_satisfied:
                    return task
        return None
    
    def mark_task_complete(self, task_id: str, result: str) -> None:
        """Mark a specific task as completed."""
        for task in self.tasks:
            if task.id == task_id:
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now().isoformat()
                break
        
        # Check if all tasks are complete
        if all(t.status == TaskStatus.COMPLETED for t in self.tasks):
            self.status = TaskStatus.COMPLETED
            self.completed_at = datetime.now().isoformat()
    
    def mark_task_failed(self, task_id: str, error: str) -> None:
        """Mark a specific task as failed."""
        for task in self.tasks:
            if task.id == task_id:
                task.status = TaskStatus.FAILED
                task.error = error
                break
        self.status = TaskStatus.FAILED


class Planner:
    """
    Goal decomposition and action planning engine.
    
    Breaks down user goals into structured, executable plans with:
    - Task sequencing
    - Dependency management
    - Priority assignment
    - Confirmation requirements
    """
    
    # Destructive actions that require explicit confirmation
    DESTRUCTIVE_ACTIONS = frozenset({
        'delete', 'remove', 'format', 'shutdown', 'restart',
        'execute_code', 'run_code', 'write_file', 'overwrite',
        'uninstall', 'kill_process', 'forget_face'
    })
    
    # High-risk tools that need confirmation
    HIGH_RISK_TOOLS = frozenset({
        'execute_code', 'write_file', 'shell_command',
        'browser_navigate', 'delete_file', 'forget_face',
        'lock_agent', 'shutdown_system'
    })
    
    def __init__(self, llm_interface=None):
        """
        Initialize the Planner.
        
        Args:
            llm_interface: Optional LLM interface for advanced planning.
        """
        self.logger = logging.getLogger("Planner")
        self.llm = llm_interface
        self._plan_counter = 0
        self._task_counter = 0
        self.logger.info("Planner initialized.")
    
    def _generate_plan_id(self) -> str:
        """Generate unique plan ID."""
        self._plan_counter += 1
        return f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._plan_counter}"
    
    def _generate_task_id(self) -> str:
        """Generate unique task ID."""
        self._task_counter += 1
        return f"task_{self._task_counter}"
    
    def _is_destructive_action(self, action: str, tool_name: str) -> bool:
        """Check if an action is destructive and requires confirmation."""
        action_lower = action.lower()
        return (
            tool_name in self.HIGH_RISK_TOOLS or
            any(da in action_lower for da in self.DESTRUCTIVE_ACTIONS)
        )
    
    def create_plan(self, goal: str, intents: List[Any]) -> ExecutionPlan:
        """
        Create an execution plan from parsed intents.
        
        Args:
            goal: The original user goal/request.
            intents: List of Intent objects from the parser.
        
        Returns:
            ExecutionPlan with sequenced tasks.
        """
        plan = ExecutionPlan(
            id=self._generate_plan_id(),
            goal=goal
        )
        
        self.logger.info(f"Creating plan for goal: {goal}")
        
        for intent in intents:
            is_destructive = self._is_destructive_action(
                intent.action,
                intent.tool_name or ""
            )
            
            task = PlannedTask(
                id=self._generate_task_id(),
                action=intent.action,
                tool_name=intent.tool_name or "",
                parameters=intent.parameters,
                requires_confirmation=is_destructive,
                is_destructive=is_destructive,
                reasoning=getattr(intent, 'reasoning', ""),
                priority=TaskPriority.HIGH if is_destructive else TaskPriority.MEDIUM
            )
            
            plan.add_task(task)
            self.logger.debug(f"Added task: {task.action} (destructive={is_destructive})")
        
        self.logger.info(f"Plan created with {len(plan.tasks)} tasks")
        return plan
    
    def decompose_complex_goal(self, goal: str) -> ExecutionPlan:
        """
        Use LLM to decompose a complex goal into steps.
        
        This is for goals that require multi-step reasoning
        beyond simple intent parsing.
        
        Args:
            goal: Complex user goal requiring decomposition.
        
        Returns:
            ExecutionPlan with decomposed tasks.
        """
        plan = ExecutionPlan(
            id=self._generate_plan_id(),
            goal=goal
        )
        
        if not self.llm:
            self.logger.warning("No LLM available for complex goal decomposition.")
            # Fallback: create a single task to handle the goal
            task = PlannedTask(
                id=self._generate_task_id(),
                action="chat_tool",
                tool_name="chat_tool",
                parameters={"message": goal},
                reasoning="No LLM available for decomposition, falling back to chat."
            )
            plan.add_task(task)
            return plan
        
        # TODO: Implement LLM-based goal decomposition
        # For now, return a placeholder plan
        self.logger.info(f"Complex goal decomposition for: {goal}")
        
        task = PlannedTask(
            id=self._generate_task_id(),
            action="chat_tool",
            tool_name="chat_tool",
            parameters={"message": goal},
            reasoning="Planning in progress - using chat as intermediate step."
        )
        plan.add_task(task)
        
        return plan
    
    def validate_plan(self, plan: ExecutionPlan) -> List[str]:
        """
        Validate a plan for potential issues.
        
        Args:
            plan: The execution plan to validate.
        
        Returns:
            List of validation warnings/errors.
        """
        issues = []
        
        # Check for missing tools
        for task in plan.tasks:
            if not task.tool_name:
                issues.append(f"Task {task.id} has no tool specified.")
        
        # Check for circular dependencies
        task_ids = {t.id for t in plan.tasks}
        for task in plan.tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    issues.append(f"Task {task.id} depends on unknown task {dep}.")
        
        # Check for destructive actions without confirmation
        for task in plan.tasks:
            if task.is_destructive and not task.requires_confirmation:
                issues.append(f"Destructive task {task.id} should require confirmation.")
        
        if issues:
            self.logger.warning(f"Plan validation found {len(issues)} issues.")
        
        return issues
