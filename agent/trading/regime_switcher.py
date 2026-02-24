"""
Quantitative Market Regime Classifier.

Deterministic regime detection using ATR percentile, trend strength,
RSI oscillation, and EMA alignment. No LLM. No probabilistic guessing.

Regimes:
    TRENDING_VOLATILE    — ATR_percentile > 80 AND trend_strength > 0.7
    LOW_VOL_RANGE        — ATR_percentile < 20
    MEAN_REVERTING       — RSI oscillating 45–55 for N candles
    EXPANSION_BREAKOUT   — Volatility spike AND strong EMA alignment
    QUIET                — Default / indeterminate
"""
import logging
from typing import List, Dict, Any, Optional
from agent.trading.indicators_engine import IndicatorsEngine


class RegimeSwitcher:
    """
    Deterministic market regime classifier.
    Classifies current regime to influence signal generation, position sizing,
    risk compression, and confidence weighting.
    """

    REGIMES = [
        "TRENDING_VOLATILE",
        "LOW_VOL_RANGE",
        "MEAN_REVERTING",
        "EXPANSION_BREAKOUT",
        "QUIET",
    ]

    def __init__(self) -> None:
        self.logger = logging.getLogger("RegimeSwitcher")
        self.current_regime = "QUIET"
        self._regime_history: List[str] = []

    def detect_regime(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: Optional[List[float]] = None,
        atr_period: int = 14,
        atr_lookback: int = 100,
        rsi_period: int = 14,
        rsi_oscillation_window: int = 10,
    ) -> str:
        """
        Classify current market regime using deterministic thresholds.

        Args:
            highs: High prices array
            lows: Low prices array
            closes: Close prices array
            volumes: Volume array (optional, for breakout confirmation)
            atr_period: ATR calculation period
            atr_lookback: Lookback for ATR percentile ranking
            rsi_period: RSI calculation period
            rsi_oscillation_window: Number of candles to check RSI oscillation

        Returns:
            str: One of TRENDING_VOLATILE, LOW_VOL_RANGE, MEAN_REVERTING,
                 EXPANSION_BREAKOUT, or QUIET
        """
        n = min(len(highs), len(lows), len(closes))
        if n < max(atr_period, rsi_period) + 10:
            self.current_regime = "QUIET"
            return self.current_regime

        # ── Compute indicators ──────────────────────────────────
        atr_percentile = IndicatorsEngine.calculate_atr_percentile(
            highs, lows, closes, atr_period, atr_lookback
        )
        trend_strength = IndicatorsEngine.calculate_trend_strength(closes)
        ema_alignment = IndicatorsEngine.calculate_ema_alignment(
            closes, [9, 21, 50]
        )
        rsi_series = IndicatorsEngine.calculate_rsi_series(closes, rsi_period)

        # ── Rule 1: TRENDING_VOLATILE ───────────────────────────
        # ATR in top 20% AND strong directional trend
        if atr_percentile > 80.0 and trend_strength > 0.7:
            self.current_regime = "TRENDING_VOLATILE"

        # ── Rule 2: EXPANSION_BREAKOUT ──────────────────────────
        # Volatility is spiking AND EMAs are strongly aligned
        elif atr_percentile > 65.0 and abs(ema_alignment) > 0.75:
            # Optional volume confirmation
            if volumes and len(volumes) > 20:
                vol_spike = IndicatorsEngine.calculate_volume_spike(volumes, 20)
                if vol_spike > 1.5:
                    self.current_regime = "EXPANSION_BREAKOUT"
                else:
                    self.current_regime = "TRENDING_VOLATILE"
            else:
                self.current_regime = "EXPANSION_BREAKOUT"

        # ── Rule 3: LOW_VOL_RANGE ───────────────────────────────
        # ATR in bottom 20%
        elif atr_percentile < 20.0:
            self.current_regime = "LOW_VOL_RANGE"

        # ── Rule 4: MEAN_REVERTING ──────────────────────────────
        # RSI stuck in 45–55 range for N consecutive candles
        elif self._check_rsi_oscillation(rsi_series, rsi_oscillation_window):
            self.current_regime = "MEAN_REVERTING"

        # ── Default: QUIET ──────────────────────────────────────
        else:
            self.current_regime = "QUIET"

        self._regime_history.append(self.current_regime)
        # Keep history bounded
        if len(self._regime_history) > 200:
            self._regime_history = self._regime_history[-200:]

        self.logger.debug(
            f"Regime: {self.current_regime} "
            f"[ATR%={atr_percentile:.1f}, trend={trend_strength:.3f}, "
            f"EMA_align={ema_alignment:.2f}]"
        )
        return self.current_regime

    def _check_rsi_oscillation(
        self, rsi_series: List[float], window: int = 10
    ) -> bool:
        """Check if RSI has been oscillating between 45–55 for `window` candles."""
        if len(rsi_series) < window:
            return False

        recent = rsi_series[-window:]
        return all(45.0 <= r <= 55.0 for r in recent)

    def is_regime_stable(self, lookback: int = 5) -> bool:
        """Check if regime has been consistent for the last `lookback` periods."""
        if len(self._regime_history) < lookback:
            return False
        recent = self._regime_history[-lookback:]
        return len(set(recent)) == 1

    def get_regime_risk_multiplier(self) -> float:
        """
        Returns a risk multiplier based on current regime.
        Used by sizing and risk engines.
        """
        multipliers = {
            "TRENDING_VOLATILE": 0.7,      # Reduce size in volatile trends
            "LOW_VOL_RANGE": 0.5,           # Small size, tight stops
            "MEAN_REVERTING": 0.8,          # Moderate size for mean reversion
            "EXPANSION_BREAKOUT": 1.0,      # Full size on breakouts
            "QUIET": 0.6,                   # Conservative in quiet markets
        }
        return multipliers.get(self.current_regime, 0.5)

    def get_state(self) -> Dict[str, Any]:
        """Return serializable regime state for API/frontend."""
        return {
            "current_regime": self.current_regime,
            "is_stable": self.is_regime_stable(),
            "risk_multiplier": self.get_regime_risk_multiplier(),
            "history_length": len(self._regime_history),
        }
