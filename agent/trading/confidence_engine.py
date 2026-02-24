"""
Institutional Confidence Scoring Model.

Computes a normalized 0–1 confidence score from 5 deterministic factors:
    0.30 × trend_strength
    0.20 × momentum_alignment
    0.15 × volatility_alignment
    0.15 × structure_alignment
    0.20 × volume_confirmation

Confidence < 0.45 → reduce position size.
Confidence < 0.35 → block signal entirely.

No LLM. Fully deterministic.
"""
import logging
from typing import List, Dict, Any, Optional
from agent.trading.indicators_engine import IndicatorsEngine


class ConfidenceEngine:
    """
    Institutional-grade confidence scoring.
    Every signal must pass through this engine before sizing.
    """

    # Factor weights — must sum to 1.0
    WEIGHTS = {
        "trend_strength": 0.30,
        "momentum_alignment": 0.20,
        "volatility_alignment": 0.15,
        "structure_alignment": 0.15,
        "volume_confirmation": 0.20,
    }

    # Thresholds
    REDUCE_THRESHOLD = 0.45    # Below this → reduce position size
    BLOCK_THRESHOLD = 0.35     # Below this → block signal entirely

    def __init__(self) -> None:
        self.logger = logging.getLogger("ConfidenceEngine")

    def compute_confidence(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        structure_score: float = 0.5,
        regime: str = "QUIET",
    ) -> Dict[str, Any]:
        """
        Compute confidence score from market data.

        Args:
            closes: Close prices
            highs: High prices
            lows: Low prices
            volumes: Volume data
            structure_score: 0–1 from structural vision engine (support/resistance alignment)
            regime: Current market regime for context

        Returns:
            dict with confidence_score, action (ALLOW/REDUCE/BLOCK), factors breakdown
        """
        if len(closes) < 50:
            return self._build_result(0.0, {}, regime)

        # ── Factor 1: Trend Strength (0.0–1.0) ─────────────────
        trend = IndicatorsEngine.calculate_trend_strength(closes)
        trend = self._clamp(trend)

        # ── Factor 2: Momentum Alignment (0.0–1.0) ─────────────
        momentum = IndicatorsEngine.calculate_momentum_alignment(closes)
        momentum = self._clamp(momentum)

        # ── Factor 3: Volatility Alignment (0.0–1.0) ───────────
        # High if ATR is in a "tradable" range (not too low/chaotic)
        atr_pct = IndicatorsEngine.calculate_atr_percentile(highs, lows, closes)
        # Sweet spot: 30–70 percentile = best trading conditions
        if 30.0 <= atr_pct <= 70.0:
            vol_alignment = 1.0
        elif 20.0 <= atr_pct <= 80.0:
            vol_alignment = 0.7
        elif 10.0 <= atr_pct <= 90.0:
            vol_alignment = 0.4
        else:
            vol_alignment = 0.2  # Extreme volatility or dead market

        # ── Factor 4: Structure Alignment (0.0–1.0) ────────────
        # Provided by structural vision engine (support/resistance proximity)
        structure = self._clamp(structure_score)

        # ── Factor 5: Volume Confirmation (0.0–1.0) ────────────
        vol_spike = IndicatorsEngine.calculate_volume_spike(volumes, 20)
        # > 1.5x average = strong confirmation, > 2.0 = very strong
        if vol_spike >= 2.0:
            volume_conf = 1.0
        elif vol_spike >= 1.5:
            volume_conf = 0.8
        elif vol_spike >= 1.0:
            volume_conf = 0.5
        else:
            volume_conf = 0.3  # Below-average volume = weak

        # ── Weighted Composite ─────────────────────────────────
        factors = {
            "trend_strength": round(trend, 4),
            "momentum_alignment": round(momentum, 4),
            "volatility_alignment": round(vol_alignment, 4),
            "structure_alignment": round(structure, 4),
            "volume_confirmation": round(volume_conf, 4),
        }

        score = sum(
            factors[k] * self.WEIGHTS[k]
            for k in self.WEIGHTS
        )
        score = self._clamp(score)

        return self._build_result(score, factors, regime)

    def _build_result(
        self, score: float, factors: Dict[str, float], regime: str
    ) -> Dict[str, Any]:
        """Build the confidence result dict with action classification."""
        # Regime-adjusted confidence
        regime_penalty = {
            "TRENDING_VOLATILE": -0.05,
            "LOW_VOL_RANGE": -0.10,
            "MEAN_REVERTING": 0.0,
            "EXPANSION_BREAKOUT": 0.05,
            "QUIET": -0.05,
        }
        adjusted = score + regime_penalty.get(regime, 0.0)
        adjusted = self._clamp(adjusted)

        if adjusted < self.BLOCK_THRESHOLD:
            action = "BLOCK"
        elif adjusted < self.REDUCE_THRESHOLD:
            action = "REDUCE"
        else:
            action = "ALLOW"

        self.logger.debug(
            f"Confidence: {adjusted:.3f} ({action}) | raw={score:.3f} | regime={regime}"
        )

        return {
            "confidence_score": round(adjusted, 4),
            "raw_score": round(score, 4),
            "action": action,
            "factors": factors,
            "regime": regime,
        }

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        """Clamp value to [low, high]."""
        return max(low, min(high, value))
