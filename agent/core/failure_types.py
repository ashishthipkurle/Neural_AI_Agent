"""
Failure Classification Engine — §10 of Production Autonomous Agent Spec.

Every error is classified into a typed category with:
  - Recovery strategy
  - Retry policy
  - Escalation threshold

NO generic failure handling allowed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("core.failures")


class FailureType(Enum):
    """Typed failure categories — §10."""
    PERCEPTION_ERROR = "perception_error"      # UI element not found, OCR failed
    TOOL_ERROR = "tool_error"                  # Tool crashed or returned invalid output
    NETWORK_ERROR = "network_error"            # Timeout, DNS, connection refused
    STATE_CORRUPTION = "state_corruption"      # Invalid state transition / missing field
    DEPENDENCY_ERROR = "dependency_error"      # Required resource unavailable
    AUTH_ERROR = "auth_error"                  # Permission denied, token expired
    LOGIC_ERROR = "logic_error"               # LLM hallucination, invalid plan step
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RetryPolicy:
    """How many times and how to retry for a failure category."""
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0
    strategy_switch_after: int = 2  # Switch strategy after N failures


@dataclass(frozen=True)
class RecoveryStrategy:
    """Defines how to recover from a specific failure type."""
    failure_type: FailureType
    retry_policy: RetryPolicy
    action: str  # Human-readable recovery action
    escalation_threshold: int = 3  # Escalate to user after N total failures
    requires_rollback: bool = False
    alternative_agents: tuple = ()  # Agents to try if current one fails


# ── Default recovery strategies per failure type ──
DEFAULT_RECOVERY: Dict[FailureType, RecoveryStrategy] = {
    FailureType.PERCEPTION_ERROR: RecoveryStrategy(
        failure_type=FailureType.PERCEPTION_ERROR,
        retry_policy=RetryPolicy(max_retries=3, base_delay_seconds=2.0),
        action="re_scan_ui",
        alternative_agents=("executor", "researcher"),
    ),
    FailureType.TOOL_ERROR: RecoveryStrategy(
        failure_type=FailureType.TOOL_ERROR,
        retry_policy=RetryPolicy(max_retries=2),
        action="retry_with_different_params",
        requires_rollback=True,
    ),
    FailureType.NETWORK_ERROR: RecoveryStrategy(
        failure_type=FailureType.NETWORK_ERROR,
        retry_policy=RetryPolicy(max_retries=5, base_delay_seconds=3.0, backoff_multiplier=3.0),
        action="wait_and_retry",
    ),
    FailureType.STATE_CORRUPTION: RecoveryStrategy(
        failure_type=FailureType.STATE_CORRUPTION,
        retry_policy=RetryPolicy(max_retries=1),
        action="rollback_to_last_valid",
        requires_rollback=True,
        escalation_threshold=1,
    ),
    FailureType.DEPENDENCY_ERROR: RecoveryStrategy(
        failure_type=FailureType.DEPENDENCY_ERROR,
        retry_policy=RetryPolicy(max_retries=2, base_delay_seconds=5.0),
        action="check_dependency_and_retry",
        alternative_agents=("executor",),
    ),
    FailureType.AUTH_ERROR: RecoveryStrategy(
        failure_type=FailureType.AUTH_ERROR,
        retry_policy=RetryPolicy(max_retries=1),
        action="escalate_to_user",
        escalation_threshold=1,
    ),
    FailureType.LOGIC_ERROR: RecoveryStrategy(
        failure_type=FailureType.LOGIC_ERROR,
        retry_policy=RetryPolicy(max_retries=2, strategy_switch_after=1),
        action="re_plan",
        alternative_agents=("planner", "critic"),
    ),
    FailureType.UNKNOWN: RecoveryStrategy(
        failure_type=FailureType.UNKNOWN,
        retry_policy=RetryPolicy(max_retries=1),
        action="escalate_to_user",
        escalation_threshold=1,
        requires_rollback=True,
    ),
}


def classify_failure(error: str | Exception) -> FailureType:
    """Classify an error string/exception into a typed FailureType.

    Uses keyword matching on the error message.  This is intentionally
    deterministic — no LLM involved.
    """
    msg = str(error).lower()

    if any(k in msg for k in ("timeout", "connectionerror", "dns", "connection refused", "ssl")):
        return FailureType.NETWORK_ERROR
    if any(k in msg for k in ("permission", "denied", "unauthorized", "403", "401", "auth")):
        return FailureType.AUTH_ERROR
    if any(k in msg for k in ("not found", "element", "button", "no such", "ocr", "screenshot")):
        return FailureType.PERCEPTION_ERROR
    if any(k in msg for k in ("schema", "validation", "invalid", "corrupt", "missing key")):
        return FailureType.STATE_CORRUPTION
    if any(k in msg for k in ("import", "module", "dependency", "not installed", "not available")):
        return FailureType.DEPENDENCY_ERROR
    if any(k in msg for k in ("tool", "execute", "skill", "handler")):
        return FailureType.TOOL_ERROR
    if any(k in msg for k in ("plan", "parse", "json", "hallucin", "logic")):
        return FailureType.LOGIC_ERROR

    return FailureType.UNKNOWN


def get_recovery(failure_type: FailureType) -> RecoveryStrategy:
    """Get the recovery strategy for a failure type."""
    return DEFAULT_RECOVERY.get(failure_type, DEFAULT_RECOVERY[FailureType.UNKNOWN])


def should_retry(failure_type: FailureType, current_retries: int) -> bool:
    """Check if we should retry based on policy."""
    strategy = get_recovery(failure_type)
    return current_retries < strategy.retry_policy.max_retries


def should_switch_strategy(failure_type: FailureType, current_retries: int) -> bool:
    """Check if we should switch to an alternative strategy."""
    strategy = get_recovery(failure_type)
    return current_retries >= strategy.retry_policy.strategy_switch_after


def should_escalate(failure_type: FailureType, total_failures: int) -> bool:
    """Check if we should escalate to the user."""
    strategy = get_recovery(failure_type)
    return total_failures >= strategy.escalation_threshold


def get_retry_delay(failure_type: FailureType, attempt: int) -> float:
    """Calculate retry delay with exponential backoff."""
    policy = get_recovery(failure_type).retry_policy
    return min(
        policy.base_delay_seconds * (policy.backoff_multiplier ** attempt),
        60.0,  # Hard cap at 60 seconds
    )
