from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any, Dict, Optional


class TaskCheckpointStore:
    def __init__(self, db_path: str = "agent_data/missions.db") -> None:
        self.db_path = db_path
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
                CREATE TABLE IF NOT EXISTS mission_checkpoints (
                    mission_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    data TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, mission_id: str, status: str, data: Dict[str, Any], version: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mission_checkpoints(mission_id, version, status, updated_at, data)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(mission_id) DO UPDATE SET
                    version = excluded.version,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    data = excluded.data
                """,
                (
                    mission_id,
                    version,
                    status,
                    datetime.now(UTC).isoformat(),
                    json.dumps(data, ensure_ascii=False),
                ),
            )
            conn.commit()

    def load(self, mission_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT mission_id, version, status, updated_at, data FROM mission_checkpoints WHERE mission_id = ?",
                (mission_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "mission_id": row["mission_id"],
            "version": row["version"],
            "status": row["status"],
            "updated_at": row["updated_at"],
            "data": json.loads(row["data"]),
        }

    def list_running(self) -> list[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT mission_id, version, status, updated_at, data
                FROM mission_checkpoints
                WHERE status IN ('pending', 'running', 'blocked')
                ORDER BY updated_at ASC
                """
            ).fetchall()
        result: list[Dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "mission_id": row["mission_id"],
                    "version": row["version"],
                    "status": row["status"],
                    "updated_at": row["updated_at"],
                    "data": json.loads(row["data"]),
                }
            )
        return result
