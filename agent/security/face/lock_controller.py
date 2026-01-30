"""
Lock Controller - Automatic lock/unlock management.

This module manages agent locking based on user presence
detection and authentication.
"""
import logging
import threading
import time
from typing import Optional, Callable
from datetime import datetime

from .verifier import FaceVerifier, VerificationResult
from .pin_fallback import PINFallback


class LockController:
    """
    Agent lock management system.
    
    Features:
    - Auto-lock on user absence
    - Face-based unlock
    - PIN fallback
    - Lock event logging
    
    Lock priority:
    1. Face verification
    2. PIN fallback
    3. Manual unlock (admin only)
    """
    
    ABSENCE_TIMEOUT = 300  # 5 minutes of no face = auto-lock
    CHECK_INTERVAL = 30   # Check presence every 30 seconds
    
    def __init__(
        self,
        face_verifier: FaceVerifier,
        pin_fallback: PINFallback,
        state_machine=None,
        audit_logger=None
    ):
        """
        Initialize lock controller.
        
        Args:
            face_verifier: Face verification system.
            pin_fallback: PIN authentication fallback.
            state_machine: Agent state machine.
            audit_logger: Audit logger for security events.
        """
        self.logger = logging.getLogger("LockController")
        self.face_verifier = face_verifier
        self.pin_fallback = pin_fallback
        self.state_machine = state_machine
        self.audit_logger = audit_logger
        
        self._is_locked = False
        self._presence_thread = None
        self._running = False
        self._last_presence = datetime.now()
        self._lock_callbacks: list = []
        
        self.logger.info("LockController initialized.")
    
    @property
    def is_locked(self) -> bool:
        """Check if agent is locked."""
        return self._is_locked
    
    def lock(self, reason: str = "Manual lock") -> bool:
        """
        Lock the agent.
        
        Args:
            reason: Reason for locking.
        
        Returns:
            True if lock succeeded.
        """
        if self._is_locked:
            return True
        
        self._is_locked = True
        self.logger.info(f"Agent LOCKED: {reason}")
        
        # Update state machine
        if self.state_machine:
            self.state_machine.lock(reason)
        
        # Log security event
        if self.audit_logger:
            self.audit_logger.log_lock_event(True, reason)
        
        # Fire callbacks
        for callback in self._lock_callbacks:
            try:
                callback(True, reason)
            except Exception as e:
                self.logger.error(f"Lock callback error: {e}")
        
        return True
    
    def unlock(self, reason: str = "Authentication successful") -> bool:
        """
        Unlock the agent.
        
        Args:
            reason: Reason for unlocking.
        
        Returns:
            True if unlock succeeded.
        """
        if not self._is_locked:
            return True
        
        self._is_locked = False
        self._last_presence = datetime.now()
        self.logger.info(f"Agent UNLOCKED: {reason}")
        
        # Update state machine
        if self.state_machine:
            self.state_machine.unlock(reason)
        
        # Log security event
        if self.audit_logger:
            self.audit_logger.log_lock_event(False, reason)
        
        # Fire callbacks
        for callback in self._lock_callbacks:
            try:
                callback(False, reason)
            except Exception as e:
                self.logger.error(f"Unlock callback error: {e}")
        
        return True
    
    def authenticate(self) -> tuple:
        """
        Attempt authentication.
        
        Tries face verification first, then falls back to PIN.
        
        Returns:
            Tuple of (success, user_name, method).
        """
        # Try face verification first
        if self.face_verifier.is_available():
            result = self.face_verifier.verify()
            
            if self.audit_logger:
                self.audit_logger.log_face_auth(
                    result.success,
                    result.user_name,
                    result.confidence
                )
            
            if result.success:
                self.unlock(f"Face verified: {result.user_name}")
                return (True, result.user_name, "face")
        
        # Face failed or unavailable, try PIN
        self.logger.info("Face verification unavailable/failed. Trying PIN...")
        return (False, None, "pending_pin")
    
    def authenticate_with_pin(self, pin: str) -> tuple:
        """
        Authenticate using PIN.
        
        Args:
            pin: PIN to verify.
        
        Returns:
            Tuple of (success, user_name, method).
        """
        if self.pin_fallback.verify(pin):
            self.unlock("PIN verified")
            return (True, "user", "pin")
        else:
            self.logger.warning("PIN verification failed.")
            return (False, None, "pin_failed")
    
    def start_presence_monitoring(self) -> None:
        """Start background presence monitoring."""
        if self._running:
            return
        
        self._running = True
        self._presence_thread = threading.Thread(
            target=self._presence_loop,
            daemon=True
        )
        self._presence_thread.start()
        self.logger.info("Presence monitoring started.")
    
    def stop_presence_monitoring(self) -> None:
        """Stop presence monitoring."""
        self._running = False
        if self._presence_thread:
            self._presence_thread.join(timeout=5)
        self.logger.info("Presence monitoring stopped.")
    
    def _presence_loop(self) -> None:
        """Background presence checking loop."""
        while self._running:
            try:
                if not self._is_locked and self.face_verifier.is_available():
                    result = self.face_verifier.verify()
                    
                    if result.success:
                        self._last_presence = datetime.now()
                    else:
                        # Check absence timeout
                        absence_duration = (
                            datetime.now() - self._last_presence
                        ).total_seconds()
                        
                        if absence_duration >= self.ABSENCE_TIMEOUT:
                            self.lock("User absence detected")
                
            except Exception as e:
                self.logger.error(f"Presence check error: {e}")
            
            time.sleep(self.CHECK_INTERVAL)
    
    def on_lock_change(self, callback: Callable[[bool, str], None]) -> None:
        """
        Register lock state change callback.
        
        Args:
            callback: Function called with (is_locked, reason).
        """
        self._lock_callbacks.append(callback)
    
    def reset_presence_timer(self) -> None:
        """Reset presence timer (called on user activity)."""
        self._last_presence = datetime.now()
