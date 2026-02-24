"""
Async Data Ingestion Worker.

Capabilities:
    - Async-ready parallel instrument processing
    - Rate limit control (configurable requests/sec)
    - Backfill mode (historical data loading)
    - Real-time streaming mode (live candle updates)
    - OHLCV data integrity validation
    - Batch ingestion with progress tracking
    - In-memory candle store (can be backed by TimescaleDB/ClickHouse)

No LLM. Deterministic. Horizontally scalable.
"""
import time
import logging
import math
from typing import Dict, Any, List, Optional, Callable, Tuple
from agent.trading.db_schema import Candle


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, max_requests_per_second: float = 10.0) -> None:
        self.max_rps = max_requests_per_second
        self.min_interval = 1.0 / max_requests_per_second if max_requests_per_second > 0 else 0
        self._last_request_time = 0.0

    def wait_if_needed(self) -> float:
        """Block until next request is allowed. Returns wait time in seconds."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.min_interval:
            wait = self.min_interval - elapsed
            time.sleep(wait)
            self._last_request_time = time.time()
            return wait
        self._last_request_time = now
        return 0.0

    def can_proceed(self) -> bool:
        """Non-blocking check."""
        return (time.time() - self._last_request_time) >= self.min_interval


class CandleValidator:
    """Validates OHLCV candle data integrity."""

    @staticmethod
    def validate_candle(candle: Candle) -> Tuple[bool, List[str]]:
        """
        Validate a single candle for data integrity.
        Returns (is_valid, list_of_issues).
        """
        issues = []

        # Basic range checks
        if candle.high < candle.low:
            issues.append(f"high ({candle.high}) < low ({candle.low})")
        if candle.open < candle.low or candle.open > candle.high:
            issues.append(f"open ({candle.open}) outside high-low range")
        if candle.close < candle.low or candle.close > candle.high:
            issues.append(f"close ({candle.close}) outside high-low range")
        if candle.volume < 0:
            issues.append(f"negative volume ({candle.volume})")
        if candle.timestamp <= 0:
            issues.append(f"invalid timestamp ({candle.timestamp})")

        # Zero price check
        if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
            issues.append("zero or negative price detected")

        # NaN/Inf check
        for name, val in [("open", candle.open), ("high", candle.high),
                          ("low", candle.low), ("close", candle.close),
                          ("volume", candle.volume)]:
            if math.isnan(val) or math.isinf(val):
                issues.append(f"{name} is NaN or Inf")

        return (len(issues) == 0, issues)

    @staticmethod
    def validate_series(candles: List[Candle]) -> Dict[str, Any]:
        """Validate a series of candles for continuity and integrity."""
        total = len(candles)
        valid = 0
        invalid = 0
        gaps = 0
        spike_count = 0

        prev_close = None
        for i, c in enumerate(candles):
            ok, _ = CandleValidator.validate_candle(c)
            if ok:
                valid += 1
            else:
                invalid += 1

            # Timestamp ordering
            if i > 0 and c.timestamp <= candles[i - 1].timestamp:
                gaps += 1

            # Price spike check (>20% single-candle move)
            if prev_close and prev_close > 0:
                change = abs(c.close - prev_close) / prev_close
                if change > 0.20:
                    spike_count += 1
            prev_close = c.close

        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "gaps": gaps,
            "spikes": spike_count,
            "integrity_score": valid / total if total > 0 else 0.0,
        }


class DataIngestionWorker:
    """
    In-memory candle store with ingestion pipeline.

    Architecture:
        - In-memory Dict[instrument_id][timeframe] → List[Candle]
        - Async-ready (can be wrapped with asyncio)
        - Rate-limited API calls
        - Backfill + streaming modes
        - Full validation pipeline
    """

    def __init__(self, max_rps: float = 10.0) -> None:
        self.logger = logging.getLogger("DataIngestionWorker")
        self.rate_limiter = RateLimiter(max_rps)
        self.validator = CandleValidator()

        # In-memory store: {instrument_id: {timeframe: [Candle, ...]}}
        self._store: Dict[int, Dict[str, List[Candle]]] = {}

        # Ingestion stats
        self._stats = {
            "total_ingested": 0,
            "total_rejected": 0,
            "total_batches": 0,
        }

    # ── Ingestion ──────────────────────────────────────────────

    def ingest_candles(
        self,
        instrument_id: int,
        timeframe: str,
        candles: List[Dict[str, Any]],
        validate: bool = True,
    ) -> Dict[str, Any]:
        """
        Ingest a batch of OHLCV candles.

        Args:
            instrument_id: Target instrument
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 4h)
            candles: List of dicts with keys: timestamp, open, high, low, close, volume
            validate: Whether to run integrity validation

        Returns:
            Ingestion report
        """
        accepted = 0
        rejected = 0
        issues_list = []

        if instrument_id not in self._store:
            self._store[instrument_id] = {}
        if timeframe not in self._store[instrument_id]:
            self._store[instrument_id][timeframe] = []

        for raw in candles:
            candle = Candle(
                instrument_id=instrument_id,
                timeframe=timeframe,
                timestamp=raw.get("timestamp", 0),
                open=raw.get("open", 0.0),
                high=raw.get("high", 0.0),
                low=raw.get("low", 0.0),
                close=raw.get("close", 0.0),
                volume=raw.get("volume", 0.0),
            )

            if validate:
                valid, issues = self.validator.validate_candle(candle)
                if not valid:
                    rejected += 1
                    issues_list.extend(issues)
                    continue

            # Check for duplicates (same timestamp)
            existing = self._store[instrument_id][timeframe]
            if existing and candle.timestamp <= existing[-1].timestamp:
                # Skip duplicate or out-of-order
                rejected += 1
                continue

            self._store[instrument_id][timeframe].append(candle)
            accepted += 1

        self._stats["total_ingested"] += accepted
        self._stats["total_rejected"] += rejected
        self._stats["total_batches"] += 1

        self.logger.debug(
            f"Ingested {accepted}/{len(candles)} candles for "
            f"instrument {instrument_id} @ {timeframe}"
        )

        return {
            "accepted": accepted,
            "rejected": rejected,
            "total_stored": len(self._store[instrument_id][timeframe]),
            "issues": issues_list[:10],  # Cap issue list
        }

    def ingest_streaming(
        self,
        instrument_id: int,
        timeframe: str,
        candle: Dict[str, Any],
    ) -> bool:
        """
        Ingest a single live candle (streaming mode).
        Returns True if accepted.
        """
        result = self.ingest_candles(instrument_id, timeframe, [candle])
        return result["accepted"] > 0

    def backfill(
        self,
        instrument_id: int,
        timeframe: str,
        candles: List[Dict[str, Any]],
        fetch_fn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Backfill historical data.

        If fetch_fn is provided, it will be called with rate limiting
        to fetch additional pages of data.
        """
        total_ingested = 0

        # Ingest provided candles first
        result = self.ingest_candles(instrument_id, timeframe, candles)
        total_ingested += result["accepted"]

        # If fetch function provided, paginate with rate limiting
        if fetch_fn:
            page = 1
            while page < 100:  # Hard cap at 100 pages
                self.rate_limiter.wait_if_needed()
                try:
                    additional = fetch_fn(instrument_id, timeframe, page)
                    if not additional:
                        break
                    r = self.ingest_candles(instrument_id, timeframe, additional)
                    total_ingested += r["accepted"]
                    if r["accepted"] == 0:
                        break  # No new data
                    page += 1
                except Exception as e:
                    self.logger.error(f"Backfill error page {page}: {e}")
                    break

        self.logger.info(
            f"Backfill complete: {total_ingested} candles for "
            f"instrument {instrument_id} @ {timeframe}"
        )

        return {
            "total_ingested": total_ingested,
            "pages_fetched": page if fetch_fn else 1,
            "total_stored": len(self.get_candles(instrument_id, timeframe)),
        }

    # ── Retrieval ──────────────────────────────────────────────

    def get_candles(
        self,
        instrument_id: int,
        timeframe: str,
        limit: Optional[int] = None,
    ) -> List[Candle]:
        """Get stored candles, optionally limited to most recent N."""
        series = self._store.get(instrument_id, {}).get(timeframe, [])
        if limit:
            return series[-limit:]
        return series

    def get_ohlcv_arrays(
        self,
        instrument_id: int,
        timeframe: str,
        limit: Optional[int] = None,
    ) -> Dict[str, List[float]]:
        """Get OHLCV as separate arrays (for indicator engine)."""
        candles = self.get_candles(instrument_id, timeframe, limit)
        return {
            "opens": [c.open for c in candles],
            "highs": [c.high for c in candles],
            "lows": [c.low for c in candles],
            "closes": [c.close for c in candles],
            "volumes": [c.volume for c in candles],
            "timestamps": [c.timestamp for c in candles],
        }

    def get_candle_count(self, instrument_id: int, timeframe: str) -> int:
        return len(self._store.get(instrument_id, {}).get(timeframe, []))

    def get_stored_instruments(self) -> List[int]:
        """Get all instrument IDs with stored data."""
        return list(self._store.keys())

    def get_available_timeframes(self, instrument_id: int) -> List[str]:
        return list(self._store.get(instrument_id, {}).keys())

    # ── Validation ─────────────────────────────────────────────

    def validate_stored_data(self, instrument_id: int, timeframe: str) -> Dict[str, Any]:
        """Run integrity validation on stored candle series."""
        candles = self.get_candles(instrument_id, timeframe)
        if not candles:
            return {"status": "NO_DATA", "total": 0}
        return self.validator.validate_series(candles)

    # ── Stats ──────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        total_candles = 0
        instruments = 0
        for inst_data in self._store.values():
            instruments += 1
            for tf_data in inst_data.values():
                total_candles += len(tf_data)

        return {
            **self._stats,
            "instruments_stored": instruments,
            "total_candles_in_memory": total_candles,
        }
