"""
Rollback Manager - Action undo and recovery system.

This module provides rollback capabilities for reversible actions,
enabling recovery from unintended changes.
"""
import logging
import os
import shutil
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import json


class ActionType(Enum):
    """Types of rollbackable actions."""
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    FILE_MOVE = "file_move"
    APP_LAUNCH = "app_launch"
    SYSTEM_COMMAND = "system_command"
    MEMORY_STORE = "memory_store"
    SETTING_CHANGE = "setting_change"


@dataclass
class RollbackableAction:
    """Represents an action that can be rolled back."""
    id: str
    action_type: ActionType
    description: str
    timestamp: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    rollback_data: Dict[str, Any] = field(default_factory=dict)
    is_rolled_back: bool = False
    rollback_timestamp: Optional[str] = None
    
    def can_rollback(self) -> bool:
        """Check if action can still be rolled back."""
        if self.is_rolled_back:
            return False
        # File actions need backup to exist
        if self.action_type in {ActionType.FILE_WRITE, ActionType.FILE_DELETE}:
            backup_path = self.rollback_data.get("backup_path")
            return backup_path and os.path.exists(backup_path)
        return True


class RollbackManager:
    """
    Manages action rollback and recovery.
    
    Features:
    - File backup before modification
    - Action history tracking
    - Selective rollback
    - Rollback chain (multiple undos)
    
    Supports rollback for:
    - File writes (backup original)
    - File deletes (backup deleted file)
    - Memory operations
    """
    
    MAX_HISTORY = 100
    BACKUP_DIR = ".agent_backups"
    
    def __init__(self, backup_base_path: str = "logs"):
        """
        Initialize the rollback manager.
        
        Args:
            backup_base_path: Base path for backup storage.
        """
        self.logger = logging.getLogger("RollbackManager")
        self.backup_path = Path(backup_base_path) / self.BACKUP_DIR
        self.backup_path.mkdir(parents=True, exist_ok=True)
        
        self._history: List[RollbackableAction] = []
        self._action_counter = 0
        
        self.logger.info(f"RollbackManager initialized. Backup path: {self.backup_path}")
    
    def _generate_action_id(self) -> str:
        """Generate unique action ID."""
        self._action_counter += 1
        return f"action_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._action_counter}"
    
    def _generate_backup_path(self, original_path: str) -> str:
        """Generate backup path for a file."""
        filename = Path(original_path).name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return str(self.backup_path / f"{timestamp}_{filename}")
    
    def record_file_write(
        self,
        file_path: str,
        original_content: Optional[str] = None,
        new_content: str = ""
    ) -> RollbackableAction:
        """
        Record a file write action for potential rollback.
        
        Args:
            file_path: Path to file being written.
            original_content: Original file content (if existed).
            new_content: New content being written.
        
        Returns:
            RollbackableAction record.
        """
        backup_path = None
        file_existed = original_content is not None
        
        # Backup original content if file existed
        if file_existed:
            backup_path = self._generate_backup_path(file_path)
            try:
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(original_content)
                self.logger.debug(f"Backed up {file_path} to {backup_path}")
            except Exception as e:
                self.logger.warning(f"Failed to backup {file_path}: {e}")
                backup_path = None
        
        action = RollbackableAction(
            id=self._generate_action_id(),
            action_type=ActionType.FILE_WRITE,
            description=f"Write to {file_path}",
            timestamp=datetime.now().isoformat(),
            parameters={
                "file_path": file_path,
                "content_length": len(new_content)
            },
            rollback_data={
                "file_existed": file_existed,
                "backup_path": backup_path,
                "original_path": file_path
            }
        )
        
        self._add_to_history(action)
        return action
    
    def record_file_delete(self, file_path: str) -> Optional[RollbackableAction]:
        """
        Record a file delete action with backup.
        
        Args:
            file_path: Path to file being deleted.
        
        Returns:
            RollbackableAction or None if backup failed.
        """
        if not os.path.exists(file_path):
            return None
        
        backup_path = self._generate_backup_path(file_path)
        
        try:
            shutil.copy2(file_path, backup_path)
            self.logger.debug(f"Backed up deleted file {file_path} to {backup_path}")
        except Exception as e:
            self.logger.warning(f"Failed to backup {file_path} before delete: {e}")
            return None
        
        action = RollbackableAction(
            id=self._generate_action_id(),
            action_type=ActionType.FILE_DELETE,
            description=f"Delete {file_path}",
            timestamp=datetime.now().isoformat(),
            parameters={"file_path": file_path},
            rollback_data={
                "backup_path": backup_path,
                "original_path": file_path
            }
        )
        
        self._add_to_history(action)
        return action
    
    def record_memory_store(
        self,
        memory_id: str,
        content: str,
        memory_type: str = "long_term"
    ) -> RollbackableAction:
        """
        Record a memory store action.
        
        Args:
            memory_id: ID of stored memory.
            content: Content that was stored.
            memory_type: Type of memory store.
        
        Returns:
            RollbackableAction record.
        """
        action = RollbackableAction(
            id=self._generate_action_id(),
            action_type=ActionType.MEMORY_STORE,
            description=f"Store memory: {content[:50]}...",
            timestamp=datetime.now().isoformat(),
            parameters={
                "memory_id": memory_id,
                "content": content,
                "memory_type": memory_type
            },
            rollback_data={
                "memory_id": memory_id,
                "memory_type": memory_type
            }
        )
        
        self._add_to_history(action)
        return action
    
    def _add_to_history(self, action: RollbackableAction) -> None:
        """Add action to history with size limit."""
        self._history.append(action)
        
        # Trim history if too large
        if len(self._history) > self.MAX_HISTORY:
            # Remove oldest entries and their backups
            removed = self._history[:len(self._history) - self.MAX_HISTORY]
            for old_action in removed:
                self._cleanup_backup(old_action)
            self._history = self._history[-self.MAX_HISTORY:]
    
    def _cleanup_backup(self, action: RollbackableAction) -> None:
        """Clean up backup files for an action."""
        backup_path = action.rollback_data.get("backup_path")
        if backup_path and os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception as e:
                self.logger.warning(f"Failed to cleanup backup {backup_path}: {e}")
    
    def rollback(self, action_id: str) -> bool:
        """
        Rollback a specific action.
        
        Args:
            action_id: ID of action to rollback.
        
        Returns:
            True if rollback succeeded.
        """
        action = self.get_action(action_id)
        if not action:
            self.logger.error(f"Action not found: {action_id}")
            return False
        
        if not action.can_rollback():
            self.logger.error(f"Action cannot be rolled back: {action_id}")
            return False
        
        try:
            if action.action_type == ActionType.FILE_WRITE:
                return self._rollback_file_write(action)
            elif action.action_type == ActionType.FILE_DELETE:
                return self._rollback_file_delete(action)
            elif action.action_type == ActionType.MEMORY_STORE:
                return self._rollback_memory_store(action)
            else:
                self.logger.warning(f"Rollback not implemented for: {action.action_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Rollback failed for {action_id}: {e}")
            return False
    
    def _rollback_file_write(self, action: RollbackableAction) -> bool:
        """Rollback a file write action."""
        original_path = action.rollback_data["original_path"]
        backup_path = action.rollback_data.get("backup_path")
        file_existed = action.rollback_data["file_existed"]
        
        if file_existed and backup_path:
            # Restore from backup
            shutil.copy2(backup_path, original_path)
            self.logger.info(f"Restored {original_path} from backup")
        elif not file_existed:
            # File didn't exist before, delete it
            if os.path.exists(original_path):
                os.remove(original_path)
            self.logger.info(f"Removed newly created {original_path}")
        
        action.is_rolled_back = True
        action.rollback_timestamp = datetime.now().isoformat()
        return True
    
    def _rollback_file_delete(self, action: RollbackableAction) -> bool:
        """Rollback a file delete action."""
        original_path = action.rollback_data["original_path"]
        backup_path = action.rollback_data["backup_path"]
        
        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, original_path)
            self.logger.info(f"Restored deleted file {original_path}")
            action.is_rolled_back = True
            action.rollback_timestamp = datetime.now().isoformat()
            return True
        
        return False
    
    def _rollback_memory_store(self, action: RollbackableAction) -> bool:
        """Rollback a memory store action."""
        # This would need integration with memory system
        # For now, just mark as rolled back
        self.logger.info(f"Memory rollback requested: {action.rollback_data['memory_id']}")
        action.is_rolled_back = True
        action.rollback_timestamp = datetime.now().isoformat()
        return True
    
    def rollback_last(self) -> bool:
        """Rollback the most recent action."""
        for action in reversed(self._history):
            if action.can_rollback():
                return self.rollback(action.id)
        return False
    
    def get_action(self, action_id: str) -> Optional[RollbackableAction]:
        """Get an action by ID."""
        for action in self._history:
            if action.id == action_id:
                return action
        return None
    
    def get_history(self, limit: int = 20, include_rolled_back: bool = False) -> List[RollbackableAction]:
        """Get action history."""
        actions = self._history[-limit:]
        if not include_rolled_back:
            actions = [a for a in actions if not a.is_rolled_back]
        return actions
    
    def get_rollbackable(self) -> List[RollbackableAction]:
        """Get all actions that can still be rolled back."""
        return [a for a in self._history if a.can_rollback()]
    
    def cleanup(self) -> int:
        """
        Clean up old backups.
        
        Returns:
            Number of backups cleaned.
        """
        cleaned = 0
        for action in self._history:
            if action.is_rolled_back:
                self._cleanup_backup(action)
                cleaned += 1
        return cleaned
