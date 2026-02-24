"""
Probability Aggregation Engine.

From K most similar historical patterns:
    - Compute bullish/bearish/neutral probabilities
    - Compute expected return, expected R, average drawdown
    - Compute regime match rate
    - Gate signal output with configurable thresholds

Signal output ONLY if ALL conditions pass:
    - probability > threshold
    - expected_R > threshold
    - average_drawdown < threshold

No LLM. Fully deterministic. Statistically validated.
"""
import logging
from typing import Dict, Any, List, Optional


class ProbabilityEngine:
    """
    Aggregates forward outcomes from K similar patterns into
    probabilistic signal decisions.
    """

    def __init__(
        self,
        min_probability: float = 0.55,
        min_expected_r: float = 0.5, # TEMPORARY: was 1.0
        max_avg_drawdown: float = 0.05,
        neutral_band: float = 0.005,  # ±0.5% return = neutral
    ) -> None:
        self.logger = logging.getLogger("ProbabilityEngine")
        self.min_probability = min_probability
        self.min_expected_r = min_expected_r
        self.max_avg_drawdown = max_avg_drawdown
        self.neutral_band = neutral_band

    def aggregate(
        self,
        similar_outcomes: List[Dict[str, Any]],
        current_regime: str = "",
    ) -> Dict[str, Any]:
        """
        Compute probability distribution from K similar pattern outcomes.

        Args:
            similar_outcomes: List of outcome dicts from pattern_store.
                Each must have: future_return, max_drawdown, max_runup,
                r_multiple, regime_label
            current_regime: Current market regime for match rate calculation

        Returns:
            Full probability assessment with signal decision
        """
        k = len(similar_outcomes)
        if k == 0:
            return self._empty_result("NO_SIMILAR_PATTERNS")

        # ── Classify each outcome (Weighted) ───────────────────
        bullish_weight = 0.0
        bearish_weight = 0.0
        neutral_weight = 0.0
        total_weight = 0.0
        regime_matches = 0

        returns = []
        drawdowns = []
        runups = []
        r_multiples = []

        for outcome in similar_outcomes:
            ret = outcome.get("future_return", 0.0)
            dd = outcome.get("max_drawdown", 0.0)
            ru = outcome.get("max_runup", 0.0)
            rm = outcome.get("r_multiple", 0.0)
            regime = outcome.get("regime_label", "")
            
            # Phase 2 Weighting
            similarity = outcome.get("similarity_score", 1.0)
            age_days = outcome.get("pattern_age_days", 0)
            recency_weight = max(0.5, 1.0 - (age_days / 1825)) # Decay over 5 years
            base_weight = similarity * recency_weight

            returns.append(ret)
            drawdowns.append(dd)
            runups.append(ru)
            r_multiples.append(rm)

            if current_regime and regime == current_regime:
                regime_matches += 1
                base_weight *= 1.5  # regime_match_weight

            total_weight += base_weight

            if ret > self.neutral_band:
                bullish_weight += base_weight
            elif ret < -self.neutral_band:
                bearish_weight += base_weight
            else:
                neutral_weight += base_weight

        # ── Probabilities (Weighted) ───────────────────────────
        if total_weight > 0:
            bull_prob = bullish_weight / total_weight
            bear_prob = bearish_weight / total_weight
            neut_prob = neutral_weight / total_weight
        else:
            bull_prob = bear_prob = neut_prob = 0.0

        # ── Expected values (Simple avg for now) ───────────────
        expected_return = sum(returns) / k
        expected_r = sum(r_multiples) / k
        avg_drawdown = sum(drawdowns) / k
        avg_runup = sum(runups) / k

        # ── Regime match rate ──────────────────────────────────
        regime_match_rate = regime_matches / k if current_regime else 0.0

        # ── Distribution stats ─────────────────────────────────
        sorted_returns = sorted(returns)
        p10 = sorted_returns[max(0, int(k * 0.10))]
        p25 = sorted_returns[max(0, int(k * 0.25))]
        p50 = sorted_returns[max(0, int(k * 0.50))]
        p75 = sorted_returns[min(k - 1, int(k * 0.75))]
        p90 = sorted_returns[min(k - 1, int(k * 0.90))]

        # Standard deviation
        mean_ret = expected_return
        variance = sum((r - mean_ret) ** 2 for r in returns) / k
        std_dev = variance ** 0.5

        # ── Signal Decision ────────────────────────────────────
        signal = self._decide_signal(
            bull_prob, bear_prob, expected_r, avg_drawdown, regime_match_rate
        )

        return {
            "k_patterns": k,

            # Probabilities
            "bullish_probability": round(bull_prob, 4),
            "bearish_probability": round(bear_prob, 4),
            "neutral_probability": round(neut_prob, 4),

            # Expected values
            "expected_return": round(expected_return, 6),
            "expected_r": round(expected_r, 4),
            "avg_drawdown": round(avg_drawdown, 6),
            "avg_runup": round(avg_runup, 6),

            # Distribution
            "return_distribution": {
                "p10": round(p10, 6),
                "p25": round(p25, 6),
                "p50": round(p50, 6),
                "p75": round(p75, 6),
                "p90": round(p90, 6),
                "std_dev": round(std_dev, 6),
            },

            # Regime
            "regime_match_rate": round(regime_match_rate, 4),
            "current_regime": current_regime,

            # Signal decision
            "signal": signal["signal"],
            "signal_confidence": signal["confidence"],
            "signal_reason": signal["reason"],
            "thresholds_met": signal["thresholds_met"],
        }

    def _decide_signal(
        self,
        bull_prob: float,
        bear_prob: float,
        expected_r: float,
        avg_drawdown: float,
        regime_match_rate: float,
    ) -> Dict[str, Any]:
        """
        Gate signal through ALL thresholds.
        Only output if every condition passes.
        """
        thresholds = {
            "probability": False,
            "expected_r": False,
            "drawdown": False,
        }

        # Determine dominant direction
        if bull_prob > bear_prob:
            dominant_prob = bull_prob
            direction = "LONG"
        elif bear_prob > bull_prob:
            dominant_prob = bear_prob
            direction = "SHORT"
        else:
            return {
                "signal": "NONE",
                "confidence": 0.0,
                "reason": "No dominant direction",
                "thresholds_met": thresholds,
            }

        # ── Gate 1: Probability threshold ──────────────────────
        if dominant_prob >= self.min_probability:
            thresholds["probability"] = True

        # ── Gate 2: Expected R threshold ───────────────────────
        effective_r = expected_r if direction == "LONG" else -expected_r
        if effective_r >= self.min_expected_r:
            thresholds["expected_r"] = True
        elif direction == "SHORT" and (-expected_r) >= self.min_expected_r:
            thresholds["expected_r"] = True

        # ── Gate 3: Drawdown threshold ─────────────────────────
        if avg_drawdown <= self.max_avg_drawdown:
            thresholds["drawdown"] = True

        # ── All gates must pass ────────────────────────────────
        all_pass = all(thresholds.values())

        # Section 3 - PROBABILITY GATING LOG
        gate_log = {
            "bullish_probability": round(bull_prob, 4),
            "bearish_probability": round(bear_prob, 4),
            "expected_R": round(effective_r, 4),
            "average_drawdown": round(avg_drawdown, 4),
            "regime_match_rate": round(regime_match_rate, 4),
            "passed_probability_threshold": thresholds["probability"],
            "passed_R_threshold": thresholds["expected_r"],
            "passed_drawdown_threshold": thresholds["drawdown"]
        }
        self.logger.info(f"PROBABILITY_GATING_CHECK: {gate_log}")

        if all_pass:
            # Confidence = probability × (1 - drawdown_ratio)
            dd_penalty = min(avg_drawdown / self.max_avg_drawdown, 1.0)
            confidence = dominant_prob * (1.0 - dd_penalty * 0.3)
            return {
                "signal": direction,
                "confidence": round(confidence, 4),
                "reason": f"All thresholds met: P={dominant_prob:.2f}, R={effective_r:.2f}, DD={avg_drawdown:.4f}",
                "thresholds_met": thresholds,
            }
        else:
            # Identify which gates failed
            failed = [k for k, v in thresholds.items() if not v]
            self.logger.info(f"GATE_REJECTED_REASON: {', '.join(failed)}")
            return {
                "signal": "NONE",
                "confidence": 0.0,
                "reason": f"Gate(s) failed: {', '.join(failed)}",
                "thresholds_met": thresholds,
            }

    def _empty_result(self, reason: str) -> Dict[str, Any]:
        return {
            "k_patterns": 0,
            "bullish_probability": 0.0,
            "bearish_probability": 0.0,
            "neutral_probability": 0.0,
            "expected_return": 0.0,
            "expected_r": 0.0,
            "avg_drawdown": 0.0,
            "avg_runup": 0.0,
            "return_distribution": {},
            "regime_match_rate": 0.0,
            "current_regime": "",
            "signal": "NONE",
            "signal_confidence": 0.0,
            "signal_reason": reason,
            "thresholds_met": {"probability": False, "expected_r": False, "drawdown": False},
        }

    # ── Configuration & Dynamic Thresholds ─────────────────────

    def apply_dynamic_volatility_thresholds(self, current_volatility: float, base_volatility: float = 0.02) -> None:
        """
        Dynamically adjust thresholds based on current market volatility cluster.
        If volatility doubles, require higher R and accept slightly more drawdown variance.
        """
        vol_ratio = current_volatility / base_volatility if base_volatility > 0 else 1.0
        
        # Scale expected R linearly with volatility increase (cap at 2.0)
        new_min_r = min(self.min_expected_r * vol_ratio, 2.0)
        
        # Expand allowed drawdown bound in high vol
        new_max_dd = self.max_avg_drawdown * min(vol_ratio, 1.5)

        self.set_thresholds(min_expected_r=new_min_r, max_avg_drawdown=new_max_dd)
        self.logger.info(f"Dynamic Thresholds Applied (Vol Ratio {vol_ratio:.2f}): min_R={new_min_r:.2f}, max_DD={new_max_dd:.3f}")

    def set_thresholds(
        self,
        min_probability: Optional[float] = None,
        min_expected_r: Optional[float] = None,
        max_avg_drawdown: Optional[float] = None,
    ) -> None:
        """Update decision thresholds at runtime."""
        if min_probability is not None:
            self.min_probability = min_probability
        if min_expected_r is not None:
            self.min_expected_r = min_expected_r
        if max_avg_drawdown is not None:
            self.max_avg_drawdown = max_avg_drawdown
        self.logger.info(
            f"Thresholds updated: P>={self.min_probability}, "
            f"R>={self.min_expected_r}, DD<={self.max_avg_drawdown}"
        )

    def get_config(self) -> Dict[str, float]:
        return {
            "min_probability": self.min_probability,
            "min_expected_r": self.min_expected_r,
            "max_avg_drawdown": self.max_avg_drawdown,
            "neutral_band": self.neutral_band,
        }
