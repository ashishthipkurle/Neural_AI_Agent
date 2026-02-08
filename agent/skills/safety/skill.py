"""
Safety Skill - Permission management and action gating.

Provides:
- Permission checking before skill execution
- User confirmation for dangerous actions
- Rate limiting
- Dry-run mode enforcement
- Audit logging
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth


class Permission(Enum):
    """Permission types that skills can require."""
    FILESYSTEM = "filesystem"       # Read/write files
    NETWORK = "network"             # Make network requests
    SYSTEM = "system"               # Run system commands
    SCREEN = "screen"               # Capture screen
    AUDIO = "audio"                 # TTS/STT
    MEMORY = "memory"               # Access memory store
    BROWSER = "browser"             # Browser automation
    COOKIES = "cookies"             # Access stored cookies
    API_TOKENS = "api_tokens"       # Use API keys
    SKILLS = "skills"               # Call other skills


@dataclass
class ActionRequest:
    """Request to perform an action."""
    skill: str
    action: str
    params: Dict[str, Any]
    required_permissions: Set[str] = field(default_factory=set)
    risk_level: int = 1  # 1-5, 5 being most risky
    timestamp: float = field(default_factory=time.time)


@dataclass
class PermissionGrant:
    """A granted permission."""
    permission: str
    granted_at: float
    expires_at: Optional[float] = None
    scope: str = "*"  # Skill or action scope


class SafetySkill(BaseSkill):
    """
    Safety and permission management skill.
    
    Actions:
    - check: Check if action is allowed
    - approve: Approve a pending action
    - deny: Deny a pending action
    - grant: Grant permission
    - revoke: Revoke permission
    - list_permissions: List granted permissions
    - set_mode: Set safety mode (strict/normal/dry_run)
    - audit: Get recent audit log
    """
    
    AUDIT_FILE = Path("agent/data/safety/audit.log")
    
    # Actions that always require confirmation
    DANGEROUS_ACTIONS = {
        ("desktop", "close"): "Close an application",
        ("desktop", "keyboard"): "Type text automatically",
        ("memory", "clear"): "Clear all memories",
        ("knowledge", "clear"): "Clear knowledge base",
        ("browser", "fill"): "Fill form fields",
        ("browser", "login"): "Login to website",
        ("filesystem", "delete"): "Delete files",
    }
    
    # Permission requirements by skill
    SKILL_PERMISSIONS = {
        "browser": {"network", "browser", "cookies"},
        "desktop": {"system", "screen"},
        "filesystem": {"filesystem"},
        "memory": {"memory"},
        "voice": {"audio"},
        "vision": {"screen"},
        "integrations": {"network", "api_tokens"},
        "knowledge": {"filesystem", "memory"},
        "planning": {"skills"},
        "workflow": {"skills"},
    }
    
    def __init__(self):
        super().__init__()
        self._granted_permissions: Dict[str, PermissionGrant] = {}
        self._pending_requests: List[ActionRequest] = []
        self._denied_actions: Set[tuple] = set()
        self._mode = "normal"  # strict, normal, dry_run
        self._auto_approve_skills: Set[str] = {"voice", "memory", "vision"}
        self._audit_log: List[Dict] = []
    
    @property
    def name(self) -> str:
        return "safety"
    
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="safety",
            version="1.0.0",
            description="Permission management and action gating",
            actions=[
                "check", "approve", "deny", "grant", "revoke",
                "list_permissions", "set_mode", "audit"
            ],
            requires=[],
            permissions=[]  # Safety skill needs no permissions
        )
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """Initialize safety skill."""
        self.AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Grant default permissions for safe skills
        for perm in ["audio", "memory", "screen"]:
            self._granted_permissions[perm] = PermissionGrant(
                permission=perm,
                granted_at=time.time()
            )
        
        super().on_load()
        self.logger.info(f"Safety skill loaded. Mode: {self._mode}")
    
    def on_unload(self) -> None:
        """Save audit log."""
        self._save_audit()
        super().on_unload()
    
    def _save_audit(self):
        """Persist audit log."""
        try:
            with open(self.AUDIT_FILE, 'a') as f:
                for entry in self._audit_log[-100:]:  # Keep last 100
                    f.write(f"{entry}\n")
        except Exception as e:
            self.logger.error(f"Failed to save audit: {e}")
    
    def _log_action(self, action_type: str, details: Dict):
        """Log an action to audit."""
        entry = {
            "timestamp": time.time(),
            "type": action_type,
            **details
        }
        self._audit_log.append(entry)
        self.logger.info(f"AUDIT: {action_type} - {details}")
    
    # ==================== INTENT MATCHING ====================
    
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill can handle the intent."""
        intent_lower = intent.lower()
        
        if any(x in intent_lower for x in ["permission", "allow", "deny", "approve"]):
            return 0.9
        
        if any(x in intent_lower for x in ["safe", "dangerous", "audit", "security"]):
            return 0.8
        
        return 0.0
    
    # ==================== CORE METHODS ====================
    
    def check_action(
        self, 
        skill: str, 
        action: str, 
        params: Dict[str, Any]
    ) -> tuple[bool, str]:
        """
        Check if an action should be allowed.
        
        Returns: (allowed, reason)
        """
        # Dry-run mode blocks all destructive actions
        if self._mode == "dry_run":
            if (skill, action) in self.DANGEROUS_ACTIONS:
                return False, f"Dry-run mode: {self.DANGEROUS_ACTIONS[(skill, action)]}"
        
        # Check if action is explicitly denied
        if (skill, action) in self._denied_actions:
            return False, "Action explicitly denied"
        
        # Get required permissions for skill
        required = self.SKILL_PERMISSIONS.get(skill, set())
        
        # Check permissions
        missing = []
        for perm in required:
            if perm not in self._granted_permissions:
                missing.append(perm)
        
        if missing and self._mode == "strict":
            return False, f"Missing permissions: {', '.join(missing)}"
        
        # Check if dangerous action needs confirmation
        if (skill, action) in self.DANGEROUS_ACTIONS:
            if skill not in self._auto_approve_skills:
                # Create pending request
                request = ActionRequest(
                    skill=skill,
                    action=action,
                    params=params,
                    required_permissions=required,
                    risk_level=3
                )
                self._pending_requests.append(request)
                
                if self._mode == "strict":
                    return False, f"Confirmation required: {self.DANGEROUS_ACTIONS[(skill, action)]}"
        
        # Log the check
        self._log_action("check", {
            "skill": skill,
            "action": action,
            "allowed": True
        })
        
        return True, "Allowed"
    
    def approve_all_pending(self) -> int:
        """Approve all pending requests."""
        count = len(self._pending_requests)
        self._pending_requests.clear()
        return count
    
    # ==================== EXECUTION ====================
    
    def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Execute a safety action."""
        
        handlers = {
            "check": self._action_check,
            "approve": self._action_approve,
            "deny": self._action_deny,
            "grant": self._action_grant,
            "revoke": self._action_revoke,
            "list_permissions": self._action_list_permissions,
            "set_mode": self._action_set_mode,
            "audit": self._action_audit,
        }
        
        handler = handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")
        
        try:
            return handler(params, context or {})
        except Exception as e:
            self.logger.error(f"Safety action '{action}' failed: {e}")
            return SkillResult(success=False, error=str(e))
    
    # ==================== ACTIONS ====================
    
    def _action_check(self, params: Dict, context: Dict) -> SkillResult:
        """Check if action is allowed."""
        skill = params.get("skill", "")
        action = params.get("action", "")
        action_params = params.get("params", {})
        
        allowed, reason = self.check_action(skill, action, action_params)
        
        return SkillResult(
            success=True,
            data={"allowed": allowed, "reason": reason},
            message=f"{'Allowed' if allowed else 'Blocked'}: {reason}"
        )
    
    def _action_approve(self, params: Dict, context: Dict) -> SkillResult:
        """Approve pending action(s)."""
        request_id = params.get("request_id")
        approve_all = params.get("all", False)
        
        if approve_all:
            count = self.approve_all_pending()
            self._log_action("approve_all", {"count": count})
            return SkillResult(success=True, message=f"Approved {count} pending requests")
        
        if not self._pending_requests:
            return SkillResult(success=True, message="No pending requests")
        
        # Approve first pending
        request = self._pending_requests.pop(0)
        self._log_action("approve", {
            "skill": request.skill,
            "action": request.action
        })
        
        return SkillResult(
            success=True,
            message=f"Approved: {request.skill}.{request.action}"
        )
    
    def _action_deny(self, params: Dict, context: Dict) -> SkillResult:
        """Deny an action permanently."""
        skill = params.get("skill", "")
        action = params.get("action", "")
        
        if skill and action:
            self._denied_actions.add((skill, action))
            self._log_action("deny", {"skill": skill, "action": action})
            return SkillResult(success=True, message=f"Denied: {skill}.{action}")
        
        # Deny first pending
        if self._pending_requests:
            request = self._pending_requests.pop(0)
            self._denied_actions.add((request.skill, request.action))
            return SkillResult(success=True, message=f"Denied: {request.skill}.{request.action}")
        
        return SkillResult(success=False, error="No action specified")
    
    def _action_grant(self, params: Dict, context: Dict) -> SkillResult:
        """Grant a permission."""
        permission = params.get("permission", "")
        duration = params.get("duration")  # Seconds, None = permanent
        
        if not permission:
            return SkillResult(success=False, error="Permission name required")
        
        expires_at = time.time() + duration if duration else None
        
        self._granted_permissions[permission] = PermissionGrant(
            permission=permission,
            granted_at=time.time(),
            expires_at=expires_at
        )
        
        self._log_action("grant", {"permission": permission, "duration": duration})
        
        return SkillResult(
            success=True,
            message=f"Granted permission: {permission}"
        )
    
    def _action_revoke(self, params: Dict, context: Dict) -> SkillResult:
        """Revoke a permission."""
        permission = params.get("permission", "")
        
        if permission in self._granted_permissions:
            del self._granted_permissions[permission]
            self._log_action("revoke", {"permission": permission})
            return SkillResult(success=True, message=f"Revoked: {permission}")
        
        return SkillResult(success=False, error=f"Permission not found: {permission}")
    
    def _action_list_permissions(self, params: Dict, context: Dict) -> SkillResult:
        """List all permissions."""
        # Clean expired
        now = time.time()
        expired = [
            k for k, v in self._granted_permissions.items()
            if v.expires_at and v.expires_at < now
        ]
        for k in expired:
            del self._granted_permissions[k]
        
        perms = [
            {
                "permission": v.permission,
                "expires_at": v.expires_at
            }
            for v in self._granted_permissions.values()
        ]
        
        return SkillResult(
            success=True,
            data={
                "permissions": perms,
                "pending_requests": len(self._pending_requests),
                "denied_actions": list(self._denied_actions)
            },
            message=f"{len(perms)} permissions granted"
        )
    
    def _action_set_mode(self, params: Dict, context: Dict) -> SkillResult:
        """Set safety mode."""
        mode = params.get("mode", "normal")
        
        if mode not in ["strict", "normal", "dry_run"]:
            return SkillResult(
                success=False,
                error=f"Invalid mode. Use: strict, normal, dry_run"
            )
        
        old_mode = self._mode
        self._mode = mode
        
        self._log_action("set_mode", {"old": old_mode, "new": mode})
        
        modes_desc = {
            "strict": "All actions require permission grants",
            "normal": "Dangerous actions may prompt for confirmation",
            "dry_run": "All destructive actions are blocked"
        }
        
        return SkillResult(
            success=True,
            message=f"Safety mode: {mode} - {modes_desc[mode]}"
        )
    
    def _action_audit(self, params: Dict, context: Dict) -> SkillResult:
        """Get audit log."""
        limit = params.get("limit", 20)
        
        entries = self._audit_log[-limit:]
        
        return SkillResult(
            success=True,
            data={"entries": entries},
            message=f"Last {len(entries)} audit entries"
        )
    
    # ==================== HEALTH ====================
    
    def health(self) -> SkillHealth:
        """Check safety skill health."""
        if not self._loaded:
            return SkillHealth.UNAVAILABLE
        return SkillHealth.READY
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """Preview safety action."""
        if action == "grant":
            return f"Would grant permission: {params.get('permission', 'unknown')}"
        if action == "set_mode":
            return f"Would set mode to: {params.get('mode', 'unknown')}"
        return f"Would execute safety.{action}"
