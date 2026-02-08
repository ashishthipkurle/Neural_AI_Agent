"""
Memory Skill - Persistent personal memory for the agent.

Provides:
- Long-term memory (Named facts, preferences)
- Short-term context (Conversation history)
- Semantic search (Vector similarity)
- Memory operations (Remember, Recall, Forget, Summarize)

Uses existing memory infrastructure from agent/memory/
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth


class MemorySkill(BaseSkill):
    """
    Personal memory skill for the agent.
    
    Actions:
    - remember: Store a fact with optional tags
    - recall: Search memories by query
    - forget: Remove specific memory
    - list_memories: List all memories
    - get_preferences: Get user preferences
    - set_preference: Set a user preference
    - summarize: Summarize recent memories
    - clear: Clear all memories (with confirmation)
    """
    
    MEMORY_DIR = Path("agent/data/memory")
    
    def __init__(self):
        super().__init__()
        self._memories: List[Dict] = []
        self._preferences: Dict[str, Any] = {}
        self._vector_store = None  # Will use existing if available
    
    @property
    def name(self) -> str:
        return "memory"
    
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="memory",
            version="1.0.0",
            description="Persistent personal memory with semantic search",
            actions=[
                "remember", "recall", "forget", "list_memories",
                "get_preferences", "set_preference", "summarize", "clear"
            ],
            requires=["sentence-transformers", "faiss-cpu"],
            permissions=["memory"]
        )
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """Load existing memories and preferences."""
        try:
            self.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            
            # Load memories
            memories_file = self.MEMORY_DIR / "memories.json"
            if memories_file.exists():
                with open(memories_file, 'r') as f:
                    self._memories = json.load(f)
            
            # Load preferences
            prefs_file = self.MEMORY_DIR / "preferences.json"
            if prefs_file.exists():
                with open(prefs_file, 'r') as f:
                    self._preferences = json.load(f)
            
            # Try to load vector store
            self._init_vector_store()
            
            super().on_load()
            self.logger.info(f"Memory skill loaded. {len(self._memories)} memories, {len(self._preferences)} prefs.")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize memory skill: {e}")
            self._health = SkillHealth.DEGRADED
    
    def _init_vector_store(self):
        """Initialize the vector store for semantic search."""
        try:
            from agent.memory.vector_store import VectorMemoryStore
            self._vector_store = VectorMemoryStore()
            self.logger.info("Vector store initialized for semantic search.")
        except Exception as e:
            self.logger.warning(f"Vector store not available: {e}")
            self._vector_store = None
    
    def on_unload(self) -> None:
        """Save memories and preferences."""
        self._save_memories()
        self._save_preferences()
        super().on_unload()
    
    def _save_memories(self):
        """Persist memories to disk."""
        try:
            memories_file = self.MEMORY_DIR / "memories.json"
            with open(memories_file, 'w') as f:
                json.dump(self._memories, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save memories: {e}")
    
    def _save_preferences(self):
        """Persist preferences to disk."""
        try:
            prefs_file = self.MEMORY_DIR / "preferences.json"
            with open(prefs_file, 'w') as f:
                json.dump(self._preferences, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save preferences: {e}")
    
    # ==================== INTENT MATCHING ====================
    
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill can handle the intent."""
        intent_lower = intent.lower()
        
        # High confidence patterns
        high_patterns = [
            "remember", "recall", "forget",
            "what did i say", "what do you know about",
            "my preference", "i prefer", "note that",
            "store this", "save this", "don't forget"
        ]
        
        for pattern in high_patterns:
            if pattern in intent_lower:
                return 0.9
        
        # Medium patterns
        if any(x in intent_lower for x in ["memory", "memories"]):
            return 0.7
        
        return 0.0
    
    # ==================== EXECUTION ====================
    
    def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Execute a memory action."""
        
        handlers = {
            "remember": self._action_remember,
            "recall": self._action_recall,
            "forget": self._action_forget,
            "list_memories": self._action_list,
            "get_preferences": self._action_get_preferences,
            "set_preference": self._action_set_preference,
            "summarize": self._action_summarize,
            "clear": self._action_clear,
        }
        
        handler = handlers.get(action)
        if not handler:
            # Try to interpret natural language
            handler = self._interpret_action(action, params)
            if not handler:
                return SkillResult(success=False, error=f"Unknown action: {action}")
        
        try:
            result = handler(params, context or {})
            # Auto-save after modifications
            if action in ["remember", "forget", "set_preference", "clear"]:
                self._save_memories()
                self._save_preferences()
            return result
        except Exception as e:
            self.logger.error(f"Memory action '{action}' failed: {e}")
            return SkillResult(success=False, error=str(e))
    
    def _interpret_action(self, intent: str, params: Dict):
        """Interpret natural language intent."""
        intent_lower = intent.lower()
        
        if any(x in intent_lower for x in ["remember", "note", "store", "save"]):
            return self._action_remember
        if any(x in intent_lower for x in ["recall", "what", "find", "search"]):
            return self._action_recall
        if "forget" in intent_lower:
            return self._action_forget
        
        return None
    
    # ==================== ACTIONS ====================
    
    def _action_remember(self, params: Dict, context: Dict) -> SkillResult:
        """Store a memory."""
        content = params.get("content") or params.get("text") or params.get("fact")
        tags = params.get("tags", [])
        category = params.get("category", "general")
        
        if not content:
            # Try to extract from natural language
            return SkillResult(success=False, error="Content required to remember")
        
        memory = {
            "id": len(self._memories) + 1,
            "content": content,
            "tags": tags if isinstance(tags, list) else [tags],
            "category": category,
            "created_at": datetime.now().isoformat(),
            "importance": params.get("importance", 1)
        }
        
        self._memories.append(memory)
        
        # Also add to vector store if available
        if self._vector_store:
            try:
                self._vector_store.add(content, metadata=memory)
            except:
                pass
        
        return SkillResult(
            success=True,
            data={"memory_id": memory["id"]},
            message=f"Remembered: {content[:50]}..."
        )
    
    def _action_recall(self, params: Dict, context: Dict) -> SkillResult:
        """Search memories."""
        query = params.get("query") or params.get("about") or params.get("search")
        limit = params.get("limit", 5)
        category = params.get("category")
        
        if not query:
            return SkillResult(success=False, error="Query required for recall")
        
        results = []
        
        # Try vector search first
        if self._vector_store:
            try:
                vector_results = self._vector_store.search(query, k=limit)
                results = [r["metadata"] for r in vector_results if "metadata" in r]
            except:
                pass
        
        # Fallback to simple text search
        if not results:
            query_lower = query.lower()
            for mem in self._memories:
                if query_lower in mem["content"].lower():
                    results.append(mem)
                elif any(query_lower in tag.lower() for tag in mem.get("tags", [])):
                    results.append(mem)
            
            results = results[:limit]
        
        # Filter by category if specified
        if category:
            results = [r for r in results if r.get("category") == category]
        
        return SkillResult(
            success=True,
            data={"memories": results, "count": len(results)},
            message=f"Found {len(results)} matching memories"
        )
    
    def _action_forget(self, params: Dict, context: Dict) -> SkillResult:
        """Remove a memory."""
        memory_id = params.get("id")
        query = params.get("query")
        
        if memory_id:
            # Remove by ID
            self._memories = [m for m in self._memories if m.get("id") != memory_id]
            return SkillResult(success=True, message=f"Forgot memory {memory_id}")
        
        if query:
            # Remove matching memories
            initial_count = len(self._memories)
            query_lower = query.lower()
            self._memories = [
                m for m in self._memories 
                if query_lower not in m["content"].lower()
            ]
            removed = initial_count - len(self._memories)
            return SkillResult(success=True, message=f"Forgot {removed} memories matching '{query}'")
        
        return SkillResult(success=False, error="Memory ID or query required")
    
    def _action_list(self, params: Dict, context: Dict) -> SkillResult:
        """List all memories."""
        category = params.get("category")
        limit = params.get("limit", 20)
        
        memories = self._memories
        if category:
            memories = [m for m in memories if m.get("category") == category]
        
        memories = memories[-limit:]  # Most recent
        
        return SkillResult(
            success=True,
            data={"memories": memories, "total": len(self._memories)},
            message=f"Showing {len(memories)} of {len(self._memories)} memories"
        )
    
    def _action_get_preferences(self, params: Dict, context: Dict) -> SkillResult:
        """Get user preferences."""
        key = params.get("key")
        
        if key:
            value = self._preferences.get(key)
            return SkillResult(
                success=True,
                data={"key": key, "value": value},
                message=f"{key}: {value}" if value else f"{key} not set"
            )
        
        return SkillResult(
            success=True,
            data={"preferences": self._preferences},
            message=f"{len(self._preferences)} preferences stored"
        )
    
    def _action_set_preference(self, params: Dict, context: Dict) -> SkillResult:
        """Set a user preference."""
        key = params.get("key")
        value = params.get("value")
        
        if not key:
            return SkillResult(success=False, error="Preference key required")
        
        self._preferences[key] = value
        
        return SkillResult(
            success=True,
            message=f"Set preference: {key} = {value}"
        )
    
    def _action_summarize(self, params: Dict, context: Dict) -> SkillResult:
        """Summarize recent memories."""
        limit = params.get("limit", 10)
        recent = self._memories[-limit:]
        
        if not recent:
            return SkillResult(success=True, message="No memories to summarize")
        
        # Simple summary - in production, use LLM
        summary = f"You have {len(self._memories)} memories. Recent topics: "
        categories = set(m.get("category", "general") for m in recent)
        summary += ", ".join(categories)
        
        return SkillResult(
            success=True,
            data={"summary": summary, "count": len(recent)},
            message=summary
        )
    
    def _action_clear(self, params: Dict, context: Dict) -> SkillResult:
        """Clear all memories (requires confirmation)."""
        confirmed = params.get("confirmed", False)
        
        if not confirmed:
            return SkillResult(
                success=False,
                error="Confirmation required to clear all memories. Set confirmed=True"
            )
        
        count = len(self._memories)
        self._memories = []
        
        return SkillResult(
            success=True,
            message=f"Cleared {count} memories"
        )
    
    # ==================== HEALTH ====================
    
    def health(self) -> SkillHealth:
        """Check memory skill health."""
        if not self._loaded:
            return SkillHealth.UNAVAILABLE
        if self._vector_store is None:
            return SkillHealth.DEGRADED  # Works but no semantic search
        return SkillHealth.READY
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """Preview memory action."""
        previews = {
            "remember": f"Would store: {params.get('content', 'unknown')[:50]}...",
            "recall": f"Would search for: {params.get('query', 'unknown')}",
            "forget": f"Would forget memory: {params.get('id') or params.get('query')}",
            "clear": "Would clear ALL memories (requires confirmation)",
        }
        
        return previews.get(action, f"Would execute memory.{action}")
