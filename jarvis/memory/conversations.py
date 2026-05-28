"""
INDRA Conversation Logger — stores voice interactions to JSON files.
Each conversation is a session from wake-word to idle.
"""

import json
import os
import time
import uuid
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("ConvLog")

CONV_DIR = Path(__file__).parent.parent / "data" / "conversations"
CONV_DIR.mkdir(parents=True, exist_ok=True)


class ConversationLogger:
    """Logs INDRA voice interactions to disk."""

    def __init__(self):
        self._current_id = None
        self._current_messages = []
        self._current_title = "New Session"
        self._start_time = None

    def start_session(self):
        """Begin a new conversation session."""
        self._current_id = str(uuid.uuid4())[:8]
        self._current_messages = []
        self._current_title = "New Session"
        self._start_time = time.time()
        logger.debug(f"Conversation started: {self._current_id}")
        return self._current_id

    def log_user(self, text: str):
        """Log what the user said."""
        if not self._current_id:
            self.start_session()

        # Use the first user message as the title
        if self._current_title == "New Session" and text.strip():
            self._current_title = text.strip()[:60]

        self._current_messages.append({
            "role": "user",
            "content": text,
            "timestamp": time.time()
        })

    def log_indra(self, text: str):
        """Log what INDRA said."""
        if not self._current_id:
            self.start_session()

        self._current_messages.append({
            "role": "assistant",
            "content": text,
            "timestamp": time.time()
        })

    def end_session(self):
        """Save the current session to disk."""
        if not self._current_id or not self._current_messages:
            return

        data = {
            "id": self._current_id,
            "title": self._current_title,
            "created_at": self._start_time,
            "updated_at": time.time(),
            "messages": self._current_messages
        }

        filepath = CONV_DIR / f"{self._current_id}.json"
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Conversation saved: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")

        self._current_id = None
        self._current_messages = []

    def save_current(self):
        """Save without ending — auto-save after each exchange."""
        if not self._current_id or not self._current_messages:
            return

        data = {
            "id": self._current_id,
            "title": self._current_title,
            "created_at": self._start_time,
            "updated_at": time.time(),
            "messages": self._current_messages
        }

        filepath = CONV_DIR / f"{self._current_id}.json"
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def get_all_conversations(self) -> list:
        """Get all conversations (newest first), lightweight — no messages."""
        conversations = []
        for f in CONV_DIR.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    conversations.append({
                        "id": data.get("id", f.stem),
                        "title": data.get("title", "Untitled"),
                        "created_at": data.get("created_at", 0),
                        "updated_at": data.get("updated_at", 0),
                        "message_count": len(data.get("messages", []))
                    })
            except Exception:
                pass

        conversations.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return conversations

    def get_conversation(self, conv_id: str) -> dict | None:
        """Get a full conversation with messages."""
        filepath = CONV_DIR / f"{conv_id}.json"
        if not filepath.exists():
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation."""
        filepath = CONV_DIR / f"{conv_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False
