"""
Audit Log - Full action logging system.

This module implements comprehensive audit logging for all agent actions,
providing accountability and forensic capabilities.
"""
import logging
import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import threading


@dataclass
class AuditEntry:
    """Single audit log entry."""
    id: str
    timestamp: str
    event_type: str
    action: str
    description: str
    user_initiated: bool
    requires_consent: bool
    consent_given: bool
    parameters: Dict[str, Any]
    result: Optional[str]
    error: Optional[str]
    source_module: str
    session_id: str
    
    # Clowbot Extended Fields
    user_id: str = "local_user"
    intent_hash: str = ""
    consent_token: str = ""
    result_hash: str = ""
    decision: str = ""
    skill: str = ""
    actions: Optional[List[str]] = None
    assumptions: Optional[List[str]] = None
    confidence: float = 0.0
    verification_passed: bool = False


class AuditLogger:
    """
    Comprehensive audit logging system.
    
    ALL agent actions are logged including:
    - User commands
    - Tool executions
    - Consent decisions
    - System events
    - Security events
    
    Log storage:
    - JSON lines format for easy parsing
    - Rotated by date
    - Preserved for forensics
    """
    
    def __init__(
        self,
        log_dir: str = "logs/audit",
        session_id: Optional[str] = None,
        retention_days: int = 30
    ):
        """
        Initialize the audit logger.
        
        Args:
            log_dir: Directory for audit logs.
            session_id: Current session identifier.
            retention_days: Days to retain logs.
        """
        self.logger = logging.getLogger("AuditLogger")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.retention_days = retention_days
        self._entry_counter = 0
        self._lock = threading.RLock()
        
        # Current log file (rotated daily)
        self._current_file: Optional[Path] = None
        self._current_date: Optional[str] = None
        
        self.logger.info(f"AuditLogger initialized. Session: {self.session_id}")
    
    def _generate_entry_id(self) -> str:
        """Generate unique entry ID."""
        with self._lock:
            self._entry_counter += 1
            return f"audit_{self.session_id}_{self._entry_counter}"
    
    def _get_log_file(self) -> Path:
        """Get current log file, rotating if needed."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if self._current_date != today:
            self._current_date = today
            self._current_file = self.log_dir / f"audit_{today}.jsonl"
            self.logger.debug(f"Log file: {self._current_file}")
        
        return self._current_file
    
    def log(
        self,
        event_type: str,
        action: str = "",
        description: str = "",
        parameters: Dict[str, Any] = None,
        result: str = None,
        error: str = None,
        user_initiated: bool = True,
        requires_consent: bool = False,
        consent_given: bool = False,
        source_module: str = "unknown",
        # Extended fields
        user_id: str = "local_user",
        intent_hash: str = "",
        consent_token: str = "",
        result_hash: str = "",
        decision: str = "",
        skill: str = "",
        actions: Optional[List[str]] = None,
        assumptions: Optional[List[str]] = None,
        confidence: float = 0.0,
        verification_passed: bool = False
    ) -> str:
        """
        Log an audit entry.
        
        Args:
            event_type: Type of event (command, consent, security, etc.)
            action: Action performed.
            description: Human-readable description.
            parameters: Action parameters (sensitive data redacted).
            result: Action result (truncated if needed).
            error: Error message if failed.
            user_initiated: Whether user triggered this.
            requires_consent: Whether consent was required.
            consent_given: Whether consent was given.
            source_module: Module that generated this event.
            user_id: ID of the user performing the action.
            intent_hash: Hash of the user intent/input.
            consent_token: Token from consent gate.
            result_hash: Hash of the execution result.
            decision: Decision made (e.g. approved/denied).
            skill: Skill that executed the action.
            actions: List of sub-actions or phases completed.
            assumptions: List of assumptions made.
            confidence: Confidence score.
            verification_passed: Whether verification passed.
        
        Returns:
            Entry ID.
        """
        entry = AuditEntry(
            id=self._generate_entry_id(),
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            action=action,
            description=description,
            user_initiated=user_initiated,
            requires_consent=requires_consent,
            consent_given=consent_given,
            parameters=self._sanitize_params(parameters or {}),
            result=self._truncate(result, 500) if result else None,
            error=error,
            source_module=source_module,
            session_id=self.session_id,
            # Extended fields
            user_id=user_id,
            intent_hash=intent_hash,
            consent_token=consent_token,
            result_hash=result_hash,
            decision=decision,
            skill=skill,
            actions=actions,
            assumptions=assumptions,
            confidence=confidence,
            verification_passed=verification_passed
        )
        
        self._write_entry(entry)
        return entry.id
    
    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive parameters."""
        sensitive_keys = {'password', 'token', 'key', 'secret', 'credential', 'pin'}
        sanitized = {}
        
        for key, value in params.items():
            key_lower = key.lower()
            if any(sk in key_lower for sk in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 200:
                sanitized[key] = value[:200] + "...[TRUNCATED]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _truncate(self, text: str, max_length: int) -> str:
        """Truncate text to max length."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "...[TRUNCATED]"
    
    def _write_entry(self, entry: AuditEntry) -> None:
        """Write entry to log file."""
        with self._lock:
            try:
                log_file = self._get_log_file()
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(asdict(entry)) + "\n")
            except Exception as e:
                self.logger.error(f"Failed to write audit entry: {e}")
    
    def log_command(
        self,
        command: str,
        parameters: Dict[str, Any],
        result: str = None,
        error: str = None,
        consent_required: bool = False,
        consent_given: bool = False
    ) -> str:
        """Log a command execution."""
        return self.log(
            event_type="command",
            action=command,
            description=f"Executed command: {command}",
            parameters=parameters,
            result=result,
            error=error,
            requires_consent=consent_required,
            consent_given=consent_given,
            source_module="orchestrator"
        )
    
    def log_consent(
        self,
        action: str,
        approved: bool,
        method: str
    ) -> str:
        """Log a consent decision."""
        return self.log(
            event_type="consent",
            action=action,
            description=f"Consent {'approved' if approved else 'denied'} via {method}",
            consent_given=approved,
            requires_consent=True,
            source_module="consent_gate"
        )
    
    def log_security(
        self,
        event: str,
        description: str,
        severity: str = "info"
    ) -> str:
        """Log a security event."""
        return self.log(
            event_type=f"security_{severity}",
            action=event,
            description=description,
            user_initiated=False,
            source_module="security"
        )
    
    def log_face_auth(
        self,
        success: bool,
        user_name: Optional[str] = None,
        confidence: float = 0.0
    ) -> str:
        """Log face authentication attempt."""
        return self.log(
            event_type="security_auth",
            action="face_authentication",
            description=f"Face auth {'success' if success else 'failed'}: {user_name or 'unknown'}",
            parameters={"confidence": confidence, "user": user_name},
            user_initiated=True,
            source_module="face_verifier"
        )
    
    def log_lock_event(self, locked: bool, reason: str) -> str:
        """Log lock/unlock event."""
        return self.log(
            event_type="security_lock",
            action="lock" if locked else "unlock",
            description=f"Agent {'locked' if locked else 'unlocked'}: {reason}",
            user_initiated=False,
            source_module="lock_controller"
        )
    
    def get_entries(
        self,
        date: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit entries.
        
        Args:
            date: Date filter (YYYY-MM-DD).
            event_type: Event type filter.
            limit: Maximum entries to return.
        
        Returns:
            List of audit entries.
        """
        entries = []
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        log_file = self.log_dir / f"audit_{target_date}.jsonl"
        
        if not log_file.exists():
            return []
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if event_type and entry.get('event_type') != event_type:
                            continue
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self.logger.error(f"Failed to read audit log: {e}")
        
        return entries[-limit:]
    
    def cleanup_old_logs(self) -> int:
        """
        Remove logs older than retention period.
        
        Returns:
            Number of files removed.
        """
        removed = 0
        cutoff = datetime.now().timestamp() - (self.retention_days * 86400)
        
        for log_file in self.log_dir.glob("audit_*.jsonl"):
            try:
                if log_file.stat().st_mtime < cutoff:
                    log_file.unlink()
                    removed += 1
                    self.logger.info(f"Removed old audit log: {log_file.name}")
            except Exception as e:
                self.logger.warning(f"Failed to remove {log_file}: {e}")
        
        return removed
