from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PipelineStage(str, Enum):
    INTENT_PARSING = "intent_parsing"
    RISK_CLASSIFICATION = "risk_classification"
    CONSENT_GATE = "consent_gate"
    SUPERVISOR_REVIEW = "supervisor_review"
    PLAN_GENERATION = "plan_generation"
    PLAN_VALIDATION = "plan_validation"
    WORKER_ASSIGNMENT = "worker_assignment"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    REFLECTION = "reflection"
    RETRY_REROUTE = "retry_reroute"
    AUDIT_LOGGING = "audit_logging"
    FINAL_SYNTHESIS = "final_synthesis"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MissionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


class WorkerType(str, Enum):
    SKILL = "skill_worker"
    RESEARCH = "research_worker"
    CODING = "coding_worker"
    BROWSER = "browser_worker"
    DESKTOP = "desktop_worker"
    INTEGRATION = "integration_worker"


@dataclass
class IntentResult:
    normalized_goal: str
    required_capabilities: List[str]
    inferred_constraints: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlanStep:
    step_id: str
    title: str
    worker_type: WorkerType
    action: str
    params: Dict[str, Any]
    acceptance_criteria: List[str]
    max_retries: int = 3
    allow_reroute: bool = True


@dataclass
class ExecutionPlan:
    mission_id: str
    plan_id: str
    generated_at: str
    deterministic_hash: str
    steps: List[PlanStep]


@dataclass
class WorkerExecutionResult:
    mission_id: str
    step_id: str
    worker_type: WorkerType
    success: bool
    output: Dict[str, Any]
    verification_passed: bool
    error: Optional[str] = None
    attempt: int = 1
    executed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class ReflectionResult:
    mission_id: str
    score: float
    findings: List[str]
    corrective_actions: List[str]


@dataclass
class MissionRecord:
    mission_id: str
    goal: str
    status: MissionStatus
    created_at: str
    updated_at: str
    policy_profile: str
    risk_level: RiskLevel
    checkpoint_version: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineDecision:
    allowed: bool
    reason: str
    requires_frozen_pipeline: bool = False
    required_approver: Optional[str] = None
