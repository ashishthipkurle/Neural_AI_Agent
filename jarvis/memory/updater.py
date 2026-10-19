"""
INDRA Memory Updater -- Updates memory after each session or task.
"""

from memory.store import MemoryStore
from memory.projects import ProjectManager
from utils.logger import get_logger

logger = get_logger("MemoryUpdater")


def update_after_task(memory: MemoryStore, task: str, success: bool, details: str = ""):
    """Store the outcome of a computer task."""
    result_str = "Succeeded" if success else "Failed"
    if details:
        result_str += f" ({details})"
        
    memory.save_task_result(task, result_str, success)
    logger.debug(f"Task outcome saved to memory: {task[:30]} -> {success}")


def extract_and_save_preferences(memory: MemoryStore, user_input: str, assistant_reply: str):
    """
    Very simple heuristic to catch explicit preference statements.
    In a full implementation, an LLM would run async to extract these.
    """
    lower_input = user_input.lower()
    
    triggers = [
        "always remember", "never do", "i prefer", "make sure you",
        "my name is", "call me", "i like"
    ]
    
    if any(t in lower_input for t in triggers):
        # Save the whole interaction as an identity fact
        fact = f"User stated preference: '{user_input}'. Assistant acknowledged: '{assistant_reply}'"
        memory.save_identity(fact)
        logger.info("Saved user preference to identity memory.")
