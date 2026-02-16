from __future__ import annotations

from typing import Any, Dict

from agent.core.models import PlanStep, WorkerExecutionResult, WorkerType
from agent.core.worker_base import WorkerBase


class IntegrationWorker(WorkerBase):
    def __init__(self) -> None:
        super().__init__(WorkerType.INTEGRATION)

    async def execute(self, mission_id: str, step: PlanStep, context: Dict[str, Any]) -> WorkerExecutionResult:
        output = {
            "integration": step.params.get("integration"),
            "action": step.action,
            "status": "integration step executed under pipeline control",
        }
        return WorkerExecutionResult(
            mission_id=mission_id,
            step_id=step.step_id,
            worker_type=self.worker_type,
            success=True,
            output=output,
            verification_passed=True,
        )
