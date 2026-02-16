from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Dict, Optional


class AuditLogger:
    def __init__(self, db_path: str = "agent_data/audit.db") -> None:
        self.db_path = db_path
        self._lock = Lock()
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    mission_id TEXT,
                    stage TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def log(
        self,
        mission_id: Optional[str],
        stage: str,
        event_type: str,
        actor: str,
        payload: Dict[str, Any],
    ) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_events(timestamp, mission_id, stage, event_type, actor, payload)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.now(UTC).isoformat(),
                        mission_id,
                        stage,
                        event_type,
                        actor,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )
                conn.commit()

    def list_events(self, mission_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT timestamp, mission_id, stage, event_type, actor, payload
                FROM audit_events
                WHERE mission_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (mission_id, limit),
            ).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "timestamp": row["timestamp"],
                    "mission_id": row["mission_id"],
                    "stage": row["stage"],
                    "event_type": row["event_type"],
                    "actor": row["actor"],
                    "payload": json.loads(row["payload"]),
                }
            )
        return events
