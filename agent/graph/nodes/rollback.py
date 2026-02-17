"""
Rollback Node — §9 of Production Autonomous Agent Spec.

Before ELEVATED/DESTRUCTIVE actions: capture filesystem snapshot.
On failure: restore changed files, revert state markers, log event.
Rollback must be real, not simulated.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.rollback")

SNAPSHOT_DIR = os.path.join("agent_data", "rollback_snapshots")


@dataclass
class FileSnapshot:
    """Snapshot of a single file."""
    path: str
    hash: str
    size: int
    content_backup_path: Optional[str] = None


@dataclass
class RollbackSnapshot:
    """Complete rollback snapshot — §9."""
    snapshot_id: str
    timestamp: str
    files: List[FileSnapshot] = field(default_factory=list)
    created_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "files": [{"path": f.path, "hash": f.hash, "size": f.size} for f in self.files],
            "created_files": self.created_files,
        }


class RollbackManager:
    """Real filesystem rollback manager — §9.

    Captures actual file hashes/content before dangerous operations.
    Restores on failure. Not simulated.
    """

    def __init__(self, snapshot_dir: str = SNAPSHOT_DIR):
        self.snapshot_dir = snapshot_dir
        os.makedirs(snapshot_dir, exist_ok=True)

    def create_snapshot(self, watch_paths: List[str]) -> RollbackSnapshot:
        """Capture filesystem snapshot of watched paths.

        Args:
            watch_paths: List of file/directory paths to snapshot.

        Returns:
            RollbackSnapshot with file hashes and backup copies.
        """
        snapshot_id = f"snap_{int(time.time())}_{os.getpid()}"
        snap_dir = os.path.join(self.snapshot_dir, snapshot_id)
        os.makedirs(snap_dir, exist_ok=True)

        files: List[FileSnapshot] = []
        ignored_dirs = {".git", "__pycache__", "node_modules", ".idea", ".vscode", "venv", "env"}
        MAX_SNAPSHOT_FILES = 200  # Safety guard — don't snapshot huge directories
        
        # Prevent recursion: don't snapshot the snapshot directory
        abs_snap_dir = os.path.abspath(self.snapshot_dir)

        for path in watch_paths:
            if not os.path.exists(path):
                continue

            # Check if path is inside snapshot dir
            if os.path.abspath(path).startswith(abs_snap_dir):
                continue
                
            if os.path.isfile(path):
                try:
                    files.append(self._snapshot_file(path, snap_dir))
                except (PermissionError, OSError) as e:
                    logger.warning(f"Skipping locked file {path}: {e}")

            elif os.path.isdir(path):
                for root, dirs, filenames in os.walk(path):
                    # Safety guard: stop if we've hit the limit
                    if len(files) >= MAX_SNAPSHOT_FILES:
                        logger.warning(f"Snapshot file limit reached ({MAX_SNAPSHOT_FILES}), truncating")
                        break

                    # Filter ignored dirs
                    dirs[:] = [d for d in dirs if d not in ignored_dirs]
                    
                    # Prevent recursion into snapshot dir
                    if os.path.abspath(root).startswith(abs_snap_dir):
                        continue

                    for fname in filenames:
                        if len(files) >= MAX_SNAPSHOT_FILES:
                            break
                        fpath = os.path.join(root, fname)
                        try:
                            # Skip locked databases
                            if fpath.endswith((".db", ".db-wal", ".db-shm")):
                                continue
                                
                            files.append(self._snapshot_file(fpath, snap_dir))
                        except (PermissionError, OSError) as e:
                            logger.warning(f"Skipping locked file {fpath}: {e}")

        snapshot = RollbackSnapshot(
            snapshot_id=snapshot_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            files=files,
        )

        # Save manifest
        manifest_path = os.path.join(snap_dir, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

        logger.info(f"Snapshot created: {snapshot_id} ({len(files)} files)")
        return snapshot

    def rollback(self, snapshot_id: str) -> Dict[str, Any]:
        """Restore files from a snapshot.

        Returns dict with rollback results.
        """
        snap_dir = os.path.join(self.snapshot_dir, snapshot_id)
        manifest_path = os.path.join(snap_dir, "manifest.json")

        if not os.path.exists(manifest_path):
            return {"success": False, "error": f"Snapshot {snapshot_id} not found"}

        with open(manifest_path) as f:
            manifest = json.load(f)

        restored = 0
        deleted = 0
        errors = []

        # Restore modified files
        for file_info in manifest.get("files", []):
            original_path = file_info["path"]
            backup_name = hashlib.md5(original_path.encode()).hexdigest()
            backup_path = os.path.join(snap_dir, backup_name)

            if os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, original_path)
                    restored += 1
                except Exception as e:
                    errors.append(f"Failed to restore {original_path}: {e}")

        # Delete files created after snapshot
        for created in manifest.get("created_files", []):
            if os.path.exists(created):
                try:
                    os.remove(created)
                    deleted += 1
                except Exception as e:
                    errors.append(f"Failed to delete {created}: {e}")

        result = {
            "success": len(errors) == 0,
            "files_restored": restored,
            "files_deleted": deleted,
            "errors": errors,
        }

        logger.info(f"Rollback {snapshot_id}: restored={restored}, deleted={deleted}, errors={len(errors)}")
        return result

    def _snapshot_file(self, path: str, snap_dir: str) -> FileSnapshot:
        """Create a snapshot of a single file."""
        file_hash = self._hash_file(path)
        size = os.path.getsize(path)

        # Backup the file content
        backup_name = hashlib.md5(path.encode()).hexdigest()
        backup_path = os.path.join(snap_dir, backup_name)
        shutil.copy2(path, backup_path)

        return FileSnapshot(
            path=path,
            hash=file_hash,
            size=size,
            content_backup_path=backup_path,
        )

    @staticmethod
    def _hash_file(path: str) -> str:
        """SHA-256 hash of file contents."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()


# Global singleton
_rollback_manager: Optional[RollbackManager] = None


def get_rollback_manager() -> RollbackManager:
    global _rollback_manager
    if _rollback_manager is None:
        _rollback_manager = RollbackManager()
    return _rollback_manager


async def rollback_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """LangGraph node — creates or restores snapshots based on state.

    - If needs_approval + no snapshot → create snapshot
    - If error + snapshot exists + failure requires rollback → restore
    """
    manager = get_rollback_manager()
    snapshot_id = state.get("rollback_snapshot_id")
    error = state.get("error")

    # If there's an error and a snapshot, consider rollback
    if error and snapshot_id:
        from agent.core.failure_types import classify_failure, get_recovery
        ft = classify_failure(error)
        recovery = get_recovery(ft)

        if recovery.requires_rollback:
            result = manager.rollback(snapshot_id)
            logger.info(f"Rollback executed: {result}")
            return {
                "rollback_snapshot_id": None,  # Clear after rollback
                "audit_log": [{
                    "node": "rollback",
                    "action": "restore",
                    "snapshot_id": snapshot_id,
                    "result": result,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            }

    # If elevated/destructive action coming, create snapshot
    risk = state.get("world_state", {}).get("risk_level", "low")
    if risk in ("high", "critical") and not snapshot_id:
        watch_paths = _get_watch_paths(state)
        if watch_paths:
            snapshot = manager.create_snapshot(watch_paths)
            return {
                "rollback_snapshot_id": snapshot.snapshot_id,
                "audit_log": [{
                    "node": "rollback",
                    "action": "snapshot",
                    "snapshot_id": snapshot.snapshot_id,
                    "files_count": len(snapshot.files),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            }

    return {}


def _get_watch_paths(state: AgentState) -> List[str]:
    """Extract specific paths to watch from plan/tool context.
    
    IMPORTANT: Never return os.getcwd() — that would scan the entire project.
    Only return specific target directories/files mentioned in the plan.
    """
    paths = []
    plan = state.get("plan_graph", {})
    goal = state.get("goal", "")
    
    # Try to extract specific directories from goal/plan
    # Look for quoted directory names or explicit path references
    import re
    
    # Match quoted strings that look like directory/file names
    quoted = re.findall(r'"([^"]+)"', goal)
    for q in quoted:
        # If it looks like a path or directory name (not a sentence)
        if len(q.split()) <= 3 and not q.startswith("http"):
            candidate = os.path.join(os.getcwd(), q)
            if os.path.exists(candidate):
                paths.append(candidate)
    
    # Also check plan nodes for file/directory targets
    for node in plan.get("nodes", []):
        task = node.get("task", "")
        # Look for file paths in the task description
        for match in re.findall(r'[\w/\\]+\.[\w]+', task):
            candidate = os.path.join(os.getcwd(), match)
            parent = os.path.dirname(candidate)
            if os.path.exists(parent) and parent not in paths:
                paths.append(parent)
    
    # If no specific paths found, DON'T fall back to os.getcwd()
    # That would scan the entire project and stall the agent
    if not paths:
        logger.info("No specific watch paths found — skipping snapshot")
    
    return paths

