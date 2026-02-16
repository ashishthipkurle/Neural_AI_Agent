from __future__ import annotations

from typing import Any, Dict

from agent.core.models import PlanStep, WorkerExecutionResult, WorkerType
from agent.core.worker_base import WorkerBase


class ResearchWorker(WorkerBase):
    def __init__(self) -> None:
        super().__init__(WorkerType.RESEARCH)

    async def execute(self, mission_id: str, step: PlanStep, context: Dict[str, Any]) -> WorkerExecutionResult:
        query = step.params.get("query", step.action)
        output = {
            "query": query,
            "summary": f"Research findings synthesized for: {query}",
            "sources": step.params.get("sources", []),
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
