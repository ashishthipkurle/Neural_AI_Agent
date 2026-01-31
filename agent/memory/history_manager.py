
import sqlite3
import json
import uuid
import logging
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("HistoryManager")

class HistoryManager:
    """
    Manages persistent chat history using SQLite.
    Stores conversations and their messages.
    """
    
    def __init__(self, db_path: str = "agent/db/history.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        
    def _init_db(self):
        """Initialize database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Conversations Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at REAL,
                    updated_at REAL
                )
                """)
                
                # Messages Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp REAL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
                """)
                
                conn.commit()
                logger.info(f"Chat history database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize history database: {e}")
            raise

    def create_conversation(self, title: str = "New Chat") -> str:
        """Create a new conversation and return its ID."""
        conv_id = str(uuid.uuid4())
        now = time.time()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (conv_id, title, now, now)
                )
                conn.commit()
                return conv_id
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            return None

    def get_conversations(self, limit: int = 50) -> list:
        """Get list of conversations, sorted by update time (newest first)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                
                return [
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "created_at": datetime.fromtimestamp(row["created_at"]).isoformat(),
                        "updated_at": datetime.fromtimestamp(row["updated_at"]).isoformat()
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get conversations: {e}")
            return []

    def get_conversation(self, conversation_id: str) -> dict:
        """Get a single conversation metadata."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
                row = cursor.fetchone()
                
                if row:
                    return {
                        "id": row["id"],
                        "title": row["title"],
                        "created_at": datetime.fromtimestamp(row["created_at"]).isoformat(),
                        "updated_at": datetime.fromtimestamp(row["updated_at"]).isoformat()
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get conversation {conversation_id}: {e}")
            return None

    def update_conversation_title(self, conversation_id: str, title: str):
        """Update the title of a conversation."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE conversations SET title = ? WHERE id = ?",
                    (title, conversation_id)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update title for {conversation_id}: {e}")

    def delete_conversation(self, conversation_id: str):
        """Delete a conversation and all its messages."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Foreign key constraint should handle messages, but explicit is safer in some sqlite versions
                cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
                cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
                conn.commit()
                logger.info(f"Deleted conversation {conversation_id}")
        except Exception as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {e}")

    def add_message(self, conversation_id: str, role: str, content: str, msg_id: str = None) -> str:
        """Add a message to a conversation."""
        if not msg_id:
            msg_id = str(uuid.uuid4())
        
        now = time.time()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if conversation exists
                cursor.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,))
                if not cursor.fetchone():
                    logger.warning(f"Conversation {conversation_id} not found, creating it.")
                    cursor.execute(
                        "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        (conversation_id, "New Chat", now, now)
                    )

                cursor.execute(
                    "INSERT INTO messages (id, conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (msg_id, conversation_id, role, content, now)
                )
                
                # Update conversation timestamp
                cursor.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conversation_id)
                )
                
                # Auto-generate title on first user message using LLM
                if role == "user":
                    cursor.execute("SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (conversation_id,))
                    count = cursor.fetchone()[0]
                    if count == 1:  # This is the FIRST message in the conversation
                        new_title = self._generate_topic_title(content)
                        cursor.execute(
                            "UPDATE conversations SET title = ? WHERE id = ?",
                            (new_title, conversation_id)
                        )
                
                conn.commit()
                return msg_id
        except Exception as e:
            logger.error(f"Failed to add message to {conversation_id}: {e}")
            return None

    def _generate_topic_title(self, user_message: str) -> str:
        """Generate a short topic title from the user's first message using the LLM."""
        logger.info(f"Generating title for message: {user_message[:50]}...")
        
        # First, try LLM generation
        try:
            import httpx
            
            # Use Ollama to generate a short title
            prompt = f"""Generate a very short (2-5 words) title that summarizes this conversation topic.
User's message: "{user_message[:200]}"

Respond with ONLY the title, nothing else. No quotes, no punctuation at the end.
Examples: Stock Market Analysis, Weather Forecast, Python Debugging, Browser Automation"""

            response = httpx.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "phi3:mini",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 20
                    }
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                title = data.get("response", "").strip()
                # Clean up: remove quotes, limit length
                title = title.strip('"\'').strip()
                # Remove any trailing punctuation
                title = title.rstrip('.!?:;,')
                if len(title) > 50:
                    title = title[:47] + "..."
                if title and len(title) > 3:
                    logger.info(f"LLM generated title: {title}")
                    return title
            else:
                logger.warning(f"LLM title generation returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"LLM title generation failed: {e}")
        
        # Fallback: Create a cleaner title from the message itself
        # Remove common filler words and create a meaningful summary
        import re
        clean_msg = re.sub(r'[^\w\s]', '', user_message)  # Remove punctuation
        words = clean_msg.split()
        
        # Skip common filler words at the start
        skip_words = {'hey', 'hello', 'hi', 'can', 'you', 'please', 'could', 'would', 'i', 'want', 'to', 'the', 'a', 'an', 'what', 'how', 'is', 'are'}
        filtered_words = [w for w in words if w.lower() not in skip_words]
        
        if len(filtered_words) >= 2:
            title = " ".join(filtered_words[:4]).title()
        elif len(words) >= 2:
            title = " ".join(words[:4]).title()
        else:
            title = user_message[:30]
        
        if len(title) > 40:
            title = title[:37] + "..."
        
        logger.info(f"Fallback title: {title}")
        return title

    def get_messages(self, conversation_id: str) -> list:
        """Get all messages for a conversation, ordered by time."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC",
                    (conversation_id,)
                )
                rows = cursor.fetchall()
                
                return [
                    {
                        "id": row["id"],
                        "role": row["role"],
                        "content": row["content"],
                        "timestamp": datetime.fromtimestamp(row["timestamp"]).isoformat()
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get messages for {conversation_id}: {e}")
            return []
