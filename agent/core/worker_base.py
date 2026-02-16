from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from agent.core.models import PlanStep, WorkerExecutionResult, WorkerType


class WorkerBase(ABC):
    def __init__(self, worker_type: WorkerType) -> None:
        self.worker_type = worker_type

    @abstractmethod
    async def execute(self, mission_id: str, step: PlanStep, context: Dict[str, Any]) -> WorkerExecutionResult:
        raise NotImplementedError
