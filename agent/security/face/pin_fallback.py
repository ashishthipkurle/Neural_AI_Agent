"""
PIN Fallback - Secondary authentication method.

This module provides PIN-based authentication as a fallback
when face recognition fails or is unavailable.
"""
import logging
import hashlib
import os
from typing import Optional
from pathlib import Path


class PINFallback:
    """
    PIN-based authentication fallback.
    
    Security:
    - PIN is stored as salted SHA-256 hash
    - Rate limiting on failed attempts
    - Lockout after max failures
    """
    
    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION = 300  # 5 minutes
    
    def __init__(
        self,
        pin_file: str = "agent/db/.pin_hash",
        default_pin: str = None
    ):
        """
        Initialize PIN fallback.
        
        Args:
            pin_file: Path to PIN hash storage.
            default_pin: Default PIN to set if none exists.
        """
        self.logger = logging.getLogger("PINFallback")
        self.pin_file = Path(pin_file)
        self.pin_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._failed_attempts = 0
        self._lockout_until = None
        self._salt = None
        self._pin_hash = None
        
        self._load_pin()
        
        # Set default PIN if none exists
        if not self._pin_hash and default_pin:
            self.set_pin(default_pin)
        
        self.logger.info("PINFallback initialized.")
    
    def _generate_salt(self) -> bytes:
        """Generate random salt."""
        return os.urandom(32)
    
    def _hash_pin(self, pin: str, salt: bytes) -> bytes:
        """Hash PIN with salt."""
        return hashlib.sha256(salt + pin.encode()).digest()
    
    def _load_pin(self) -> None:
        """Load PIN hash from file."""
        if not self.pin_file.exists():
            return
        
        try:
            with open(self.pin_file, 'rb') as f:
                data = f.read()
                if len(data) >= 64:  # 32 bytes salt + 32 bytes hash
                    self._salt = data[:32]
                    self._pin_hash = data[32:64]
                    self.logger.debug("PIN hash loaded.")
        except Exception as e:
            self.logger.error(f"Failed to load PIN: {e}")
    
    def _save_pin(self) -> None:
        """Save PIN hash to file."""
        if not self._salt or not self._pin_hash:
            return
        
        try:
            with open(self.pin_file, 'wb') as f:
                f.write(self._salt + self._pin_hash)
            self.logger.debug("PIN hash saved.")
        except Exception as e:
            self.logger.error(f"Failed to save PIN: {e}")
    
    def set_pin(self, pin: str) -> bool:
        """
        Set or change PIN.
        
        Args:
            pin: New PIN (4-8 digits).
        
        Returns:
            True if PIN was set.
        """
        # Validate PIN format
        if not pin.isdigit() or len(pin) < 4 or len(pin) > 8:
            self.logger.warning("Invalid PIN format. Must be 4-8 digits.")
            return False
        
        self._salt = self._generate_salt()
        self._pin_hash = self._hash_pin(pin, self._salt)
        self._save_pin()
        
        self.logger.info("PIN set successfully.")
        return True
    
    def verify(self, pin: str) -> bool:
        """
        Verify PIN.
        
        Args:
            pin: PIN to verify.
        
        Returns:
            True if PIN is correct.
        """
        # Check lockout
        if self._is_locked_out():
            self.logger.warning("PIN verification locked out.")
            return False
        
        # Check if PIN is set
        if not self._pin_hash or not self._salt:
            self.logger.warning("No PIN set.")
            return False
        
        # Verify
        attempt_hash = self._hash_pin(pin, self._salt)
        
        if attempt_hash == self._pin_hash:
            self._failed_attempts = 0
            self.logger.info("PIN verified successfully.")
            return True
        else:
            self._failed_attempts += 1
            remaining = self.MAX_ATTEMPTS - self._failed_attempts
            
            if self._failed_attempts >= self.MAX_ATTEMPTS:
                self._trigger_lockout()
                self.logger.warning("Max PIN attempts reached. Locked out.")
            else:
                self.logger.warning(f"Incorrect PIN. {remaining} attempts remaining.")
            
            return False
    
    def _is_locked_out(self) -> bool:
        """Check if PIN verification is locked out."""
        if self._lockout_until is None:
            return False
        
        from datetime import datetime
        if datetime.now().timestamp() < self._lockout_until:
            return True
        
        # Lockout expired
        self._lockout_until = None
        self._failed_attempts = 0
        return False
    
    def _trigger_lockout(self) -> None:
        """Trigger lockout period."""
        from datetime import datetime
        self._lockout_until = datetime.now().timestamp() + self.LOCKOUT_DURATION
    
    def is_configured(self) -> bool:
        """Check if PIN is configured."""
        return self._pin_hash is not None
    
    def get_remaining_attempts(self) -> int:
        """Get remaining PIN attempts."""
        if self._is_locked_out():
            return 0
        return self.MAX_ATTEMPTS - self._failed_attempts
    
    def get_lockout_remaining(self) -> int:
        """Get remaining lockout time in seconds."""
        if not self._lockout_until:
            return 0
        
        from datetime import datetime
        remaining = self._lockout_until - datetime.now().timestamp()
        return max(0, int(remaining))
    
    def reset_attempts(self) -> None:
        """Reset failed attempt counter (admin only)."""
        self._failed_attempts = 0
        self._lockout_until = None
        self.logger.info("PIN attempts reset.")
