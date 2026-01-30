"""
State Machine - Strict agent state management.

This module implements a finite state machine for agent states
ensuring deterministic behavior and preventing invalid transitions.
"""
import logging
from typing import Optional, Callable, Dict, List, Set
from enum import Enum, auto
from dataclasses import dataclass
from datetime import datetime
import threading


class AgentState(Enum):
    """Valid agent states."""
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    ACTING = "acting"
    CONFIRMING = "confirming"
    LOCKED = "locked"
    ERROR = "error"


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: AgentState
    to_state: AgentState
    timestamp: str
    reason: str


class StateMachine:
    """
    Finite State Machine for agent state management.
    
    Features:
    - Strict state validation
    - Transition history
    - State change callbacks
    - Thread-safe operations
    - Lock enforcement
    
    State Diagram:
    
    IDLE <--> LISTENING <--> THINKING <--> ACTING
              ^                |
              |                v
              +---- CONFIRMING --+
              
    LOCKED <--> (any state except ERROR)
    ERROR --> IDLE (recovery)
    """
    
    # Valid state transitions
    TRANSITIONS: Dict[AgentState, Set[AgentState]] = {
        AgentState.IDLE: {AgentState.LISTENING, AgentState.LOCKED, AgentState.ERROR},
        AgentState.LISTENING: {AgentState.IDLE, AgentState.THINKING, AgentState.LOCKED, AgentState.ERROR},
        AgentState.THINKING: {AgentState.IDLE, AgentState.ACTING, AgentState.CONFIRMING, AgentState.LOCKED, AgentState.ERROR},
        AgentState.ACTING: {AgentState.IDLE, AgentState.THINKING, AgentState.LOCKED, AgentState.ERROR},
        AgentState.CONFIRMING: {AgentState.ACTING, AgentState.IDLE, AgentState.LOCKED, AgentState.ERROR},
        AgentState.LOCKED: {AgentState.IDLE},  # Can only unlock to IDLE
        AgentState.ERROR: {AgentState.IDLE},   # Can only recover to IDLE
    }
    
    def __init__(self, initial_state: AgentState = AgentState.IDLE):
        """
        Initialize the state machine.
        
        Args:
            initial_state: Starting state (default: IDLE).
        """
        self.logger = logging.getLogger("StateMachine")
        self._state = initial_state
        self._lock = threading.RLock()
        self._history: List[StateTransition] = []
        self._callbacks: Dict[AgentState, List[Callable]] = {}
        self._on_transition: List[Callable[[AgentState, AgentState], None]] = []
        
        self.logger.info(f"StateMachine initialized in state: {initial_state.value}")
    
    @property
    def state(self) -> AgentState:
        """Get current state."""
        with self._lock:
            return self._state
    
    @property
    def is_locked(self) -> bool:
        """Check if agent is locked."""
        return self.state == AgentState.LOCKED
    
    @property
    def is_busy(self) -> bool:
        """Check if agent is busy (not IDLE or LISTENING)."""
        return self.state in {AgentState.THINKING, AgentState.ACTING, AgentState.CONFIRMING}
    
    def can_transition(self, to_state: AgentState) -> bool:
        """
        Check if transition to target state is valid.
        
        Args:
            to_state: Target state.
        
        Returns:
            True if transition is valid.
        """
        with self._lock:
            valid_transitions = self.TRANSITIONS.get(self._state, set())
            return to_state in valid_transitions
    
    def transition(self, to_state: AgentState, reason: str = "") -> bool:
        """
        Transition to a new state.
        
        Args:
            to_state: Target state.
            reason: Reason for transition.
        
        Returns:
            True if transition succeeded, False if invalid.
        """
        with self._lock:
            if not self.can_transition(to_state):
                self.logger.warning(
                    f"Invalid transition: {self._state.value} -> {to_state.value}"
                )
                return False
            
            from_state = self._state
            self._state = to_state
            
            # Record transition
            transition = StateTransition(
                from_state=from_state,
                to_state=to_state,
                timestamp=datetime.now().isoformat(),
                reason=reason
            )
            self._history.append(transition)
            
            self.logger.info(f"State: {from_state.value} -> {to_state.value} ({reason})")
            
            # Fire callbacks
            self._fire_callbacks(from_state, to_state)
            
            return True
    
    def _fire_callbacks(self, from_state: AgentState, to_state: AgentState) -> None:
        """Fire registered callbacks for state transition."""
        # State-specific callbacks
        if to_state in self._callbacks:
            for callback in self._callbacks[to_state]:
                try:
                    callback()
                except Exception as e:
                    self.logger.error(f"Callback error: {e}")
        
        # General transition callbacks
        for callback in self._on_transition:
            try:
                callback(from_state, to_state)
            except Exception as e:
                self.logger.error(f"Transition callback error: {e}")
    
    def on_enter_state(self, state: AgentState, callback: Callable) -> None:
        """
        Register callback for when entering a state.
        
        Args:
            state: State to monitor.
            callback: Callback function.
        """
        if state not in self._callbacks:
            self._callbacks[state] = []
        self._callbacks[state].append(callback)
    
    def on_transition(self, callback: Callable[[AgentState, AgentState], None]) -> None:
        """
        Register callback for any state transition.
        
        Args:
            callback: Callback receiving (from_state, to_state).
        """
        self._on_transition.append(callback)
    
    def lock(self, reason: str = "User requested lock") -> bool:
        """Lock the agent."""
        return self.transition(AgentState.LOCKED, reason)
    
    def unlock(self, reason: str = "Authentication successful") -> bool:
        """Unlock the agent."""
        if self.state != AgentState.LOCKED:
            return True  # Already unlocked
        return self.transition(AgentState.IDLE, reason)
    
    def to_idle(self, reason: str = "Task complete") -> bool:
        """Transition to IDLE state."""
        return self.transition(AgentState.IDLE, reason)
    
    def to_listening(self, reason: str = "Awaiting input") -> bool:
        """Transition to LISTENING state."""
        return self.transition(AgentState.LISTENING, reason)
    
    def to_thinking(self, reason: str = "Processing input") -> bool:
        """Transition to THINKING state."""
        return self.transition(AgentState.THINKING, reason)
    
    def to_acting(self, reason: str = "Executing action") -> bool:
        """Transition to ACTING state."""
        return self.transition(AgentState.ACTING, reason)
    
    def to_confirming(self, reason: str = "Awaiting confirmation") -> bool:
        """Transition to CONFIRMING state."""
        return self.transition(AgentState.CONFIRMING, reason)
    
    def to_error(self, reason: str = "Error occurred") -> bool:
        """Transition to ERROR state."""
        return self.transition(AgentState.ERROR, reason)
    
    def recover(self) -> bool:
        """Recover from ERROR state to IDLE."""
        if self.state == AgentState.ERROR:
            return self.transition(AgentState.IDLE, "Error recovery")
        return True
    
    def get_history(self, limit: int = 10) -> List[StateTransition]:
        """
        Get recent state transition history.
        
        Args:
            limit: Maximum entries to return.
        
        Returns:
            List of recent transitions.
        """
        with self._lock:
            return self._history[-limit:]
    
    def clear_history(self) -> None:
        """Clear transition history."""
        with self._lock:
            self._history.clear()
    
    def reset(self) -> None:
        """Reset state machine to IDLE."""
        with self._lock:
            self._state = AgentState.IDLE
            self.logger.info("StateMachine reset to IDLE")
