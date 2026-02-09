
import logging
from typing import List, Dict, Any, Optional
import json
import os

logger = logging.getLogger(__name__)

class TaskStateManager:
    """
    Manages persistent state for tasks, allowing resume after restart.
    """
    
    def __init__(self, state_dir: str = "agent/data/task_states"):
        self.state_dir = state_dir
        os.makedirs(self.state_dir, exist_ok=True)
        
    def save_task_state(self, task_id: str, state: dict) -> None:
        """Save task state to file."""
        file_path = os.path.join(self.state_dir, f"{task_id}.json")
        try:
            with open(file_path, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state for {task_id}: {e}")
            
    def load_task_state(self, task_id: str) -> dict:
        """Load task state from file."""
        file_path = os.path.join(self.state_dir, f"{task_id}.json")
        if not os.path.exists(file_path):
            return {}
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load state for {task_id}: {e}")
            return {}
            
    def clear_task_state(self, task_id: str) -> None:
        """Remove task state file."""
        file_path = os.path.join(self.state_dir, f"{task_id}.json")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to clear state for {task_id}: {e}")
                
    def get_all_active_states(self) -> List[dict]:
        """Get states for all active tasks."""
        states = []
        if not os.path.exists(self.state_dir):
            return states
            
        for filename in os.listdir(self.state_dir):
            if filename.endswith(".json"):
                task_id = filename.replace(".json", "")
                state = self.load_task_state(task_id)
                if state:
                    state['task_id'] = task_id
                    states.append(state)
        return states
