"""
INDRA Memory Loader -- Loads memory at startup.
"""

from memory.store import MemoryStore
from memory.projects import ProjectManager
from config import MEMORY_RECALL_N


def load_startup_context(memory: MemoryStore, projects: ProjectManager) -> tuple[list[str], str]:
    """
    Load relevant memories and project status for startup greeting.
    Returns: (memory_context_list, project_briefing_string)
    """
    # Grab core preferences and recent context
    context = memory.recall(
        query="Ashish preferences habits recent projects status",
        n=MEMORY_RECALL_N
    )
    
    briefing = projects.get_briefing()
    
    return context, briefing
