"""
Data Integrity & Feed Failure Guard.

Monitors:
    - WebSocket heartbeat (last received timestamp)
    - Candle anomalies (gap, impossible OHLC)
    - Price spikes beyond threshold
    - Missing ticks / stale data

If anomaly detected:
    Freeze signal engine.
    Set data_unstable = True.

No LLM. Fully deterministic.
"""
import time
import logging
from typing import List, Dict, Any, Optional


class DataIntegrityGuard:
    """
    Real-time data quality monitoring and circuit breaker.
    """

    def __init__(
        self,
        max_heartbeat_gap_seconds: float = 30.0,
        max_price_spike_pct: float = 10.0,
        min_candle_count: int = 10,
    ) -> None:
        self.logger = logging.getLogger("DataIntegrityGuard")
        self.max_heartbeat_gap = max_heartbeat_gap_seconds
        self.max_price_spike_pct = max_price_spike_pct
        self.min_candle_count = min_candle_count

        # State
        self.data_stable = True
        self.last_heartbeat = time.time()
        self._anomalies: List[Dict[str, Any]] = []
        self._frozen = False
        self._freeze_reason: Optional[str] = None
        
        # Phase 2: Global Kill Switch (HALTED)
        self.system_halted = False
        self.halt_reason: Optional[str] = None

    def record_heartbeat(self) -> None:
        """Record that data feed is alive."""
        self.last_heartbeat = time.time()

    def validate_candle(
        self, open_: float, high: float, low: float, close: float, volume: float
    ) -> Dict[str, Any]:
        """
        Validate a single OHLCV candle for data integrity.

        Returns:
            dict with valid (bool), anomalies (list)
        """
        anomalies = []

        # OHLC consistency
        if high < low:
            anomalies.append("HIGH < LOW")
        if high < open_ or high < close:
            anomalies.append("HIGH not highest")
        if low > open_ or low > close:
            anomalies.append("LOW not lowest")

        # Zero/negative prices
        if open_ <= 0 or high <= 0 or low <= 0 or close <= 0:
            anomalies.append("ZERO_OR_NEGATIVE_PRICE")

        # Zero volume (suspicious)
        if volume <= 0:
            anomalies.append("ZERO_VOLUME")

        # NaN / Inf check
        for name, val in [("open", open_), ("high", high), ("low", low), ("close", close)]:
            if val != val or val == float('inf') or val == float('-inf'):
                anomalies.append(f"{name}_NAN_OR_INF")

        if anomalies:
            self._record_anomaly("CANDLE_INVALID", anomalies)

        return {
            "valid": len(anomalies) == 0,
            "anomalies": anomalies,
        }

    def validate_price_series(
        self, closes: List[float]
    ) -> Dict[str, Any]:
        """
        Check for price spikes and missing data in a series.
        """
        anomalies = []

        if len(closes) < self.min_candle_count:
            anomalies.append(f"INSUFFICIENT_DATA: {len(closes)} < {self.min_candle_count}")
            self._record_anomaly("INSUFFICIENT_DATA", anomalies)
            return {"stable": False, "anomalies": anomalies}

        # Check for spikes
        for i in range(1, len(closes)):
            if closes[i - 1] == 0:
                continue
            change_pct = abs(closes[i] - closes[i - 1]) / closes[i - 1] * 100
            if change_pct > self.max_price_spike_pct:
                anomalies.append(
                    f"PRICE_SPIKE at index {i}: {change_pct:.2f}% "
                    f"({closes[i-1]:.2f} → {closes[i]:.2f})"
                )

        # Check for stale data (same price repeated many times)
        if len(set(closes[-10:])) == 1 and len(closes) >= 10:
            anomalies.append("STALE_DATA: Last 10 prices identical")

        if anomalies:
            self._record_anomaly("PRICE_SERIES", anomalies)

        stable = len(anomalies) == 0
        self.data_stable = stable
        return {"stable": stable, "anomalies": anomalies}

    def check_heartbeat(self) -> Dict[str, Any]:
        """
        Check if data feed heartbeat is recent enough.
        """
        gap = time.time() - self.last_heartbeat
        alive = gap < self.max_heartbeat_gap

        if not alive:
            self._record_anomaly("HEARTBEAT_TIMEOUT", [f"Gap: {gap:.1f}s"])
            self.data_stable = False

        return {
            "alive": alive,
            "gap_seconds": round(gap, 2),
            "threshold": self.max_heartbeat_gap,
        }

    def should_freeze_engine(self) -> bool:
        """Check if the signal engine should be frozen."""
        if self.system_halted:
            return True
            
        heartbeat = self.check_heartbeat()
        if not heartbeat["alive"]:
            self._frozen = True
            self._freeze_reason = "Heartbeat timeout"
            return True

        if not self.data_stable:
            self._frozen = True
            self._freeze_reason = "Data unstable"
            return True

        self._frozen = False
        self._freeze_reason = None
        return False

    def unfreeze(self) -> None:
        """Manual unfreeze after anomaly resolution."""
        if self.system_halted:
            self.logger.warning("Attempted to unfreeze while HALTED. Use manual_override_halt().")
            return
            
        self._frozen = False
        self._freeze_reason = None
        self.data_stable = True
        self.record_heartbeat()
        self.logger.info("Data integrity guard unfrozen.")

    # ── Phase 2: Hard Fail-Safe ────────────────────────────────

    def trigger_hard_fail_safe(self, reason: str) -> None:
        """
        Global kill-switch. Triggers on catastrophic drift, OOM, or split-brain.
        Instantly halts the system. Requires explicit administrator override to resume.
        """
        self.system_halted = True
        self.halt_reason = reason
        self._frozen = True
        self._freeze_reason = f"SYSTEM HALTED: {reason}"
        self.logger.critical(f"HARD FAIL-SAFE TRIGGERED: {reason}. All trading halted.")

    def manual_override_halt(self) -> None:
        """Institutional override to exit HALTED state."""
        self.system_halted = False
        self.halt_reason = None
        self.logger.warning("Hard Fail-Safe manually overridden. System returning to normal operations.")
        self.unfreeze()

    def _record_anomaly(self, category: str, details: List[str]) -> None:
        self._anomalies.append({
            "category": category,
            "details": details,
            "timestamp": time.time(),
        })
        # Keep bounded
        if len(self._anomalies) > 100:
            self._anomalies = self._anomalies[-100:]

        self.logger.warning(f"Data anomaly [{category}]: {details}")

    def get_state(self) -> Dict[str, Any]:
        return {
            "system_halted": self.system_halted,
            "halt_reason": self.halt_reason,
            "data_stable": self.data_stable,
            "frozen": self._frozen,
            "freeze_reason": self._freeze_reason,
            "heartbeat_gap": round(time.time() - self.last_heartbeat, 2),
            "recent_anomalies": len(self._anomalies),
        }
