import yaml
import os
import logging
import fnmatch
from typing import List, Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass, field

class PermissionMode(Enum):
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"
    DANGER_FULL_ACCESS = "full_access"

class PermissionDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"

@dataclass
class PermissionRule:
    tool_name: Optional[str] = None
    tool_prefix: Optional[str] = None
    path_pattern: Optional[str] = None
    decision: PermissionDecision = PermissionDecision.ASK

@dataclass
class PermissionRequirement:
    minimum_mode: PermissionMode
    always_ask: bool = False

class PermissionPolicy:
    """Complete permission policy — Claw-parity §permissions.rs"""
    def __init__(self, mode: PermissionMode, blocked_tools: List[str], rules: List[PermissionRule], tool_requirements: Dict[str, PermissionRequirement]):
        self.mode = mode
        self.blocked_tools = blocked_tools
        self.rules = rules
        self.tool_requirements = tool_requirements

    def is_tool_blocked(self, tool_name: str) -> bool:
        for blocked in self.blocked_tools:
            if tool_name == blocked or tool_name.startswith(blocked):
                return True
        return False

    def evaluate(self, tool_name: str, params: Dict[str, Any]) -> PermissionDecision:
        if self.is_tool_blocked(tool_name):
            return PermissionDecision.DENY

        # Evaluate rules
        # Match rules based on priority: exact tool, prefix tool
        for rule in self.rules:
            if rule.tool_name and rule.tool_name == tool_name:
                return rule.decision
            if rule.tool_prefix and tool_name.startswith(rule.tool_prefix):
                return rule.decision
        
        # Check requirements
        req = self.tool_requirements.get(tool_name)
        if req:
            modes_rank = {PermissionMode.READ_ONLY: 1, PermissionMode.WORKSPACE_WRITE: 2, PermissionMode.DANGER_FULL_ACCESS: 3}
            if modes_rank[self.mode] < modes_rank[req.minimum_mode]:
                return PermissionDecision.DENY
            if req.always_ask:
                return PermissionDecision.ASK

        return PermissionDecision.ASK

class PermissionManager:
    """
    Manages security permissions for the agent.
    Checks if paths are allowed and if actions require confirmation.
    """
    def __init__(self, config_path: str = "agent/config/settings.yaml", rules_path: str = "agent/config/permission_rules.yaml"):
        self.logger = logging.getLogger("PermissionManager")
        self.config = self._load_config(config_path)
        self.rules_config = self._load_config(rules_path)
        self.allowed_paths = [os.path.normpath(p) for p in self.config.get('security', {}).get('allowed_paths', [])]
        
        # Legacy auto_approval logic
        self.auto_approval = (
            self.config.get('security', {}).get('auto_approval', False) or
            os.environ.get('AGENT_API_MODE', '').lower() == 'true'
        )
        self.policy = self._build_policy()

    def _load_config(self, path: str) -> dict:
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return yaml.safe_load(f) or {}
            else:
                return {}
        except Exception as e:
            print(f"Warning: Could not load config from {path}: {e}")
            return {}

    def _build_policy(self) -> PermissionPolicy:
        # Legacy overrides wrapper maps 'auto_approval=True' to DANGER_FULL_ACCESS
        if self.auto_approval:
            mode = PermissionMode.DANGER_FULL_ACCESS
        else:
            mode_str = self.rules_config.get("mode", "workspace_write")
            try:
                mode = PermissionMode(mode_str)
            except ValueError:
                mode = PermissionMode.WORKSPACE_WRITE
            
        blocked_tools = self.rules_config.get("blocked_tools", [])
        
        rules = []
        for r_dict in self.rules_config.get("rules", []):
            decision_str = r_dict.get("decision", "ask")
            try:
                decision = PermissionDecision(decision_str)
            except ValueError:
                decision = PermissionDecision.ASK
                
            rules.append(PermissionRule(
                tool_name=r_dict.get("tool_name"),
                tool_prefix=r_dict.get("tool_prefix"),
                path_pattern=r_dict.get("path_pattern"),
                decision=decision
            ))
            
        tool_reqs = {}
        for tool, req_dict in self.rules_config.get("tool_requirements", {}).items():
            min_mode_str = req_dict.get("minimum_mode", "workspace_write")
            try:
                min_mode = PermissionMode(min_mode_str)
            except ValueError:
                min_mode = PermissionMode.WORKSPACE_WRITE
                
            tool_reqs[tool] = PermissionRequirement(
                minimum_mode=min_mode,
                always_ask=req_dict.get("always_ask", False)
            )

        return PermissionPolicy(mode, blocked_tools, rules, tool_reqs)

    def is_path_allowed(self, path: str) -> bool:
        """
        Checks if the given path is within the allowed directories.
        """
        if self.policy.mode == PermissionMode.DANGER_FULL_ACCESS:
            return True

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

    def check_tool_permission(self, tool_name: str, params: Dict[str, Any]) -> PermissionDecision:
        """New method: Checks permission using Claw-parity policy."""
        if self.policy.mode == PermissionMode.DANGER_FULL_ACCESS:
            return PermissionDecision.ALLOW
        return self.policy.evaluate(tool_name, params)

    def request_permission(self, action_description: str) -> bool:
        """
        Requests permission for a potentially dangerous action.
        If auto_approval/DANGER_FULL_ACCESS is True, returns True immediately.
        Otherwise, asks the user.
        """
        if self.policy.mode == PermissionMode.DANGER_FULL_ACCESS:
            self.logger.info(f"Auto-approved action: {action_description}")
            return True
        
        print(f"\\n[SECURITY ALERT] The agent wants to: {action_description}")
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
    "execute_code", 
    "forget_face" 
]

def requires_confirmation(intent_str: str) -> bool:
    """
    Checks if the intent string contains any dangerous keywords.
    """
    return any(action in intent_str.lower() for action in DANGEROUS_ACTIONS)
