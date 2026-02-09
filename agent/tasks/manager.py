
import logging
import asyncio
from typing import List, Dict, Any, Callable
from datetime import datetime
from sqlalchemy.orm import sessionmaker
from .models import init_task_db, Task, TaskQueue, TaskHistory, TaskStatus
from .executor import TaskExecutor
from .scheduler import TaskScheduler
from .state import TaskStateManager

logger = logging.getLogger(__name__)

class TaskManager:
    """
    Central coordinator for long-running tasks.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_path = config.get('tasks', {}).get('db_path', 'agent/data/tasks.db')
        self.engine = None
        self.Session = None
        
        self.executor = None
        self.scheduler = None
        self.state_manager = None
        self.completion_callbacks = []
        
        self.initialize()
        
    def initialize(self) -> None:
        """
        Initialize database and components.
        """
        logger.info(f"Initializing Task Database at {self.db_path}")
        self.engine = init_task_db(self.db_path)
        self.Session = sessionmaker(bind=self.engine)
        
        self.executor = TaskExecutor(self.Session)
        self.scheduler = TaskScheduler(self.Session, self)
        self.state_manager = TaskStateManager()
        
    def submit_task(self, description: str, skill_name: str, params: Dict[str, Any] = None, priority: int = 5) -> str:
        """
        Submit a new task to queue.
        """
        session = self.Session()
        try:
            task = Task(
                description=description,
                skill_name=skill_name,
                parameters=params or {},
                priority=priority,
                status=TaskStatus.PENDING.value
            )
            session.add(task)
            session.commit()
            
            # Add to queue
            queue_item = TaskQueue(task_id=task.id, position=0) # Simplified queue logic
            session.add(queue_item)
            session.commit()
            
            logger.info(f"Task submitted: {task.id} - {description}")
            return task.id
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to submit task: {e}")
            return ""
        finally:
            session.close()

    def get_task_status(self, task_id: str) -> dict:
        """Get status of a task."""
        session = self.Session()
        try:
            task = session.query(Task).filter_by(id=task_id).first()
            return task.to_dict() if task else {}
        finally:
            session.close()

    def get_active_tasks(self) -> List[dict]:
        """Get all pending or running tasks."""
        session = self.Session()
        try:
            tasks = session.query(Task).filter(
                Task.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value])
            ).all()
            return [t.to_dict() for t in tasks]
        finally:
            session.close()

    def get_completed_tasks(self, limit: int = 50) -> List[dict]:
        """Get history of completed tasks."""
        session = self.Session()
        try:
            tasks = session.query(Task).filter(
                Task.status.in_([TaskStatus.COMPLETED.value, TaskStatus.FAILED.value])
            ).order_by(Task.completed_at.desc()).limit(limit).all()
            return [t.to_dict() for t in tasks]
        finally:
            session.close()

    def pause_task(self, task_id: str) -> bool:
        """Pause a task."""
        return self.executor.pause_task(task_id)

    def resume_task(self, task_id: str) -> bool:
        """Resume a task."""
        return self.executor.resume_task(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        session = self.Session()
        try:
            task = session.query(Task).filter_by(id=task_id).first()
            if task and task.status == TaskStatus.PENDING.value:
                task.status = TaskStatus.CANCELLED.value
                session.commit()
                return True
            return self.executor.cancel_task(task_id)
        finally:
            session.close()

    def on_task_complete(self, callback: Callable):
        """Register a callback for task completion."""
        self.completion_callbacks.append(callback)
        
    def _notify_complete(self, task_id: str, result: Any):
        """Internal: Notify callbacks."""
        for cb in self.completion_callbacks:
            try:
                cb(task_id, result)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    async def execute_pending_tasks(self, skill_executor_map: Dict[str, Callable]):
        """
        Main loop to pick tasks and execute them.
        skill_executor_map: dict mapping skill_name -> async function(task_id, params)
        """
        while True:
            session = self.Session()
            try:
                # Find highest priority pending task
                queue_item = session.query(TaskQueue).order_by(TaskQueue.position).first()
                if queue_item:
                    task = session.query(Task).filter_by(id=queue_item.task_id).first()
                    
                    if task and task.status == TaskStatus.PENDING.value:
                        # Find executor for skill
                        executor_func = skill_executor_map.get(task.skill_name)
                        if executor_func:
                            # Start execution
                            # Remove from queue immediately or keep until done? 
                            # Usually remove from queue once picked up
                            session.delete(queue_item)
                            session.commit()
                            
                            # We wrap the executor func to inject task_id
                            async def wrapped_execution():
                                return await executor_func(
                                    task_id=task.id, 
                                    params=task.parameters
                                )
                            
                            # Fire and forget (executor handles state)
                            self.executor.start_background_task(task.id, self.executor.execute_task(task.id, wrapped_execution))
                        else:
                            logger.error(f"No executor found for skill {task.skill_name}")
                            task.status = TaskStatus.FAILED.value
                            task.error = "No matching skill executor"
                            session.delete(queue_item)
                            session.commit()
            except Exception as e:
                logger.error(f"Task loop error: {e}")
                session.rollback()
            finally:
                session.close()
            
            await asyncio.sleep(1) # Polling interval
