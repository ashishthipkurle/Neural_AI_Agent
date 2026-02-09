
import logging
import asyncio
import traceback
from typing import Dict, Any, Callable, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from .models import Task, TaskStatus

logger = logging.getLogger(__name__)

class TaskExecutor:
    """
    Executes tasks in background threads/async loops.
    """
    
    def __init__(self, session_factory, skill_registry=None):
        self.Session = session_factory
        self.skill_registry = skill_registry
        self.running_tasks = {} # task_id -> asyncio.Task
        self.stop_events = {} # task_id -> asyncio.Event
        
    async def execute_task(self, task_id: str, skill_execution_func: Callable) -> None:
        """
        Execute a task asynchronously.
        
        Args:
            task_id: ID of method
            skill_execution_func: Async function to execute the skill logic
        """
        session = self.Session()
        try:
            task = session.query(Task).filter_by(id=task_id).first()
            if not task:
                return
            
            # Update status
            task.status = TaskStatus.RUNNING.value
            task.started_at = datetime.utcnow()
            session.commit()
            
            # Create cancellation event
            self.stop_events[task_id] = asyncio.Event()
            
            # Run
            try:
                # We wrap execution to allow for detailed logging/state management
                logger.info(f"Starting execution of task {task_id}")
                result = await skill_execution_func()
                
                # Check if cancelled during execution
                if self.stop_events[task_id].is_set():
                    task.status = TaskStatus.CANCELLED.value
                else:
                    task.status = TaskStatus.COMPLETED.value
                    task.result = result
                    task.completed_at = datetime.utcnow()
                    task.progress = 100
                
            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED.value
                logger.info(f"Task {task_id} cancelled.")
            except Exception as e:
                task.status = TaskStatus.FAILED.value
                task.error = f"{str(e)}\n{traceback.format_exc()}"
                logger.error(f"Task {task_id} failed: {e}")
            
            session.commit()
            
        except Exception as e:
            logger.error(f"Critical executor error for {task_id}: {e}")
            if session:
                session.rollback()
        finally:
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            if task_id in self.stop_events:
                del self.stop_events[task_id]
            session.close()

    def start_background_task(self, task_id: str, coro):
        """Helper to schedule async execution."""
        task = asyncio.create_task(coro)
        self.running_tasks[task_id] = task
        return task

    def pause_task(self, task_id: str) -> bool:
        """Pause a running task (requires skill support)."""
        # Checks if we can signal the task to pause
        # For now, we'll just set the status in DB, 
        # actual execution pause depends on the skill checking this status
        session = self.Session()
        try:
            task = session.query(Task).filter_by(id=task_id).first()
            if task and task.status == TaskStatus.RUNNING.value:
                task.status = TaskStatus.PAUSED.value
                session.commit()
                return True
            return False
        finally:
            session.close()

    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        session = self.Session()
        try:
            task = session.query(Task).filter_by(id=task_id).first()
            if task and task.status == TaskStatus.PAUSED.value:
                task.status = TaskStatus.RUNNING.value
                session.commit()
                return True
            return False
        finally:
            session.close()

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            if task_id in self.stop_events:
                self.stop_events[task_id].set()
            return True
        return False
        
    def retry_task(self, task_id: str) -> bool:
        """Reset task to pending state for retry."""
        session = self.Session()
        try:
            task = session.query(Task).filter_by(id=task_id).first()
            if task and task.status in [TaskStatus.FAILED.value, TaskStatus.CANCELLED.value]:
                task.status = TaskStatus.PENDING.value
                task.error = None
                task.result = None
                task.progress = 0
                session.commit()
                return True
            return False
        finally:
            session.close()

    def get_progress(self, task_id: str) -> int:
        """Get current progress."""
        session = self.Session()
        try:
            task = session.query(Task).filter_by(id=task_id).first()
            return task.progress if task else 0
        finally:
            session.close()
            
    def update_progress(self, task_id: str, progress: int) -> None:
        """Update task progress."""
        session = self.Session()
        try:
            task = session.query(Task).filter_by(id=task_id).first()
            if task:
                task.progress = progress
                session.commit()
        except:
            session.rollback()
        finally:
            session.close()
