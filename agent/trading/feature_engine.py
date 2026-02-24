"""
Feature Engineering Engine.

Extracts a normalized 15-dimensional feature vector from a sliding
window of candles. Uses IndicatorsEngine for all calculations.

Feature categories:
    Trend (4):      EMA20 slope, EMA50 slope, EMA200 alignment, ADX
    Momentum (3):   RSI, RSI slope, MACD delta
    Volatility (3): ATR percentile, Bollinger width percentile, vol compression
    Volume (2):     Volume spike ratio, OBV slope
    Structure (3):  Price vs VWAP, candle body ratio, wick ratio

All features normalized to [0, 1] or [-1, 1] range.
Deterministic. No LLM.
"""
import math
import logging
import hashlib
from typing import Dict, Any, List, Optional
from agent.trading.indicators_engine import IndicatorsEngine


# Feature vector dimension
FEATURE_DIM = 15

# Feature names for auditability
FEATURE_NAMES = [
    "ema20_slope", "ema50_slope", "ema200_alignment", "adx",
    "rsi", "rsi_slope", "macd_delta",
    "atr_percentile", "bband_width_pct", "vol_compression",
    "volume_spike", "obv_slope",
    "vwap_distance", "body_ratio", "wick_ratio",
]

# Cryptographic hash of the exact schema being used
# Any change to FEATURE_NAMES changes this hash, invalidating old indexes
SCHEMA_VERSION = hashlib.sha256(str(FEATURE_NAMES).encode('utf-8')).hexdigest()[:16]


class FeatureEngine:
    """
    Sliding window feature extraction for pattern similarity.
    Produces a normalized 15-dim vector per window.
    """

    def __init__(self, window_size: int = 50) -> None:
        self.logger = logging.getLogger("FeatureEngine")
        self.window_size = window_size

    def extract_features(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        opens: Optional[List[float]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract a 15-dim normalized feature vector from the most recent
        `window_size` candles.

        Args:
            closes, highs, lows, volumes: Price series (must have >= window_size)
            opens: Optional (used for body/wick ratios)

        Returns:
            dict with 'vector' (List[float]), 'names' (List[str]),
            'raw' (Dict[str, float]) or None if insufficient data
        """
        n = len(closes)
        if n < self.window_size or n < 50:
            return None

        # Use last window_size candles
        c = closes[-self.window_size:]
        h = highs[-self.window_size:]
        lo = lows[-self.window_size:]
        v = volumes[-self.window_size:]
        o = opens[-self.window_size:] if opens and len(opens) >= self.window_size else c

        # Use full series for indicators that need lookback
        raw = {}

        # ══════════════════════════════════════════════════════
        # TREND (4 features)
        # ══════════════════════════════════════════════════════

        # EMA20 slope (normalized by price)
        ema20_series = IndicatorsEngine.calculate_ema_series(closes, 20)
        if len(ema20_series) >= 5:
            slope_20 = (ema20_series[-1] - ema20_series[-5]) / (ema20_series[-5] if ema20_series[-5] != 0 else 1)
            raw["ema20_slope"] = self._clip(slope_20 * 100, -5, 5)  # scale
        else:
            raw["ema20_slope"] = 0.0

        # EMA50 slope
        ema50_series = IndicatorsEngine.calculate_ema_series(closes, 50)
        if len(ema50_series) >= 5:
            slope_50 = (ema50_series[-1] - ema50_series[-5]) / (ema50_series[-5] if ema50_series[-5] != 0 else 1)
            raw["ema50_slope"] = self._clip(slope_50 * 100, -5, 5)
        else:
            raw["ema50_slope"] = 0.0

        # EMA200 alignment (-1 to +1)
        raw["ema200_alignment"] = IndicatorsEngine.calculate_ema_alignment(closes)

        # ADX (0-100, normalize to 0-1)
        adx = IndicatorsEngine.calculate_adx(highs, lows, closes, 14)
        raw["adx"] = adx / 100.0

        # ══════════════════════════════════════════════════════
        # MOMENTUM (3 features)
        # ══════════════════════════════════════════════════════

        # RSI (0-100, normalize to 0-1)
        rsi = IndicatorsEngine.calculate_rsi(closes, 14)
        raw["rsi"] = rsi / 100.0

        # RSI slope (rate of change over 5 periods)
        rsi_series = IndicatorsEngine.calculate_rsi_series(closes, 14)
        if len(rsi_series) >= 5:
            rsi_slope = rsi_series[-1] - rsi_series[-5]
            raw["rsi_slope"] = self._clip(rsi_slope / 50.0, -1, 1)
        else:
            raw["rsi_slope"] = 0.0

        # MACD delta (histogram value normalized by price)
        macd_line, signal_line, histogram = IndicatorsEngine.calculate_macd(closes)
        if closes[-1] > 0:
            raw["macd_delta"] = self._clip(histogram / closes[-1] * 100, -2, 2)
        else:
            raw["macd_delta"] = 0.0

        # ══════════════════════════════════════════════════════
        # VOLATILITY (3 features)
        # ══════════════════════════════════════════════════════

        # ATR percentile (0-100, normalize to 0-1)
        atr_pct = IndicatorsEngine.calculate_atr_percentile(highs, lows, closes, 14, 100)
        raw["atr_percentile"] = atr_pct / 100.0

        # Bollinger Band width percentile
        bb_upper, bb_middle, bb_lower = IndicatorsEngine.calculate_bollinger_bands(closes, 20, 2.0)
        if bb_middle > 0:
            bb_width = (bb_upper - bb_lower) / bb_middle
            raw["bband_width_pct"] = self._clip(bb_width * 10, 0, 1)  # scale
        else:
            raw["bband_width_pct"] = 0.5

        # Volatility compression ratio (current ATR / avg ATR)
        atr_series = IndicatorsEngine.calculate_atr_series(highs, lows, closes, 14)
        if len(atr_series) >= 20:
            avg_atr = sum(atr_series[-20:]) / 20
            current_atr = atr_series[-1]
            compression = current_atr / avg_atr if avg_atr > 0 else 1.0
            raw["vol_compression"] = self._clip(compression, 0, 3) / 3.0
        else:
            raw["vol_compression"] = 0.5

        # ══════════════════════════════════════════════════════
        # VOLUME (2 features)
        # ══════════════════════════════════════════════════════

        # Volume spike ratio
        vol_spike = IndicatorsEngine.calculate_volume_spike(volumes, 20)
        raw["volume_spike"] = self._clip(vol_spike / 3.0, 0, 1)  # cap at 3x

        # OBV slope (normalized)
        obv_series = IndicatorsEngine.calculate_obv_series(closes, volumes)
        if len(obv_series) >= 10:
            obv_range = max(obv_series[-10:]) - min(obv_series[-10:])
            if obv_range > 0:
                obv_slope = (obv_series[-1] - obv_series[-10]) / obv_range
                raw["obv_slope"] = self._clip(obv_slope, -1, 1)
            else:
                raw["obv_slope"] = 0.0
        else:
            raw["obv_slope"] = 0.0

        # ══════════════════════════════════════════════════════
        # STRUCTURE (3 features)
        # ══════════════════════════════════════════════════════

        # Price distance from VWAP (normalized)
        vwap = IndicatorsEngine.calculate_vwap(h, lo, c, v)
        if vwap > 0 and c[-1] > 0:
            vwap_dist = (c[-1] - vwap) / vwap
            raw["vwap_distance"] = self._clip(vwap_dist * 10, -1, 1)
        else:
            raw["vwap_distance"] = 0.0

        # Average candle body ratio (last 10 candles)
        body_ratios = []
        for i in range(-10, 0):
            total_range = h[i] - lo[i]
            if total_range > 0:
                body = abs(c[i] - o[i]) / total_range
                body_ratios.append(body)
        raw["body_ratio"] = sum(body_ratios) / len(body_ratios) if body_ratios else 0.5

        # Average wick ratio (upper wick / total range, last 10)
        wick_ratios = []
        for i in range(-10, 0):
            total_range = h[i] - lo[i]
            if total_range > 0:
                top = max(o[i], c[i])
                upper_wick = (h[i] - top) / total_range
                wick_ratios.append(upper_wick)
        raw["wick_ratio"] = sum(wick_ratios) / len(wick_ratios) if wick_ratios else 0.5

        # ══════════════════════════════════════════════════════
        # BUILD VECTOR
        # ══════════════════════════════════════════════════════

        vector = [raw[name] for name in FEATURE_NAMES]

        # Final normalization: ensure all values are finite
        for i in range(len(vector)):
            if math.isnan(vector[i]) or math.isinf(vector[i]):
                vector[i] = 0.0

        return {
            "vector": vector,
            "names": FEATURE_NAMES,
            "raw": raw,
            "dimension": FEATURE_DIM,
            "window_size": self.window_size,
            "schema_version": SCHEMA_VERSION,
        }

    def extract_bulk(
        self,
        closes: List[float],
        highs: List[float],
        lows: List[float],
        volumes: List[float],
        opens: Optional[List[float]] = None,
        stride: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Extract feature vectors from all sliding windows in the series.
        Used for building the historical pattern database.

        Args:
            stride: Step size between windows (1 = every candle, 5 = every 5th)

        Returns:
            List of feature dicts with 'candle_index' added
        """
        results = []
        n = len(closes)

        for end_idx in range(self.window_size, n + 1, stride):
            window_closes = closes[:end_idx]
            window_highs = highs[:end_idx]
            window_lows = lows[:end_idx]
            window_volumes = volumes[:end_idx]
            window_opens = opens[:end_idx] if opens else None

            features = self.extract_features(
                window_closes, window_highs, window_lows,
                window_volumes, window_opens
            )
            if features:
                features["candle_index"] = end_idx - 1
                results.append(features)

        self.logger.debug(f"Extracted {len(results)} feature vectors (stride={stride})")
        return results

    @staticmethod
    def _clip(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
