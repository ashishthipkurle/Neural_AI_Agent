"""
TTL Manager - Time-to-live based memory expiration.

This module manages automatic expiration of memories
based on configurable TTL policies.
"""
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class TTLPolicy:
    """TTL policy for a memory type."""
    memory_type: str
    ttl_seconds: int
    refresh_on_access: bool = False
    max_refreshes: int = 3


class TTLManager:
    """
    Manages memory expiration.
    
    Features:
    - Per-type TTL policies
    - Optional refresh on access
    - Background cleanup
    - Expiration callbacks
    
    Default TTLs:
    - Episodic: 7 days
    - Semantic: 30 days
    - Session: End of session
    """
    
    DEFAULT_POLICIES = {
        "episodic": TTLPolicy("episodic", 7 * 86400),  # 7 days
        "semantic": TTLPolicy("semantic", 30 * 86400),  # 30 days
        "session": TTLPolicy("session", 0),  # No TTL (session-bound)
        "temporary": TTLPolicy("temporary", 3600),  # 1 hour
    }
    
    CLEANUP_INTERVAL = 3600  # 1 hour
    
    def __init__(self, memory_store=None):
        """
        Initialize TTL manager.
        
        Args:
            memory_store: Long-term memory store reference.
        """
        self.logger = logging.getLogger("TTLManager")
        self.memory_store = memory_store
        
        self._policies = dict(self.DEFAULT_POLICIES)
        self._expiration_times: Dict[str, datetime] = {}
        self._refresh_counts: Dict[str, int] = {}
        self._on_expire_callbacks: list = []
        
        self._cleanup_thread = None
        self._running = False
        self._lock = threading.RLock()
        
        self.logger.info("TTLManager initialized.")
    
    def set_policy(self, policy: TTLPolicy) -> None:
        """Set or update TTL policy for a memory type."""
        self._policies[policy.memory_type] = policy
        self.logger.debug(f"TTL policy set: {policy.memory_type} = {policy.ttl_seconds}s")
    
    def get_policy(self, memory_type: str) -> TTLPolicy:
        """Get TTL policy for a memory type."""
        return self._policies.get(memory_type, self.DEFAULT_POLICIES["episodic"])
    
    def register_memory(self, memory_id: str, memory_type: str) -> None:
        """
        Register a memory for TTL tracking.
        
        Args:
            memory_id: Memory identifier.
            memory_type: Type of memory.
        """
        policy = self.get_policy(memory_type)
        
        if policy.ttl_seconds <= 0:
            return  # No TTL for this type
        
        with self._lock:
            expiration = datetime.now() + timedelta(seconds=policy.ttl_seconds)
            self._expiration_times[memory_id] = expiration
            self._refresh_counts[memory_id] = 0
        
        self.logger.debug(f"Memory {memory_id} expires at {expiration}")
    
    def refresh_memory(self, memory_id: str) -> bool:
        """
        Refresh memory TTL on access.
        
        Args:
            memory_id: Memory identifier.
        
        Returns:
            True if TTL was refreshed.
        """
        with self._lock:
            if memory_id not in self._expiration_times:
                return False
            
            # Get memory type and policy
            # (Would need to look up from memory store in production)
            policy = self.DEFAULT_POLICIES.get("episodic")
            
            if not policy.refresh_on_access:
                return False
            
            current_refreshes = self._refresh_counts.get(memory_id, 0)
            if current_refreshes >= policy.max_refreshes:
                self.logger.debug(f"Memory {memory_id} max refreshes reached.")
                return False
            
            new_expiration = datetime.now() + timedelta(seconds=policy.ttl_seconds)
            self._expiration_times[memory_id] = new_expiration
            self._refresh_counts[memory_id] = current_refreshes + 1
            
            self.logger.debug(f"Memory {memory_id} TTL refreshed.")
            return True
    
    def get_expiration(self, memory_id: str) -> Optional[datetime]:
        """Get expiration time for a memory."""
        return self._expiration_times.get(memory_id)
    
    def is_expired(self, memory_id: str) -> bool:
        """Check if memory is expired."""
        with self._lock:
            expiration = self._expiration_times.get(memory_id)
            if not expiration:
                return False
            return datetime.now() > expiration
    
    def get_expired_memories(self) -> list:
        """Get list of expired memory IDs."""
        now = datetime.now()
        expired = []
        
        with self._lock:
            for memory_id, expiration in self._expiration_times.items():
                if now > expiration:
                    expired.append(memory_id)
        
        return expired
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired memories.
        
        Returns:
            Number of memories cleaned up.
        """
        expired = self.get_expired_memories()
        
        for memory_id in expired:
            # Remove from tracking
            with self._lock:
                self._expiration_times.pop(memory_id, None)
                self._refresh_counts.pop(memory_id, None)
            
            # Delete from memory store
            if self.memory_store:
                try:
                    # Would call memory_store.delete(memory_id)
                    pass
                except Exception as e:
                    self.logger.error(f"Failed to delete expired memory: {e}")
            
            # Fire callbacks
            for callback in self._on_expire_callbacks:
                try:
                    callback(memory_id)
                except Exception as e:
                    self.logger.error(f"Expiration callback error: {e}")
        
        if expired:
            self.logger.info(f"Cleaned up {len(expired)} expired memories.")
        
        return len(expired)
    
    def on_memory_expire(self, callback: Callable[[str], None]) -> None:
        """Register callback for memory expiration."""
        self._on_expire_callbacks.append(callback)
    
    def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._running:
            return
        
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self._cleanup_thread.start()
        self.logger.info("TTL cleanup task started.")
    
    def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        self.logger.info("TTL cleanup task stopped.")
    
    def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self._running:
            try:
                self.cleanup_expired()
            except Exception as e:
                self.logger.error(f"Cleanup error: {e}")
            
            time.sleep(self.CLEANUP_INTERVAL)
