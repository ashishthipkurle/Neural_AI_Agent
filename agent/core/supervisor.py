from __future__ import annotations

from typing import Dict, List

from agent.core.models import ExecutionPlan, PlanStep, RiskLevel, WorkerType
from agent.core.plan_validator import PlanValidator


class Supervisor:
    def __init__(self, plan_validator: PlanValidator) -> None:
        self.plan_validator = plan_validator
        self.execution_history: Dict[str, List[dict]] = {}
        self.mission_state: Dict[str, str] = {}

    def review(self, mission_id: str, risk: RiskLevel, proposed_steps: List[PlanStep]) -> bool:
        if risk == RiskLevel.CRITICAL:
            return False
        if not proposed_steps:
            return False
        self.mission_state[mission_id] = "reviewed"
        return True

    def approve_plan(self, plan: ExecutionPlan) -> tuple[bool, list[str]]:
        valid, errors = self.plan_validator.validate(plan)
        return valid, errors

    def assign_worker(self, step: PlanStep) -> WorkerType:
        return step.worker_type

    def analyze_progress(self, mission_id: str, completed_steps: int, total_steps: int, consecutive_failures: int) -> str:
        if consecutive_failures >= 3:
            return "escalate_strategy"
        if completed_steps >= total_steps:
            self.mission_state[mission_id] = "completed"
            return "complete"
        if completed_steps == 0 and consecutive_failures > 0:
            return "replan"
        return "continue"

    def detect_stagnation(self, mission_id: str, repeated_step_failures: int) -> bool:
        return repeated_step_failures >= 3

    def log_history(self, mission_id: str, event: dict) -> None:
        self.execution_history.setdefault(mission_id, []).append(event)
