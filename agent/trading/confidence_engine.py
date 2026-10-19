"""
Confidence Scoring — Multi-Source Aggregator v2.

v1 (ConfidenceEngineV1): 5 technical factors — kept for backward compatibility.
v2 (ConfidenceAggregatorV2): 4 independent source signals:
    0.25 × technical_score      (from strategy signal confidence)
    0.30 × ta_conviction        (from TradingAgents research)
    0.20 × ml_model             (ML predictor agreement)
    0.25 × historical_edge      (from Learning Engine win rate)

Confidence < 0.45 → reduce position size.
Confidence < 0.30 → block signal entirely.

No LLM. Fully deterministic.
"""
import logging
from typing import List, Dict, Any, Optional
from agent.trading.indicators_engine import IndicatorsEngine


# ══════════════════════════════════════════════════════════════
# V1: Original 5-Factor Technical Confidence (backward compat)
# ══════════════════════════════════════════════════════════════

class ConfidenceEngineV1:
    """
    Original institutional-grade confidence scoring (5 technical factors).
    Kept for backward compatibility.
    """

    WEIGHTS = {
        "trend_strength": 0.30,
        "momentum_alignment": 0.20,
        "volatility_alignment": 0.15,
        "structure_alignment": 0.15,
        "volume_confirmation": 0.20,
    }

    REDUCE_THRESHOLD = 0.45
    BLOCK_THRESHOLD = 0.35

    def __init__(self) -> None:
        self.logger = logging.getLogger("ConfidenceEngineV1")

    def compute_confidence(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        structure_score: float = 0.5,
        regime: str = "QUIET",
    ) -> Dict[str, Any]:
        """Compute confidence from market data (v1 technical-only)."""
        if len(closes) < 50:
            return self._build_result(0.0, {}, regime)

        trend = self._clamp(IndicatorsEngine.calculate_trend_strength(closes))
        momentum = self._clamp(IndicatorsEngine.calculate_momentum_alignment(closes))

        atr_pct = IndicatorsEngine.calculate_atr_percentile(highs, lows, closes)
        if 30.0 <= atr_pct <= 70.0:
            vol_alignment = 1.0
        elif 20.0 <= atr_pct <= 80.0:
            vol_alignment = 0.7
        elif 10.0 <= atr_pct <= 90.0:
            vol_alignment = 0.4
        else:
            vol_alignment = 0.2

        structure = self._clamp(structure_score)

        vol_spike = IndicatorsEngine.calculate_volume_spike(volumes, 20)
        if vol_spike >= 2.0:
            volume_conf = 1.0
        elif vol_spike >= 1.5:
            volume_conf = 0.8
        elif vol_spike >= 1.0:
            volume_conf = 0.5
        else:
            volume_conf = 0.3

        factors = {
            "trend_strength": round(trend, 4),
            "momentum_alignment": round(momentum, 4),
            "volatility_alignment": round(vol_alignment, 4),
            "structure_alignment": round(structure, 4),
            "volume_confirmation": round(volume_conf, 4),
        }

        score = sum(factors[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        score = self._clamp(score)
        return self._build_result(score, factors, regime)

    def _build_result(self, score, factors, regime):
        regime_penalty = {
            "TRENDING_VOLATILE": -0.05,
            "LOW_VOL_RANGE": -0.10,
            "MEAN_REVERTING": 0.0,
            "EXPANSION_BREAKOUT": 0.05,
            "QUIET": -0.05,
        }
        adjusted = self._clamp(score + regime_penalty.get(regime, 0.0))

        if adjusted < self.BLOCK_THRESHOLD:
            action = "BLOCK"
        elif adjusted < self.REDUCE_THRESHOLD:
            action = "REDUCE"
        else:
            action = "ALLOW"

        return {
            "confidence_score": round(adjusted, 4),
            "raw_score": round(score, 4),
            "action": action,
            "factors": factors,
            "regime": regime,
        }

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))


# ══════════════════════════════════════════════════════════════
# V2: Multi-Source Confidence Aggregator
# ══════════════════════════════════════════════════════════════

class ConfidenceAggregatorV2:
    """
    Multi-source confidence scoring. Four independent signals vote
    on each trade, breaking the circular dependency of v1.

    Sources:
        1. Technical (from strategy signal)     — 0.25 weight
        2. TradingAgents conviction             — 0.30 weight
        3. ML Predictor agreement               — 0.20 weight
        4. Historical win rate                  — 0.25 weight
    """

    WEIGHTS = {
        "technical":     0.25,
        "ta_conviction": 0.30,
        "ml_model":      0.20,
        "historical":    0.25,
    }

    BLOCK_THRESHOLD = 0.30
    REDUCE_THRESHOLD = 0.45

    def __init__(self) -> None:
        self.logger = logging.getLogger("ConfidenceAggregatorV2")

    def aggregate(
        self,
        technical_confidence: float,
        ta_conviction: float = 0.5,
        ml_agrees: bool = True,
        historical_win_rate: float = 0.5,
        direction: str = "LONG",
    ) -> Dict[str, Any]:
        """
        Aggregate 4 independent confidence sources into a single score.

        Args:
            technical_confidence: 0-1 score from strategy signal
            ta_conviction: 0-1 from TradingAgents (0=strong sell, 1=strong buy)
            ml_agrees: True if ML predictor agrees with signal direction
            historical_win_rate: 0-1 from Learning Engine
            direction: LONG or SHORT (used to flip ta_conviction for shorts)

        Returns:
            dict with confidence, action, scores breakdown, weights
        """
        # For SHORT direction, invert TA conviction
        # (high conviction = strong buy → bad for shorts)
        ta_score = ta_conviction if direction == "LONG" else (1.0 - ta_conviction)

        scores = {
            "technical":     self._clamp(technical_confidence),
            "ta_conviction": self._clamp(ta_score),
            "ml_model":      0.8 if ml_agrees else 0.2,
            "historical":    self._clamp(historical_win_rate),
        }

        final = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        final = self._clamp(final)

        if final < self.BLOCK_THRESHOLD:
            action = "BLOCK"
        elif final < self.REDUCE_THRESHOLD:
            action = "REDUCE"
        else:
            action = "ALLOW"

        self.logger.debug(
            f"Confidence v2: {final:.3f} ({action}) | "
            f"tech={scores['technical']:.2f} ta={scores['ta_conviction']:.2f} "
            f"ml={scores['ml_model']:.2f} hist={scores['historical']:.2f}"
        )

        return {
            "confidence": round(final, 4),
            "action": action,
            "scores": {k: round(v, 4) for k, v in scores.items()},
            "weights": self.WEIGHTS,
            "direction": direction,
        }

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))


# ══════════════════════════════════════════════════════════════
# UNIFIED INTERFACE: ConfidenceEngine (delegates to v1 or v2)
# ══════════════════════════════════════════════════════════════

class ConfidenceEngine:
    """
    Unified confidence engine that supports both v1 (technical-only)
    and v2 (multi-source) scoring modes.

    Used by OrderManager Gate 8. Automatically selects v2 when
    multi-source data is available, falls back to v1 otherwise.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("ConfidenceEngine")
        self.v1 = ConfidenceEngineV1()
        self.v2 = ConfidenceAggregatorV2()

    def compute_confidence(self, signal_or_data, *args, **kwargs) -> Dict[str, Any]:
        """
        Compute confidence — dispatches to v1 or v2 based on input type.

        If called with a signal dict containing 'ta_conviction', uses v2.
        If called with raw price arrays (v1 interface), uses v1.
        """
        # v2 path: signal dict with multi-source data
        if isinstance(signal_or_data, dict):
            signal = signal_or_data
            # Check if we have v2 data available
            has_ta = signal.get("ta_conviction") is not None
            has_hist = signal.get("historical_win_rate") is not None

            if has_ta or has_hist:
                return self.v2.aggregate(
                    technical_confidence=signal.get("confidence", 0.5),
                    ta_conviction=signal.get("ta_conviction", 0.5),
                    ml_agrees=not signal.get("ml_conflict", False),
                    historical_win_rate=signal.get("historical_win_rate", 0.5),
                    direction=signal.get("direction", "LONG"),
                )

            # Fall back to simple threshold check for v1
            conf = signal.get("confidence", 0.5)
            if conf < self.v2.BLOCK_THRESHOLD:
                return {"confidence_score": conf, "action": "BLOCK", "factors": {}}
            elif conf < self.v2.REDUCE_THRESHOLD:
                return {"confidence_score": conf, "action": "REDUCE", "factors": {}}
            else:
                return {"confidence_score": conf, "action": "ALLOW", "factors": {}}

        # v1 path: raw price arrays
        if isinstance(signal_or_data, list):
            return self.v1.compute_confidence(signal_or_data, *args, **kwargs)

        return {"confidence_score": 0.5, "action": "ALLOW", "factors": {}}

    def aggregate(self, *args, **kwargs) -> Dict[str, Any]:
        """Direct access to v2 aggregation."""
        return self.v2.aggregate(*args, **kwargs)
