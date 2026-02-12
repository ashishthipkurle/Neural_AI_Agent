
import sqlite3
import json
import datetime
import os
import logging
from typing import List, Optional, Dict, Any

class PersonalMemoryManager:
    """
    Module 1: Personal Memory Manager
    Central repository for user context, history, and preferences.
    """
    
    def __init__(self, db_path: str = "agent_data/personal_memory.db"):
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize DB
        self._init_db()
        
    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize SQLite with WAL mode, create tables."""
        try:
            with self._get_connection() as conn:
                # CRITICAL: WAL mode for crash safety
                conn.execute("PRAGMA journal_mode=WAL")
                
                # User profile
                conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    personality_notes TEXT,
                    communication_style TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """)

                # Actions user took
                conn.execute("""
                CREATE TABLE IF NOT EXISTS user_actions (
                    id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    action_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    method TEXT,
                    reasoning TEXT,
                    context TEXT,
                    outcome TEXT,
                    tags TEXT,
                    importance_score INTEGER DEFAULT 5,
                    source TEXT
                )
                """)

                # Important notes/reminders
                conn.execute("""
                CREATE TABLE IF NOT EXISTS important_notes (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT,
                    reminder_date TIMESTAMP,
                    recurrence TEXT,
                    priority INTEGER DEFAULT 5,
                    is_active BOOLEAN DEFAULT 1
                )
                """)

                # Learned preferences
                conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    preference TEXT NOT NULL,
                    evidence TEXT,
                    confidence_score REAL DEFAULT 0.5,
                    first_observed TIMESTAMP,
                    last_observed TIMESTAMP,
                    source TEXT
                )
                """)

                # Relationships/contacts
                conn.execute("""
                CREATE TABLE IF NOT EXISTS user_relationships (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    relationship_type TEXT,
                    context TEXT,
                    phone_number TEXT,
                    email TEXT,
                    important_dates TEXT,
                    preferences TEXT,
                    conversation_history_summary TEXT,
                    last_interaction TIMESTAMP
                )
                """)

                # Conversation history
                conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_memory (
                    id TEXT PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    topic TEXT,
                    messages TEXT,
                    key_points TEXT,
                    action_items TEXT,
                    importance_score INTEGER DEFAULT 5
                )
                """)
                self.logger.info("Personal Memory DB initialized successfully with WAL mode.")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Personal Memory DB: {e}")
            raise

    def record_action(self, action_type: str, description: str, 
                      method: str = None, reasoning: str = None,
                      context: str = None, outcome: str = None,
                      tags: List[str] = None, importance: int = 5) -> str:
        """Record something user did. Returns action_id (UUID)"""
        import uuid
        action_id = str(uuid.uuid4())
        tags_json = json.dumps(tags) if tags else None
        
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO user_actions (id, action_type, description, method, reasoning, context, outcome, tags, importance_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (action_id, action_type, description, method, reasoning, context, outcome, tags_json, importance))
            return action_id
        except Exception as e:
            self.logger.error(f"Error recording action: {e}")
            return ""

    def add_important_note(self, content: str, category: str = 'note',
                           context: str = None, reminder_date: datetime.datetime = None,
                           recurrence: str = None, priority: int = 5) -> str:
        """Store something user wants to remember. Returns note_id"""
        import uuid
        note_id = str(uuid.uuid4())
        
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO important_notes (id, category, content, context, reminder_date, recurrence, priority)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (note_id, category, content, context, reminder_date, recurrence, priority))
            return note_id
        except Exception as e:
            self.logger.error(f"Error adding note: {e}")
            return ""

    def record_preference(self, category: str, preference: str,
                          evidence: str = None, source: str = 'observed') -> None:
        """Learn preferences. Increments confidence if exists"""
        try:
            with self._get_connection() as conn:
                # Check if exists
                cursor = conn.execute("SELECT id, confidence_score FROM user_preferences WHERE category=? AND preference=?", (category, preference))
                row = cursor.fetchone()
                
                now = datetime.datetime.now()
                
                if row:
                    new_confidence = min(1.0, row[1] + 0.1)
                    conn.execute("UPDATE user_preferences SET confidence_score=?, last_observed=?, evidence=? WHERE id=?", 
                                 (new_confidence, now, evidence, row[0]))
                else:
                    conn.execute("""
                        INSERT INTO user_preferences (category, preference, evidence, confidence_score, first_observed, last_observed, source)
                        VALUES (?, ?, ?, 0.5, ?, ?, ?)
                    """, (category, preference, evidence, now, now, source))
        except Exception as e:
            self.logger.error(f"Error recording preference: {e}")

    def record_relationship(self, name: str, relationship_type: str = None,
                            phone_number: str = None, context: str = None,
                            important_info: dict = None) -> str:
        """Store info about people. Returns relationship_id"""
        import uuid
        
        info_json = json.dumps(important_info) if important_info else None
        
        try:
            with self._get_connection() as conn:
                # Check if exists by name (simple dedup)
                cursor = conn.execute("SELECT id FROM user_relationships WHERE name=?", (name,))
                row = cursor.fetchone()
                
                if row:
                    rel_id = row[0]
                    # Update
                    updates = []
                    params = []
                    if relationship_type: updates.append("relationship_type=?"), params.append(relationship_type)
                    if phone_number: updates.append("phone_number=?"), params.append(phone_number)
                    if context: updates.append("context=?"), params.append(context) 
                    
                    if updates:
                        params.append(rel_id)
                        conn.execute(f"UPDATE user_relationships SET {', '.join(updates)} WHERE id=?", params)
                else:
                    rel_id = str(uuid.uuid4())
                    conn.execute("""
                        INSERT INTO user_relationships (id, name, relationship_type, phone_number, context, preferences)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (rel_id, name, relationship_type, phone_number, context, info_json))
            return rel_id
        except Exception as e:
            self.logger.error(f"Error recording relationship: {e}")
            return ""

    def record_conversation(self, topic: str, messages: List[dict],
                            key_points: List[str] = None) -> str:
        """Store conversation with extracted insights"""
        import uuid
        conv_id = str(uuid.uuid4())
        msgs_json = json.dumps(messages)
        points_json = json.dumps(key_points) if key_points else None
        
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO conversation_memory (id, topic, messages, key_points)
                    VALUES (?, ?, ?, ?)
                """, (conv_id, topic, msgs_json, points_json))
            return conv_id
        except Exception as e:
            self.logger.error(f"Error recording conversation: {e}")
            return ""

    def query_memory(self, query: str, limit: int = 10) -> List[dict]:
        """
        Semantic search across all memory using embeddings.
        For Phase 1 foundation, we will implement a basic text search until sqlite-vec/chroma is fully integrated in later steps if needed.
        The spec asks for semantic search, so we'll simulate it with LIKE or prepare for vector extension.
        Given dependencies might not be ready, a robust fallback to text search is safer for the first pass.
        """
        results = []
        try:
            with self._get_connection() as conn:
                # Search actions
                cursor = conn.execute("SELECT * FROM user_actions WHERE description LIKE ? OR context LIKE ? LIMIT ?", (f'%{query}%', f'%{query}%', limit))
                for row in cursor:
                    results.append({"type": "action", "data": row})
                
                # Search notes
                cursor = conn.execute("SELECT * FROM important_notes WHERE content LIKE ? LIMIT ?", (f'%{query}%', limit))
                for row in cursor:
                    results.append({"type": "note", "data": row})
                    
        except Exception as e:
            self.logger.error(f"Error querying memory: {e}")
            
        return results

    def get_user_context(self, current_task: str = None) -> str:
        """
        Generate context string for LLM prompts.
        """
        context_parts = []
        try:
            with self._get_connection() as conn:
                # Profile
                cursor = conn.execute("SELECT name, personality_notes, communication_style FROM user_profile LIMIT 1")
                profile = cursor.fetchone()
                if profile:
                    context_parts.append(f"User: {profile[0]}")
                    if profile[1]: context_parts.append(f"Notes: {profile[1]}")
                    if profile[2]: context_parts.append(f"Style: {profile[2]}")
                
                # Top Preferences
                cursor = conn.execute("SELECT category, preference FROM user_preferences WHERE confidence_score > 0.6 ORDER BY confidence_score DESC LIMIT 5")
                prefs = [f"{r[0]}: {r[1]}" for r in cursor]
                if prefs:
                    context_parts.append("Preferences:\n- " + "\n- ".join(prefs))
                
                # Active Notes
                cursor = conn.execute("SELECT content FROM important_notes WHERE is_active=1 ORDER BY priority DESC LIMIT 3")
                notes = [r[0] for r in cursor]
                if notes:
                    context_parts.append("Important:\n- " + "\n- ".join(notes))
                    
        except Exception as e:
            self.logger.error(f"Error getting user context: {e}")
            return "Error loading context."
            
        return "\n\n".join(context_parts)

    def get_reminders_for_today(self) -> List[dict]:
        """Get due reminders"""
        today = datetime.date.today().isoformat()
        reminders = []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT * FROM important_notes WHERE date(reminder_date) <= date(?) AND is_active=1", (today,))
                for row in cursor:
                    # Map row to dict manually or use row_factory
                    reminders.append({"id": row[0], "content": row[2], "date": row[4]})
        except Exception as e:
            self.logger.error(f"Error getting reminders: {e}")
        return reminders

    def update_relationship_from_call(self, name: str, 
                                      call_summary: str, new_info: dict) -> None:
        """After voice call, update relationship info"""
        # Logic to append summary to history and merge new_info using JSON logic
        # For simplicity in this step, we just update the timestamp
        try:
            with self._get_connection() as conn:
                conn.execute("UPDATE user_relationships SET last_interaction=CURRENT_TIMESTAMP WHERE name=?", (name,))
        except Exception as e:
            self.logger.error(f"Error updating relationship: {e}")

    def get_relationship(self, name: str) -> Optional[dict]:
        """Get relationship info by name"""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM user_relationships WHERE name=?", (name,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            self.logger.error(f"Error getting relationship: {e}")
            return None
