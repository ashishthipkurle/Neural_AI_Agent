"""
Directional Bias Engine.

Computes per-timeframe directional bias from technical indicators.
Returns a bias score from -3.0 (extreme bearish) to +3.0 (extreme bullish).
Fed into the Multi-Timeframe Fusion Engine.

No LLM. Fully deterministic.
"""
import logging
from typing import List, Dict, Any
from agent.trading.indicators_engine import IndicatorsEngine


class BiasEngine:
    """
    Computes directional bias for a single timeframe from price data.
    Combines EMA slope direction, RSI zone, and MACD histogram sign.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("BiasEngine")

    def compute_bias(
        self,
        closes: List[float],
        highs: List[float] = None,
        lows: List[float] = None,
        volumes: List[float] = None,
    ) -> Dict[str, Any]:
        """
        Compute directional bias score for one timeframe.

        Returns:
            dict with:
                bias_score: float (-3.0 to +3.0)
                bias_label: str (STRONG_BULLISH, BULLISH, NEUTRAL, BEARISH, STRONG_BEARISH)
                components: dict of individual factor scores
        """
        if len(closes) < 50:
            return {
                "bias_score": 0.0,
                "bias_label": "NEUTRAL",
                "components": {},
            }

        # ── Factor 1: EMA Slope Direction (weight: 1.0) ────────
        # Compare current EMA vs EMA from 5 bars ago
        ema_series = IndicatorsEngine.calculate_ema_series(closes, 21)
        if len(ema_series) >= 6:
            ema_now = ema_series[-1]
            ema_prev = ema_series[-6]
            ema_slope = (ema_now - ema_prev) / ema_prev * 100.0 if ema_prev != 0 else 0.0
            # Normalize: ±0.5% = ±1.0
            ema_score = max(-1.0, min(1.0, ema_slope / 0.5))
        else:
            ema_score = 0.0

        # ── Factor 2: RSI Zone (weight: 0.8) ───────────────────
        rsi = IndicatorsEngine.calculate_rsi(closes, 14)
        if rsi > 70:
            rsi_score = 0.8   # Overbought = bullish momentum
        elif rsi > 55:
            rsi_score = 0.4
        elif rsi > 45:
            rsi_score = 0.0   # Neutral zone
        elif rsi > 30:
            rsi_score = -0.4
        else:
            rsi_score = -0.8  # Oversold = bearish momentum

        # ── Factor 3: MACD Histogram Sign (weight: 0.7) ────────
        _, _, histogram = IndicatorsEngine.calculate_macd(closes)
        if histogram > 0:
            macd_score = min(0.7, histogram * 10.0)  # Scale small histograms
        elif histogram < 0:
            macd_score = max(-0.7, histogram * 10.0)
        else:
            macd_score = 0.0

        # ── Factor 4: Price vs VWAP (weight: 0.5) ──────────────
        vwap_score = 0.0
        if highs and lows and volumes:
            vwap = IndicatorsEngine.calculate_vwap(highs, lows, closes, volumes)
            if vwap > 0 and closes[-1] != 0:
                deviation = (closes[-1] - vwap) / vwap * 100.0
                vwap_score = max(-0.5, min(0.5, deviation / 0.3))

        # ── Composite Bias Score ───────────────────────────────
        bias_score = ema_score + rsi_score + macd_score + vwap_score
        bias_score = max(-3.0, min(3.0, bias_score))

        # ── Label ──────────────────────────────────────────────
        if bias_score >= 2.0:
            label = "STRONG_BULLISH"
        elif bias_score >= 0.5:
            label = "BULLISH"
        elif bias_score > -0.5:
            label = "NEUTRAL"
        elif bias_score > -2.0:
            label = "BEARISH"
        else:
            label = "STRONG_BEARISH"

        components = {
            "ema_slope": round(ema_score, 3),
            "rsi_zone": round(rsi_score, 3),
            "macd_histogram": round(macd_score, 3),
            "vwap_deviation": round(vwap_score, 3),
            "rsi_raw": round(rsi, 2),
        }

        self.logger.debug(f"Bias: {bias_score:.2f} ({label}) | {components}")

        return {
            "bias_score": round(bias_score, 3),
            "bias_label": label,
            "components": components,
        }
