from __future__ import annotations

from typing import List

from agent.core.models import ReflectionResult, WorkerExecutionResult


class ReflectionEngine:
    def reflect(self, mission_id: str, step_results: List[WorkerExecutionResult]) -> ReflectionResult:
        if not step_results:
            return ReflectionResult(mission_id, 0.0, ["No steps executed"], ["Replan mission"])

        success_count = sum(1 for step in step_results if step.success and step.verification_passed)
        score = success_count / len(step_results)

        findings: List[str] = []
        corrective_actions: List[str] = []
        for step in step_results:
            if not step.success:
                findings.append(f"Step {step.step_id} failed: {step.error or 'unknown'}")
                corrective_actions.append(f"Retry or reroute step {step.step_id}")
            elif not step.verification_passed:
                findings.append(f"Step {step.step_id} failed verification")
                corrective_actions.append(f"Strengthen verification criteria for {step.step_id}")

        if not findings:
            findings.append("Execution matched acceptance criteria")
            corrective_actions.append("No corrective action required")

        return ReflectionResult(
            mission_id=mission_id,
            score=score,
            findings=findings,
            corrective_actions=corrective_actions,
        )
