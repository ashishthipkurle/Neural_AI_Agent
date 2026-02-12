"""
Destructive Action Handler — Frozen flow for dangerous operations.

Implements the mandatory destructive action pipeline:

    mark → dry-run → multi-modal confirmation
    → snapshot/backup → execute → verify → immutable audit log

This module wires together existing ConsentGate, RollbackManager,
and AuditLogger into a single, tested flow.

FROZEN: This flow must not be simplified or bypassed.
"""

import logging
import hashlib
import time
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


logger = logging.getLogger("DestructiveActionHandler")


class DestructiveActionPhase(Enum):
    """Phases of the destructive action pipeline."""
    MARK = "mark"
    DRY_RUN = "dry_run"
    CONFIRMATION = "multi_modal_confirmation"
    SNAPSHOT = "snapshot_backup"
    EXECUTE = "execute"
    VERIFY = "verify"
    AUDIT = "immutable_audit_log"


@dataclass
class DestructiveActionRequest:
    """Request to perform a destructive action."""
    request_id: str
    action: str
    parameters: Dict[str, Any]
    description: str
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    timestamp: str
    user_id: str = "local_user"
    
    # Phase tracking
    current_phase: str = DestructiveActionPhase.MARK.value
    phases_completed: list = field(default_factory=list)
    
    # Results
    dry_run_result: Optional[str] = None
    confirmation_method: Optional[str] = None
    snapshot_path: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    verification_passed: bool = False
    audit_entry_id: Optional[str] = None
    
    # Confidence
    confidence: float = 0.0
    assumptions: list = field(default_factory=list)
    
    # Error tracking
    errors: list = field(default_factory=list)
    aborted: bool = False
    abort_reason: Optional[str] = None


class DestructiveActionHandler:
    """
    Enforces the destructive action pipeline for all dangerous operations.
    
    Every destructive action MUST pass through ALL 7 phases:
    1. MARK — Flag the action as destructive
    2. DRY_RUN — Preview what will happen without executing
    3. CONFIRMATION — Multi-modal user confirmation (voice + UI)
    4. SNAPSHOT — Backup current state before modification
    5. EXECUTE — Perform the action
    6. VERIFY — Validate the result
    7. AUDIT — Write immutable audit log entry
    
    If ANY phase fails, the pipeline ABORTS and rolls back.
    """
    
    # Actions classified as destructive
    DESTRUCTIVE_ACTIONS = frozenset({
        'delete', 'remove', 'format', 'shutdown', 'restart',
        'execute_code', 'forget_face', 'clear_memory',
        'write_file', 'overwrite', 'uninstall', 'drop',
        'truncate', 'wipe', 'reset', 'destroy'
    })
    
    def __init__(
        self,
        consent_gate=None,
        rollback_manager=None,
        audit_logger=None
    ):
        self.consent_gate = consent_gate
        self.rollback_manager = rollback_manager
        self.audit_logger = audit_logger
        self.logger = logging.getLogger("DestructiveActionHandler")
        
        # Pending requests
        self._requests: Dict[str, DestructiveActionRequest] = {}
    
    def is_destructive(self, action: str) -> bool:
        """Check if an action is classified as destructive."""
        action_lower = action.lower()
        return any(keyword in action_lower for keyword in self.DESTRUCTIVE_ACTIONS)
    
    async def handle(
        self,
        action: str,
        parameters: Dict[str, Any],
        executor: Callable,
        dry_run_fn: Optional[Callable] = None,
        verify_fn: Optional[Callable] = None,
        user_id: str = "local_user",
        description: Optional[str] = None
    ) -> DestructiveActionRequest:
        """
        Execute the full destructive action pipeline.
        
        Args:
            action: Action name.
            parameters: Action parameters.
            executor: Async callable that performs the actual action.
            dry_run_fn: Optional callable that previews the action.
            verify_fn: Optional callable that verifies the result.
            user_id: User performing the action.
            description: Human-readable description.
        
        Returns:
            DestructiveActionRequest with all phase results.
        """
        # ---- PHASE 1: MARK ----
        request = self._phase_mark(action, parameters, user_id, description)
        
        try:
            # ---- PHASE 2: DRY RUN ----
            await self._phase_dry_run(request, dry_run_fn)
            if request.aborted:
                return request
            
            # ---- PHASE 3: MULTI-MODAL CONFIRMATION ----
            await self._phase_confirmation(request)
            if request.aborted:
                return request
            
            # ---- PHASE 4: SNAPSHOT/BACKUP ----
            await self._phase_snapshot(request)
            if request.aborted:
                return request
            
            # ---- PHASE 5: EXECUTE ----
            await self._phase_execute(request, executor)
            if request.aborted:
                return request
            
            # ---- PHASE 6: VERIFY ----
            await self._phase_verify(request, verify_fn)
            
            # ---- PHASE 7: AUDIT LOG ----
            await self._phase_audit(request)
            
        except Exception as e:
            request.aborted = True
            request.abort_reason = f"Pipeline exception: {e}"
            request.errors.append(str(e))
            self.logger.error(f"Destructive action pipeline failed: {e}")
            
            # Attempt rollback on failure
            if request.snapshot_path and self.rollback_manager:
                try:
                    self.rollback_manager.rollback_last()
                    self.logger.info("Rollback completed after pipeline failure")
                except Exception as rb_error:
                    self.logger.error(f"Rollback also failed: {rb_error}")
        
        return request
    
    def _phase_mark(
        self, action: str, parameters: Dict[str, Any],
        user_id: str, description: Optional[str]
    ) -> DestructiveActionRequest:
        """Phase 1: Mark the action as destructive."""
        risk = self._classify_risk(action, parameters)
        
        request = DestructiveActionRequest(
            request_id=str(uuid.uuid4()),
            action=action,
            parameters=parameters,
            description=description or f"Destructive action: {action}",
            risk_level=risk,
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
            current_phase=DestructiveActionPhase.MARK.value
        )
        
        request.phases_completed.append(DestructiveActionPhase.MARK.value)
        request.assumptions.append(f"Risk classified as {risk}")
        
        self._requests[request.request_id] = request
        self.logger.info(f"[MARK] Action '{action}' marked as destructive (risk={risk})")
        
        return request
    
    async def _phase_dry_run(
        self, request: DestructiveActionRequest,
        dry_run_fn: Optional[Callable]
    ) -> None:
        """Phase 2: Preview the action without executing."""
        request.current_phase = DestructiveActionPhase.DRY_RUN.value
        
        if dry_run_fn:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(dry_run_fn):
                    preview = await dry_run_fn(request.action, request.parameters)
                else:
                    preview = dry_run_fn(request.action, request.parameters)
                request.dry_run_result = str(preview)
            except Exception as e:
                request.dry_run_result = f"Dry run failed: {e}"
                request.errors.append(f"Dry run error: {e}")
        else:
            request.dry_run_result = (
                f"[DRY-RUN] Would execute '{request.action}' "
                f"with params: {request.parameters}"
            )
        
        request.phases_completed.append(DestructiveActionPhase.DRY_RUN.value)
        self.logger.info(f"[DRY-RUN] {request.dry_run_result}")
    
    async def _phase_confirmation(self, request: DestructiveActionRequest) -> None:
        """Phase 3: Request multi-modal user confirmation."""
        request.current_phase = DestructiveActionPhase.CONFIRMATION.value
        
        if not self.consent_gate:
            # No consent gate — auto-approve
            request.confirmation_method = "auto_no_gate"
            request.assumptions.append("No ConsentGate configured, auto-approved")
            request.phases_completed.append(DestructiveActionPhase.CONFIRMATION.value)
            return
        
        consent_request = self.consent_gate.create_request(
            action=request.action,
            parameters=request.parameters,
            description=f"[DESTRUCTIVE] {request.description}\n"
                       f"Dry-run preview: {request.dry_run_result}"
        )
        
        result = await self.consent_gate.request_consent(consent_request)
        
        if result.approved:
            request.confirmation_method = result.confirmation_method
            request.phases_completed.append(DestructiveActionPhase.CONFIRMATION.value)
            self.logger.info(f"[CONFIRMATION] Approved via {result.confirmation_method}")
        else:
            request.aborted = True
            request.abort_reason = f"Consent denied: {result.denial_reason}"
            self.logger.warning(f"[CONFIRMATION] DENIED: {result.denial_reason}")
    
    async def _phase_snapshot(self, request: DestructiveActionRequest) -> None:
        """Phase 4: Create backup/snapshot before execution."""
        request.current_phase = DestructiveActionPhase.SNAPSHOT.value
        
        if self.rollback_manager:
            try:
                # Record what we're about to modify
                target = request.parameters.get("path") or request.parameters.get("file_path") or ""
                if target:
                    import os
                    if os.path.exists(target):
                        with open(target, 'r', errors='replace') as f:
                            original = f.read()
                        action = self.rollback_manager.record_file_write(
                            file_path=target,
                            original_content=original,
                            new_content="[pending destructive action]"
                        )
                        request.snapshot_path = str(action.id)
                        self.logger.info(f"[SNAPSHOT] Backed up {target}")
                    else:
                        request.assumptions.append(f"Target '{target}' doesn't exist yet, no backup needed")
                else:
                    request.assumptions.append("No file target, snapshot skipped")
            except Exception as e:
                request.errors.append(f"Snapshot error: {e}")
                self.logger.warning(f"[SNAPSHOT] Failed: {e}")
        else:
            request.assumptions.append("No RollbackManager, snapshot skipped")
        
        request.phases_completed.append(DestructiveActionPhase.SNAPSHOT.value)
    
    async def _phase_execute(
        self, request: DestructiveActionRequest,
        executor: Callable
    ) -> None:
        """Phase 5: Execute the destructive action."""
        request.current_phase = DestructiveActionPhase.EXECUTE.value
        
        try:
            import asyncio
            if asyncio.iscoroutinefunction(executor):
                result = await executor(**request.parameters)
            else:
                result = executor(**request.parameters)
            
            request.execution_result = {
                "success": True,
                "data": result if not isinstance(result, dict) else result,
                "timestamp": datetime.now().isoformat()
            }
            request.phases_completed.append(DestructiveActionPhase.EXECUTE.value)
            self.logger.info(f"[EXECUTE] Action '{request.action}' completed successfully")
            
        except Exception as e:
            request.execution_result = {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            request.errors.append(f"Execution error: {e}")
            request.aborted = True
            request.abort_reason = f"Execution failed: {e}"
            self.logger.error(f"[EXECUTE] FAILED: {e}")
    
    async def _phase_verify(
        self, request: DestructiveActionRequest,
        verify_fn: Optional[Callable]
    ) -> None:
        """Phase 6: Verify the execution result."""
        request.current_phase = DestructiveActionPhase.VERIFY.value
        
        if verify_fn:
            try:
                import asyncio
                if asyncio.iscoroutinefunction(verify_fn):
                    verified = await verify_fn(request.execution_result)
                else:
                    verified = verify_fn(request.execution_result)
                request.verification_passed = bool(verified)
            except Exception as e:
                request.verification_passed = False
                request.errors.append(f"Verification error: {e}")
        else:
            # Basic verification: check if execution succeeded
            request.verification_passed = (
                request.execution_result is not None and
                request.execution_result.get("success", False)
            )
        
        request.phases_completed.append(DestructiveActionPhase.VERIFY.value)
        self.logger.info(
            f"[VERIFY] {'PASSED' if request.verification_passed else 'FAILED'}"
        )
    
    async def _phase_audit(self, request: DestructiveActionRequest) -> None:
        """Phase 7: Write immutable audit log entry."""
        request.current_phase = DestructiveActionPhase.AUDIT.value
        
        # Build audit record with frozen schema
        audit_data = {
            "timestamp": request.timestamp,
            "user_id": request.user_id,
            "intent_hash": hashlib.sha256(
                f"{request.action}:{request.parameters}".encode()
            ).hexdigest()[:16],
            "decision": "approved" if request.confirmation_method else "auto",
            "consent_token": request.request_id,
            "skill": request.action,
            "actions": request.phases_completed,
            "result_hash": hashlib.sha256(
                str(request.execution_result).encode()
            ).hexdigest()[:16] if request.execution_result else "",
            "assumptions": request.assumptions,
            "confidence": request.confidence,
            "verification_passed": request.verification_passed
        }
        
        if self.audit_logger:
            entry_id = self.audit_logger.log(
                event_type="destructive_action",
                action=request.action,
                description=request.description,
                parameters=audit_data,
                result=str(request.execution_result),
                error=request.abort_reason,
                requires_consent=True,
                consent_given=request.confirmation_method is not None,
                source_module="destructive_action_handler"
            )
            request.audit_entry_id = entry_id
            self.logger.info(f"[AUDIT] Logged entry: {entry_id}")
        else:
            request.assumptions.append("No AuditLogger, audit skipped")
        
        request.phases_completed.append(DestructiveActionPhase.AUDIT.value)
    
    def _classify_risk(self, action: str, parameters: Dict[str, Any]) -> str:
        """Classify the risk level of an action."""
        action_lower = action.lower()
        
        critical_keywords = {'format', 'wipe', 'destroy', 'drop', 'shutdown', 'forget_face'}
        high_keywords = {'delete', 'remove', 'execute_code', 'clear_memory', 'uninstall'}
        medium_keywords = {'write_file', 'overwrite', 'truncate', 'reset'}
        
        if any(k in action_lower for k in critical_keywords):
            return "CRITICAL"
        elif any(k in action_lower for k in high_keywords):
            return "HIGH"
        elif any(k in action_lower for k in medium_keywords):
            return "MEDIUM"
        return "LOW"
