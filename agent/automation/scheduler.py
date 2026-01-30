import schedule
import time
import logging
from typing import Callable, Any

class TaskScheduler:
    """
    Manages recurring tasks.
    """
    def __init__(self):
        self.logger = logging.getLogger("TaskScheduler")
        self.active = True

    def add_job(self, interval: int, unit: str, job_func: Callable, *args):
        """
        Adds a job to the schedule.
        Unit: 'seconds', 'minutes', 'hours'
        """
        try:
            if unit == 'seconds':
                schedule.every(interval).seconds.do(job_func, *args)
            elif unit == 'minutes':
                schedule.every(interval).minutes.do(job_func, *args)
            elif unit == 'hours':
                schedule.every(interval).hours.do(job_func, *args)
            else:
                return f"Error: Invalid time unit {unit}"
            
            self.logger.info(f"Scheduled job every {interval} {unit}")
            return f"Scheduled task every {interval} {unit}."
        except Exception as e:
            self.logger.error(f"Error scheduling job: {e}")
            return f"Error: {e}"

    def run_pending(self):
        """
        Must be called periodically to execute pending jobs.
        """
        if self.active:
            schedule.run_pending()
