from __future__ import annotations

from typing import Dict

from agent.core.models import RiskLevel


class RiskEngine:
    DESTRUCTIVE_MARKERS = {
        "delete",
        "destroy",
        "drop",
        "wipe",
        "format",
        "shutdown",
        "terminate",
        "kill process",
    }

    def classify(self, goal: str, metadata: Dict[str, object] | None = None) -> RiskLevel:
        text = goal.lower()
        if any(marker in text for marker in self.DESTRUCTIVE_MARKERS):
            return RiskLevel.CRITICAL
        if any(marker in text for marker in {"install", "execute", "shell", "run command"}):
            return RiskLevel.HIGH
        if any(marker in text for marker in {"edit", "modify", "change"}):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
