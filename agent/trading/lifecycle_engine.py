"""
Signal Lifecycle State Machine — Hard Lock.

Architecture:
    - Singular state ownership for all signals.
    - VALID_TRANSITIONS matrix enforcement.
    - Thread-safe transaction locks around mutation + sequence increment + emission.
    - Globally monotonic `event_sequence_number`.
    - Per-signal `version_number` logic.
"""
import time
import logging
import threading
import json
import os
from typing import Dict, Any, List, Optional, Callable
from enum import Enum


class SignalState(Enum):
    IDLE = "IDLE"
    GENERATED = "GENERATED"
    LOCKED = "LOCKED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    RESET = "RESET"


VALID_TRANSITIONS = {
    SignalState.IDLE: [SignalState.GENERATED],
    SignalState.GENERATED: [SignalState.LOCKED],
    SignalState.LOCKED: [SignalState.ACTIVE, SignalState.CLOSED],
    SignalState.ACTIVE: [SignalState.CLOSED],
    SignalState.CLOSED: [SignalState.RESET],
    SignalState.RESET: [SignalState.IDLE]
}


class Signal:
    """
    Immutable-once-created signal with hard lifecycle.
    Entry, stop, target, and candle_index NEVER change after __init__.
    """

    def __init__(
        self,
        signal_id: str,
        asset: str,
        direction: str,
        entry_price: float,
        stop_price: float,
        target_price: float,
        candle_index: int,
        timeframe: str,
        confidence: float = 0.5,
        position_size_pct: float = 0.01,
        max_age_candles: int = 50,
        metadata: Dict[str, Any] = None
    ) -> None:
        self.signal_id = signal_id
        self.asset = asset
        self.direction = direction
        self.entry_price = entry_price
        self.stop_price = stop_price
        self.target_price = target_price
        self.candle_index = candle_index
        self.timeframe = timeframe
        self.confidence = confidence
        self.position_size_pct = position_size_pct
        self.max_age_candles = max_age_candles
        self.metadata = metadata or {}

        # Mutable state
        self.state = SignalState.GENERATED
        self.version_number = 1
        self.created_at = time.time()
        self.resolved_at: Optional[float] = None
        self.resolution_reason: Optional[str] = None
        self.candles_elapsed: int = 0

        self._current_price: float = entry_price
        self._highest_r: float = 0.0

    @property
    def is_terminal(self) -> bool:
        return self.state in {SignalState.CLOSED, SignalState.RESET}

    @property
    def current_r(self) -> float:
        risk = abs(self.entry_price - self.stop_price)
        if risk <= 0:
            return 0.0
        if self.direction == "LONG":
            return (self._current_price - self.entry_price) / risk
        else:
            return (self.entry_price - self._current_price) / risk

    # Transitions are explicitly enforced by LifecycleEngine.

    def to_dict(self) -> Dict[str, Any]:
        """Frozen serialization for payloads."""
        return {
            "signal_id": self.signal_id,
            "version_number": self.version_number,
            "asset": self.asset,
            "direction": self.direction,
            "state": self.state.value,
            "entry_price": self.entry_price,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "candle_index": self.candle_index,
            "timeframe": self.timeframe,
            "confidence": round(self.confidence, 4),
            "position_size_pct": round(self.position_size_pct, 6),
            "current_r": round(self.current_r, 4),
            "highest_r": round(self._highest_r, 4),
            "candles_elapsed": self.candles_elapsed,
            "is_terminal": self.is_terminal,
            "resolution_reason": self.resolution_reason,
            "metadata": self.metadata
        }


class LifecycleEngine:
    """
    Hard-locked signal lifecycle manager. Owns signal state mutability exclusively.
    Events are guaranteed to be atomic (Action + Sequence Increment + Emit).
    """

    def __init__(self, event_emitter: Callable[[Dict[str, Any]], None]) -> None:
        self.logger = logging.getLogger("LifecycleEngine")
        self.event_emitter = event_emitter
        
        self._active: Dict[str, Signal] = {}
        self._history: List[Dict[str, Any]] = []
        self._used_candles: Dict[str, set] = {}
        
        
        self._event_sequence_number: int = self._load_sequence()
        self._lock = threading.Lock()
        self.system_halted: bool = False

    def _load_sequence(self) -> int:
        state_file = "lifecycle_state.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    data = json.load(f)
                    return data.get("event_sequence_number", 0)
            except Exception as e:
                self.logger.error(f"Failed to load sequence state: {e}")
        return 0

    def _save_sequence(self) -> None:
        state_file = "lifecycle_state.json"
        try:
            with open(state_file, "w") as f:
                json.dump({"event_sequence_number": self._event_sequence_number}, f)
        except Exception as e:
            self.logger.error(f"Failed to save sequence state: {e}")

    def trigger_system_halt(self, reason: str) -> None:
        """Emergency kill switch - halts transition capability and notifies."""
        with self._lock:
            self.system_halted = True
            
            # Close all active
            for sig_id, signal in list(self._active.items()):
                if not signal.is_terminal:
                    self._transition_unsafe(
                        signal, 
                        SignalState.CLOSED, 
                        resolution_reason=f"SYSTEM_HALTED: {reason}"
                    )
                    
            self._event_sequence_number += 1
            self._save_sequence()
            payload = {
                "event": "SYSTEM_HALTED",
                "event_sequence_number": self._event_sequence_number,
                "reason": reason,
                "timestamp_utc": time.time()
            }
            self.event_emitter(payload)
            self.logger.critical(f"SYSTEM HALTED: {reason}")

    def _transition_unsafe(self, signal: Signal, new_state: SignalState, resolution_reason: str = None) -> None:
        """Internal transition explicitly under lock. Validates against matrix."""
        
        trans_log = {
            "current_state": signal.state.value,
            "requested_transition": new_state.value,
            "signal_id": signal.signal_id,
            "version_number": signal.version_number,
            "event_sequence_number": self._event_sequence_number + 1
        }
        self.logger.info(f"LIFECYCLE_TRANSITION_CHECK: {trans_log}")

        if new_state not in VALID_TRANSITIONS.get(signal.state, []):
            self.logger.warning(f"INVALID_TRANSITION: {signal.signal_id} {signal.state} -> {new_state}")
            err = f"ILLEGAL TRANSITION: {signal.signal_id} {signal.state} -> {new_state}"
            self.logger.critical(err)
            raise RuntimeError(err) # We allow this to crash the thread intentionally to prevent corruption

        signal.state = new_state
        signal.version_number += 1
        
        if new_state == SignalState.CLOSED:
            signal.resolved_at = time.time()
            signal.resolution_reason = resolution_reason or "UNKNOWN"
            self._history.append(signal.to_dict())

        # Atomically emit event
        self._event_sequence_number += 1
        self._save_sequence()
        event_name = f"SIGNAL_{new_state.value}"
        payload = {
            "event": event_name,
            "event_sequence_number": self._event_sequence_number,
            "signal": signal.to_dict()
        }
        self.event_emitter(payload)
        
        self.logger.info(f"Transitioned {signal.signal_id} to {new_state.value} (v{signal.version_number})")

    def handle_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Unified entry point for declarative state transitions and signal generation.
        """
        if event_type == "GENERATE_SIGNAL":
            self.generate_and_lock(
                signal_id=payload.get("signal_id"),
                asset=payload.get("asset"),
                direction=payload.get("direction"),
                entry_price=payload.get("entry_price"),
                stop_price=payload.get("stop_price"),
                target_price=payload.get("target_price"),
                candle_index=payload.get("candle_index", 0),
                timeframe=payload.get("timeframe", "15m"),
                confidence=payload.get("confidence", 0.5),
                position_size_pct=payload.get("position_size_pct", 0.01),
                metadata=payload.get("metadata", {})
            )
        elif event_type == "CONFIRM_SIGNAL":
            with self._lock:
                signal_id = payload.get("signal_id")
                
                if signal_id and signal_id in self._active:
                    sig = self._active[signal_id]
                    if sig.state == SignalState.LOCKED:
                        self._transition_unsafe(sig, SignalState.ACTIVE)
                        return
                        
                self.logger.warning(f"Could not confirm signal {signal_id}. Not found or not LOCKED.")
        else:
            self.logger.warning(f"LifecycleEngine unhandled event_type: {event_type}")

    def generate_and_lock(
        self,
        signal_id: str,
        asset: str,
        direction: str,
        entry_price: float,
        stop_price: float,
        target_price: float,
        candle_index: int,
        timeframe: str,
        confidence: float,
        position_size_pct: float,
        metadata: Dict[str, Any]
    ) -> Optional[Signal]:
        with self._lock:
            if self.system_halted:
                return None
                
            # Gate check - if there's an active in-trade signal for this asset, block new generation.
            for current in list(self._active.values()):
                if current.asset == asset and current.state == SignalState.ACTIVE:
                    return None
                    
            # Supersede any old LOCKED (staged) signals for this asset to keep the UI clean
            # We enforce a > 5 second limit to avoid superseding freshly generated signals from the same scan
            for current in list(self._active.values()):
                if current.asset == asset and current.state == SignalState.LOCKED:
                    if time.time() - current.created_at > 5.0:
                        self._transition_unsafe(current, SignalState.CLOSED, "SUPERSEDED_BY_NEW_ANALYSIS")
                
            used = self._used_candles.get(asset, set())
            # We allow multiple identical candle_indexes IF we are just staging (LOCKED)
            # as the LLM might output both a BUY and a SELL for the same candle context.

            signal = Signal(
                signal_id=signal_id,
                asset=asset,
                direction=direction,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                candle_index=candle_index,
                timeframe=timeframe,
                confidence=confidence,
                position_size_pct=position_size_pct,
                metadata=metadata
            )
            self._active[signal.signal_id] = signal

            # Track candle
            if asset not in self._used_candles:
                self._used_candles[asset] = set()
            self._used_candles[asset].add(candle_index)

            # Instantly transition GENERATED -> LOCKED as per rule
            self._transition_unsafe(signal, SignalState.LOCKED)
            return signal

    def evaluate_price_tick(self, asset: str, current_price: float, current_candle_index: int = 0) -> None:
        """
        Passive monitoring logic identifying when entry/target/stops are crossed.
        Triggers explicit valid state transitions. Handled solely by backend.
        """
        with self._lock:
            if self.system_halted:
                return
                
            for signal in list(self._active.values()):
                if signal.asset != asset or signal.is_terminal:
                    continue
                    
                signal._current_price = current_price
                signal._highest_r = max(signal._highest_r, signal.current_r)
                signal.candles_elapsed = max(0, current_candle_index - signal.candle_index)

                # Expiry
                if signal.candles_elapsed >= signal.max_age_candles:
                    self._transition_unsafe(signal, SignalState.CLOSED, "EXPIRED_BY_CANDLES")
                    continue

                if signal.state == SignalState.LOCKED:
                    # Did it cross entry?
                    if signal.direction == "LONG" and current_price >= signal.entry_price:
                        self._transition_unsafe(signal, SignalState.ACTIVE)
                    elif signal.direction == "SHORT" and current_price <= signal.entry_price:
                        self._transition_unsafe(signal, SignalState.ACTIVE)
                
                elif signal.state == SignalState.ACTIVE:
                    # Check stop and target
                    if signal.direction == "LONG":
                        if current_price <= signal.stop_price:
                            self._transition_unsafe(signal, SignalState.CLOSED, "STOP_HIT")
                        elif current_price >= signal.target_price:
                            self._transition_unsafe(signal, SignalState.CLOSED, "TARGET_HIT")
                    else: # SHORT
                        if current_price >= signal.stop_price:
                            self._transition_unsafe(signal, SignalState.CLOSED, "STOP_HIT")
                        elif current_price <= signal.target_price:
                            self._transition_unsafe(signal, SignalState.CLOSED, "TARGET_HIT")

    def override_close_signal(self, asset: str, reason: str) -> None:
        """E.g., for regime flips or risk escalation."""
        with self._lock:
            if self.system_halted:
                return
            for signal in list(self._active.values()):
                if signal.asset == asset and not signal.is_terminal:
                    self._transition_unsafe(signal, SignalState.CLOSED, reason)

    def get_state_snapshot(self, portfolio_state: Dict = None, risk_state: Dict = None) -> Dict[str, Any]:
        """Provides the full deterministic sync payload for reconnecting WebSockets."""
        with self._lock:
            active_signals = [s.to_dict() for s in self._active.values() if not s.is_terminal]
            return {
                "event": "STATE_SNAPSHOT",
                "snapshot_sequence_number": self._event_sequence_number,
                "system_halted": self.system_halted,
                "active_signals": active_signals,
                "portfolio_state": portfolio_state or {},
                "risk_state": risk_state or {},
                "timestamp_utc": time.time()
            }
