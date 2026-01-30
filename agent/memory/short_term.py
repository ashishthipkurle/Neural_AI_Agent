"""
Short-Term Memory - Session-based working memory.

This module provides temporary memory storage for the current session,
enabling context awareness within conversations.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import threading


@dataclass
class MemoryEntry:
    """Single short-term memory entry."""
    id: str
    content: str
    type: str  # message, action, observation, context
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5


class ShortTermMemory:
    """
    Session-based short-term memory.
    
    Features:
    - Fixed capacity with FIFO eviction
    - Recent memory retrieval
    - Message history tracking
    - Context window for LLM
    
    Short-term memory is NOT persisted across sessions.
    """
    
    MAX_ENTRIES = 100
    MAX_CONTEXT_ENTRIES = 10
    
    def __init__(self, max_entries: int = None):
        """
        Initialize short-term memory.
        
        Args:
            max_entries: Maximum entries to store.
        """
        self.logger = logging.getLogger("ShortTermMemory")
        self.max_entries = max_entries or self.MAX_ENTRIES
        
        self._entries: deque = deque(maxlen=self.max_entries)
        self._message_history: deque = deque(maxlen=50)
        self._entry_counter = 0
        self._lock = threading.RLock()
        
        self.logger.info(f"ShortTermMemory initialized (max={self.max_entries})")
    
    def _generate_id(self) -> str:
        """Generate entry ID."""
        with self._lock:
            self._entry_counter += 1
            return f"stm_{self._entry_counter}"
    
    def add(
        self,
        content: str,
        type: str = "general",
        importance: float = 0.5,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Add entry to short-term memory.
        
        Args:
            content: Memory content.
            type: Type of memory entry.
            importance: Importance score (0-1).
            metadata: Additional metadata.
        
        Returns:
            Entry ID.
        """
        entry = MemoryEntry(
            id=self._generate_id(),
            content=content,
            type=type,
            timestamp=datetime.now().isoformat(),
            importance=importance,
            metadata=metadata or {}
        )
        
        with self._lock:
            self._entries.append(entry)
        
        self.logger.debug(f"Added STM entry: {entry.id}")
        return entry.id
    
    def add_message(self, role: str, content: str) -> str:
        """
        Add conversation message.
        
        Args:
            role: Role (user, assistant, system).
            content: Message content.
        
        Returns:
            Entry ID.
        """
        with self._lock:
            self._message_history.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
        
        return self.add(
            content=content,
            type="message",
            metadata={"role": role}
        )
    
    def add_action(self, action: str, result: str) -> str:
        """Add action record."""
        return self.add(
            content=f"Action: {action} -> Result: {result}",
            type="action",
            importance=0.7
        )
    
    def add_observation(self, observation: str) -> str:
        """Add observation (e.g., from vision)."""
        return self.add(
            content=observation,
            type="observation",
            importance=0.6
        )
    
    def get_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Get n most recent entries.
        
        Args:
            n: Number of entries.
        
        Returns:
            List of entry dicts.
        """
        with self._lock:
            entries = list(self._entries)[-n:]
            return [
                {
                    "id": e.id,
                    "text": e.content,
                    "type": e.type,
                    "timestamp": e.timestamp,
                    "importance": e.importance,
                    **e.metadata
                }
                for e in entries
            ]
    
    def get_message_history(self, n: int = 10) -> List[Dict[str, str]]:
        """
        Get recent message history for LLM context.
        
        Args:
            n: Number of messages.
        
        Returns:
            List of message dicts.
        """
        with self._lock:
            return list(self._message_history)[-n:]
    
    def get_context_string(self, max_entries: int = None) -> str:
        """
        Get context string for LLM injection.
        
        Args:
            max_entries: Maximum entries to include.
        
        Returns:
            Formatted context string.
        """
        n = max_entries or self.MAX_CONTEXT_ENTRIES
        recent = self.get_recent(n)
        
        if not recent:
            return ""
        
        lines = ["--- SHORT-TERM MEMORY ---"]
        for entry in recent:
            lines.append(f"[{entry['type']}] {entry['text']}")
        
        return "\n".join(lines)
    
    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Simple text search in short-term memory.
        
        Args:
            query: Search query.
            limit: Maximum results.
        
        Returns:
            Matching entries.
        """
        query_lower = query.lower()
        results = []
        
        with self._lock:
            for entry in reversed(self._entries):
                if query_lower in entry.content.lower():
                    results.append({
                        "id": entry.id,
                        "text": entry.content,
                        "type": entry.type,
                        "timestamp": entry.timestamp
                    })
                    if len(results) >= limit:
                        break
        
        return results
    
    def clear(self) -> None:
        """Clear all short-term memory."""
        with self._lock:
            self._entries.clear()
            self._message_history.clear()
        self.logger.info("Short-term memory cleared.")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        with self._lock:
            return {
                "total_entries": len(self._entries),
                "max_entries": self.max_entries,
                "message_count": len(self._message_history),
                "entry_types": self._count_by_type()
            }
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count entries by type."""
        counts = {}
        for entry in self._entries:
            counts[entry.type] = counts.get(entry.type, 0) + 1
        return counts
