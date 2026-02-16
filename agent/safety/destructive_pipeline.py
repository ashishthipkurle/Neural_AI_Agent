from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FrozenPipelineDecision:
    allowed: bool
    reason: str


class DestructiveActionPipeline:
    def evaluate(self, action_text: str, explicit_override: bool = False) -> FrozenPipelineDecision:
        lowered = action_text.lower()
        destructive = any(token in lowered for token in ["delete", "destroy", "drop", "wipe", "format"])
        if not destructive:
            return FrozenPipelineDecision(True, "Non-destructive action")
        if explicit_override:
            return FrozenPipelineDecision(True, "Destructive action explicitly approved")
        return FrozenPipelineDecision(False, "Destructive action blocked by frozen pipeline")
