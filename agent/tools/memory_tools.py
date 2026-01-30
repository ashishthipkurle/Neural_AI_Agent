
from agent.memory.memory_manager import MemoryManager

class MemoryTools:
    """
    Tools for interacting with Long-Term Memory.
    """
    def __init__(self):
        self.manager = MemoryManager()

    def store_memory(self, text: str):
        """
        Stores a fact or event in long-term memory.
        """
        self.manager.remember_fact(text)
        return "Memory stored."

    def search_memory(self, query: str):
        """
        Retrieves relevant memories based on query.
        """
        return self.manager.recall(query)
