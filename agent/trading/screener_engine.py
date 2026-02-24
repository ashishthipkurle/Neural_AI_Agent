"""
Market Screener Engine.

Score = 0.30 × trend_strength
      + 0.25 × volatility_expansion
      + 0.20 × volume_spike
      + 0.15 × breakout_probability
      + 0.10 × momentum_divergence

Returns ranked top N assets.
No LLM. Fully deterministic.
"""
import logging
from typing import List, Dict, Any
from agent.trading.indicators_engine import IndicatorsEngine


class ScreenerEngine:
    """
    Multi-factor asset screening and ranking engine.
    """

    WEIGHTS = {
        "trend_strength": 0.30,
        "volatility_expansion": 0.25,
        "volume_spike": 0.20,
        "breakout_probability": 0.15,
        "momentum_divergence": 0.10,
    }

    def __init__(self) -> None:
        self.logger = logging.getLogger("ScreenerEngine")

    def score_asset(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
    ) -> Dict[str, Any]:
        """
        Score a single asset across all screening factors.

        Returns:
            dict with total_score (0–1), individual factor scores, and breakdown
        """
        if len(closes) < 50:
            return {"total_score": 0.0, "factors": {}, "status": "INSUFFICIENT_DATA"}

        # ── Factor 1: Trend Strength (0–1) ─────────────────────
        trend = IndicatorsEngine.calculate_trend_strength(closes)

        # ── Factor 2: Volatility Expansion (0–1) ───────────────
        atr_pct = IndicatorsEngine.calculate_atr_percentile(highs, lows, closes)
        # Higher percentile = more expansion
        vol_expansion = min(atr_pct / 100.0, 1.0)

        # ── Factor 3: Volume Spike (0–1) ───────────────────────
        vol_spike_raw = IndicatorsEngine.calculate_volume_spike(volumes, 20)
        # Normalize: 1.5x = 0.5, 3.0x = 1.0
        vol_spike = min(max((vol_spike_raw - 1.0) / 2.0, 0.0), 1.0)

        # ── Factor 4: Breakout Probability (0–1) ───────────────
        # Price near Bollinger upper band = potential breakout
        upper, middle, lower = IndicatorsEngine.calculate_bollinger_bands(closes, 20, 2.0)
        if upper > lower and upper > 0:
            band_range = upper - lower
            current = closes[-1]
            # How close to upper band (1.0 = at or above upper)
            breakout_prob = max(0.0, min(1.0, (current - middle) / (band_range / 2)))
        else:
            breakout_prob = 0.5

        # ── Factor 5: Momentum Divergence (0–1) ────────────────
        momentum = IndicatorsEngine.calculate_momentum_alignment(closes)

        # ── Composite Score ────────────────────────────────────
        factors = {
            "trend_strength": round(trend, 4),
            "volatility_expansion": round(vol_expansion, 4),
            "volume_spike": round(vol_spike, 4),
            "breakout_probability": round(breakout_prob, 4),
            "momentum_divergence": round(momentum, 4),
        }

        total = sum(factors[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        total = max(0.0, min(1.0, total))

        return {
            "total_score": round(total, 4),
            "factors": factors,
            "status": "SCORED",
        }

    def screen_assets(
        self,
        assets: Dict[str, Dict[str, List[float]]],
        top_n: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Screen and rank multiple assets.

        Args:
            assets: Dict mapping asset name to price data:
                {
                    "BTC": {"closes": [...], "highs": [...], "lows": [...], "volumes": [...]},
                    "ETH": {"closes": [...], ...},
                }
            top_n: Number of top assets to return

        Returns:
            Sorted list of top N scored assets
        """
        results = []
        for name, data in assets.items():
            closes = data.get("closes", [])
            highs = data.get("highs", closes)
            lows = data.get("lows", closes)
            volumes = data.get("volumes", [1.0] * len(closes))

            score_result = self.score_asset(closes, highs, lows, volumes)
            score_result["asset"] = name
            results.append(score_result)

        # Sort by total_score descending
        results.sort(key=lambda x: x["total_score"], reverse=True)
        top = results[:top_n]

        self.logger.info(
            f"Screened {len(assets)} assets. Top {top_n}: "
            + ", ".join(f"{r['asset']}={r['total_score']:.3f}" for r in top)
        )

        return top
