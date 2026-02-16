from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from agent.core.models import PipelineDecision, RiskLevel


@dataclass
class ConsentPolicy:
    profile_name: str
    require_for_medium: bool
    require_for_high: bool
    require_for_critical: bool


class ConsentManager:
    def __init__(self, policy: ConsentPolicy) -> None:
        self.policy = policy

    def evaluate(self, risk: RiskLevel, mission_metadata: Dict[str, object] | None = None) -> PipelineDecision:
        if risk == RiskLevel.CRITICAL:
            return PipelineDecision(
                allowed=False,
                reason="CRITICAL action denied pending explicit user override",
                requires_frozen_pipeline=True,
                required_approver="user",
            )

        if risk == RiskLevel.HIGH and self.policy.require_for_high:
            approved = bool((mission_metadata or {}).get("user_approved", False))
            return PipelineDecision(
                allowed=approved,
                reason="High-risk consent required" if not approved else "High-risk consent granted",
                requires_frozen_pipeline=False,
                required_approver="user" if not approved else None,
            )

        if risk == RiskLevel.MEDIUM and self.policy.require_for_medium:
            approved = bool((mission_metadata or {}).get("user_approved", False))
            return PipelineDecision(
                allowed=approved,
                reason="Medium-risk consent required" if not approved else "Medium-risk consent granted",
            )

        return PipelineDecision(allowed=True, reason="Consent policy passed")
