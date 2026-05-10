"""
Institutional-Grade Technical Analysis Indicators Engine.

Deterministic, pure-math indicator calculations.
No LLM dependency. No external API calls.
All methods are static — stateless computation on price arrays.
"""
import math
from typing import List, Tuple, Optional


class IndicatorsEngine:
    """
    Deterministic technical indicator computations for institutional trading.
    All methods accept raw price/volume arrays and return numeric results.
    """

    # ─── Moving Averages ───────────────────────────────────────────

    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> float:
        """Simple Moving Average over the last `period` prices."""
        if len(prices) < period or period <= 0:
            return 0.0
        return sum(prices[-period:]) / period

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> float:
        """Exponential Moving Average — full series computation, returns final value."""
        if len(prices) < period or period <= 0:
            return 0.0
        multiplier = 2.0 / (period + 1.0)
        ema = sum(prices[:period]) / period  # seed with SMA
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    @staticmethod
    def calculate_ema_series(prices: List[float], period: int) -> List[float]:
        """Full EMA series — needed for MACD signal line and ADX smoothing."""
        if len(prices) < period or period <= 0:
            return []
        multiplier = 2.0 / (period + 1.0)
        ema = sum(prices[:period]) / period
        series = [ema]
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
            series.append(ema)
        return series

    # ─── Momentum Oscillators ──────────────────────────────────────

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        """Relative Strength Index using Wilder's smoothing."""
        if len(prices) <= period or period <= 0:
            return 50.0

        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            gains.append(max(change, 0.0))
            losses.append(max(-change, 0.0))

        if len(gains) < period:
            return 50.0

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def calculate_rsi_series(prices: List[float], period: int = 14) -> List[float]:
        """Full RSI series — needed for regime oscillation detection."""
        if len(prices) <= period or period <= 0:
            return []

        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            gains.append(max(change, 0.0))
            losses.append(max(-change, 0.0))

        if len(gains) < period:
            return []

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        rsi_series = []
        if avg_loss == 0:
            rsi_series.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_series.append(100.0 - (100.0 / (1.0 + rs)))

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                rsi_series.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi_series.append(100.0 - (100.0 / (1.0 + rs)))

        return rsi_series

    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Tuple[float, float, float]:
        """
        MACD with proper signal line (EMA of MACD series).
        Returns (macd_line, signal_line, histogram).
        """
        if len(prices) < slow_period + signal_period:
            return 0.0, 0.0, 0.0

        fast_series = IndicatorsEngine.calculate_ema_series(prices, fast_period)
        slow_series = IndicatorsEngine.calculate_ema_series(prices, slow_period)

        # Align series — slow_series starts later
        offset = fast_period - slow_period if fast_period > slow_period else 0
        min_len = min(len(fast_series), len(slow_series))
        fast_aligned = fast_series[-min_len:]
        slow_aligned = slow_series[-min_len:]

        macd_series = [f - s for f, s in zip(fast_aligned, slow_aligned)]

        if len(macd_series) < signal_period:
            macd_line = macd_series[-1] if macd_series else 0.0
            return macd_line, 0.0, macd_line

        # Signal line = EMA of MACD series
        signal_series = IndicatorsEngine.calculate_ema_series(macd_series, signal_period)

        macd_line = macd_series[-1]
        signal_line = signal_series[-1] if signal_series else 0.0
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    # ─── Volatility Indicators ─────────────────────────────────────

    @staticmethod
    def calculate_atr(
        highs: List[float], lows: List[float], closes: List[float], period: int = 14
    ) -> float:
        """
        Average True Range — Wilder's smoothed.
        Requires high, low, close arrays of equal length.
        """
        n = min(len(highs), len(lows), len(closes))
        if n < 2 or period <= 0:
            return 0.0

        true_ranges = []
        for i in range(1, n):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

        # Initial ATR = SMA of first `period` true ranges
        atr = sum(true_ranges[:period]) / period

        # Wilder's smoothing
        for i in range(period, len(true_ranges)):
            atr = (atr * (period - 1) + true_ranges[i]) / period

        return atr

    @staticmethod
    def calculate_atr_series(
        highs: List[float], lows: List[float], closes: List[float], period: int = 14
    ) -> List[float]:
        """Full ATR series — needed for ATR percentile calculation."""
        n = min(len(highs), len(lows), len(closes))
        if n < 2 or period <= 0:
            return []

        true_ranges = []
        for i in range(1, n):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return []

        atr = sum(true_ranges[:period]) / period
        series = [atr]

        for i in range(period, len(true_ranges)):
            atr = (atr * (period - 1) + true_ranges[i]) / period
            series.append(atr)

        return series

    @staticmethod
    def calculate_atr_percentile(
        highs: List[float], lows: List[float], closes: List[float],
        period: int = 14, lookback: int = 100
    ) -> float:
        """
        ATR Percentile — where current ATR ranks vs last `lookback` ATR values.
        Returns 0.0–100.0. Used for regime classification.
        """
        atr_series = IndicatorsEngine.calculate_atr_series(highs, lows, closes, period)
        if len(atr_series) < 2:
            return 50.0

        window = atr_series[-lookback:] if len(atr_series) >= lookback else atr_series
        current_atr = atr_series[-1]

        count_below = sum(1 for a in window if a <= current_atr)
        return (count_below / len(window)) * 100.0

    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float], period: int = 20, num_std: float = 2.0
    ) -> Tuple[float, float, float]:
        """Bollinger Bands. Returns (upper_band, middle_band, lower_band)."""
        if len(prices) < period or period <= 0:
            return 0.0, 0.0, 0.0

        recent = prices[-period:]
        middle = sum(recent) / period
        variance = sum((p - middle) ** 2 for p in recent) / period
        std = math.sqrt(variance)

        return middle + std * num_std, middle, middle - std * num_std

    @staticmethod
    def calculate_bollinger_bands_series(
        prices: List[float], period: int = 20, num_std: float = 2.0
    ) -> Tuple[List[float], List[float], List[float]]:
        """Bollinger Bands Series. Returns full arrays for (upper, middle, lower)."""
        upper, middle, lower = [], [], []
        if len(prices) < period or period <= 0:
            return upper, middle, lower

        for i in range(len(prices)):
            if i < period - 1:
                upper.append(0.0)
                middle.append(0.0)
                lower.append(0.0)
                continue
            
            recent = prices[i - period + 1 : i + 1]
            mid = sum(recent) / period
            variance = sum((p - mid) ** 2 for p in recent) / period
            std = math.sqrt(variance)
            
            upper.append(mid + std * num_std)
            middle.append(mid)
            lower.append(mid - std * num_std)

        return upper, middle, lower

    # ─── Volume Indicators ─────────────────────────────────────────

    @staticmethod
    def calculate_obv(closes: List[float], volumes: List[float]) -> float:
        """On Balance Volume — cumulative volume flow direction."""
        n = min(len(closes), len(volumes))
        if n < 2:
            return 0.0

        obv = 0.0
        for i in range(1, n):
            if closes[i] > closes[i - 1]:
                obv += volumes[i]
            elif closes[i] < closes[i - 1]:
                obv -= volumes[i]
            # equal = no change
        return obv

    @staticmethod
    def calculate_obv_series(closes: List[float], volumes: List[float]) -> List[float]:
        """Full OBV series — for volume trend confirmation."""
        n = min(len(closes), len(volumes))
        if n < 2:
            return []

        obv = 0.0
        series = [0.0]
        for i in range(1, n):
            if closes[i] > closes[i - 1]:
                obv += volumes[i]
            elif closes[i] < closes[i - 1]:
                obv -= volumes[i]
            series.append(obv)
        return series

    @staticmethod
    def calculate_vwap(
        highs: List[float], lows: List[float], closes: List[float], volumes: List[float]
    ) -> float:
        """
        Volume Weighted Average Price — sum(typical_price * volume) / sum(volume).
        Typically computed intraday from session open.
        """
        n = min(len(highs), len(lows), len(closes), len(volumes))
        if n < 1:
            return 0.0

        tp_vol_sum = 0.0
        vol_sum = 0.0
        for i in range(n):
            typical_price = (highs[i] + lows[i] + closes[i]) / 3.0
            tp_vol_sum += typical_price * volumes[i]
            vol_sum += volumes[i]

        return tp_vol_sum / vol_sum if vol_sum > 0 else 0.0

    # ─── Trend Strength Indicators ─────────────────────────────────

    @staticmethod
    def calculate_adx(
        highs: List[float], lows: List[float], closes: List[float], period: int = 14
    ) -> float:
        """
        Average Directional Index — measures trend strength (0–100).
        Above 25 = trending. Above 50 = strong trend.
        """
        n = min(len(highs), len(lows), len(closes))
        if n < period + 1:
            return 0.0

        plus_dm_list = []
        minus_dm_list = []
        tr_list = []

        for i in range(1, n):
            high_diff = highs[i] - highs[i - 1]
            low_diff = lows[i - 1] - lows[i]

            plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0.0
            minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0.0

            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )

            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
            tr_list.append(tr)

        if len(tr_list) < period:
            return 0.0

        # Wilder's smoothing for +DM, -DM, and TR
        smoothed_plus = sum(plus_dm_list[:period])
        smoothed_minus = sum(minus_dm_list[:period])
        smoothed_tr = sum(tr_list[:period])

        dx_list = []
        for i in range(period, len(tr_list)):
            smoothed_plus = smoothed_plus - (smoothed_plus / period) + plus_dm_list[i]
            smoothed_minus = smoothed_minus - (smoothed_minus / period) + minus_dm_list[i]
            smoothed_tr = smoothed_tr - (smoothed_tr / period) + tr_list[i]

            if smoothed_tr == 0:
                dx_list.append(0.0)
                continue

            plus_di = 100.0 * smoothed_plus / smoothed_tr
            minus_di = 100.0 * smoothed_minus / smoothed_tr

            di_sum = plus_di + minus_di
            if di_sum == 0:
                dx_list.append(0.0)
            else:
                dx = 100.0 * abs(plus_di - minus_di) / di_sum
                dx_list.append(dx)

        if len(dx_list) < period:
            return sum(dx_list) / len(dx_list) if dx_list else 0.0

        # ADX = smoothed average of DX
        adx = sum(dx_list[:period]) / period
        for i in range(period, len(dx_list)):
            adx = (adx * (period - 1) + dx_list[i]) / period

        return adx

    @staticmethod
    def calculate_trend_strength(prices: List[float], fast_period: int = 9, slow_period: int = 21) -> float:
        """
        Trend strength normalized 0.0–1.0 based on EMA separation.
        Measures how far apart fast and slow EMAs are relative to price.
        """
        if len(prices) < slow_period:
            return 0.0

        fast_ema = IndicatorsEngine.calculate_ema(prices, fast_period)
        slow_ema = IndicatorsEngine.calculate_ema(prices, slow_period)
        current_price = prices[-1]

        if current_price == 0:
            return 0.0

        # Normalized separation
        separation = abs(fast_ema - slow_ema) / current_price
        # Scale: 0.5% separation ≈ 0.5 strength, 1%+ ≈ 1.0
        strength = min(separation * 100.0, 1.0)
        return strength

    @staticmethod
    def calculate_ema_alignment(prices: List[float], periods: Optional[List[int]] = None) -> float:
        """
        EMA Alignment score — checks if EMAs are stacked in order.
        Returns +1.0 for perfect bullish alignment (9 > 21 > 50 > 100 > 200),
        -1.0 for perfect bearish, 0.0 for mixed.
        """
        if periods is None:
            periods = [9, 21, 50, 100, 200]

        if len(prices) < max(periods):
            return 0.0

        emas = [IndicatorsEngine.calculate_ema(prices, p) for p in periods]

        # Check bullish alignment: each shorter EMA > longer EMA
        bullish_pairs = sum(1 for i in range(len(emas) - 1) if emas[i] > emas[i + 1])
        bearish_pairs = sum(1 for i in range(len(emas) - 1) if emas[i] < emas[i + 1])

        total_pairs = len(emas) - 1
        if total_pairs == 0:
            return 0.0

        # Score: +1 if all bullish, -1 if all bearish, fractional otherwise
        return (bullish_pairs - bearish_pairs) / total_pairs

    # ─── Derived / Composite ───────────────────────────────────────

    @staticmethod
    def calculate_volume_spike(volumes: List[float], lookback: int = 20) -> float:
        """
        Volume spike ratio: current volume / average volume over lookback.
        > 2.0 = significant spike. > 3.0 = extreme.
        """
        if len(volumes) < lookback + 1 or lookback <= 0:
            return 1.0

        avg_vol = sum(volumes[-(lookback + 1):-1]) / lookback
        if avg_vol <= 0:
            return 1.0

        return volumes[-1] / avg_vol

    @staticmethod
    def calculate_momentum_alignment(prices: List[float], period: int = 14) -> float:
        """
        Momentum alignment: direction consistency of RSI and MACD.
        Returns 0.0–1.0. 1.0 = both agree strongly, 0.0 = full disagreement.
        """
        rsi = IndicatorsEngine.calculate_rsi(prices, period)
        macd_line, signal_line, histogram = IndicatorsEngine.calculate_macd(prices)

        # Normalize RSI to -1..+1 (50 = neutral)
        rsi_direction = (rsi - 50.0) / 50.0  # -1 to +1

        # MACD direction
        macd_direction = 1.0 if histogram > 0 else -1.0 if histogram < 0 else 0.0

        # Agreement: both positive or both negative
        agreement = rsi_direction * macd_direction
        # Clamp 0–1
        return max(0.0, min(1.0, (agreement + 1.0) / 2.0))
