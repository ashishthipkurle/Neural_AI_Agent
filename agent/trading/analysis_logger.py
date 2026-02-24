import json
import os
import sqlite3
import hashlib
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Dict, Optional

class AnalysisLogger:
    """
    Immutable, hash-chained audit logger for trading analysis.
    Ensures that all trading decisions and analyses have deterministic, reproducible histories.
    """
    def __init__(self, db_path: str = "agent_data/trading_audit.db") -> None:
        self.db_path = db_path
        self._lock = Lock()
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._init_db()
        self._last_hash = self._get_last_hash()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trading_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    compliance_record_id TEXT UNIQUE NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    record_hash TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def _get_last_hash(self) -> str:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT record_hash FROM trading_audit_events
                ORDER BY id DESC LIMIT 1
                """
            ).fetchone()
            return row["record_hash"] if row else "GENESIS_HASH"

    def _generate_compliance_id(self, timestamp: str) -> str:
        # e.g., TRD-20231024-153022-XXXX
        time_part = datetime.fromisoformat(timestamp).strftime("%Y%m%d-%H%M%S")
        random_suffix = os.urandom(4).hex().upper()
        return f"TRD-{time_part}-{random_suffix}"

    def _compute_hash(self, payload_str: str, prev_hash: str, timestamp: str) -> str:
        data = f"{prev_hash}:{timestamp}:{payload_str}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def log(
        self,
        event_type: str,
        actor: str,
        payload: Dict[str, Any]
    ) -> str:
        """
        Logs an immutable event and returns the generated compliance_record_id.
        """
        with self._lock:
            timestamp = datetime.now(UTC).isoformat()
            compliance_id = self._generate_compliance_id(timestamp)
            payload_str = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            
            # Compute hash chain
            record_hash = self._compute_hash(payload_str, self._last_hash, timestamp)

            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO trading_audit_events(
                        timestamp, compliance_record_id, event_type, 
                        actor, payload, previous_hash, record_hash
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        timestamp,
                        compliance_id,
                        event_type,
                        actor,
                        payload_str,
                        self._last_hash,
                        record_hash
                    ),
                )
                conn.commit()
            
            self._last_hash = record_hash
            return compliance_id

    def list_events(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT timestamp, compliance_record_id, event_type, actor, payload, previous_hash, record_hash
                FROM trading_audit_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "timestamp": row["timestamp"],
                    "compliance_record_id": row["compliance_record_id"],
                    "event_type": row["event_type"],
                    "actor": row["actor"],
                    "payload": json.loads(row["payload"]),
                    "previous_hash": row["previous_hash"],
                    "record_hash": row["record_hash"]
                }
            )
        return events

    def verify_chain(self) -> bool:
        """
        Verifies the cryptographic integrity of the entire audit chain.
        Returns True if intact, False if tampered with.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT timestamp, payload, previous_hash, record_hash
                FROM trading_audit_events
                ORDER BY id ASC
                """
            ).fetchall()
            
            current_expected_prev_hash = "GENESIS_HASH"
            for row in rows:
                if row["previous_hash"] != current_expected_prev_hash:
                    return False
                
                calculated_hash = self._compute_hash(row["payload"], row["previous_hash"], row["timestamp"])
                if calculated_hash != row["record_hash"]:
                    return False
                
                current_expected_prev_hash = row["record_hash"]
                
        return True
