"""
Strategy Engine — 4 Concrete Algorithmic Trading Strategies.

Strategies:
    1. Trend Following    — EMA crossover + ADX + RSI filter
    2. Mean Reversion     — Bollinger bounce + RSI extremes + volume spike
    3. Breakout           — 20-period high/low + ATR expansion + OBV
    4. FAISS Pattern      — Feature extraction → similarity → probability gates

All math via IndicatorsEngine. No LLM. Fully deterministic.
Anti-whipsaw: 4-bar cooldown per symbol after each signal.
Same-direction filter: no duplicate signals.
"""
import uuid
import time
import logging
import math
from typing import Dict, Any, List, Optional


class StrategyEngine:
    """
    Evaluates 4 concrete trading strategies against live market data.
    """

    COOLDOWN_BARS = 4  # Anti-whipsaw: 4-bar cooldown per symbol

    def __init__(
        self,
        indicators_engine=None,
        regime_switcher=None,
        feature_engine=None,
        similarity_engine=None,
        pattern_store=None,
        probability_engine=None,
        mtf_fusion_engine=None,
        bias_engine=None,
    ) -> None:
        self.logger = logging.getLogger("StrategyEngine")

        # Core engines (imported by caller)
        self.indicators = indicators_engine
        self.regime = regime_switcher
        self.feature_engine = feature_engine
        self.similarity_engine = similarity_engine
        self.pattern_store = pattern_store
        self.probability_engine = probability_engine
        self.mtf_fusion = mtf_fusion_engine
        self.bias_engine = bias_engine

        # Anti-whipsaw cooldown tracker: {symbol: bar_index_of_last_signal}
        self._last_signal_bar: Dict[str, int] = {}

        # Active direction tracker: {symbol: "LONG"|"SHORT"}
        self._active_directions: Dict[str, str] = {}

        # Strategy registry
        self._strategies = {
            "trend_following": self._strategy_trend_following,
            "mean_reversion": self._strategy_mean_reversion,
            "breakout": self._strategy_breakout,
            "faiss_pattern": self._strategy_faiss_pattern,
        }

    # ══════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════

    def evaluate_all_strategies(
        self,
        symbol: str,
        ohlcv: Dict[str, List[float]],
        regime: str,
        current_bar_index: int = 0,
        strategies_enabled: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Run all enabled strategies against the current market data.
        Returns list of signal dicts (may be empty if no signals fire).
        """
        if not ohlcv or not ohlcv.get("closes") or len(ohlcv["closes"]) < 50:
            return []

        enabled = strategies_enabled or list(self._strategies.keys())
        signals = []

        for name in enabled:
            sig = self.evaluate_strategy(name, symbol, ohlcv, regime, current_bar_index)
            if sig:
                signals.append(sig)

        return signals

    def evaluate_strategy(
        self,
        strategy_name: str,
        symbol: str,
        ohlcv: Dict[str, List[float]],
        regime: str,
        current_bar_index: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single strategy. Returns signal dict or None.
        Enforces cooldown and same-direction filters.
        """
        # Anti-whipsaw cooldown check
        if not self._check_cooldown(symbol, current_bar_index):
            return None

        strategy_fn = self._strategies.get(strategy_name)
        if not strategy_fn:
            self.logger.warning(f"Unknown strategy: {strategy_name}")
            return None

        try:
            signal = strategy_fn(symbol, ohlcv, regime)
        except Exception as e:
            self.logger.error(f"Strategy {strategy_name} error on {symbol}: {e}")
            return None

        if not signal:
            return None

        # Same-direction filter: skip if already in the same direction
        direction = signal.get("direction", "")
        if self._active_directions.get(symbol) == direction:
            return None

        # Record cooldown
        self._last_signal_bar[symbol] = current_bar_index

        # Stamp metadata
        signal["signal_id"] = str(uuid.uuid4())
        signal["strategy_name"] = strategy_name
        signal["symbol"] = symbol
        signal["regime"] = regime
        signal["created_at"] = time.time()

        self.logger.info(
            f"Signal: {strategy_name} | {symbol} {direction} @ {signal.get('entry_price', 0):.2f}"
        )
        return signal

    def register_active_position(self, symbol: str, direction: str) -> None:
        """Track active position direction for same-direction filter."""
        self._active_directions[symbol] = direction

    def clear_active_position(self, symbol: str) -> None:
        """Clear active position tracker when position closes."""
        self._active_directions.pop(symbol, None)

    # ══════════════════════════════════════════════════════════════
    # COOLDOWN
    # ══════════════════════════════════════════════════════════════

    def _check_cooldown(self, symbol: str, current_bar_index: int) -> bool:
        """Returns True if the cooldown period has elapsed."""
        last = self._last_signal_bar.get(symbol, -999)
        return (current_bar_index - last) >= self.COOLDOWN_BARS

    # ══════════════════════════════════════════════════════════════
    # STRATEGY 1: TREND FOLLOWING (EMA Crossover + ADX)
    # ══════════════════════════════════════════════════════════════

    def _strategy_trend_following(
        self, symbol: str, ohlcv: Dict[str, List[float]], regime: str
    ) -> Optional[Dict[str, Any]]:
        """
        LONG:  EMA20 crosses above EMA50, ADX > 25, RSI in [40, 70]
        SHORT: EMA20 crosses below EMA50, ADX > 25, RSI in [30, 60]
        Stop:  2× ATR from entry
        Target: 4× ATR from entry (2:1 R:R)
        Filter: TRENDING_VOLATILE or EXPANSION_BREAKOUT regimes only
        """
        # Regime filter: only fire in trending/breakout regimes
        if regime not in ("TRENDING_VOLATILE", "EXPANSION_BREAKOUT"):
            return None

        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]

        if len(closes) < 51:
            return None

        ind = self.indicators

        # Current and previous EMA values
        ema20_now = ind.calculate_ema(closes, 20)
        ema50_now = ind.calculate_ema(closes, 50)
        ema20_prev = ind.calculate_ema(closes[:-1], 20)
        ema50_prev = ind.calculate_ema(closes[:-1], 50)

        # ADX and RSI
        adx = ind.calculate_adx(highs, lows, closes, period=14)
        rsi = ind.calculate_rsi(closes, period=14)
        atr = ind.calculate_atr(highs, lows, closes, period=14)

        if atr <= 0:
            return None

        # ADX filter: need sufficient trend strength
        if adx < 20:
            return None

        entry_price = closes[-1]
        direction = None

        # Bullish crossover: EMA20 crosses above EMA50 (was below, now above)
        if ema20_now > ema50_now and ema20_prev <= ema50_prev:
            # RSI range filter for LONG: only if RSI in [40, 70]
            if 40 <= rsi <= 70:
                direction = "LONG"

        # Bearish crossover: EMA20 crosses below EMA50 (was above, now below)
        elif ema20_now < ema50_now and ema20_prev >= ema50_prev:
            # RSI range filter for SHORT: only if RSI in [30, 60]
            if 30 <= rsi <= 60:
                direction = "SHORT"

        if not direction:
            return None

        if direction == "LONG":
            stop = entry_price - 2 * atr
            target = entry_price + 4 * atr
        else:
            stop = entry_price + 2 * atr
            target = entry_price - 4 * atr

        return {
            "direction": direction,
            "entry_price": round(entry_price, 4),
            "stop_price": round(stop, 4),
            "target_price": round(target, 4),
            "confidence": min(0.9, 0.5 + (adx - 25) / 100),
            "indicators": {"ema20": ema20_now, "ema50": ema50_now, "adx": adx, "rsi": rsi, "atr": atr},
        }

    # ══════════════════════════════════════════════════════════════
    # STRATEGY 2: MEAN REVERSION (Bollinger Bounce)
    # ══════════════════════════════════════════════════════════════

    def _strategy_mean_reversion(
        self, symbol: str, ohlcv: Dict[str, List[float]], regime: str
    ) -> Optional[Dict[str, Any]]:
        """
        LONG:  Price ≤ Lower BB, RSI < 30, volume > 1.5× avg
        SHORT: Price ≥ Upper BB, RSI > 70, volume > 1.5× avg
        Stop:  1.5× ATR from entry
        Target: Middle Bollinger Band
        Filter: MEAN_REVERTING or LOW_VOL_RANGE regimes only
        """
        if regime not in ("MEAN_REVERTING", "LOW_VOL_RANGE"):
            return None

        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv.get("volumes", [])

        if len(closes) < 21:
            return None

        ind = self.indicators

        bb = ind.calculate_bollinger_bands(closes, period=20, num_std=2.0)
        if not bb or bb[0] == 0:
            return None

        rsi = ind.calculate_rsi(closes, period=14)
        atr = ind.calculate_atr(highs, lows, closes, period=14)
        entry_price = closes[-1]

        # Volume spike check
        volume_ok = True
        if volumes and len(volumes) >= 20:
            avg_vol = sum(volumes[-20:]) / 20
            volume_ok = volumes[-1] > 1.5 * avg_vol if avg_vol > 0 else False

        if not volume_ok or atr <= 0:
            return None

        direction = None
        upper = bb[0]
        lower = bb[2]
        middle = bb[1]

        if entry_price <= lower and rsi < 30:
            direction = "LONG"
        elif entry_price >= upper and rsi > 70:
            direction = "SHORT"

        if not direction:
            return None

        if direction == "LONG":
            stop = entry_price - 1.5 * atr
            target = middle
        else:
            stop = entry_price + 1.5 * atr
            target = middle

        return {
            "direction": direction,
            "entry_price": round(entry_price, 4),
            "stop_price": round(stop, 4),
            "target_price": round(target, 4),
            "confidence": min(0.85, 0.5 + abs(rsi - 50) / 100),
            "indicators": {"bb_upper": upper, "bb_lower": lower, "bb_middle": middle, "rsi": rsi, "atr": atr},
        }

    # ══════════════════════════════════════════════════════════════
    # STRATEGY 3: BREAKOUT (Volatility Expansion)
    # ══════════════════════════════════════════════════════════════

    def _strategy_breakout(
        self, symbol: str, ohlcv: Dict[str, List[float]], regime: str
    ) -> Optional[Dict[str, Any]]:
        """
        LONG:  Close > 20-period high, ATR percentile > 70, OBV rising
        SHORT: Close < 20-period low, ATR percentile > 70, OBV falling
        Stop:  Entry candle low (LONG) or high (SHORT)
        Target: 3× ATR from entry
        Filter: EXPANSION_BREAKOUT regime only
        """
        if regime != "EXPANSION_BREAKOUT":
            return None

        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv.get("volumes", [])

        if len(closes) < 21:
            return None

        ind = self.indicators

        atr = ind.calculate_atr(highs, lows, closes, period=14)
        entry_price = closes[-1]

        # 20-period high/low (excluding current bar)
        period_high = max(highs[-21:-1]) if len(highs) >= 21 else max(highs[:-1])
        period_low = min(lows[-21:-1]) if len(lows) >= 21 else min(lows[:-1])

        # ATR percentile (is current ATR in top 30% of recent ATRs?)
        atr_values = []
        for i in range(min(100, len(closes) - 14)):
            a = ind.calculate_atr(
                highs[i:i+15], lows[i:i+15], closes[i:i+15], period=14
            )
            if a > 0:
                atr_values.append(a)

        atr_percentile = 50
        if atr_values and atr > 0:
            below_count = sum(1 for v in atr_values if v < atr)
            atr_percentile = (below_count / len(atr_values)) * 100

        if atr_percentile < 70 or atr <= 0:
            return None

        # OBV direction (simplified: compare last 5 bars vs previous 5)
        obv_rising = True
        if volumes and len(volumes) >= 10:
            recent_vol = sum(volumes[-5:])
            prev_vol = sum(volumes[-10:-5])
            obv_rising = recent_vol > prev_vol

        direction = None

        if entry_price > period_high and obv_rising:
            direction = "LONG"
        elif entry_price < period_low and not obv_rising:
            direction = "SHORT"

        if not direction:
            return None

        if direction == "LONG":
            stop = lows[-1]  # Entry candle low
            target = entry_price + 3 * atr
        else:
            stop = highs[-1]  # Entry candle high
            target = entry_price - 3 * atr

        # Safety: ensure stop is not too tight
        min_stop_distance = atr * 0.5
        if abs(entry_price - stop) < min_stop_distance:
            if direction == "LONG":
                stop = entry_price - min_stop_distance
            else:
                stop = entry_price + min_stop_distance

        return {
            "direction": direction,
            "entry_price": round(entry_price, 4),
            "stop_price": round(stop, 4),
            "target_price": round(target, 4),
            "confidence": min(0.8, 0.5 + (atr_percentile - 70) / 100),
            "indicators": {"period_high": period_high, "period_low": period_low, "atr": atr, "atr_percentile": atr_percentile},
        }

    # ══════════════════════════════════════════════════════════════
    # STRATEGY 4: FAISS PATTERN SIMILARITY
    # ══════════════════════════════════════════════════════════════

    def _strategy_faiss_pattern(
        self, symbol: str, ohlcv: Dict[str, List[float]], regime: str
    ) -> Optional[Dict[str, Any]]:
        """
        1. FeatureEngine.extract() → 15-dim vector
        2. SimilarityEngine.query(vector, K=50) → similar pattern IDs
        3. PatternStore.get outcomes → forward outcomes
        4. ProbabilityEngine.aggregate → probability + R
        5. If passes gates → generate signal
        """
        if not all([self.feature_engine, self.similarity_engine,
                     self.pattern_store, self.probability_engine]):
            return None

        closes = ohlcv["closes"]
        highs = ohlcv["highs"]
        lows = ohlcv["lows"]
        volumes = ohlcv.get("volumes", [])

        if len(closes) < 50:
            return None

        try:
            # Step 1: Extract feature vector
            features = self.feature_engine.extract(
                closes=closes, highs=highs, lows=lows, volumes=volumes
            )
            if not features or len(features) < 10:
                return None

            # Step 2: Query similar patterns
            matches = self.similarity_engine.query(features, k=50)
            if not matches or len(matches) < 10:
                return None

            # Step 3: Get forward outcomes for matched patterns
            pattern_ids = [m.get("id", m.get("pattern_id", i)) for i, m in enumerate(matches)]
            outcomes = self.pattern_store.get_outcomes_batch(pattern_ids)
            if not outcomes or len(outcomes) < 10:
                return None

            # Step 4: Aggregate probabilities
            forward_returns = [o.get("forward_return", 0.0) for o in outcomes if o]
            if not forward_returns:
                return None

            positive_count = sum(1 for r in forward_returns if r > 0)
            win_probability = positive_count / len(forward_returns)
            avg_return = sum(forward_returns) / len(forward_returns)

            # Gate: need > 60% win rate AND positive expected value
            if win_probability < 0.60 or avg_return <= 0:
                return None

            entry_price = closes[-1]
            atr = self.indicators.calculate_atr(highs, lows, closes, period=14)
            if atr <= 0:
                return None

            direction = "LONG" if avg_return > 0 else "SHORT"

            if direction == "LONG":
                stop = entry_price - 2 * atr
                target = entry_price + abs(avg_return) * entry_price
            else:
                stop = entry_price + 2 * atr
                target = entry_price - abs(avg_return) * entry_price

            return {
                "direction": direction,
                "entry_price": round(entry_price, 4),
                "stop_price": round(stop, 4),
                "target_price": round(target, 4),
                "confidence": round(win_probability, 4),
                "indicators": {
                    "pattern_matches": len(matches),
                    "win_probability": win_probability,
                    "avg_forward_return": avg_return,
                },
            }

        except Exception as e:
            self.logger.error(f"FAISS strategy error for {symbol}: {e}")
            return None
