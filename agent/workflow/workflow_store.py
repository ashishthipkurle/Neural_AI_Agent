"""
Workflow Store — SQLite persistence for workflows, runs, and schedules.

Tables:
  - workflows: stores saved workflow definitions (nodes + edges JSON)
  - workflow_runs: execution history per workflow
  - workflow_schedules: cron schedules for automated triggers
"""

import sqlite3
import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger("WorkflowStore")

DB_PATH = Path(__file__).parent.parent.parent / "workflow.db"


class WorkflowStore:
    """SQLite-backed storage for workflow definitions, runs, and schedules."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT 'Untitled Workflow',
                    description TEXT DEFAULT '',
                    nodes_json TEXT NOT NULL DEFAULT '[]',
                    edges_json TEXT NOT NULL DEFAULT '[]',
                    config_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    trigger_type TEXT DEFAULT 'manual',
                    started_at TEXT,
                    finished_at TEXT,
                    node_results_json TEXT NOT NULL DEFAULT '{}',
                    logs_json TEXT NOT NULL DEFAULT '[]',
                    error_message TEXT,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS workflow_schedules (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL UNIQUE,
                    cron_expression TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    last_run TEXT,
                    next_run TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_runs_workflow ON workflow_runs(workflow_id);
                CREATE INDEX IF NOT EXISTS idx_schedules_active ON workflow_schedules(is_active);
            """)
            conn.commit()
            logger.info(f"Workflow DB initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize workflow DB: {e}")
            raise
        finally:
            conn.close()

    # ── WORKFLOWS CRUD ──

    def create_workflow(self, name: str, nodes: List[Dict], edges: List[Dict],
                        description: str = "", config: Dict = None) -> Dict[str, Any]:
        """Create a new workflow and return it."""
        wf_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO workflows (id, name, description, nodes_json, edges_json, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (wf_id, name, description, json.dumps(nodes), json.dumps(edges), json.dumps(config or {}), now, now)
            )
            conn.commit()
            logger.info(f"Created workflow '{name}' (id={wf_id}) with {len(nodes)} nodes")
            return self.get_workflow(wf_id)
        finally:
            conn.close()

    def get_workflow(self, wf_id: str) -> Optional[Dict[str, Any]]:
        """Get a workflow by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM workflows WHERE id = ?", (wf_id,)).fetchone()
            if not row:
                return None
            return self._row_to_workflow(row)
        finally:
            conn.close()

    def list_workflows(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """List all workflows."""
        conn = self._get_conn()
        try:
            if include_inactive:
                rows = conn.execute("SELECT * FROM workflows ORDER BY updated_at DESC").fetchall()
            else:
                rows = conn.execute("SELECT * FROM workflows WHERE is_active = 1 ORDER BY updated_at DESC").fetchall()
            return [self._row_to_workflow(r) for r in rows]
        finally:
            conn.close()

    def update_workflow(self, wf_id: str, name: str = None, nodes: List[Dict] = None,
                        edges: List[Dict] = None, description: str = None, config: Dict = None) -> Optional[Dict[str, Any]]:
        """Update an existing workflow."""
        existing = self.get_workflow(wf_id)
        if not existing:
            return None

        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """UPDATE workflows SET
                    name = ?, description = ?, nodes_json = ?, edges_json = ?, config_json = ?, updated_at = ?
                   WHERE id = ?""",
                (
                    name if name is not None else existing["name"],
                    description if description is not None else existing["description"],
                    json.dumps(nodes) if nodes is not None else json.dumps(existing["nodes"]),
                    json.dumps(edges) if edges is not None else json.dumps(existing["edges"]),
                    json.dumps(config) if config is not None else json.dumps(existing.get("config", {})),
                    now,
                    wf_id,
                )
            )
            conn.commit()
            logger.info(f"Updated workflow {wf_id}")
            return self.get_workflow(wf_id)
        finally:
            conn.close()

    def delete_workflow(self, wf_id: str) -> bool:
        """Soft-delete a workflow (sets is_active = 0)."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("UPDATE workflows SET is_active = 0, updated_at = ? WHERE id = ?",
                                  (datetime.now(timezone.utc).isoformat(), wf_id))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted workflow {wf_id}")
            return deleted
        finally:
            conn.close()

    def _row_to_workflow(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "nodes": json.loads(row["nodes_json"]),
            "edges": json.loads(row["edges_json"]),
            "config": json.loads(row["config_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "is_active": bool(row["is_active"]),
        }

    # ── WORKFLOW RUNS ──

    def create_run(self, workflow_id: str, trigger_type: str = "manual") -> str:
        """Create a new run record, return run_id."""
        run_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO workflow_runs (id, workflow_id, status, trigger_type, started_at) VALUES (?, ?, 'running', ?, ?)",
                (run_id, workflow_id, trigger_type, now)
            )
            conn.commit()
            return run_id
        finally:
            conn.close()

    def update_run(self, run_id: str, status: str = None, node_results: Dict = None,
                   logs: List = None, error_message: str = None):
        """Update a run record."""
        conn = self._get_conn()
        try:
            updates = []
            params = []

            if status:
                updates.append("status = ?")
                params.append(status)
                if status in ("completed", "failed", "cancelled"):
                    updates.append("finished_at = ?")
                    params.append(datetime.now(timezone.utc).isoformat())

            if node_results is not None:
                updates.append("node_results_json = ?")
                params.append(json.dumps(node_results))

            if logs is not None:
                updates.append("logs_json = ?")
                params.append(json.dumps(logs))

            if error_message is not None:
                updates.append("error_message = ?")
                params.append(error_message)

            if updates:
                params.append(run_id)
                conn.execute(f"UPDATE workflow_runs SET {', '.join(updates)} WHERE id = ?", params)
                conn.commit()
        finally:
            conn.close()

    def get_runs(self, workflow_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get run history for a workflow."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM workflow_runs WHERE workflow_id = ? ORDER BY started_at DESC LIMIT ?",
                (workflow_id, limit)
            ).fetchall()
            return [self._row_to_run(r) for r in rows]
        finally:
            conn.close()

    def _row_to_run(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "workflow_id": row["workflow_id"],
            "status": row["status"],
            "trigger_type": row["trigger_type"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "node_results": json.loads(row["node_results_json"]),
            "logs": json.loads(row["logs_json"]),
            "error_message": row["error_message"],
        }

    # ── SCHEDULES ──

    def set_schedule(self, workflow_id: str, cron_expression: str) -> Dict[str, Any]:
        """Create or update a cron schedule for a workflow."""
        sched_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            # Upsert: delete existing then insert
            conn.execute("DELETE FROM workflow_schedules WHERE workflow_id = ?", (workflow_id,))
            conn.execute(
                "INSERT INTO workflow_schedules (id, workflow_id, cron_expression, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                (sched_id, workflow_id, cron_expression, now)
            )
            conn.commit()
            logger.info(f"Scheduled workflow {workflow_id} with cron '{cron_expression}'")
            return {"id": sched_id, "workflow_id": workflow_id, "cron_expression": cron_expression, "is_active": True}
        finally:
            conn.close()

    def remove_schedule(self, workflow_id: str) -> bool:
        """Remove schedule for a workflow."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("DELETE FROM workflow_schedules WHERE workflow_id = ?", (workflow_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_schedule(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get the schedule for a workflow."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM workflow_schedules WHERE workflow_id = ?", (workflow_id,)).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "workflow_id": row["workflow_id"],
                "cron_expression": row["cron_expression"],
                "is_active": bool(row["is_active"]),
                "last_run": row["last_run"],
                "next_run": row["next_run"],
            }
        finally:
            conn.close()

    def get_active_schedules(self) -> List[Dict[str, Any]]:
        """Get all active schedules."""
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM workflow_schedules WHERE is_active = 1").fetchall()
            return [{
                "id": row["id"],
                "workflow_id": row["workflow_id"],
                "cron_expression": row["cron_expression"],
                "is_active": True,
                "last_run": row["last_run"],
                "next_run": row["next_run"],
            } for row in rows]
        finally:
            conn.close()

    def update_schedule_last_run(self, workflow_id: str, last_run: str, next_run: str = None):
        """Update the last_run timestamp of a schedule."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE workflow_schedules SET last_run = ?, next_run = ? WHERE workflow_id = ?",
                (last_run, next_run, workflow_id)
            )
            conn.commit()
        finally:
            conn.close()
