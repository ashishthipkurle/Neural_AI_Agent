"""
Upstox Adapter — Indian Market Data Provider (NSE/BSE).

Provides real-time and historical OHLCV data for Indian equities
via the Upstox API v2.

Architecture:
    - OAuth2 code flow for authentication (token valid until 3:30 AM IST next day)
    - Historical candle endpoint for backfill
    - WebSocket streaming for real-time ticks (via protobuf)
    - Instrument key resolver (trading symbol → Upstox instrument_key)
    - Circuit breaker for resilience (same pattern as BrokerAdapter)

Environment variables:
    UPSTOX_API_KEY        — Client ID from Upstox developer console
    UPSTOX_API_SECRET     — Client secret
    UPSTOX_REDIRECT_URI   — OAuth redirect URI (default: http://127.0.0.1:8000/api/upstox/callback)
    UPSTOX_ACCESS_TOKEN   — Pre-generated access token (optional, skips OAuth)

No LLM. Fully deterministic.
"""

import os
import time
import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    import requests as req_lib
    REQUESTS_AVAILABLE = True
except ImportError:
    req_lib = None
    REQUESTS_AVAILABLE = False

try:
    import websocket as ws_lib
    WEBSOCKET_AVAILABLE = True
except ImportError:
    ws_lib = None
    WEBSOCKET_AVAILABLE = False


# ══════════════════════════════════════════════════════════════
# INSTRUMENT KEY MAPPINGS (NSE Equities & Indices)
# ══════════════════════════════════════════════════════════════

# Common Indian stocks: trading_symbol → instrument_key
# These are the ISIN-based keys required by Upstox API v2
DEFAULT_INSTRUMENT_MAP = {
    # ── Indices ──
    "NIFTY 50":     "NSE_INDEX|Nifty 50",
    "NIFTY50":      "NSE_INDEX|Nifty 50",
    "^NSEI":        "NSE_INDEX|Nifty 50",
    "NIFTY BANK":   "NSE_INDEX|Nifty Bank",
    "BANKNIFTY":    "NSE_INDEX|Nifty Bank",

    # ── Large-Cap Equities ──
    "RELIANCE":     "NSE_EQ|INE002A01018",
    "RELIANCE.NS":  "NSE_EQ|INE002A01018",
    "TCS":          "NSE_EQ|INE467B01029",
    "TCS.NS":       "NSE_EQ|INE467B01029",
    "HDFCBANK":     "NSE_EQ|INE040A01034",
    "HDFCBANK.NS":  "NSE_EQ|INE040A01034",
    "INFY":         "NSE_EQ|INE009A01021",
    "INFY.NS":      "NSE_EQ|INE009A01021",
    "SBIN":         "NSE_EQ|INE062A01020",
    "SBIN.NS":      "NSE_EQ|INE062A01020",
    "ICICIBANK":    "NSE_EQ|INE090A01021",
    "ICICIBANK.NS": "NSE_EQ|INE090A01021",
    "HINDUNILVR":   "NSE_EQ|INE030A01027",
    "HINDUNILVR.NS":"NSE_EQ|INE030A01027",
    "ITC":          "NSE_EQ|INE154A01025",
    "ITC.NS":       "NSE_EQ|INE154A01025",
    "KOTAKBANK":    "NSE_EQ|INE237A01028",
    "KOTAKBANK.NS": "NSE_EQ|INE237A01028",
    "LT":           "NSE_EQ|INE018A01030",
    "LT.NS":        "NSE_EQ|INE018A01030",
    "BHARTIARTL":   "NSE_EQ|INE397D01024",
    "BHARTIARTL.NS":"NSE_EQ|INE397D01024",
    "AXISBANK":     "NSE_EQ|INE238A01034",
    "AXISBANK.NS":  "NSE_EQ|INE238A01034",
    "WIPRO":        "NSE_EQ|INE075A01022",
    "WIPRO.NS":     "NSE_EQ|INE075A01022",
    "BAJFINANCE":   "NSE_EQ|INE296A01024",
    "BAJFINANCE.NS":"NSE_EQ|INE296A01024",
    "MARUTI":       "NSE_EQ|INE585B01010",
    "MARUTI.NS":    "NSE_EQ|INE585B01010",
    "HCLTECH":      "NSE_EQ|INE860A01027",
    "HCLTECH.NS":   "NSE_EQ|INE860A01027",
    "TATAMOTORS":   "NSE_EQ|INE155A01022",
    "TATAMOTORS.NS":"NSE_EQ|INE155A01022",
    "SUNPHARMA":    "NSE_EQ|INE044A01036",
    "SUNPHARMA.NS": "NSE_EQ|INE044A01036",
    "TITAN":        "NSE_EQ|INE280A01028",
    "TITAN.NS":     "NSE_EQ|INE280A01028",
    "ASIANPAINT":   "NSE_EQ|INE021A01026",
    "ASIANPAINT.NS":"NSE_EQ|INE021A01026",
    "ULTRACEMCO":   "NSE_EQ|INE481G01011",
    "ULTRACEMCO.NS":"NSE_EQ|INE481G01011",
    "TATASTEEL":    "NSE_EQ|INE081A01020",
    "TATASTEEL.NS": "NSE_EQ|INE081A01020",
    "POWERGRID":    "NSE_EQ|INE752E01010",
    "POWERGRID.NS": "NSE_EQ|INE752E01010",
    "NTPC":         "NSE_EQ|INE733E01010",
    "NTPC.NS":      "NSE_EQ|INE733E01010",
    "ONGC":         "NSE_EQ|INE213A01029",
    "ONGC.NS":      "NSE_EQ|INE213A01029",
    "ADANIENT":     "NSE_EQ|INE423A01024",
    "ADANIENT.NS":  "NSE_EQ|INE423A01024",
    "TECHM":        "NSE_EQ|INE669C01036",
    "TECHM.NS":     "NSE_EQ|INE669C01036",
    "M&M":          "NSE_EQ|INE101A01026",
    "M&M.NS":       "NSE_EQ|INE101A01026",
    "JSWSTEEL":     "NSE_EQ|INE019A01038",
    "JSWSTEEL.NS":  "NSE_EQ|INE019A01038",
}

# Timeframe mapping: our internal format → Upstox interval
# Upstox API v2 only supports: 1minute, 30minute, day, week, month
# For unsupported intervals (5m, 10m, 15m), we fetch 1minute data and aggregate
TIMEFRAME_MAP = {
    "1m":  "1minute",
    "5m":  "1minute",   # Fetch 1m, aggregate to 5m
    "10m": "1minute",   # Fetch 1m, aggregate to 10m
    "15m": "1minute",   # Fetch 1m, aggregate to 15m
    "30m": "30minute",
    "1h":  "30minute",  # Fetch 30m, aggregate to 1h
    "1d":  "day",
    "1w":  "week",
    "1M":  "month",
}

# Aggregation targets: which intervals need post-fetch aggregation
# Maps our internal timeframe → number of base candles to merge
AGGREGATION_MAP = {
    "5m":  5,    # 5 x 1minute = 5 minutes
    "10m": 10,   # 10 x 1minute = 10 minutes
    "15m": 15,   # 15 x 1minute = 15 minutes
    "1h":  2,    # 2 x 30minute = 1 hour
}


class UpstoxAdapter:
    """
    Upstox API v2 client for Indian market data.

    Provides:
        - OAuth2 authentication flow
        - Historical OHLCV candle data
        - Real-time WebSocket streaming
        - Instrument key resolution
    """

    BASE_URL = "https://api.upstox.com/v2"

    def __init__(self) -> None:
        self.logger = logging.getLogger("UpstoxAdapter")

        # Credentials from environment
        self.api_key = os.environ.get("UPSTOX_API_KEY", "")
        self.api_secret = os.environ.get("UPSTOX_API_SECRET", "")
        self.redirect_uri = os.environ.get(
            "UPSTOX_REDIRECT_URI",
            "http://127.0.0.1:8000/api/upstox/callback"
        )

        # Access token (can be pre-set or obtained via OAuth)
        self._access_token = os.environ.get("UPSTOX_ACCESS_TOKEN", "")
        self._token_expiry: float = 0.0  # UTC timestamp when token expires
        self._token_file = Path(__file__).resolve().parent.parent / "agent_data" / "upstox_token.json"

        # Instrument mapping
        self._instrument_map: Dict[str, str] = dict(DEFAULT_INSTRUMENT_MAP)

        # Connection state
        self._connected = False
        self._ws_thread: Optional[threading.Thread] = None
        self._ws_running = False
        self._live_quotes: Dict[str, Dict[str, Any]] = {}

        # Rate limiting
        self._last_request_time = 0.0
        self._min_request_interval = 0.25  # 250ms between requests

        # Try to load persisted token
        self._load_token()

        if not REQUESTS_AVAILABLE:
            self.logger.warning("requests library not installed. Upstox adapter disabled.")
            return

        if not self.api_key:
            self.logger.warning("UPSTOX_API_KEY not configured. Indian market data disabled.")
            return

        if self._access_token:
            self._connected = True
            self.logger.info("UpstoxAdapter initialized with pre-configured access token")
        else:
            self.logger.info(
                "UpstoxAdapter initialized — awaiting OAuth login. "
                f"Visit: {self.get_login_url()}"
            )

    # ══════════════════════════════════════════════════════════════
    # PROPERTIES
    # ══════════════════════════════════════════════════════════════

    @property
    def is_connected(self) -> bool:
        """Returns True if we have a valid access token."""
        if not self._access_token:
            return False
        # Check token expiry (tokens expire at 3:30 AM IST next day)
        if self._token_expiry > 0 and time.time() > self._token_expiry:
            self.logger.warning("Upstox access token expired")
            self._connected = False
            return False
        return self._connected

    # ══════════════════════════════════════════════════════════════
    # OAUTH2 AUTHENTICATION
    # ══════════════════════════════════════════════════════════════

    def get_login_url(self) -> str:
        """Generate the OAuth2 login URL for user to authorize."""
        return (
            f"{self.BASE_URL}/login/authorization/dialog"
            f"?response_type=code"
            f"&client_id={self.api_key}"
            f"&redirect_uri={self.redirect_uri}"
        )

    def exchange_code_for_token(self, auth_code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        Called after user authorizes via the login URL.
        """
        if not REQUESTS_AVAILABLE:
            return {"error": True, "message": "requests library not available"}

        url = f"{self.BASE_URL}/login/authorization/token"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "code": auth_code,
            "client_id": self.api_key,
            "client_secret": self.api_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            response = req_lib.post(url, headers=headers, data=data, timeout=30)
            if response.status_code == 200:
                result = response.json()
                self._access_token = result.get("access_token", "")
                # Token expires at 3:30 AM IST next day
                # IST = UTC + 5:30, so 3:30 AM IST = 22:00 UTC previous day
                now_utc = datetime.now(timezone.utc)
                # Next 3:30 AM IST = next 22:00 UTC
                next_expiry = now_utc.replace(hour=22, minute=0, second=0, microsecond=0)
                if now_utc.hour >= 22:
                    next_expiry += timedelta(days=1)
                self._token_expiry = next_expiry.timestamp()
                self._connected = True

                # Persist token
                self._save_token()

                self.logger.info("Upstox access token obtained successfully!")
                return {
                    "error": False,
                    "access_token": self._access_token[:20] + "...",
                    "expires_at": next_expiry.isoformat(),
                }
            else:
                err_msg = response.text
                self.logger.error(f"Token exchange failed: {response.status_code} — {err_msg}")
                return {"error": True, "message": err_msg, "status": response.status_code}
        except Exception as e:
            self.logger.error(f"Token exchange exception: {e}")
            return {"error": True, "message": str(e)}

    def _save_token(self) -> None:
        """Persist access token to disk for reuse across restarts."""
        try:
            self._token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._token_file, "w") as f:
                json.dump({
                    "access_token": self._access_token,
                    "token_expiry": self._token_expiry,
                    "saved_at": time.time(),
                }, f)
            self.logger.debug("Upstox token persisted to disk")
        except Exception as e:
            self.logger.warning(f"Failed to persist token: {e}")

    def _load_token(self) -> None:
        """Load persisted access token from disk."""
        try:
            if self._token_file.exists():
                with open(self._token_file, "r") as f:
                    data = json.load(f)
                saved_token = data.get("access_token", "")
                saved_expiry = data.get("token_expiry", 0)

                # Only use if not expired
                if saved_token and saved_expiry > time.time():
                    self._access_token = saved_token
                    self._token_expiry = saved_expiry
                    self._connected = True
                    self.logger.info("Loaded persisted Upstox token (still valid)")
                else:
                    self.logger.debug("Persisted Upstox token expired, ignoring")
        except Exception as e:
            self.logger.debug(f"No persisted token found: {e}")

    def _headers(self) -> Dict[str, str]:
        """Standard authenticated headers."""
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

    def _rate_limit(self) -> None:
        """Simple rate limiter to avoid hitting Upstox API limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    # ══════════════════════════════════════════════════════════════
    # INSTRUMENT KEY RESOLUTION
    # ══════════════════════════════════════════════════════════════

    def resolve_instrument_key(self, symbol: str) -> Optional[str]:
        """
        Resolve a trading symbol to its Upstox instrument_key.

        Tries local map first, then falls back to Upstox search API.
        """
        # Clean up common suffixes
        clean_symbol = symbol.replace(".NS", "").replace(".BO", "").upper()

        # Check local map (try both original and cleaned)
        if symbol in self._instrument_map:
            return self._instrument_map[symbol]
        if clean_symbol in self._instrument_map:
            return self._instrument_map[clean_symbol]

        # Fallback: search via API
        if self.is_connected:
            key = self._search_instrument(clean_symbol)
            if key:
                self._instrument_map[clean_symbol] = key
                self._instrument_map[symbol] = key
                return key

        self.logger.warning(f"Could not resolve instrument key for: {symbol}")
        return None

    def _search_instrument(self, symbol: str) -> Optional[str]:
        """Search Upstox API for an instrument key."""
        if not REQUESTS_AVAILABLE or not self.is_connected:
            return None

        try:
            self._rate_limit()
            url = f"{self.BASE_URL}/search/instruments"
            params = {"query": symbol}
            response = req_lib.get(url, headers=self._headers(), params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                instruments = data.get("data", [])

                # Prefer NSE_EQ match
                for inst in instruments:
                    if (inst.get("exchange") == "NSE" and
                        inst.get("instrument_type") == "EQ" and
                        inst.get("trading_symbol", "").upper() == symbol.upper()):
                        key = inst.get("instrument_key", "")
                        if key:
                            self.logger.info(f"Resolved {symbol} → {key}")
                            return key

                # Fallback: first NSE result
                for inst in instruments:
                    if inst.get("exchange") == "NSE":
                        key = inst.get("instrument_key", "")
                        if key:
                            self.logger.info(f"Resolved {symbol} → {key} (best match)")
                            return key

        except Exception as e:
            self.logger.warning(f"Instrument search failed for {symbol}: {e}")

        return None

    # ══════════════════════════════════════════════════════════════
    # HISTORICAL CANDLE DATA
    # ══════════════════════════════════════════════════════════════

    def get_historical_candles(
        self,
        symbol: str,
        interval: str = "15m",
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical OHLCV candles from Upstox.

        Args:
            symbol: Trading symbol (e.g., "RELIANCE", "TCS.NS", "^NSEI")
            interval: Candle interval ("1m", "5m", "15m", "30m", "1d", etc.)
            days: Number of days of history to fetch

        Returns:
            List of candle dicts with keys: timestamp, open, high, low, close, volume
        """
        if not self.is_connected:
            self.logger.warning("Upstox not connected — cannot fetch candles")
            return []

        # Resolve instrument key
        instrument_key = self.resolve_instrument_key(symbol)
        if not instrument_key:
            self.logger.error(f"Cannot resolve instrument key for {symbol}")
            return []

        # Map interval
        upstox_interval = TIMEFRAME_MAP.get(interval, "1minute")

        # Date range
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # URL-encode the instrument key (pipe character needs encoding)
        encoded_key = instrument_key.replace("|", "%7C")

        url = (
            f"{self.BASE_URL}/historical-candle/"
            f"{encoded_key}/{upstox_interval}/{to_date}/{from_date}"
        )

        self.logger.debug(f"Fetching candles: {symbol} ({instrument_key}) {upstox_interval} {from_date}→{to_date}")

        try:
            self._rate_limit()
            response = req_lib.get(url, headers=self._headers(), timeout=30)

            if response.status_code == 200:
                data = response.json()
                raw_candles = data.get("data", {}).get("candles", [])

                if not raw_candles:
                    self.logger.warning(f"No candle data returned for {symbol}")
                    return []

                # Parse Upstox candle format:
                # Each candle is an array: [timestamp_iso, open, high, low, close, volume, oi]
                candles = []
                for c in raw_candles:
                    try:
                        # Parse ISO timestamp → UTC epoch seconds
                        ts_str = c[0]
                        if isinstance(ts_str, str):
                            # Handle ISO format: "2024-01-15T09:15:00+05:30"
                            dt = datetime.fromisoformat(ts_str)
                            timestamp = dt.timestamp()
                        else:
                            timestamp = float(ts_str)

                        candles.append({
                            "timestamp": timestamp,
                            "open": float(c[1]),
                            "high": float(c[2]),
                            "low": float(c[3]),
                            "close": float(c[4]),
                            "volume": float(c[5]) if len(c) > 5 else 0.0,
                        })
                    except (IndexError, ValueError, TypeError) as parse_err:
                        self.logger.debug(f"Skipping malformed candle: {c} — {parse_err}")
                        continue

                # Upstox returns newest first; we want oldest first
                candles.sort(key=lambda x: x["timestamp"])

                # Aggregate if the requested interval differs from what Upstox returned
                agg_factor = AGGREGATION_MAP.get(interval)
                if agg_factor and agg_factor > 1 and candles:
                    candles = self._aggregate_candles(candles, agg_factor)

                self.logger.info(f"Fetched {len(candles)} candles for {symbol}/{interval} (via {upstox_interval})")
                return candles

            elif response.status_code == 401:
                self.logger.error("Upstox token expired or invalid (401)")
                self._connected = False
                return []
            else:
                self.logger.error(
                    f"Upstox candle fetch failed: {response.status_code} — {response.text[:200]}"
                )
                return []

        except Exception as e:
            self.logger.error(f"Upstox historical fetch exception for {symbol}: {e}")
            return []

    @staticmethod
    def _aggregate_candles(
        candles: List[Dict[str, Any]], factor: int
    ) -> List[Dict[str, Any]]:
        """
        Aggregate fine-grained candles into coarser bars.

        E.g., factor=5 merges every 5 consecutive 1-minute candles into
        a single 5-minute OHLCV bar.
        """
        if factor <= 1 or not candles:
            return candles

        aggregated = []
        for i in range(0, len(candles), factor):
            chunk = candles[i : i + factor]
            if not chunk:
                break
            aggregated.append({
                "timestamp": chunk[0]["timestamp"],  # Open time of the bar
                "open": chunk[0]["open"],
                "high": max(c["high"] for c in chunk),
                "low": min(c["low"] for c in chunk),
                "close": chunk[-1]["close"],
                "volume": sum(c.get("volume", 0) for c in chunk),
            })

        return aggregated

    def get_bars(
        self, symbol: str, timeframe: str = "15m", limit: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Get historical bars (compatible interface with BrokerAdapter.get_bars).

        This is the primary method called by MarketDataFeed.
        Caches historical data and merges with live intraday data for real-time updates.
        """
        # ── Cache historical candles (heavy API call) — refresh every 60s ──
        hist_cache_key = f"_hist_cache_{symbol}_{timeframe}"
        hist_ts_key = f"_hist_cache_ts_{symbol}_{timeframe}"
        hist_cache = getattr(self, hist_cache_key, None)
        hist_ts = getattr(self, hist_ts_key, 0.0)
        hist_refresh_interval = 60  # seconds

        if hist_cache is None or (time.time() - hist_ts) >= hist_refresh_interval:
            # Determine days needed based on timeframe and limit
            tf_minutes = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "1d": 1440}
            minutes = tf_minutes.get(timeframe, 15)
            bars_per_day = max(1, (6.25 * 60) / minutes)
            days_needed = max(7, int(limit / bars_per_day) + 5)

            hist_cache = self.get_historical_candles(symbol, timeframe, days=days_needed)
            setattr(self, hist_cache_key, hist_cache)
            setattr(self, hist_ts_key, time.time())
            self.logger.debug(f"Historical cache refreshed: {len(hist_cache)} candles for {symbol}/{timeframe}")

        candles = list(hist_cache)  # Don't mutate the cache

        # ── Merge with intraday data for live candles (called every poll) ──
        intraday = self.get_intraday_candles(symbol, timeframe)
        if intraday:
            existing_ts = {c["timestamp"] for c in candles}
            for ic in intraday:
                if ic["timestamp"] in existing_ts:
                    for i, c in enumerate(candles):
                        if c["timestamp"] == ic["timestamp"]:
                            candles[i] = ic
                            break
                else:
                    candles.append(ic)

            candles.sort(key=lambda x: x["timestamp"])

        # Trim to requested limit
        if len(candles) > limit:
            candles = candles[-limit:]

        # ── Inject absolute live price tick ──
        # Intraday endpoint lags by ~1 minute. Get the exact live quote to update the last candle's close
        try:
            live_quote = self.get_live_quote(symbol)
            if live_quote and candles:
                ltp = live_quote.get("ltp")
                if ltp and ltp > 0:
                    last_c = candles[-1]
                    # Only inject if the quote is reasonably close to the current candle price (prevent bad ticks)
                    if abs(last_c["close"] - ltp) / last_c["close"] < 0.05:
                        last_c["close"] = ltp
                        # Update high/low bounds dynamically
                        if ltp > last_c["high"]: last_c["high"] = ltp
                        if ltp < last_c["low"]: last_c["low"] = ltp
        except Exception as e:
            self.logger.debug(f"Failed to inject live quote for {symbol}: {e}")

        return candles

    def get_intraday_candles(
        self, symbol: str, interval: str = "15m"
    ) -> List[Dict[str, Any]]:
        """
        Fetch today's intraday candles from Upstox.
        This includes the CURRENTLY FORMING candle — critical for live chart updates.

        Uses the /historical-candle/intraday/ endpoint.
        """
        if not self.is_connected:
            return []

        instrument_key = self.resolve_instrument_key(symbol)
        if not instrument_key:
            return []

        upstox_interval = TIMEFRAME_MAP.get(interval, "1minute")
        encoded_key = instrument_key.replace("|", "%7C")

        url = (
            f"{self.BASE_URL}/historical-candle/intraday/"
            f"{encoded_key}/{upstox_interval}"
        )

        try:
            self._rate_limit()
            response = req_lib.get(url, headers=self._headers(), timeout=15)

            if response.status_code == 200:
                data = response.json()
                raw_candles = data.get("data", {}).get("candles", [])

                if not raw_candles:
                    return []

                candles = []
                for c in raw_candles:
                    try:
                        ts_str = c[0]
                        if isinstance(ts_str, str):
                            dt = datetime.fromisoformat(ts_str)
                            timestamp = dt.timestamp()
                        else:
                            timestamp = float(ts_str)

                        candles.append({
                            "timestamp": timestamp,
                            "open": float(c[1]),
                            "high": float(c[2]),
                            "low": float(c[3]),
                            "close": float(c[4]),
                            "volume": float(c[5]) if len(c) > 5 else 0.0,
                        })
                    except (IndexError, ValueError, TypeError):
                        continue

                candles.sort(key=lambda x: x["timestamp"])

                # Aggregate if needed (e.g., 1minute → 5minute or 15minute)
                agg_factor = AGGREGATION_MAP.get(interval)
                if agg_factor and agg_factor > 1 and candles:
                    candles = self._aggregate_candles(candles, agg_factor)

                self.logger.debug(f"Intraday: {len(candles)} candles for {symbol}/{interval} (via {upstox_interval})")
                return candles

            elif response.status_code == 401:
                self.logger.error("Upstox token expired (401) during intraday fetch")
                self._connected = False
            else:
                self.logger.debug(f"Intraday fetch failed: {response.status_code}")

        except Exception as e:
            self.logger.debug(f"Intraday fetch exception for {symbol}: {e}")

        return []

    # ══════════════════════════════════════════════════════════════
    # REAL-TIME QUOTES (REST-based polling, simpler than WebSocket)
    # ══════════════════════════════════════════════════════════════

    def get_live_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest quote for a symbol via REST API."""
        if not self.is_connected:
            return None

        instrument_key = self.resolve_instrument_key(symbol)
        if not instrument_key:
            return None

        try:
            self._rate_limit()
            url = f"{self.BASE_URL}/market-quote/quotes"
            params = {"instrument_key": instrument_key}
            response = req_lib.get(url, headers=self._headers(), params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                quotes = data.get("data", {})
                # The key in quotes dict is the instrument_key
                quote = quotes.get(instrument_key, {})
                if quote:
                    ohlc = quote.get("ohlc", {})
                    return {
                        "symbol": symbol,
                        "ltp": float(quote.get("last_price", 0)),
                        "open": float(ohlc.get("open", 0)),
                        "high": float(ohlc.get("high", 0)),
                        "low": float(ohlc.get("low", 0)),
                        "close": float(ohlc.get("close", 0)),
                        "volume": float(quote.get("volume", 0)),
                        "timestamp": time.time(),
                    }
        except Exception as e:
            self.logger.warning(f"Quote fetch failed for {symbol}: {e}")

        return None

    # ══════════════════════════════════════════════════════════════
    # MARKET STATUS
    # ══════════════════════════════════════════════════════════════

    def is_market_open(self) -> bool:
        """
        Check if Indian stock market (NSE) is currently open.
        NSE hours: 9:15 AM to 3:30 PM IST, Monday–Friday.
        """
        try:
            # IST = UTC + 5:30
            ist_offset = timezone(timedelta(hours=5, minutes=30))
            now_ist = datetime.now(ist_offset)

            # Weekend check
            if now_ist.weekday() >= 5:  # Saturday=5, Sunday=6
                return False

            # Market hours: 9:15 AM to 3:30 PM IST
            market_open = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
            market_close = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)

            return market_open <= now_ist <= market_close

        except Exception:
            return False

    # ══════════════════════════════════════════════════════════════
    # STATUS & DIAGNOSTICS
    # ══════════════════════════════════════════════════════════════

    def get_status(self) -> Dict[str, Any]:
        """Return adapter connection status."""
        return {
            "connected": self.is_connected,
            "api_key_configured": bool(self.api_key),
            "token_present": bool(self._access_token),
            "token_expired": self._token_expiry > 0 and time.time() > self._token_expiry,
            "market_open": self.is_market_open(),
            "instruments_loaded": len(self._instrument_map),
            "login_url": self.get_login_url() if not self.is_connected else None,
        }
