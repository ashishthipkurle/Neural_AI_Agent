from __future__ import annotations

import re
from typing import Dict, List

from agent.core.models import IntentResult


class IntentParser:
    def parse(self, user_input: str, context: Dict[str, object] | None = None) -> IntentResult:
        normalized = " ".join(user_input.strip().split())
        lowered = normalized.lower()

        capabilities: List[str] = []
        if re.search(r"\b(code|fix|refactor|test|python|bug)\b", lowered):
            capabilities.append("coding")
        if re.search(r"\b(research|search|find|investigate|analyze)\b", lowered):
            capabilities.append("research")
        if re.search(r"\b(browser|web|website|navigate|click)\b", lowered):
            capabilities.append("browser")
        if re.search(r"\b(desktop|window|app|open|os)\b", lowered):
            capabilities.append("desktop")
        if re.search(r"\b(api|integration|telegram|twilio|service)\b", lowered):
            capabilities.append("integration")

        if not capabilities:
            capabilities.append("skill")

        constraints: List[str] = []
        if "never stop" in lowered or "until goal" in lowered:
            constraints.append("persistent_execution")
        if "deterministic" in lowered:
            constraints.append("deterministic_plan")

        return IntentResult(
            normalized_goal=normalized,
            required_capabilities=sorted(set(capabilities)),
            inferred_constraints=constraints,
            metadata={"input_length": len(normalized), "context_present": bool(context)},
        )
