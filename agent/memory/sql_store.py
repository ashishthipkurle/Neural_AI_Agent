import sqlite3
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

class SQLStore:
    """
    Manages SQLite database for logs and structured entity data.
    """
    def __init__(self, db_path: str = "agent/memory/agent_memory.db"):
        self.logger = logging.getLogger("SQLStore")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """
        Initialize the database tables.
        """
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Events table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        description TEXT,
                        location TEXT
                    )
                ''')
                # Faces table (Identity metadata)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS faces (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        date_added TEXT NOT NULL,
                        last_seen TEXT
                    )
                ''')
                conn.commit()
        except Exception as e:
            self.logger.error(f"DB Initialization Error: {e}")

    def log_event(self, event_type: str, description: str, location: str = "local"):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO events (timestamp, event_type, description, location) VALUES (?, ?, ?, ?)",
                    (datetime.now().isoformat(), event_type, description, location)
                )
                conn.commit()
        except Exception as e:
            self.logger.error(f"Log Event Error: {e}")

    def add_face(self, name: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO faces (name, date_added, last_seen) VALUES (?, ?, ?)",
                    (name, datetime.now().isoformat(), datetime.now().isoformat())
                )
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Add Face Error: {e}")
            return False

    def get_face_id(self, name: str) -> Optional[int]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM faces WHERE name = ?", (name,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            self.logger.error(f"Get Face ID Error: {e}")
            return None

    def remove_face(self, name: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM faces WHERE name = ?", (name,))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Remove Face Error: {e}")
            return False
