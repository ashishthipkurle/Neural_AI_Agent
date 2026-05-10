"""
Pattern Database Builder — FAISS Pattern Population.

Builds historical pattern database for Strategy 4 (FAISS Pattern Similarity).
Processes 2 years of historical candles per symbol to create 50K+ patterns.

Pipeline per symbol:
    1. Backfill historical candles
    2. Slide a window across the data
    3. Detect regime on each window
    4. Extract 15-dim feature vector (FeatureEngine)
    5. Compute forward outcomes (PatternStore)
    6. Bulk-add to PatternStore + FAISS index

No LLM. Fully deterministic.
"""
import time
import logging
from typing import Dict, Any, List, Optional


class PatternDatabaseBuilder:
    """
    Populates the FAISS-backed pattern database from historical data.
    """

    def __init__(
        self,
        market_data_feed=None,
        feature_engine=None,
        pattern_store=None,
        similarity_engine=None,
        regime_switcher=None,
        indicators_engine=None,
    ) -> None:
        self.logger = logging.getLogger("PatternBuilder")
        self.data_feed = market_data_feed
        self.feature_engine = feature_engine
        self.pattern_store = pattern_store
        self.similarity_engine = similarity_engine
        self.regime = regime_switcher
        self.indicators = indicators_engine

    def build_full_database(
        self,
        symbols: List[str],
        timeframes: List[str] = None,
        days: int = 730,
        window_size: int = 50,
        forward_bars: int = 20,
    ) -> Dict[str, Any]:
        """
        Build the full pattern database for all symbols and timeframes.
        Returns statistics about the build.
        """
        if timeframes is None:
            timeframes = ["15m", "1h"]

        total_patterns = 0
        stats = {}

        for symbol in symbols:
            symbol_count = 0
            for tf in timeframes:
                count = self._build_for_symbol(symbol, tf, days, window_size, forward_bars)
                symbol_count += count
                self.logger.info(f"Built {count} patterns for {symbol}/{tf}")

            stats[symbol] = symbol_count
            total_patterns += symbol_count

        self.logger.info(f"Pattern database complete: {total_patterns} total patterns")
        return {"total_patterns": total_patterns, "per_symbol": stats}

    def update_incremental(
        self,
        symbol: str,
        timeframe: str = "15m",
        window_size: int = 50,
        forward_bars: int = 20,
    ) -> int:
        """
        Add new patterns from recently ingested candles.
        Called hourly by the autonomous loop.
        """
        return self._build_for_symbol(symbol, timeframe, days=7, window_size=window_size, forward_bars=forward_bars)

    def _build_for_symbol(
        self,
        symbol: str,
        timeframe: str,
        days: int,
        window_size: int,
        forward_bars: int,
    ) -> int:
        """Build patterns for a single symbol/timeframe pair."""
        if not all([self.data_feed, self.feature_engine, self.indicators]):
            self.logger.warning("Missing engines, skipping pattern build")
            return 0

        try:
            # Get historical data
            ohlcv = self.data_feed.get_ohlcv_arrays(symbol, timeframe, limit=days * 26)
            closes = ohlcv.get("closes", [])
            highs = ohlcv.get("highs", [])
            lows = ohlcv.get("lows", [])
            volumes = ohlcv.get("volumes", [])

            if len(closes) < window_size + forward_bars + 10:
                return 0

            count = 0
            max_idx = len(closes) - forward_bars

            for i in range(window_size, max_idx):
                window_closes = closes[i - window_size:i]
                window_highs = highs[i - window_size:i]
                window_lows = lows[i - window_size:i]
                window_volumes = volumes[i - window_size:i] if volumes else []

                # Extract features
                try:
                    features = self.feature_engine.extract(
                        closes=window_closes,
                        highs=window_highs,
                        lows=window_lows,
                        volumes=window_volumes,
                    )
                except Exception:
                    continue

                if not features or len(features) < 10:
                    continue

                # Compute forward outcome
                forward_closes = closes[i:i + forward_bars]
                if len(forward_closes) < forward_bars:
                    continue

                entry_price = closes[i]
                exit_price = forward_closes[-1]
                forward_return = (exit_price - entry_price) / entry_price if entry_price > 0 else 0

                # Detect regime at this point
                regime = "QUIET"
                if self.regime and len(window_highs) >= 15:
                    try:
                        regime = self.regime.detect_regime(window_highs, window_lows, window_closes)
                    except Exception:
                        pass

                # Add to pattern store
                if self.pattern_store:
                    try:
                        self.pattern_store.add_pattern(
                            features=features,
                            outcome={
                                "forward_return": forward_return,
                                "max_favorable": max(forward_closes) / entry_price - 1 if entry_price > 0 else 0,
                                "max_adverse": min(forward_closes) / entry_price - 1 if entry_price > 0 else 0,
                                "regime": regime,
                                "symbol": symbol,
                                "timeframe": timeframe,
                            },
                        )
                        count += 1
                    except Exception:
                        continue

            # Rebuild FAISS index after bulk add
            if self.similarity_engine and count > 0:
                try:
                    self.similarity_engine.rebuild_index()
                except Exception as e:
                    self.logger.warning(f"FAISS rebuild failed: {e}")

            return count

        except Exception as e:
            self.logger.error(f"Pattern build failed for {symbol}/{timeframe}: {e}")
            return 0
