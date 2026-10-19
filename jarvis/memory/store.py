"""
INDRA Memory Store -- ChromaDB persistent vector storage.
Stores and recalls memories semantically for personalised interactions.
"""

import chromadb
from chromadb.config import Settings
from pathlib import Path
from datetime import datetime
import json
import sys
import os

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MEMORY_DB_PATH, MEMORY_RECALL_N
from utils.logger import get_logger

logger = get_logger("Memory")


class MemoryStore:
    """
    Persistent vector memory using ChromaDB.
    
    Collections:
      - identity:  Ashish's preferences, habits, facts (never decays)
      - sessions:  Per-session summaries and task outcomes (decays after 7 days)
      - projects:  Active project context (kept until marked done)
    """

    def __init__(self):
        db_path = Path(MEMORY_DB_PATH)
        db_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False)
        )

        # Create or get collections
        self.identity = self.client.get_or_create_collection(
            name="identity",
            metadata={"description": "Ashish's permanent preferences and facts"}
        )
        self.sessions = self.client.get_or_create_collection(
            name="sessions",
            metadata={"description": "Session summaries and task outcomes"}
        )
        self.projects = self.client.get_or_create_collection(
            name="projects",
            metadata={"description": "Active project context"}
        )

        logger.info(
            f"Memory loaded -- identity: {self.identity.count()}, "
            f"sessions: {self.sessions.count()}, "
            f"projects: {self.projects.count()}"
        )

    def save(self, text: str, collection: str = "sessions", metadata: dict = None):
        """
        Store a memory in the specified collection.
        
        Args:
            text: The memory content
            collection: 'identity', 'sessions', or 'projects'
            metadata: Optional metadata dict (e.g. {"type": "preference"})
        """
        col = self._get_collection(collection)
        doc_id = f"{collection}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        meta = metadata or {}
        meta["timestamp"] = datetime.now().isoformat()
        meta["collection"] = collection

        col.add(
            documents=[text],
            ids=[doc_id],
            metadatas=[meta]
        )
        logger.debug(f"Saved to {collection}: {text[:80]}...")

    def recall(self, query: str, n: int = None, collection: str = None) -> list[str]:
        """
        Recall memories relevant to a query via semantic search.
        
        Args:
            query: The search query
            n: Number of results (defaults to MEMORY_RECALL_N)
            collection: Specific collection, or None to search all
            
        Returns:
            List of memory strings, most relevant first.
        """
        n = n or MEMORY_RECALL_N
        results = []

        if collection:
            collections = [self._get_collection(collection)]
        else:
            collections = [self.identity, self.sessions, self.projects]

        for col in collections:
            if col.count() == 0:
                continue
            try:
                # Don't request more results than documents exist
                query_n = min(n, col.count())
                res = col.query(query_texts=[query], n_results=query_n)
                if res and res["documents"]:
                    results.extend(res["documents"][0])
            except Exception as e:
                logger.warning(f"Recall failed for {col.name}: {e}")

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for r in results:
            if r not in seen:
                seen.add(r)
                unique.append(r)

        return unique[:n]

    def save_identity(self, fact: str):
        """Store a permanent identity fact about Ashish."""
        self.save(fact, collection="identity", metadata={"type": "identity"})

    def save_session(self, summary: str):
        """Store a session summary."""
        self.save(summary, collection="sessions", metadata={"type": "session_summary"})

    def save_task_result(self, task: str, result: str, success: bool):
        """Store the outcome of a completed task."""
        text = f"Task: {task} | Result: {result} | Success: {success}"
        self.save(text, collection="sessions", metadata={
            "type": "task_result",
            "success": str(success)
        })

    def save_session_summary(self):
        """Called on shutdown -- stores a summary of the current session."""
        summary = f"Session ended at {datetime.now().strftime('%I:%M %p on %A %d %B %Y')}."
        self.save_session(summary)
        logger.info("Session summary saved to memory.")

    def is_empty(self) -> bool:
        """Check if identity collection is empty (for first-run detection)."""
        return self.identity.count() == 0

    def _get_collection(self, name: str):
        """Get collection by name."""
        return {
            "identity": self.identity,
            "sessions": self.sessions,
            "projects": self.projects
        }.get(name, self.sessions)

    def get_all_identity(self) -> list[str]:
        """Get all identity facts (for debugging/display)."""
        if self.identity.count() == 0:
            return []
        res = self.identity.get()
        return res.get("documents", [])
