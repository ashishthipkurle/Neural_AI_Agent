from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from agent.core.audit_logger import AuditLogger
from agent.core.consent_manager import ConsentManager
from agent.core.intent_parser import IntentParser
from agent.core.mission_engine import MissionEngine
from agent.core.models import (
    ExecutionPlan,
    MissionStatus,
    PipelineStage,
    PlanStep,
    RiskLevel,
    WorkerExecutionResult,
    WorkerType,
)
from agent.core.plan_validator import PlanValidator
from agent.core.reflection_engine import ReflectionEngine
from agent.core.retry_manager import RetryManager
from agent.core.risk_engine import RiskEngine
from agent.core.supervisor import Supervisor
from agent.core.worker_base import WorkerBase


class ExecutionPipeline:
    def __init__(
        self,
        mission_engine: MissionEngine,
        supervisor: Supervisor,
        intent_parser: IntentParser,
        risk_engine: RiskEngine,
        consent_manager: ConsentManager,
        retry_manager: RetryManager,
        reflection_engine: ReflectionEngine,
        audit_logger: AuditLogger,
        workers: Dict[WorkerType, WorkerBase],
        plan_validator: PlanValidator,
        memory_context_provider: Optional[Any] = None,
    ) -> None:
        self.mission_engine = mission_engine
        self.supervisor = supervisor
        self.intent_parser = intent_parser
        self.risk_engine = risk_engine
        self.consent_manager = consent_manager
        self.retry_manager = retry_manager
        self.reflection_engine = reflection_engine
        self.audit_logger = audit_logger
        self.workers = workers
        self.plan_validator = plan_validator
        self.memory_context_provider = memory_context_provider

    async def run(self, goal: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        metadata = metadata or {}

        intent = self._stage_intent_parsing(goal, metadata)
        risk = self._stage_risk_classification(intent.normalized_goal, metadata)
        mission = self.mission_engine.create_mission(intent.normalized_goal, metadata.get("policy_profile", "strict"), risk)

        consent = self._stage_consent_gate(mission.mission_id, risk, metadata)
        if not consent["allowed"]:
            self.mission_engine.update_status(mission, MissionStatus.BLOCKED, {"reason": consent["reason"]})
            self._stage_audit_logging(mission.mission_id, PipelineStage.CONSENT_GATE, "blocked", consent)
            return self._stage_final_synthesis(mission.mission_id, MissionStatus.BLOCKED.value, [], consent["reason"])

        rag_context = self._stage_memory_rag_injection(mission.mission_id, intent.normalized_goal)
        metadata = {**metadata, "rag_context": rag_context}

        steps = self._generate_plan_steps(intent.required_capabilities, metadata)
        if not self._stage_supervisor_review(mission.mission_id, risk, steps):
            self.mission_engine.update_status(mission, MissionStatus.BLOCKED, {"reason": "Supervisor denied plan"})
            return self._stage_final_synthesis(mission.mission_id, MissionStatus.BLOCKED.value, [], "Supervisor denied plan")

        plan = self._stage_plan_generation(mission.mission_id, steps)
        plan_valid, plan_errors = self._stage_plan_validation(plan)
        if not plan_valid:
            self.mission_engine.update_status(mission, MissionStatus.FAILED, {"errors": plan_errors})
            self._stage_audit_logging(mission.mission_id, PipelineStage.PLAN_VALIDATION, "invalid", {"errors": plan_errors})
            return self._stage_final_synthesis(mission.mission_id, MissionStatus.FAILED.value, [], "Plan validation failed")

        self.mission_engine.update_status(mission, MissionStatus.RUNNING, {"plan_id": plan.plan_id})

        step_results: List[WorkerExecutionResult] = []
        consecutive_failures = 0
        failed_steps: List[PlanStep] = []
        for step in plan.steps:
            worker = self._stage_worker_assignment(step)
            result = await self._stage_execution(mission.mission_id, worker, step, metadata)
            verified = self._stage_verification(step, result)
            result.verification_passed = verified
            step_results.append(result)

            if result.success and verified:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                failed_steps.append(step)

            decision = self.supervisor.analyze_progress(
                mission.mission_id,
                completed_steps=sum(1 for s in step_results if s.success and s.verification_passed),
                total_steps=len(plan.steps),
                consecutive_failures=consecutive_failures,
            )
            self._stage_audit_logging(mission.mission_id, PipelineStage.SUPERVISOR_REVIEW, "progress", {"decision": decision})
            if decision == "escalate_strategy":
                self.mission_engine.update_status(mission, MissionStatus.BLOCKED, {"reason": "stagnation_detected"})
                break

        reflection = self._stage_reflection(mission.mission_id, step_results)

        if failed_steps and mission.status == MissionStatus.RUNNING:
            for failed_step in failed_steps:
                latest_failure = next((s for s in reversed(step_results) if s.step_id == failed_step.step_id), None)
                if latest_failure is None:
                    continue
                reroute_result = await self._stage_retry_reroute(mission.mission_id, failed_step, latest_failure, metadata)
                if reroute_result is not None:
                    step_results.append(reroute_result)

        all_ok = all(s.success and s.verification_passed for s in step_results) if step_results else False
        final_status = MissionStatus.COMPLETED if all_ok else mission.status
        if mission.status == MissionStatus.RUNNING and not all_ok:
            final_status = MissionStatus.FAILED

        self.mission_engine.update_status(
            mission,
            final_status,
            {
                "results": [r.__dict__ for r in step_results],
                "reflection": reflection.__dict__,
            },
        )
        self._stage_audit_logging(mission.mission_id, PipelineStage.REFLECTION, "reflection", reflection.__dict__)
        return self._stage_final_synthesis(
            mission.mission_id,
            final_status.value,
            [r.__dict__ for r in step_results],
            "Mission complete" if final_status == MissionStatus.COMPLETED else "Mission ended with failures",
        )

    def _stage_intent_parsing(self, goal: str, metadata: Dict[str, Any]):
        result = self.intent_parser.parse(goal, metadata)
        self._stage_audit_logging(None, PipelineStage.INTENT_PARSING, "parsed", result.__dict__)
        return result

    def _stage_risk_classification(self, goal: str, metadata: Dict[str, Any]) -> RiskLevel:
        risk = self.risk_engine.classify(goal, metadata)
        self._stage_audit_logging(None, PipelineStage.RISK_CLASSIFICATION, "classified", {"risk": risk.value})
        return risk

    def _stage_consent_gate(self, mission_id: str, risk: RiskLevel, metadata: Dict[str, Any]) -> Dict[str, Any]:
        decision = self.consent_manager.evaluate(risk, metadata)
        payload = {
            "allowed": decision.allowed,
            "reason": decision.reason,
            "requires_frozen_pipeline": decision.requires_frozen_pipeline,
            "required_approver": decision.required_approver,
        }
        self._stage_audit_logging(mission_id, PipelineStage.CONSENT_GATE, "consent", payload)
        return payload

    def _stage_supervisor_review(self, mission_id: str, risk: RiskLevel, steps: List[PlanStep]) -> bool:
        approved = self.supervisor.review(mission_id, risk, steps)
        self._stage_audit_logging(mission_id, PipelineStage.SUPERVISOR_REVIEW, "review", {"approved": approved})
        return approved

    def _stage_plan_generation(self, mission_id: str, steps: List[PlanStep]) -> ExecutionPlan:
        deterministic_hash = self.plan_validator.compute_hash(mission_id, steps)
        plan = ExecutionPlan(
            mission_id=mission_id,
            plan_id=f"plan-{uuid.uuid4().hex[:10]}",
            generated_at=datetime.now(UTC).isoformat(),
            deterministic_hash=deterministic_hash,
            steps=steps,
        )
        self._stage_audit_logging(mission_id, PipelineStage.PLAN_GENERATION, "generated", {"plan_id": plan.plan_id})
        return plan

    def _stage_memory_rag_injection(self, mission_id: str, goal: str) -> List[Dict[str, Any]]:
        if self.memory_context_provider is None:
            self._stage_audit_logging(mission_id, PipelineStage.PLAN_GENERATION, "rag_context", {"count": 0})
            return []

        try:
            memories = self.memory_context_provider(goal)
            if not isinstance(memories, list):
                memories = []
            self._stage_audit_logging(mission_id, PipelineStage.PLAN_GENERATION, "rag_context", {"count": len(memories)})
            return memories
        except Exception as exc:
            self._stage_audit_logging(mission_id, PipelineStage.PLAN_GENERATION, "rag_context_error", {"error": str(exc)})
            return []

    def _stage_plan_validation(self, plan: ExecutionPlan) -> tuple[bool, list[str]]:
        valid, errors = self.supervisor.approve_plan(plan)
        self._stage_audit_logging(plan.mission_id, PipelineStage.PLAN_VALIDATION, "validated", {"valid": valid, "errors": errors})
        return valid, errors

    def _stage_worker_assignment(self, step: PlanStep) -> WorkerBase:
        worker_type = self.supervisor.assign_worker(step)
        worker = self.workers[worker_type]
        return worker

    async def _stage_execution(
        self,
        mission_id: str,
        worker: WorkerBase,
        step: PlanStep,
        metadata: Dict[str, Any],
    ) -> WorkerExecutionResult:
        result = await worker.execute(mission_id, step, metadata)
        self._stage_audit_logging(mission_id, PipelineStage.EXECUTION, "executed", result.__dict__)
        return result

    def _stage_verification(self, step: PlanStep, result: WorkerExecutionResult) -> bool:
        if not result.success:
            self._stage_audit_logging(result.mission_id, PipelineStage.VERIFICATION, "failed", {"step_id": step.step_id})
            return False
        checks = step.acceptance_criteria
        output_as_text = str(result.output).lower()
        passed = all(check.lower() in output_as_text or check == "always_true" for check in checks)
        self._stage_audit_logging(result.mission_id, PipelineStage.VERIFICATION, "verified", {"step_id": step.step_id, "passed": passed})
        return passed

    async def _stage_retry_reroute(
        self,
        mission_id: str,
        step: PlanStep,
        previous: WorkerExecutionResult,
        metadata: Dict[str, Any],
    ) -> Optional[WorkerExecutionResult]:
        decision = self.retry_manager.decide(previous.attempt, previous.error or "verification_failed", metadata)
        self._stage_audit_logging(mission_id, PipelineStage.RETRY_REROUTE, "decision", decision.__dict__)
        if not decision.should_retry:
            return None

        await asyncio.sleep(decision.next_delay_seconds)

        reroute_worker_type = step.worker_type
        if decision.strategy == "reroute-alternate-worker" and step.allow_reroute:
            reroute_worker_type = WorkerType.SKILL

        reroute_step = PlanStep(
            step_id=step.step_id,
            title=step.title,
            worker_type=reroute_worker_type,
            action=step.action,
            params=step.params,
            acceptance_criteria=step.acceptance_criteria,
            max_retries=step.max_retries,
            allow_reroute=step.allow_reroute,
        )

        reroute_worker = self.workers[reroute_worker_type]
        retry_result = await reroute_worker.execute(mission_id, reroute_step, metadata)
        retry_result.attempt = previous.attempt + 1
        retry_result.verification_passed = self._stage_verification(reroute_step, retry_result)
        self._stage_audit_logging(mission_id, PipelineStage.RETRY_REROUTE, "retry_result", retry_result.__dict__)
        return retry_result

    def _stage_reflection(self, mission_id: str, step_results: List[WorkerExecutionResult]):
        return self.reflection_engine.reflect(mission_id, step_results)

    def _stage_audit_logging(self, mission_id: Optional[str], stage: PipelineStage, event_type: str, payload: Dict[str, Any]) -> None:
        self.audit_logger.log(mission_id, stage.value, event_type, "pipeline", payload)

    def _stage_final_synthesis(self, mission_id: str, status: str, results: List[Dict[str, Any]], summary: str) -> Dict[str, Any]:
        payload = {
            "mission_id": mission_id,
            "status": status,
            "summary": summary,
            "results": results,
        }
        self._stage_audit_logging(mission_id, PipelineStage.FINAL_SYNTHESIS, "final", payload)
        return payload

    def _generate_plan_steps(self, capabilities: List[str], metadata: Dict[str, Any]) -> List[PlanStep]:
        mapping = {
            "coding": WorkerType.CODING,
            "research": WorkerType.RESEARCH,
            "browser": WorkerType.BROWSER,
            "desktop": WorkerType.DESKTOP,
            "integration": WorkerType.INTEGRATION,
            "skill": WorkerType.SKILL,
        }
        steps: List[PlanStep] = []
        for idx, capability in enumerate(capabilities, start=1):
            worker_type = mapping.get(capability, WorkerType.SKILL)
            steps.append(
                PlanStep(
                    step_id=f"step-{idx}",
                    title=f"Execute {capability}",
                    worker_type=worker_type,
                    action=f"run_{capability}",
                    params={"capability": capability, "rag_context": metadata.get("rag_context", [])},
                    acceptance_criteria=["status", "always_true"],
                )
            )
        return steps
