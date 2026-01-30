"""
Memory Explainer - Memory explainability system.

This module provides explanations for why memories were stored
and how they relate to queries.
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class MemoryExplanation:
    """Explanation for a memory item."""
    memory_id: str
    memory_text: str
    storage_reason: str
    relevance_reason: str
    confidence: float
    related_memories: List[str]


class MemoryExplainer:
    """
    Provides explainability for memory operations.
    
    Features:
    - Explains why memories were stored
    - Explains relevance to queries
    - Shows memory relationships
    - Human-readable explanations
    """
    
    STORAGE_REASONS = {
        "user_request": "User explicitly asked to remember this.",
        "important_fact": "This appears to be an important fact about the user.",
        "preference": "This seems to be a user preference.",
        "action_result": "This is the result of an action.",
        "conversation": "This is part of our conversation history.",
        "observation": "This is an observation from visual input.",
        "system_event": "This is a system event record."
    }
    
    def __init__(self, memory_store=None):
        """
        Initialize memory explainer.
        
        Args:
            memory_store: Reference to memory store.
        """
        self.logger = logging.getLogger("MemoryExplainer")
        self.memory_store = memory_store
        self.logger.info("MemoryExplainer initialized.")
    
    def explain_storage(
        self,
        memory_text: str,
        memory_type: str,
        tags: List[str] = None
    ) -> str:
        """
        Explain why a memory was stored.
        
        Args:
            memory_text: The memory content.
            memory_type: Type of memory.
            tags: Memory tags.
        
        Returns:
            Human-readable explanation.
        """
        reason = self._infer_storage_reason(memory_text, memory_type, tags)
        
        explanation = f"Memory stored because: {reason}"
        
        if tags:
            explanation += f"\nTags: {', '.join(tags)}"
        
        explanation += f"\nType: {memory_type}"
        
        return explanation
    
    def _infer_storage_reason(
        self,
        text: str,
        memory_type: str,
        tags: List[str]
    ) -> str:
        """Infer why memory was stored."""
        text_lower = text.lower()
        
        # Check for explicit remember requests
        remember_phrases = ["remember", "don't forget", "note that", "keep in mind"]
        if any(phrase in text_lower for phrase in remember_phrases):
            return self.STORAGE_REASONS["user_request"]
        
        # Check for preference indicators
        preference_phrases = ["i like", "i prefer", "my favorite", "i love", "i hate"]
        if any(phrase in text_lower for phrase in preference_phrases):
            return self.STORAGE_REASONS["preference"]
        
        # Check for factual statements about user
        fact_phrases = ["my name is", "i am", "i work", "i live"]
        if any(phrase in text_lower for phrase in fact_phrases):
            return self.STORAGE_REASONS["important_fact"]
        
        # Default based on type
        if memory_type in self.STORAGE_REASONS:
            return self.STORAGE_REASONS[memory_type]
        
        return "This information may be useful for future interactions."
    
    def explain_retrieval(
        self,
        query: str,
        memory: Dict[str, Any],
        similarity_score: float
    ) -> MemoryExplanation:
        """
        Explain why a memory was retrieved for a query.
        
        Args:
            query: The search query.
            memory: Retrieved memory item.
            similarity_score: Similarity score.
        
        Returns:
            MemoryExplanation with details.
        """
        memory_text = memory.get("text", "")
        memory_id = memory.get("id", "unknown")
        
        # Analyze relevance
        relevance_reason = self._analyze_relevance(query, memory_text, similarity_score)
        
        # Get storage reason
        storage_reason = self._infer_storage_reason(
            memory_text,
            memory.get("type", "episodic"),
            memory.get("tags", [])
        )
        
        return MemoryExplanation(
            memory_id=memory_id,
            memory_text=memory_text,
            storage_reason=storage_reason,
            relevance_reason=relevance_reason,
            confidence=min(similarity_score, 1.0),
            related_memories=[]
        )
    
    def _analyze_relevance(
        self,
        query: str,
        memory_text: str,
        score: float
    ) -> str:
        """Analyze why memory is relevant to query."""
        query_words = set(query.lower().split())
        memory_words = set(memory_text.lower().split())
        
        overlap = query_words & memory_words
        
        if score > 0.9:
            return f"Highly relevant - direct semantic match (score: {score:.2f})"
        elif score > 0.7:
            return f"Relevant - similar topics discussed (score: {score:.2f})"
        elif score > 0.5:
            return f"Possibly relevant - some conceptual overlap (score: {score:.2f})"
        else:
            return f"Weakly relevant - distant connection (score: {score:.2f})"
    
    def format_explanation(self, explanation: MemoryExplanation) -> str:
        """Format explanation for display."""
        lines = [
            f"Memory: \"{explanation.memory_text[:100]}...\"",
            f"",
            f"Why was this remembered?",
            f"  {explanation.storage_reason}",
            f"",
            f"Why is it relevant now?",
            f"  {explanation.relevance_reason}",
            f"",
            f"Confidence: {explanation.confidence:.0%}"
        ]
        
        return "\n".join(lines)
    
    def generate_summary(self, memories: List[Dict[str, Any]]) -> str:
        """Generate summary of memory collection."""
        if not memories:
            return "No memories in this collection."
        
        types = {}
        for mem in memories:
            mem_type = mem.get("type", "unknown")
            types[mem_type] = types.get(mem_type, 0) + 1
        
        type_summary = ", ".join(f"{count} {t}" for t, count in types.items())
        
        return f"Memory collection contains {len(memories)} items: {type_summary}"
