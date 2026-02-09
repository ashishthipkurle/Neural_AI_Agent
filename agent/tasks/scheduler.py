
import logging
import asyncio
from typing import List, Dict
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import ScheduledTask

logger = logging.getLogger(__name__)

class TaskScheduler:
    """
    Manages scheduled tasks (Cron-like).
    """
    
    def __init__(self, session_factory, task_manager):
        self.Session = session_factory
        self.task_manager = task_manager
        self.running = False
        
    async def start(self):
        """Start the scheduler loop."""
        self.running = True
        logger.info("Task Scheduler started.")
        while self.running:
            try:
                self.run_pending()
                await asyncio.sleep(60) # Check every minute
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)

    def stop(self):
        """Stop the scheduler."""
        self.running = False

    def schedule_task(self, task_description: str, skill_name: str, cron_expression: str) -> str:
        """Add a new scheduled task."""
        # Simple cron parser placeholder: "every X minutes"
        # Real impl would use a cron library
        
        interval = 60 # Default 1 hour
        if "minute" in cron_expression:
            parts = cron_expression.split()
            if len(parts) > 1 and parts[1].isdigit():
                interval = int(parts[1])
                
        next_run = datetime.utcnow() + timedelta(minutes=interval)
        
        session = self.Session()
        try:
            task = ScheduledTask(
                task_description=task_description,
                skill_name=skill_name,
                cron_expression=cron_expression,
                next_run=next_run
            )
            session.add(task)
            session.commit()
            return task.id
        finally:
            session.close()

    def unschedule_task(self, task_id: str) -> bool:
        """Remove a scheduled task."""
        session = self.Session()
        try:
            session.query(ScheduledTask).filter_by(id=task_id).delete()
            session.commit()
            return True
        finally:
            session.close()

    def get_scheduled_tasks(self) -> List[dict]:
        """List all scheduled tasks."""
        session = self.Session()
        try:
            tasks = session.query(ScheduledTask).all()
            return [t.to_dict() for t in tasks]
        finally:
            session.close()

    def run_pending(self):
        """Check and run tasks due for execution."""
        session = self.Session()
        try:
            now = datetime.utcnow()
            due_tasks = session.query(ScheduledTask).filter(
                ScheduledTask.next_run <= now,
                ScheduledTask.enabled == True
            ).all()
            
            for st in due_tasks:
                logger.info(f"Executing scheduled task: {st.task_description}")
                # Submit to Task Manager
                self.task_manager.submit_task(
                    description=st.task_description,
                    skill_name=st.skill_name,
                    priority=5
                )
                
                # Update next run
                # Simplified logic: just add 1 hour
                st.last_run = now
                st.next_run = now + timedelta(hours=1) 
                # Ideally check cron_expression here
                
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to run pending tasks: {e}")
        finally:
            session.close()
