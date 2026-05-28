"""
Market Data Feed — Historical & Real-Time Data Provider.

Architecture:
    - US Market: Alpaca REST API (primary), yfinance (fallback)
    - Indian Market: Upstox API v2 (primary), yfinance (fallback)
    - In-memory cache: last 500 candles per symbol/timeframe
    - Data freshness detection: skip stale symbols
    - Candle-close-aligned scheduling helpers
    - Asset-type-aware market hours (crypto 24/7, equity market hours)

All timestamps are UTC epoch seconds.
No LLM. Fully deterministic.
"""
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    yf = None
    YFINANCE_AVAILABLE = False


class MarketDataFeed:
    """
    Unified data provider for the autonomous trading system.
    Routes to Upstox for Indian market, Alpaca for US market.
    """

    def __init__(self, broker_adapter, database, data_ingestion_worker=None, upstox_adapter=None) -> None:
        self.logger = logging.getLogger("MarketDataFeed")
        self.broker = broker_adapter
        self.database = database
        self.data_worker = data_ingestion_worker
        self.upstox = upstox_adapter  # UpstoxAdapter for Indian market

        # In-memory cache: {(symbol, timeframe): [candle_dicts]}
        self._cache: Dict[tuple, List[Dict[str, Any]]] = {}
        self._cache_max_size = 500

        # Staleness tracking: {symbol: last_bar_timestamp_utc}
        self._last_bar_timestamp: Dict[str, float] = {}

        # Current market context (set by AutonomousTradingLoop)
        self._active_market: str = "USA"

        # Timeframe to yfinance interval mapping
        self._yf_interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1h", "1d": "1d",
        }

        # Timeframe to Alpaca timeframe mapping
        self._alpaca_tf_map = {
            "1m": "1Min", "5m": "5Min", "15m": "15Min", "30m": "30Min",
            "1h": "1Hour", "1d": "1Day",
        }

        # yfinance symbol mapping for Indian market (display name → yfinance ticker)
        self._yf_indian_map = {
            "NIFTY 50": "^NSEI",
            "NIFTY50": "^NSEI",
            "SENSEX": "^BSESN",
            "BANKNIFTY": "^NSEBANK",
            "NIFTY BANK": "^NSEBANK",
            "RELIANCE": "RELIANCE.NS",
            "TCS": "TCS.NS",
            "HDFCBANK": "HDFCBANK.NS",
            "INFY": "INFY.NS",
            "SBIN": "SBIN.NS",
            "ICICIBANK": "ICICIBANK.NS",
            "HINDUNILVR": "HINDUNILVR.NS",
            "BHARTIARTL": "BHARTIARTL.NS",
            "ITC": "ITC.NS",
            "KOTAKBANK": "KOTAKBANK.NS",
            "LT": "LT.NS",
            "AXISBANK": "AXISBANK.NS",
            "WIPRO": "WIPRO.NS",
            "TATAMOTORS": "TATAMOTORS.NS",
            "ADANIENT": "ADANIENT.NS",
            "MARUTI": "MARUTI.NS",
            "SUNPHARMA": "SUNPHARMA.NS",
            "TATASTEEL": "TATASTEEL.NS",
            "ULTRACEMCO": "ULTRACEMCO.NS",
            "NTPC": "NTPC.NS",
            "POWERGRID": "POWERGRID.NS",
            "ONGC": "ONGC.NS",
            "BAJFINANCE": "BAJFINANCE.NS",
            "HCLTECH": "HCLTECH.NS",
            "ASIANPAINT": "ASIANPAINT.NS",
            "TITAN": "TITAN.NS",
            "TECHM": "TECHM.NS",
        }

    # ══════════════════════════════════════════════════════════════
    # MARKET CONTEXT
    # ══════════════════════════════════════════════════════════════

    def set_active_market(self, market: str) -> None:
        """Set the active market (USA or IND) for data routing."""
        self._active_market = market.upper()
        self.logger.info(f"MarketDataFeed active market set to: {self._active_market}")

    def _is_indian_symbol(self, symbol: str) -> bool:
        """Detect if a symbol belongs to the Indian market."""
        # Explicit Indian market mode
        if self._active_market == "IND":
            return True
        # Symbol pattern detection
        indian_patterns = (".NS", ".BO", "^NSEI", "^BSESN", "NIFTY")
        return any(p in symbol.upper() for p in indian_patterns)

    def _resolve_yf_symbol(self, symbol: str) -> str:
        """Resolve a display symbol to its yfinance ticker.
        
        Uses the Indian mapping table for known symbols, 
        appends .NS for unmapped NSE stocks, returns as-is for US stocks.
        """
        # Already a valid yfinance symbol
        if symbol.startswith("^") or ".NS" in symbol or ".BO" in symbol:
            return symbol
        
        # Check mapping table
        if symbol.upper() in self._yf_indian_map:
            return self._yf_indian_map[symbol.upper()]
        
        # If in Indian market mode, append .NS as default
        if self._active_market == "IND":
            return f"{symbol}.NS"
        
        return symbol

    # ══════════════════════════════════════════════════════════════
    # HISTORICAL BACKFILL
    # ══════════════════════════════════════════════════════════════

    def backfill_historical(
        self, symbol: str, timeframe: str = "15m", days: int = 365
    ) -> int:
        """
        Fetch historical bars and persist to database.
        Routes to Upstox for Indian symbols, Alpaca for US.
        Falls back to yfinance if primary source fails.
        Returns total candle count saved.
        """
        instrument_id = self.database.get_or_create_instrument(symbol)
        candles = []

        # ── Route based on market ──
        if self._is_indian_symbol(symbol):
            # Primary: Upstox API
            candles = self._fetch_upstox_historical(symbol, timeframe, days)
            # Fallback: yfinance (use proper symbol mapping)
            if not candles and YFINANCE_AVAILABLE:
                self.logger.info(f"Upstox backfill failed for {symbol}, trying yfinance...")
                yf_symbol = self._resolve_yf_symbol(symbol)
                candles = self._fetch_yfinance_historical(yf_symbol, timeframe, days)
        else:
            # Primary: Alpaca (US market)
            candles = self._fetch_alpaca_historical(symbol, timeframe, days)
            # Fallback: yfinance
            if not candles and YFINANCE_AVAILABLE:
                self.logger.info(f"Alpaca backfill failed for {symbol}, trying yfinance...")
                candles = self._fetch_yfinance_historical(symbol, timeframe, days)

        if not candles:
            self.logger.error(f"No historical data available for {symbol}")
            return 0

        # Persist to database
        count = self.database.save_candles(instrument_id, timeframe, candles)

        # Update cache
        self._update_cache(symbol, timeframe, candles)

        self.logger.info(f"Backfilled {count} candles for {symbol}/{timeframe}")
        return count

    def _fetch_alpaca_historical(
        self, symbol: str, timeframe: str, days: int
    ) -> List[Dict[str, Any]]:
        """Fetch historical bars from Alpaca."""
        alpaca_tf = self._alpaca_tf_map.get(timeframe)
        if not alpaca_tf or not self.broker.is_connected:
            return []

        try:
            # Alpaca limits to 10000 bars per request
            all_bars = self.broker.get_bars(symbol, alpaca_tf, limit=min(days * 26, 10000))
            if all_bars:
                self.logger.debug(f"Alpaca returned {len(all_bars)} bars for {symbol}")
            return all_bars
        except Exception as e:
            self.logger.warning(f"Alpaca historical fetch failed for {symbol}: {e}")
            return []

    def _fetch_yfinance_historical(
        self, symbol: str, timeframe: str, days: int
    ) -> List[Dict[str, Any]]:
        """Fetch historical bars from yfinance as fallback."""
        yf_interval = self._yf_interval_map.get(timeframe)
        if not yf_interval:
            return []

        try:
            # yfinance period mapping
            if days <= 7:
                period = "7d"
            elif days <= 30:
                period = "1mo"
            elif days <= 90:
                period = "3mo"
            elif days <= 180:
                period = "6mo"
            elif days <= 365:
                period = "1y"
            else:
                period = "2y"

            # yfinance has interval limits for intraday
            # 1m: max 7d, 5m/15m/30m: max 60d, 1h: max 730d
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=yf_interval)

            if df.empty:
                return []

            candles = []
            for idx, row in df.iterrows():
                candles.append({
                    "timestamp": idx.timestamp() if hasattr(idx, 'timestamp') else time.time(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row.get("Volume", 0)),
                })

            self.logger.debug(f"yfinance returned {len(candles)} bars for {symbol}")
            return candles

        except Exception as e:
            self.logger.warning(f"yfinance fetch failed for {symbol}: {e}")
            return []

    # ══════════════════════════════════════════════════════════════
    # UPSTOX DATA (INDIAN MARKET)
    # ══════════════════════════════════════════════════════════════

    def _fetch_upstox_historical(
        self, symbol: str, timeframe: str, days: int
    ) -> List[Dict[str, Any]]:
        """Fetch historical bars from Upstox API for Indian stocks."""
        if not self.upstox or not self.upstox.is_connected:
            self.logger.debug(f"Upstox not available for {symbol}")
            return []

        try:
            candles = self.upstox.get_bars(symbol, timeframe, limit=min(days * 26, 5000))
            if candles:
                self.logger.debug(f"Upstox returned {len(candles)} bars for {symbol}")
            return candles
        except Exception as e:
            self.logger.warning(f"Upstox historical fetch failed for {symbol}: {e}")
            return []

    # ══════════════════════════════════════════════════════════════
    # LATEST DATA ACCESS
    # ══════════════════════════════════════════════════════════════

    def get_latest_bars(
        self, symbol: str, timeframe: str = "15m", limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get most recent bars. Checks cache first, then broker/Upstox, then database.
        Routes Indian symbols to Upstox, US symbols to Alpaca.
        Falls back to yfinance with periodic refresh when primary brokers are offline.
        Returns list of candle dicts (oldest first).
        """
        cache_key = (symbol, timeframe)
        is_indian = self._is_indian_symbol(symbol)
        
        # Determine if a primary (real-time) broker is available for this symbol
        has_live_broker = False
        if is_indian and self.upstox and self.upstox.is_connected:
            has_live_broker = True
        elif not is_indian and self.broker.is_connected:
            has_live_broker = True

        # ── Route: Indian market via Upstox (live) ──
        if is_indian and self.upstox and self.upstox.is_connected:
            bars = self.upstox.get_bars(symbol, timeframe, limit=limit)
            if bars:
                self._update_cache(symbol, timeframe, bars)
                instrument_id = self.database.get_or_create_instrument(symbol)
                self.database.save_candles(instrument_id, timeframe, bars)
                return bars

        # ── Route: US market via Alpaca (live) ──
        if not is_indian:
            alpaca_tf = self._alpaca_tf_map.get(timeframe)
            if alpaca_tf and self.broker.is_connected:
                bars = self.broker.get_bars(symbol, alpaca_tf, limit=limit)
                if bars:
                    self._update_cache(symbol, timeframe, bars)
                    instrument_id = self.database.get_or_create_instrument(symbol)
                    self.database.save_candles(instrument_id, timeframe, bars)
                    return bars

        # ── Fallback: yfinance live refresh (when no primary broker) ──
        # Use a per-symbol cooldown to avoid hammering yfinance on every poll
        if not has_live_broker and YFINANCE_AVAILABLE:
            cooldown_key = f"_yf_last_fetch_{symbol}_{timeframe}"
            last_yf_fetch = getattr(self, cooldown_key, 0.0)
            yf_cooldown = 5  # seconds between yfinance refreshes

            if time.time() - last_yf_fetch >= yf_cooldown:
                yf_symbol = self._resolve_yf_symbol(symbol)
                self.logger.info(f"yfinance live refresh: {symbol} → {yf_symbol} (tf={timeframe})")
                bars = self._fetch_yfinance_historical(yf_symbol, timeframe, days=7)
                setattr(self, cooldown_key, time.time())
                if bars:
                    self._update_cache(symbol, timeframe, bars)
                    instrument_id = self.database.get_or_create_instrument(symbol)
                    self.database.save_candles(instrument_id, timeframe, bars)
                    return bars[-limit:]

        # ── Use cache if available ──
        if cache_key in self._cache and self._cache[cache_key]:
            return self._cache[cache_key][-limit:]

        # ── Fall back to database ──
        instrument_id = self.database.get_or_create_instrument(symbol)
        db_candles = self.database.get_candles(instrument_id, timeframe, limit=limit)
        if db_candles:
            self._update_cache(symbol, timeframe, db_candles)
            return db_candles

        # ── Last resort: force yfinance fetch ──
        if YFINANCE_AVAILABLE:
            yf_symbol = self._resolve_yf_symbol(symbol)
            self.logger.info(f"Trying yfinance last-resort fetch: {symbol} → {yf_symbol}")
            bars = self._fetch_yfinance_historical(yf_symbol, timeframe, days=30)
            if bars:
                self._update_cache(symbol, timeframe, bars)
                instrument_id = self.database.get_or_create_instrument(symbol)
                self.database.save_candles(instrument_id, timeframe, bars)
                return bars[-limit:]

        return []

    def get_ohlcv_arrays(
        self, symbol: str, timeframe: str = "15m", limit: int = 200
    ) -> Dict[str, List[float]]:
        """
        Primary data access: returns separate arrays for indicators engine.
        {opens, highs, lows, closes, volumes}
        """
        bars = self.get_latest_bars(symbol, timeframe, limit)
        if not bars:
            return {"opens": [], "highs": [], "lows": [], "closes": [], "volumes": []}

        return {
            "opens": [b["open"] for b in bars],
            "highs": [b["high"] for b in bars],
            "lows": [b["low"] for b in bars],
            "closes": [b["close"] for b in bars],
            "volumes": [b.get("volume", 0.0) for b in bars],
        }

    # ══════════════════════════════════════════════════════════════
    # DATA FRESHNESS (Gap 10 fix)
    # ══════════════════════════════════════════════════════════════

    def is_data_fresh(self, symbol: str, max_age_seconds: int = 900) -> bool:
        """
        Returns False if the last candle for this symbol is older than max_age_seconds.
        Used to skip evaluation of symbols with stale data.
        """
        last_ts = self._last_bar_timestamp.get(symbol, 0)
        if last_ts == 0:
            return False
        age = time.time() - last_ts
        return age < max_age_seconds

    def get_data_age(self, symbol: str) -> float:
        """Returns seconds since last bar was received for this symbol."""
        last_ts = self._last_bar_timestamp.get(symbol, 0)
        return time.time() - last_ts if last_ts > 0 else float("inf")

    # ══════════════════════════════════════════════════════════════
    # CANDLE-CLOSE ALIGNMENT (Gap 2 fix)
    # ══════════════════════════════════════════════════════════════

    @staticmethod
    def seconds_until_next_candle_close(timeframe: str = "15m") -> int:
        """
        Returns seconds until the next candle close boundary.
        For 15m: fires at :00, :15, :30, :45.
        For 1h: fires at :00.
        """
        interval_map = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}
        interval_minutes = interval_map.get(timeframe, 15)

        now = datetime.now(timezone.utc)
        minutes_past = now.minute % interval_minutes
        remaining_minutes = interval_minutes - minutes_past
        remaining_seconds = remaining_minutes * 60 - now.second

        # If exactly at boundary, wait full interval
        if remaining_seconds <= 0:
            remaining_seconds = interval_minutes * 60

        return remaining_seconds

    # ══════════════════════════════════════════════════════════════
    # MARKET HOURS (Gap 12 fix)
    # ══════════════════════════════════════════════════════════════

    def should_trade(self, symbol: str, asset_type: str = "EQUITY", mode: str = "paper") -> bool:
        """
        Asset-type-aware market hours check.
        Crypto: always tradeable (24/7).
        Paper mode: always tradeable (for testing/demo).
        Equity (live): only during respective market hours.
        """
        if asset_type.upper() in ("CRYPTO", "CRYPTOCURRENCY"):
            return True
        # Paper mode: always allow trading for demo/testing
        if mode == "paper":
            return True
        # Indian market hours check
        if self._is_indian_symbol(symbol) and self.upstox:
            return self.upstox.is_market_open()
        return self.broker.is_market_open()

    # ══════════════════════════════════════════════════════════════
    # CACHE MANAGEMENT
    # ══════════════════════════════════════════════════════════════

    def _update_cache(
        self, symbol: str, timeframe: str, candles: List[Dict[str, Any]]
    ) -> None:
        """Update in-memory cache and staleness tracker."""
        if not candles:
            return

        cache_key = (symbol, timeframe)
        existing = self._cache.get(cache_key, [])

        # Merge by timestamp (avoid duplicates)
        existing_ts = {c["timestamp"] for c in existing}
        new_candles = [c for c in candles if c["timestamp"] not in existing_ts]
        merged = existing + new_candles
        merged.sort(key=lambda c: c["timestamp"])

        # Trim to max size
        self._cache[cache_key] = merged[-self._cache_max_size:]

        # Update staleness tracker
        if merged:
            self._last_bar_timestamp[symbol] = merged[-1]["timestamp"]

    def clear_cache(self, symbol: str = None) -> None:
        """Clear cache for a symbol or all symbols."""
        if symbol:
            keys_to_remove = [k for k in self._cache if k[0] == symbol]
            for k in keys_to_remove:
                del self._cache[k]
            self._last_bar_timestamp.pop(symbol, None)
        else:
            self._cache.clear()
            self._last_bar_timestamp.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        return {
            "cached_pairs": len(self._cache),
            "total_cached_candles": sum(len(v) for v in self._cache.values()),
            "tracked_symbols": len(self._last_bar_timestamp),
            "symbols": list(self._last_bar_timestamp.keys()),
        }
