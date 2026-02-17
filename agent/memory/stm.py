"""
Short-Term Working Memory (STM) — §5 of Production Autonomous Agent Spec.

In-memory structure. Auto-cleared on task completion.
Holds current task state, active subgoals, temporary observations.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("memory.stm")


class ShortTermWorkingMemory:
    """In-memory STM — §5.

    Thread-safe deque-backed store.
    Auto-clears when task completes.
    Maximum capacity enforced.
    """

    MAX_ENTRIES = 100
    MAX_OBSERVATIONS = 50

    def __init__(self):
        self._lock = threading.Lock()
        self._messages: Deque[Dict[str, Any]] = deque(maxlen=self.MAX_ENTRIES)
        self._observations: Deque[Dict[str, Any]] = deque(maxlen=self.MAX_OBSERVATIONS)
        self._task_state: Dict[str, Any] = {}
        self._active_subgoals: List[str] = []

    # ── Messages ──
    def add_message(self, role: str, content: str) -> None:
        with self._lock:
            self._messages.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def get_messages(self, last_n: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._messages)[-last_n:]

    def get_context_window(self) -> str:
        """Get formatted message history for LLM context."""
        msgs = self.get_messages(10)
        return "\n".join(f"[{m['role']}] {m['content']}" for m in msgs)

    # ── Task State ──
    def set_task_state(self, key: str, value: Any) -> None:
        with self._lock:
            self._task_state[key] = value

    def get_task_state(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._task_state.get(key, default)

    def get_full_task_state(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._task_state)

    # ── Observations ──
    def add_observation(self, observation: str, category: str = "general") -> None:
        with self._lock:
            self._observations.append({
                "text": observation,
                "category": category,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def get_observations(self, category: str = None) -> List[Dict[str, Any]]:
        with self._lock:
            if category:
                return [o for o in self._observations if o["category"] == category]
            return list(self._observations)

    # ── Active Subgoals ──
    def set_active_subgoals(self, subgoals: List[str]) -> None:
        with self._lock:
            self._active_subgoals = list(subgoals)

    def get_active_subgoals(self) -> List[str]:
        with self._lock:
            return list(self._active_subgoals)

    # ── Lifecycle ──
    def clear(self) -> None:
        """Auto-clear on task completion — §5."""
        with self._lock:
            self._messages.clear()
            self._observations.clear()
            self._task_state.clear()
            self._active_subgoals.clear()
        logger.info("STM cleared")

    def get_stm_id(self) -> str:
        """Return a ref ID for state tracking."""
        return f"stm_{id(self)}"

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._messages) + len(self._observations)
