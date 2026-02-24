"""
Advanced Risk Compression System.

Risk modes:
    NORMAL   → 1R per trade
    DEFENSIVE → 0.5R per trade
    CRITICAL  → 0.25R per trade
    HALTED    → 0R (all signals blocked)

Triggers:
    - Drawdown thresholds
    - Confidence deterioration
    - Volatility spike
    - Correlation overload
    - Regime instability

System MUST block signals in HALTED mode.

No LLM. Fully deterministic.
"""
import time
import logging
from typing import Dict, Any, List, Optional


class RiskEngine:
    """
    Advanced risk compression with multi-trigger state machine.
    """

    # Risk modes and their per-trade R multipliers
    MODES = {
        "NORMAL": 1.0,
        "DEFENSIVE": 0.5,
        "CRITICAL": 0.25,
        "HALTED": 0.0,
    }

    def __init__(
        self,
        drawdown_defensive: float = 0.05,    # 5% DD → DEFENSIVE
        drawdown_critical: float = 0.10,      # 10% DD → CRITICAL
        drawdown_halted: float = 0.20,        # 20% DD → HALTED
        confidence_defensive: float = 0.45,   # Avg confidence below → DEFENSIVE
        confidence_critical: float = 0.35,    # Avg confidence below → CRITICAL
        max_portfolio_risk: float = 0.05,     # 5% total portfolio risk
        max_position_risk: float = 0.02,      # 2% per position risk
    ) -> None:
        self.logger = logging.getLogger("RiskEngine")

        # Thresholds
        self.dd_defensive = drawdown_defensive
        self.dd_critical = drawdown_critical
        self.dd_halted = drawdown_halted
        self.conf_defensive = confidence_defensive
        self.conf_critical = confidence_critical
        self.max_portfolio_risk = max_portfolio_risk
        self.max_position_risk = max_position_risk

        # State
        self.current_mode = "NORMAL"
        self._mode_history: List[Dict[str, Any]] = []
        self._last_assessment: Optional[Dict[str, Any]] = None
        self._halted_reason: Optional[str] = None

    def assess_risk(
        self,
        current_drawdown: float,
        avg_confidence: float = 0.5,
        atr_percentile: float = 50.0,
        regime: str = "QUIET",
        regime_stable: bool = True,
        total_exposure: float = 0.0,
        correlation_overload: bool = False,
    ) -> Dict[str, Any]:
        """
        Run full risk assessment and determine risk mode.

        Args:
            current_drawdown: Current portfolio drawdown (0.0–1.0)
            avg_confidence: Average confidence of recent signals
            atr_percentile: Current ATR percentile (0–100)
            regime: Current market regime
            regime_stable: Whether regime has been stable
            total_exposure: Total portfolio exposure
            correlation_overload: Whether correlation limits are breached

        Returns:
            dict with mode, r_multiplier, triggers, position limits
        """
        triggers = []
        proposed_mode = "NORMAL"

        # ── Drawdown triggers ──────────────────────────────────
        if current_drawdown >= self.dd_halted:
            proposed_mode = "HALTED"
            triggers.append(f"DRAWDOWN: {current_drawdown:.2%} >= HALT threshold {self.dd_halted:.2%}")
        elif current_drawdown >= self.dd_critical:
            proposed_mode = "CRITICAL"
            triggers.append(f"DRAWDOWN: {current_drawdown:.2%} >= CRITICAL threshold {self.dd_critical:.2%}")
        elif current_drawdown >= self.dd_defensive:
            proposed_mode = "DEFENSIVE"
            triggers.append(f"DRAWDOWN: {current_drawdown:.2%} >= DEFENSIVE threshold {self.dd_defensive:.2%}")

        # ── Confidence deterioration ───────────────────────────
        if avg_confidence < self.conf_critical and proposed_mode != "HALTED":
            proposed_mode = max(proposed_mode, "CRITICAL", key=self._mode_severity)
            triggers.append(f"CONFIDENCE: {avg_confidence:.3f} < CRITICAL threshold {self.conf_critical}")
        elif avg_confidence < self.conf_defensive and proposed_mode == "NORMAL":
            proposed_mode = "DEFENSIVE"
            triggers.append(f"CONFIDENCE: {avg_confidence:.3f} < DEFENSIVE threshold {self.conf_defensive}")

        # ── Volatility spike ───────────────────────────────────
        if atr_percentile > 95.0 and proposed_mode != "HALTED":
            proposed_mode = max(proposed_mode, "CRITICAL", key=self._mode_severity)
            triggers.append(f"VOLATILITY: ATR percentile {atr_percentile:.1f} > 95")
        elif atr_percentile > 85.0 and proposed_mode == "NORMAL":
            proposed_mode = "DEFENSIVE"
            triggers.append(f"VOLATILITY: ATR percentile {atr_percentile:.1f} > 85")

        # ── Correlation overload ───────────────────────────────
        if correlation_overload:
            proposed_mode = max(proposed_mode, "DEFENSIVE", key=self._mode_severity)
            triggers.append("CORRELATION: Cluster exposure limits breached")

        # ── Regime instability ─────────────────────────────────
        if not regime_stable:
            proposed_mode = max(proposed_mode, "DEFENSIVE", key=self._mode_severity)
            triggers.append("REGIME: Unstable regime transitions detected")

        # ── Update mode ────────────────────────────────────────
        old_mode = self.current_mode
        self.current_mode = proposed_mode

        if proposed_mode == "HALTED":
            self._halted_reason = "; ".join(triggers)
        else:
            self._halted_reason = None

        if old_mode != proposed_mode:
            self._mode_history.append({
                "from": old_mode,
                "to": proposed_mode,
                "triggers": triggers,
                "timestamp": time.time(),
            })
            self.logger.warning(f"Risk mode: {old_mode} → {proposed_mode} | {triggers}")

        r_multiplier = self.MODES.get(self.current_mode, 0.0)

        result = {
            "mode": self.current_mode,
            "r_multiplier": r_multiplier,
            "signals_allowed": self.current_mode != "HALTED",
            "triggers": triggers,
            "max_position_risk": self.max_position_risk * r_multiplier,
            "max_portfolio_risk": self.max_portfolio_risk * r_multiplier,
            "halted_reason": self._halted_reason,
        }

        self._last_assessment = result
        return result

    def check_position_risk(
        self, dollar_risk: float, portfolio_value: float
    ) -> Dict[str, Any]:
        """Check if a single position's risk is within current mode limits."""
        if portfolio_value <= 0:
            return {"allowed": False, "reason": "Invalid portfolio value"}

        r_mult = self.MODES.get(self.current_mode, 0.0)
        effective_limit = self.max_position_risk * r_mult
        risk_pct = dollar_risk / portfolio_value

        allowed = risk_pct <= effective_limit and r_mult > 0
        return {
            "allowed": allowed,
            "risk_pct": round(risk_pct, 6),
            "effective_limit": round(effective_limit, 6),
            "mode": self.current_mode,
            "reason": None if allowed else f"Risk {risk_pct:.4%} exceeds {effective_limit:.4%} in {self.current_mode} mode",
        }

    def _mode_severity(self, mode: str) -> int:
        severity = {"NORMAL": 0, "DEFENSIVE": 1, "CRITICAL": 2, "HALTED": 3}
        return severity.get(mode, 0)

    def force_halt(self, reason: str) -> None:
        """Emergency halt — kill switch."""
        self.current_mode = "HALTED"
        self._halted_reason = reason
        self._mode_history.append({
            "from": self.current_mode,
            "to": "HALTED",
            "triggers": [f"FORCE_HALT: {reason}"],
            "timestamp": time.time(),
        })
        self.logger.critical(f"FORCE HALT: {reason}")

    def reset_to_normal(self) -> None:
        """Manual reset back to NORMAL (requires human authorization)."""
        old = self.current_mode
        self.current_mode = "NORMAL"
        self._halted_reason = None
        self._mode_history.append({
            "from": old,
            "to": "NORMAL",
            "triggers": ["MANUAL_RESET"],
            "timestamp": time.time(),
        })
        self.logger.info(f"Risk mode manually reset: {old} → NORMAL")

    def get_state(self) -> Dict[str, Any]:
        return {
            "mode": self.current_mode,
            "r_multiplier": self.MODES.get(self.current_mode, 0.0),
            "signals_allowed": self.current_mode != "HALTED",
            "halted_reason": self._halted_reason,
            "mode_transitions": len(self._mode_history),
        }
