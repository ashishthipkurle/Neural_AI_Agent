from __future__ import annotations

from typing import Any, Dict

from agent.core.models import PlanStep, WorkerExecutionResult, WorkerType
from agent.core.worker_base import WorkerBase


class SkillExecutionWorker(WorkerBase):
    def __init__(self) -> None:
        super().__init__(WorkerType.SKILL)

    async def execute(self, mission_id: str, step: PlanStep, context: Dict[str, Any]) -> WorkerExecutionResult:
        output = {
            "action": step.action,
            "params": step.params,
            "result": "generic skill execution complete",
            "status": "ok",
        }
        return WorkerExecutionResult(
            mission_id=mission_id,
            step_id=step.step_id,
            worker_type=self.worker_type,
            success=True,
            output=output,
            verification_passed=True,
        )
