import yaml
import os
import logging
from typing import List

class PermissionManager:
    """
    Manages security permissions for the agent.
    Checks if paths are allowed and if actions require confirmation.
    """
    def __init__(self, config_path: str = "agent/config/settings.yaml"):
        self.config = self._load_config(config_path)
        self.allowed_paths = [os.path.normpath(p) for p in self.config.get('security', {}).get('allowed_paths', [])]
        # Auto-approve if config says so OR if running in API mode
        self.auto_approval = (
            self.config.get('security', {}).get('auto_approval', False) or
            os.environ.get('AGENT_API_MODE', '').lower() == 'true'
        )
        self.logger = logging.getLogger("PermissionManager")

    def _load_config(self, path: str) -> dict:
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not load config from {path}: {e}")
            return {}

    def is_path_allowed(self, path: str) -> bool:
        """
        Checks if the given path is within the allowed directories.
        """
        abs_path = os.path.abspath(path)
        abs_path = os.path.abspath(path)
        for allowed in self.allowed_paths:
            try:
                if os.path.commonpath([allowed, abs_path]) == os.path.normpath(allowed):
                    return True
            except ValueError:
                # Paths on different drives
                continue
        self.logger.warning(f"Access denied to path: {path}")
        return False

    def request_permission(self, action_description: str) -> bool:
        """
        Requests permission for a potentially dangerous action.
        If auto_approval is True, returns True immediately.
        Otherwise, asks the user (simulated via CLI for now).
        """
        if self.auto_approval:
            self.logger.info(f"Auto-approved action: {action_description}")
            return True
        
        # In a real GUI app, this would be a popup.
        # For CLI, we print and ask input.
        print(f"\n[SECURITY ALERT] The agent wants to: {action_description}")
        response = input("Allow this action? (y/n): ")
        if response.lower().strip() == 'y':
            self.logger.info(f"User approved action: {action_description}")
            return True
        
        self.logger.warning(f"User denied action: {action_description}")
        return False

# Command Authority Layer configuration
DANGEROUS_ACTIONS = [
    "delete",
    "shutdown",
    "format",
    "open_browser",
    "run_code",
    "execute_code", # Explicitly checking our tool name
    "forget_face" 
]

def requires_confirmation(intent_str: str) -> bool:
    """
    Checks if the intent string contains any dangerous keywords.
    """
    return any(action in intent_str.lower() for action in DANGEROUS_ACTIONS)
