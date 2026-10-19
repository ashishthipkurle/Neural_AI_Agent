"""
Workflow Scheduler — Background cron scheduler for automated workflow triggers.

Uses asyncio to check cron expressions and trigger workflow execution
on schedule. Persists schedule state in SQLite via WorkflowStore.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Callable

from agent.workflow.workflow_store import WorkflowStore

logger = logging.getLogger("WorkflowScheduler")


def _parse_cron_field(field: str, min_val: int, max_val: int) -> list:
    """Parse a single cron field into a list of matching values."""
    values = set()

    for part in field.split(","):
        part = part.strip()

        if part == "*":
            values.update(range(min_val, max_val + 1))
        elif "/" in part:
            # Step values: */5 or 1-30/5
            base, step = part.split("/", 1)
            step = int(step)
            if base == "*":
                start = min_val
                end = max_val
            elif "-" in base:
                start, end = map(int, base.split("-", 1))
            else:
                start = int(base)
                end = max_val
            values.update(range(start, end + 1, step))
        elif "-" in part:
            # Range: 1-5
            start, end = map(int, part.split("-", 1))
            values.update(range(start, end + 1))
        else:
            values.add(int(part))

    return sorted(values)


def cron_matches(cron_expression: str, dt: datetime) -> bool:
    """
    Check if a datetime matches a cron expression.

    Format: minute hour day_of_month month day_of_week
    Examples:
      "0 9 * * *"     → Every day at 9:00 AM
      "*/5 * * * *"   → Every 5 minutes
      "0 9 * * 1-5"   → Weekdays at 9:00 AM
      "30 8 1 * *"    → 1st of each month at 8:30 AM
    """
    try:
        parts = cron_expression.strip().split()
        if len(parts) != 5:
            logger.error(f"Invalid cron expression: {cron_expression}")
            return False

        minute_field, hour_field, dom_field, month_field, dow_field = parts

        minutes = _parse_cron_field(minute_field, 0, 59)
        hours = _parse_cron_field(hour_field, 0, 23)
        doms = _parse_cron_field(dom_field, 1, 31)
        months = _parse_cron_field(month_field, 1, 12)
        dows = _parse_cron_field(dow_field, 0, 6)  # 0 = Sunday

        # Python weekday: 0 = Monday, cron: 0 = Sunday
        py_dow = (dt.weekday() + 1) % 7  # Convert to cron format

        return (
            dt.minute in minutes
            and dt.hour in hours
            and dt.day in doms
            and dt.month in months
            and py_dow in dows
        )
    except Exception as e:
        logger.error(f"Cron parse error for '{cron_expression}': {e}")
        return False


def _next_cron_time(cron_expression: str, after: datetime = None) -> Optional[datetime]:
    """Calculate the next time a cron expression will fire after the given datetime."""
    if after is None:
        after = datetime.now(timezone.utc)

    # Check the next 48 hours worth of minutes
    check_time = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(2880):  # 48 hours * 60 minutes
        if cron_matches(cron_expression, check_time):
            return check_time
        check_time += timedelta(minutes=1)

    return None


class WorkflowScheduler:
    """
    Background scheduler that monitors cron schedules and triggers workflows.
    """

    def __init__(self, store: WorkflowStore, engine_execute_fn: Callable):
        """
        Args:
            store: WorkflowStore instance
            engine_execute_fn: Async function to execute a workflow by ID
                               signature: async (workflow_id, trigger_type, trigger_data) -> result
        """
        self.store = store
        self.execute_fn = engine_execute_fn
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._check_interval = 30  # Check every 30 seconds

    async def start(self):
        """Start the scheduler loop."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("⏰ Workflow scheduler started")

    async def stop(self):
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("⏰ Workflow scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop — checks cron expressions every interval."""
        # Track last check minute to avoid duplicate fires
        last_checked_minute = None

        while self._running:
            try:
                now = datetime.now(timezone.utc)
                current_minute = now.replace(second=0, microsecond=0)

                # Only check once per minute
                if current_minute != last_checked_minute:
                    last_checked_minute = current_minute
                    await self._check_schedules(now)

            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            await asyncio.sleep(self._check_interval)

    async def _check_schedules(self, now: datetime):
        """Check all active schedules and fire matching ones."""
        schedules = self.store.get_active_schedules()

        for schedule in schedules:
            try:
                cron_expr = schedule["cron_expression"]
                workflow_id = schedule["workflow_id"]

                if cron_matches(cron_expr, now):
                    logger.info(f"⏰ Cron fired for workflow {workflow_id}: {cron_expr}")

                    # Update last_run and next_run
                    next_time = _next_cron_time(cron_expr, now)
                    self.store.update_schedule_last_run(
                        workflow_id,
                        last_run=now.isoformat(),
                        next_run=next_time.isoformat() if next_time else None
                    )

                    # Execute workflow in background
                    asyncio.create_task(self._execute_scheduled(workflow_id))

            except Exception as e:
                logger.error(f"Error checking schedule for workflow {schedule.get('workflow_id')}: {e}")

    async def _execute_scheduled(self, workflow_id: str):
        """Execute a scheduled workflow."""
        try:
            result = await self.execute_fn(
                workflow_id,
                trigger_type="scheduled",
                trigger_data={"scheduled_at": datetime.now(timezone.utc).isoformat()}
            )
            logger.info(f"⏰ Scheduled workflow {workflow_id} completed: {result.get('status', 'unknown')}")
        except Exception as e:
            logger.error(f"⏰ Scheduled workflow {workflow_id} failed: {e}")

    def reload_schedules(self):
        """Force reload of active schedules (called after schedule changes)."""
        schedules = self.store.get_active_schedules()
        logger.info(f"⏰ Reloaded {len(schedules)} active schedules")
        return schedules
