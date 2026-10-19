"""
LLM Budget Tracker — Track and Cap LLM API Spending.

Prevents runaway LLM costs by enforcing daily and per-analysis caps.
Persists spending data to SQLite for audit trail.

No LLM. Fully deterministic.
"""
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone


class LLMBudget:
    """Track and cap LLM API spending."""

    MAX_DAILY_USD = 5.00          # Hard daily cap
    MAX_PER_ANALYSIS_USD = 0.50   # Max per symbol analysis

    def __init__(self, database=None, max_daily: float = None, max_per_analysis: float = None) -> None:
        self.logger = logging.getLogger("LLMBudget")
        self.database = database

        if max_daily is not None:
            self.MAX_DAILY_USD = max_daily
        if max_per_analysis is not None:
            self.MAX_PER_ANALYSIS_USD = max_per_analysis

        self.logger.info(
            f"LLMBudget initialized: daily=${self.MAX_DAILY_USD:.2f}, "
            f"per_analysis=${self.MAX_PER_ANALYSIS_USD:.2f}"
        )

    def can_spend(self, estimated_cost: float) -> bool:
        """
        Check if we're within budget for a new analysis.
        Returns True if the estimated cost is within both daily and per-analysis caps.
        """
        # Check per-analysis cap
        if estimated_cost > self.MAX_PER_ANALYSIS_USD:
            self.logger.warning(
                f"Estimated cost ${estimated_cost:.4f} exceeds per-analysis cap "
                f"${self.MAX_PER_ANALYSIS_USD:.2f}"
            )
            return False

        # Check daily cap
        daily_spent = self._get_daily_spend()
        if daily_spent + estimated_cost > self.MAX_DAILY_USD:
            self.logger.warning(
                f"Daily spend ${daily_spent:.4f} + ${estimated_cost:.4f} would exceed "
                f"daily cap ${self.MAX_DAILY_USD:.2f}"
            )
            return False

        return True

    def record_spend(self, actual_cost: float, symbol: str = "",
                     provider: str = "ollama", operation: str = "analysis") -> None:
        """Record actual LLM cost after analysis completes."""
        if self.database:
            self.database.record_llm_spend(
                cost_usd=actual_cost,
                symbol=symbol,
                provider=provider,
                operation=operation,
            )

        daily_total = self._get_daily_spend()
        remaining = max(0, self.MAX_DAILY_USD - daily_total)

        self.logger.info(
            f"LLM spend: ${actual_cost:.4f} for {symbol or 'general'} "
            f"(daily total: ${daily_total:.4f}, remaining: ${remaining:.4f})"
        )

        if remaining < 1.0:
            self.logger.warning(f"⚠️ LLM budget running low: ${remaining:.2f} remaining today")

    def get_budget_status(self) -> Dict[str, Any]:
        """Get current budget status for dashboard display."""
        daily_spent = self._get_daily_spend()
        return {
            "daily_limit": self.MAX_DAILY_USD,
            "daily_spent": round(daily_spent, 4),
            "daily_remaining": round(max(0, self.MAX_DAILY_USD - daily_spent), 4),
            "per_analysis_limit": self.MAX_PER_ANALYSIS_USD,
            "budget_healthy": daily_spent < self.MAX_DAILY_USD * 0.8,
        }

    def _get_daily_spend(self) -> float:
        """Get today's total LLM spend."""
        if self.database:
            return self.database.get_daily_llm_spend()
        return 0.0
