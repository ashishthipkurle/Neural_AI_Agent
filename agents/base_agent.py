"""
INDRA OS — Base Agent Interface

Every agent in the system inherits from BaseAgent. This guarantees INDRA
can manage all agents through a single, consistent interface regardless
of what each agent actually does internally.

Lifecycle:
    1. Agent is instantiated and registered with AgentRegistry
    2. INDRA assigns a Task via execute()
    3. Agent works, publishes progress via message bus
    4. Agent returns TaskResult
    5. INDRA logs result and reports to user
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from agents.task import Task, TaskResult, ProgressReport


class AgentStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    ERROR = "error"
    PAUSED = "paused"
    OFFLINE = "offline"
    INITIALIZING = "initializing"


class BaseAgent(ABC):
    """
    Abstract base class for all INDRA OS agents.
    Every agent must implement execute() and can_handle().
    """

    def __init__(self, name: str, description: str, capabilities: list[str]):
        self.name = name
        self.description = description
        self.capabilities = capabilities
        self.status = AgentStatus.INITIALIZING
        self.current_task: Optional[Task] = None
        self._task_history: list[TaskResult] = []
        self._cancel_requested = False
        self._message_bus = None  # set by registry after registration
        self.memory = None         # set by MemoryManager during startup
        self.logger = logging.getLogger(f"Agent.{name}")

        # Performance metrics
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._total_time = 0.0

    # ── Core Interface (must implement) ───────────────────────────────────

    @abstractmethod
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute the given task. This is the agent's main work method.

        The agent should:
        1. Update task.status to RUNNING
        2. Do the actual work (may be multi-step)
        3. Publish progress updates via self.publish_progress()
        4. Return a TaskResult with success/failure info

        If self._cancel_requested becomes True, the agent should stop
        gracefully and return a CANCELLED result.
        """
        ...

    @abstractmethod
    async def can_handle(self, task_description: str) -> float:
        """
        Return a confidence score (0.0 to 1.0) indicating how well
        this agent can handle the described task.

        0.0 = definitely cannot handle
        0.5 = might be able to handle
        1.0 = this is exactly what I'm built for

        The orchestrator uses these scores to route tasks.
        """
        ...

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def initialize(self) -> bool:
        """
        Called once at startup. Override to load models, check resources, etc.
        Returns True if ready, False if initialization failed.
        """
        self.status = AgentStatus.IDLE
        self.logger.info(f"{self.name} agent initialized")
        return True

    async def shutdown(self) -> None:
        """Called on system shutdown. Override to cleanup resources."""
        # Save memory to disk before shutting down
        if self.memory:
            self.memory.save_to_disk()
        self.status = AgentStatus.OFFLINE
        self.logger.info(f"{self.name} agent shut down")

    # ── Task Execution Wrapper ────────────────────────────────────────────

    async def run_task(self, task: Task) -> TaskResult:
        """
        Wraps execute() with status tracking, timing, and error handling.
        INDRA calls this — not execute() directly.
        """
        self.current_task = task
        self._cancel_requested = False
        self.status = AgentStatus.WORKING
        task.start()

        start_time = time.time()
        self.logger.info(f"Starting task: {task.description[:80]}")

        try:
            result = await self.execute(task)

            elapsed = time.time() - start_time
            result.duration_seconds = elapsed

            if result.success:
                task.complete()
                self._tasks_completed += 1
                self.logger.info(
                    f"Task completed in {elapsed:.1f}s: {result.output[:80]}"
                )
            else:
                task.fail()
                self._tasks_failed += 1
                self.logger.warning(
                    f"Task failed after {elapsed:.1f}s: {result.error}"
                )

            self._total_time += elapsed
            self._task_history.append(result)

            # Record interaction in memory (KV cache)
            if self.memory:
                self.memory.add_interaction(
                    user_input=task.description,
                    agent_response=result.output,
                    task_result=result.to_dict(),
                )

            # Keep history bounded
            if len(self._task_history) > 100:
                self._task_history = self._task_history[-50:]

            return result

        except asyncio.CancelledError:
            task.cancel()
            self.logger.info("Task cancelled")
            return TaskResult(
                task_id=task.id,
                success=False,
                output="Task was cancelled",
                error="Cancelled by user or INDRA",
            )

        except Exception as e:
            task.fail()
            self._tasks_failed += 1
            self.logger.error(f"Task crashed: {e}", exc_info=True)
            return TaskResult(
                task_id=task.id,
                success=False,
                output="Task failed with an unexpected error",
                error=str(e),
            )

        finally:
            self.current_task = None
            self.status = AgentStatus.IDLE

    # ── Control ───────────────────────────────────────────────────────────

    async def cancel(self) -> None:
        """Request the agent to stop its current task gracefully."""
        if self.current_task:
            self._cancel_requested = True
            self.logger.info("Cancel requested")

    async def pause(self) -> None:
        self.status = AgentStatus.PAUSED

    async def resume(self) -> None:
        if self.status == AgentStatus.PAUSED:
            self.status = AgentStatus.WORKING

    # ── Progress Reporting ────────────────────────────────────────────────

    async def publish_progress(
        self,
        progress: float,
        current_step: str,
        steps_completed: int = 0,
        steps_total: int = -1,
        message: str = "",
    ):
        """Publish a progress update to the message bus."""
        if not self.current_task:
            return

        report = ProgressReport(
            agent_name=self.name,
            task_id=self.current_task.id,
            progress=progress,
            current_step=current_step,
            steps_completed=steps_completed,
            steps_total=steps_total,
            message=message,
        )

        if self._message_bus:
            await self._message_bus.publish(
                f"agent.{self.name}.progress", report.to_dict()
            )

    # ── Memory Access ─────────────────────────────────────────────────────

    def get_memory_context(self, current_query: str = "") -> str:
        """Get memory context to inject into LLM prompts."""
        if self.memory:
            return self.memory.get_context_for_prompt(current_query)
        return ""

    def remember(self, content: str, key: str = "", importance: float = 0.5):
        """Manually store something important in memory."""
        if self.memory:
            self.memory.add(role="system", content=content, key=key, importance=importance)

    # ── Introspection ─────────────────────────────────────────────────────

    async def get_history(self) -> list[dict]:
        """Return recent task history."""
        return [r.to_dict() for r in self._task_history[-20:]]

    def get_stats(self) -> dict:
        """Return agent performance stats."""
        total = self._tasks_completed + self._tasks_failed
        return {
            "name": self.name,
            "status": self.status.value,
            "tasks_completed": self._tasks_completed,
            "tasks_failed": self._tasks_failed,
            "success_rate": (
                self._tasks_completed / total if total > 0 else 1.0
            ),
            "avg_duration": (
                self._total_time / total if total > 0 else 0.0
            ),
            "current_task": (
                self.current_task.to_dict() if self.current_task else None
            ),
            "capabilities": self.capabilities,
            "description": self.description,
        }

    def to_dict(self) -> dict:
        """Serialize agent state for API/UI."""
        result = {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "current_task": (
                self.current_task.to_dict() if self.current_task else None
            ),
            "stats": self.get_stats(),
        }
        if self.memory:
            result["memory"] = self.memory.get_stats()
        return result
