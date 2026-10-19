"""
INDRA OS — Task & Result Data Models

Standardized task objects used across all agents. Every task has:
- A unique ID, description, priority, and status
- Assignment tracking (who created it, who's working on it)
- Sub-task decomposition for complex multi-step work
- Artifact tracking (files, URLs produced)
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_CONFIRM = "waiting_confirm"  # needs user approval before proceeding


class TaskPriority(int, Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


@dataclass
class Task:
    """A unit of work assigned to an agent."""

    description: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    assigned_to: str = ""              # agent name (e.g. "trading")
    assigned_by: str = "indra"         # "indra" or "user"
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    subtasks: list["Task"] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    # Parent task ID for sub-tasks
    parent_id: Optional[str] = None

    def start(self):
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()

    def complete(self):
        self.status = TaskStatus.DONE
        self.completed_at = datetime.utcnow()

    def fail(self):
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.utcnow()

    def cancel(self):
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.utcnow()

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        if self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return 0.0

    @property
    def progress(self) -> float:
        """Estimate progress from sub-task completion (0.0 to 1.0)."""
        if not self.subtasks:
            if self.status == TaskStatus.DONE:
                return 1.0
            if self.status == TaskStatus.RUNNING:
                return 0.5  # unknown progress without subtasks
            return 0.0
        done = sum(1 for st in self.subtasks if st.status == TaskStatus.DONE)
        return done / len(self.subtasks)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "assigned_by": self.assigned_by,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "duration_seconds": self.duration_seconds,
            "subtask_count": len(self.subtasks),
            "parent_id": self.parent_id,
        }


@dataclass
class TaskResult:
    """The outcome of a completed task."""

    task_id: str
    success: bool
    output: str                            # human-readable result summary
    artifacts: list[str] = field(default_factory=list)  # files, URLs produced
    error: Optional[str] = None
    duration_seconds: float = 0.0
    steps_taken: list[str] = field(default_factory=list)  # log of actions

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "output": self.output,
            "artifacts": self.artifacts,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
            "steps_taken": self.steps_taken,
        }


@dataclass
class ProgressReport:
    """Real-time progress update from an agent."""

    agent_name: str
    task_id: str
    progress: float          # 0.0 to 1.0
    current_step: str        # what the agent is doing right now
    steps_completed: int
    steps_total: int         # -1 if unknown
    message: str = ""        # optional status message

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "task_id": self.task_id,
            "progress": self.progress,
            "current_step": self.current_step,
            "steps_completed": self.steps_completed,
            "steps_total": self.steps_total,
            "message": self.message,
        }
