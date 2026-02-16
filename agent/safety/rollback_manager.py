from __future__ import annotations

from typing import Dict, List


class RollbackManager:
    def __init__(self) -> None:
        self._history: Dict[str, List[dict]] = {}

    def snapshot(self, mission_id: str, state: dict) -> None:
        self._history.setdefault(mission_id, []).append(state)

    def rollback(self, mission_id: str) -> dict | None:
        snapshots = self._history.get(mission_id, [])
        if not snapshots:
            return None
        return snapshots.pop()

    def has_rollback_point(self, mission_id: str) -> bool:
        return bool(self._history.get(mission_id))
