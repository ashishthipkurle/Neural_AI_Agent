"""
Memory Injector - Injects relevant memories into LLM context.

This module handles:
- Memory retrieval based on context
- Memory ranking and selection
- Context window management
- Memory formatting for LLM consumption
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MemoryItem:
    """Represents a single memory item for injection."""
    text: str
    relevance_score: float
    memory_type: str  # episodic, semantic, procedural
    timestamp: str
    tags: List[str]
    source: str  # short_term, long_term


@dataclass
class InjectionResult:
    """Result of memory injection."""
    injected_memories: List[MemoryItem]
    total_tokens_used: int
    truncated: bool
    context_string: str


class MemoryInjector:
    """
    Manages memory injection into LLM context.
    
    Features:
    - Semantic similarity search
    - Token budget management
    - Memory prioritization
    - Context formatting
    """
    
    # Approximate tokens per character (conservative estimate)
    CHARS_PER_TOKEN = 4
    
    def __init__(
        self,
        short_term_memory=None,
        long_term_memory=None,
        max_context_tokens: int = 2048
    ):
        """
        Initialize the Memory Injector.
        
        Args:
            short_term_memory: Short-term memory store interface.
            long_term_memory: Long-term (vector) memory store interface.
            max_context_tokens: Maximum tokens to use for memory context.
        """
        self.logger = logging.getLogger("MemoryInjector")
        self.short_term = short_term_memory
        self.long_term = long_term_memory
        self.max_context_tokens = max_context_tokens
        self.logger.info(f"MemoryInjector initialized with {max_context_tokens} token limit.")
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return len(text) // self.CHARS_PER_TOKEN
    
    def retrieve_relevant_memories(
        self,
        query: str,
        k: int = 5,
        include_short_term: bool = True,
        include_long_term: bool = True
    ) -> List[MemoryItem]:
        """
        Retrieve memories relevant to the query.
        
        Args:
            query: The query to find relevant memories for.
            k: Maximum number of memories to retrieve.
            include_short_term: Whether to include short-term memories.
            include_long_term: Whether to include long-term memories.
        
        Returns:
            List of MemoryItems sorted by relevance.
        """
        memories = []
        
        # Retrieve from short-term memory
        if include_short_term and self.short_term:
            try:
                st_memories = self.short_term.get_recent(k)
                for mem in st_memories:
                    memories.append(MemoryItem(
                        text=mem.get('text', ''),
                        relevance_score=0.9,  # Recent memories are highly relevant
                        memory_type=mem.get('type', 'episodic'),
                        timestamp=mem.get('timestamp', ''),
                        tags=mem.get('tags', []),
                        source='short_term'
                    ))
            except Exception as e:
                self.logger.warning(f"Short-term memory retrieval failed: {e}")
        
        # Retrieve from long-term memory (semantic search)
        if include_long_term and self.long_term:
            try:
                lt_memories = self.long_term.search(query, k=k)
                for mem in lt_memories:
                    # Convert distance to relevance (lower distance = higher relevance)
                    score = 1.0 / (1.0 + mem.get('score', 1.0))
                    memories.append(MemoryItem(
                        text=mem.get('text', ''),
                        relevance_score=score,
                        memory_type=mem.get('type', 'semantic'),
                        timestamp=mem.get('timestamp', ''),
                        tags=mem.get('tags', []),
                        source='long_term'
                    ))
            except Exception as e:
                self.logger.warning(f"Long-term memory retrieval failed: {e}")
        
        # Sort by relevance score
        memories.sort(key=lambda m: m.relevance_score, reverse=True)
        
        self.logger.debug(f"Retrieved {len(memories)} total memories for query.")
        return memories[:k]
    
    def inject_memories(
        self,
        query: str,
        base_context: str = "",
        k: int = 5
    ) -> InjectionResult:
        """
        Inject memories into context string.
        
        Args:
            query: Query to find relevant memories.
            base_context: Base context string to add memories to.
            k: Maximum memories to inject.
        
        Returns:
            InjectionResult with formatted context.
        """
        memories = self.retrieve_relevant_memories(query, k=k)
        
        # Calculate available token budget
        base_tokens = self._estimate_tokens(base_context)
        available_tokens = self.max_context_tokens - base_tokens
        
        # Build memory context within budget
        memory_parts = []
        total_memory_tokens = 0
        truncated = False
        injected = []
        
        for memory in memories:
            memory_text = f"[{memory.source.upper()}] {memory.text}"
            memory_tokens = self._estimate_tokens(memory_text)
            
            if total_memory_tokens + memory_tokens <= available_tokens:
                memory_parts.append(memory_text)
                total_memory_tokens += memory_tokens
                injected.append(memory)
            else:
                truncated = True
                break
        
        # Format final context
        if memory_parts:
            memory_context = "\n--- RELEVANT MEMORIES ---\n" + "\n".join(memory_parts)
            full_context = base_context + "\n" + memory_context
        else:
            full_context = base_context
        
        self.logger.info(f"Injected {len(injected)} memories ({total_memory_tokens} tokens)")
        
        return InjectionResult(
            injected_memories=injected,
            total_tokens_used=base_tokens + total_memory_tokens,
            truncated=truncated,
            context_string=full_context
        )
    
    def format_memory_for_display(self, memory: MemoryItem) -> str:
        """Format a memory item for user display."""
        return f"[{memory.timestamp}] ({memory.source}) {memory.text}"
    
    def explain_memory_selection(self, memories: List[MemoryItem], query: str) -> str:
        """
        Explain why certain memories were selected.
        
        Args:
            memories: List of selected memories.
            query: The query that was used.
        
        Returns:
            Human-readable explanation.
        """
        explanations = [f"For query '{query}', I found {len(memories)} relevant memories:"]
        
        for i, mem in enumerate(memories, 1):
            explanations.append(
                f"{i}. From {mem.source} memory (relevance: {mem.relevance_score:.2f}): "
                f"'{mem.text[:50]}...'"
            )
        
        return "\n".join(explanations)
