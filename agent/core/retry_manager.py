from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class RetryDecision:
    should_retry: bool
    next_delay_seconds: float
    strategy: str


class RetryManager:
    def __init__(self, base_delay: float = 1.0, max_delay: float = 30.0, max_attempts: int = 5) -> None:
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_attempts = max_attempts

    def decide(self, attempt: int, error: str, context: Dict[str, object] | None = None) -> RetryDecision:
        if attempt >= self.max_attempts:
            return RetryDecision(False, 0.0, "abort-max-attempts")

        lowered = (error or "").lower()
        if "rate limit" in lowered or "timeout" in lowered or "network" in lowered:
            delay = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
            return RetryDecision(True, delay, "exponential-backoff")

        if "unsupported" in lowered or "tool" in lowered or "capability" in lowered:
            return RetryDecision(True, 0.2, "reroute-alternate-worker")

        delay = min(self.max_delay, self.base_delay * attempt)
        return RetryDecision(True, delay, "linear-backoff")
