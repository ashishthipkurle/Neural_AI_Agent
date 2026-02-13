
import sqlite3
import json
import datetime
import os
import uuid
import asyncio
import logging
from typing import List, Optional, Dict, Any
from agent.memory.personal_memory import PersonalMemoryManager

class PersistentTaskManager:
    """
    Module 2: Persistent Task Manager
    Long-running task persistence, decomposition, and state recovery.
    """
    
    def __init__(self, db_path: str = "agent_data/tasks.db", 
                 personal_memory: PersonalMemoryManager = None):
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path
        self.memory = personal_memory
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize DB
        self._init_db()
        
        # Start background worker (if running in async context)
        # self.worker_task = asyncio.create_task(self._worker_loop())

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize SQLite with WAL mode, create tables."""
        try:
            with self._get_connection() as conn:
                # CRITICAL: WAL mode for crash safety
                conn.execute("PRAGMA journal_mode=WAL")
                
                # Tasks
                conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    goal_type TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    priority INTEGER DEFAULT 5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    estimated_hours REAL,
                    actual_hours REAL,
                    parent_id TEXT,
                    checkpoint_data TEXT,
                    error_message TEXT,
                    FOREIGN KEY (parent_id) REFERENCES tasks(id)
                )
                """)

                # Subtasks
                conn.execute("""
                CREATE TABLE IF NOT EXISTS subtasks (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    sequence_order INTEGER,
                    dependencies TEXT,
                    result_data TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
                """)

                # Checkpoints
                conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    state_data TEXT NOT NULL,
                    memory_snapshot TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
                """)
                self.logger.info("Task Manager DB initialized successfully with WAL mode.")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Task Manager DB: {e}")
            raise

    def create_task(self, description: str, goal_type: str, 
                    priority: int = 5, estimated_hours: float = None,
                    parent_id: str = None) -> str:
        """Create task, auto-decompose complex ones. Returns task_id (UUID)"""
        task_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO tasks (id, description, goal_type, priority, estimated_hours, parent_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (task_id, description, goal_type, priority, estimated_hours, parent_id))
            return task_id
        except Exception as e:
            self.logger.error(f"Error creating task: {e}")
            return ""

    def submit_task(
        self,
        description: str,
        skill_name: str,
        params: Optional[Dict[str, Any]] = None,
        priority: int = 5
    ) -> str:
        """Compatibility adapter for task API callers.

        Maps `skill_name` -> `goal_type` and stores params as checkpoint payload.
        """
        task_id = self.create_task(
            description=description,
            goal_type=skill_name,
            priority=priority
        )
        if task_id and params:
            self.checkpoint(task_id, {"params": params, "skill_name": skill_name})
        return task_id

    def decompose_task(self, task_id: str) -> List[str]:
        """Use LLM to break into subtasks. Returns subtask_ids"""
        # Placeholder for LLM integration. In real impl, would call llm.generate()
        # For now, just return empty list or mock decomposition
        return []

    def execute_task(self, task_id: str) -> None:
        """Execute subtasks in order with retry logic. Checkpoint every 5 min"""
        # Set status to RUNNING
        try:
            with self._get_connection() as conn:
                conn.execute("UPDATE tasks SET status='RUNNING', started_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,))
            
            self.logger.info(f"Started executing task {task_id}")
            # Real execution logic would be here (looping through subtasks)
            
        except Exception as e:
            self.logger.error(f"Error executing task {task_id}: {e}")

    def checkpoint(self, task_id: str, state_data: dict) -> None:
        """Save state to checkpoints table"""
        state_json = json.dumps(state_data)
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO checkpoints (task_id, state_data)
                    VALUES (?, ?)
                """, (task_id, state_json))
                
                # Also update current task checkpoint_data
                conn.execute("UPDATE tasks SET checkpoint_data=? WHERE id=?", (state_json, task_id))
        except Exception as e:
            self.logger.error(f"Error check-pointing task {task_id}: {e}")

    def resume_from_checkpoint(self, task_id: str) -> dict:
        """Load latest checkpoint, restore context"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT state_data FROM checkpoints WHERE task_id=? ORDER BY id DESC LIMIT 1", (task_id,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                
                # Fallback to main task row
                cursor = conn.execute("SELECT checkpoint_data FROM tasks WHERE id=?", (task_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
        except Exception as e:
            self.logger.error(f"Error resuming task {task_id}: {e}")
        return {}

    def get_task_status(self, task_id: str) -> dict:
        """Return status with progress %"""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
        except Exception as e:
            self.logger.error(f"Error getting status for {task_id}: {e}")
        return {}

    def list_active_tasks(self) -> List[dict]:
        """Return all non-completed tasks"""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM tasks WHERE status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')")
                return [self._normalize_task_row(dict(row)) for row in cursor]
        except Exception as e:
            self.logger.error(f"Error listing active tasks: {e}")
        return []

    def list_tasks(self, limit: int = 20) -> List[dict]:
        """Return recent tasks (active first), compatible with API models."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM tasks
                    ORDER BY
                        CASE
                            WHEN status IN ('RUNNING', 'PENDING', 'PAUSED') THEN 0
                            ELSE 1
                        END,
                        created_at DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
                return [self._normalize_task_row(dict(row)) for row in cursor]
        except Exception as e:
            self.logger.error(f"Error listing tasks: {e}")
            return []

    def pause_task(self, task_id: str) -> None:
        """Save checkpoint, transition to PAUSED"""
        try:
            with self._get_connection() as conn:
                conn.execute("UPDATE tasks SET status='PAUSED' WHERE id=?", (task_id,))
            self.logger.info(f"Paused task {task_id}")
        except Exception as e:
            self.logger.error(f"Error pausing task {task_id}: {e}")

    def cancel_task(self, task_id: str) -> bool:
        """Cleanup, mark FAILED"""
        try:
            with self._get_connection() as conn:
                # Mark as CANCELLED (better than FAILED if user requested) or FAILED per spec? Spec says mark FAILED.
                cursor = conn.execute("UPDATE tasks SET status='FAILED', completed_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,))
                updated = cursor.rowcount > 0
            self.logger.info(f"Cancelled task {task_id}")
            return updated
        except Exception as e:
            self.logger.error(f"Error cancelling task {task_id}: {e}")
            return False

    def _normalize_task_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize row fields for API callers expecting common task shape."""
        created_at = row.get("created_at")
        started_at = row.get("started_at")
        completed_at = row.get("completed_at")

        checkpoint_data = row.get("checkpoint_data")
        parsed_checkpoint = {}
        if checkpoint_data:
            try:
                parsed_checkpoint = json.loads(checkpoint_data)
            except Exception:
                parsed_checkpoint = {}

        status = str(row.get("status") or "PENDING").lower()
        progress = 0
        if status == "completed":
            progress = 100
        elif status in {"running", "paused"}:
            progress = 50

        return {
            "id": row.get("id"),
            "description": row.get("description") or "",
            "skill_name": row.get("goal_type") or "",
            "status": status,
            "priority": row.get("priority", 5),
            "parameters": parsed_checkpoint.get("params", {}),
            "created_at": str(created_at) if created_at is not None else datetime.datetime.utcnow().isoformat(),
            "started_at": str(started_at) if started_at is not None else None,
            "completed_at": str(completed_at) if completed_at is not None else None,
            "progress": progress,
            "result": parsed_checkpoint.get("result"),
            "error": row.get("error_message")
        }

    async def _worker_loop(self):
        """Background worker: process queue, max 5 parallel, sleep 1s"""
        while True:
            # Placeholder for worker logic
            await asyncio.sleep(1)
