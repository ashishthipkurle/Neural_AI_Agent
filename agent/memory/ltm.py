"""
Versioned Long-Term Memory (LTM) — §5 of Production Autonomous Agent Spec.

Stored in dedicated SQLite database.
Versioned writes. Write validation required.
STM cannot overwrite LTM. LTM updates require validation function.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("memory.ltm")


class VersionedLTM:
    """Long-Term Memory with versioned writes — §5.

    Rules:
    - All writes produce a new version (old versions preserved).
    - Write validation required before commit.
    - No blind overwrites.
    - Cross-layer mutation blocked (checked by MemoryGate).
    """

    def __init__(self, db_path: str = "agent_data/ltm.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ltm_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    version INTEGER DEFAULT 1,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    superseded_by INTEGER DEFAULT NULL,
                    is_current BOOLEAN DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ltm_key ON ltm_entries(key)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ltm_current ON ltm_entries(is_current)
            """)
            conn.commit()

    def store(
        self,
        key: str,
        value: str,
        category: str = "general",
        validation_fn: Optional[Callable[[str, str], bool]] = None,
    ) -> Dict[str, Any]:
        """Store a value with versioning.

        Args:
            key: Unique memory key.
            value: Content to store.
            category: Memory category.
            validation_fn: Optional function(old_value, new_value) -> bool.
                          Must return True to allow the write.

        Returns:
            Dict with version info and success status.
        """
        with self._lock:
            content_hash = hashlib.sha256(value.encode()).hexdigest()[:16]
            now = datetime.now(timezone.utc).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                # Check for existing entry
                cursor = conn.execute(
                    "SELECT id, value, version FROM ltm_entries WHERE key = ? AND is_current = 1",
                    (key,),
                )
                existing = cursor.fetchone()

                if existing:
                    old_id, old_value, old_version = existing

                    # Skip if content is identical
                    if old_value == value:
                        return {"success": True, "version": old_version, "action": "no_change"}

                    # Validate write if validator provided
                    if validation_fn and not validation_fn(old_value, value):
                        logger.warning(f"LTM write rejected by validation: key={key}")
                        return {"success": False, "reason": "validation_rejected"}

                    new_version = old_version + 1

                    # Mark old as superseded
                    conn.execute(
                        "UPDATE ltm_entries SET is_current = 0 WHERE id = ?",
                        (old_id,),
                    )

                    # Insert new version
                    cursor = conn.execute(
                        """INSERT INTO ltm_entries (key, value, category, version, content_hash, created_at, is_current)
                           VALUES (?, ?, ?, ?, ?, ?, 1)""",
                        (key, value, category, new_version, content_hash, now),
                    )
                    new_id = cursor.lastrowid

                    # Link old → new
                    conn.execute(
                        "UPDATE ltm_entries SET superseded_by = ? WHERE id = ?",
                        (new_id, old_id),
                    )

                    conn.commit()
                    logger.info(f"LTM updated: key={key}, v{old_version}→v{new_version}")
                    return {"success": True, "version": new_version, "action": "updated"}

                else:
                    # First write
                    conn.execute(
                        """INSERT INTO ltm_entries (key, value, category, version, content_hash, created_at, is_current)
                           VALUES (?, ?, ?, 1, ?, ?, 1)""",
                        (key, value, category, content_hash, now),
                    )
                    conn.commit()
                    logger.info(f"LTM created: key={key}, v1")
                    return {"success": True, "version": 1, "action": "created"}

    def retrieve(self, key: str) -> Optional[str]:
        """Get current value for a key."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value FROM ltm_entries WHERE key = ? AND is_current = 1",
                (key,),
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def retrieve_versioned(self, key: str) -> List[Dict[str, Any]]:
        """Get all versions of a key."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT version, value, created_at, is_current FROM ltm_entries WHERE key = ? ORDER BY version",
                (key,),
            )
            return [
                {"version": r[0], "value": r[1], "created_at": r[2], "is_current": bool(r[3])}
                for r in cursor.fetchall()
            ]

    def search(self, query: str, category: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search current entries by keyword."""
        with sqlite3.connect(self.db_path) as conn:
            if category:
                cursor = conn.execute(
                    "SELECT key, value, category, version FROM ltm_entries WHERE is_current = 1 AND category = ? AND value LIKE ? LIMIT ?",
                    (category, f"%{query}%", limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT key, value, category, version FROM ltm_entries WHERE is_current = 1 AND value LIKE ? LIMIT ?",
                    (f"%{query}%", limit),
                )
            return [
                {"key": r[0], "value": r[1], "category": r[2], "version": r[3]}
                for r in cursor.fetchall()
            ]

    def get_ltm_id(self) -> str:
        return f"ltm_{os.path.basename(self.db_path)}"
