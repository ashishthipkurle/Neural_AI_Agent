from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from typing import Dict, List, Tuple

from agent.core.models import ExecutionPlan, PlanStep


class PlanValidator:
    def validate(self, plan: ExecutionPlan) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not plan.steps:
            errors.append("Plan has no steps")

        seen = set()
        for step in plan.steps:
            if step.step_id in seen:
                errors.append(f"Duplicate step id: {step.step_id}")
            seen.add(step.step_id)
            if not step.acceptance_criteria:
                errors.append(f"Step {step.step_id} missing acceptance criteria")
            if step.max_retries < 1:
                errors.append(f"Step {step.step_id} max_retries must be >=1")

        expected_hash = self.compute_hash(plan.mission_id, plan.steps)
        if expected_hash != plan.deterministic_hash:
            errors.append("Deterministic hash mismatch")

        return len(errors) == 0, errors

    @staticmethod
    def compute_hash(mission_id: str, steps: List[PlanStep]) -> str:
        normalized: List[Dict[str, object]] = []
        for step in steps:
            data = asdict(step)
            data["acceptance_criteria"] = sorted(step.acceptance_criteria)
            normalized.append(data)
        serialized = str({"mission_id": mission_id, "steps": normalized}).encode("utf-8")
        return sha256(serialized).hexdigest()
