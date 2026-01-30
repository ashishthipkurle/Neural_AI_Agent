
import logging
from agent.memory.vector_store import VectorStore

class MemoryManager:
    """
    High-level interface for Agent Memory.
    """
    def __init__(self):
        self.logger = logging.getLogger("MemoryManager")
        self.store = VectorStore() # Defaults to agent/db/memory.index

    def remember_fact(self, text: str):
        """
        Store a semantic fact.
        """
        self.store.add_memory(text, type="semantic")
        return f"I will remember that: {text}"

    def remember_event(self, description: str):
        """
        Store an episodic event.
        """
        self.store.add_memory(description, type="episodic")

    def recall(self, query: str):
        """
        Search for relevant memories.
        """
        results = self.store.search(query)
        if not results:
            return "I don't recall anything about that."
            
        # Format results
        summary = "Here is what I remember:\n"
        for item in results:
            # timestamp = item.get('timestamp', '')
            text = item.get('text', '')
            summary += f"- {text}\n"
            
        return summary
