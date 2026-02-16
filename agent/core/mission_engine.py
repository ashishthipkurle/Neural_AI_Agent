from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from agent.core.models import MissionRecord, MissionStatus, RiskLevel
from agent.core.task_checkpoint import TaskCheckpointStore


class MissionEngine:
    def __init__(self, checkpoint_store: TaskCheckpointStore) -> None:
        self.checkpoint_store = checkpoint_store

    def create_mission(self, goal: str, policy_profile: str, risk_level: RiskLevel) -> MissionRecord:
        now = datetime.now(UTC).isoformat()
        mission = MissionRecord(
            mission_id=f"mission-{uuid.uuid4().hex[:12]}",
            goal=goal,
            status=MissionStatus.PENDING,
            created_at=now,
            updated_at=now,
            policy_profile=policy_profile,
            risk_level=risk_level,
            checkpoint_version=1,
        )
        self.save_checkpoint(mission, {"events": ["mission_created"]})
        return mission

    def save_checkpoint(self, mission: MissionRecord, state: Dict[str, Any]) -> None:
        mission.updated_at = datetime.now(UTC).isoformat()
        self.checkpoint_store.save(
            mission_id=mission.mission_id,
            status=mission.status.value,
            data={"mission": mission.__dict__, "state": state},
            version=mission.checkpoint_version,
        )

    def update_status(self, mission: MissionRecord, status: MissionStatus, state: Dict[str, Any]) -> None:
        mission.status = status
        mission.checkpoint_version += 1
        self.save_checkpoint(mission, state)

    def resume(self, mission_id: str) -> Optional[Dict[str, Any]]:
        return self.checkpoint_store.load(mission_id)

    def running_missions(self) -> list[Dict[str, Any]]:
        return self.checkpoint_store.list_running()
