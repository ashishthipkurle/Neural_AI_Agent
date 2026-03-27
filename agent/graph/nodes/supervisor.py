"""
Supervisor Node — Smart routing for Plan → Approve → Execute workflow.

Routes based on phase:
- No plan yet + big task → planner
- Plan awaiting approval → completion (return plan to UI)
- Plan approved → coder
- Coder finished → completion
- Small task → coder directly (skip planning)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict

from langgraph.types import Command
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.supervisor")

MAX_CODER_RETRIES = 3

# Patterns that indicate a simple/small task (skip planning)
SIMPLE_TASK_PATTERNS = [
    r"\b(explain|what is|what does|how does|describe|tell me about)\b",
    r"\b(fix this typo|add a comment|rename)\b",
    r"\b(hello|hi|hey|thanks|thank you|ok|okay)\b",
    r"\b(what's the error|show me|list)\b",
]

# Patterns that indicate a big/comprehensive task (needs planning)
BIG_TASK_PATTERNS = [
    r"\b(implement|create|build|develop|design|architect)\b",
    r"\b(refactor|restructure|rewrite|overhaul|modernize|upgrade)\b",
    r"\b(change the ui|update the ui|modify the ui|redesign)\b",
    r"\b(add feature|new feature|integrate|migrate)\b",
    r"\b(set up|setup|configure|deploy)\b",
    r"\b(change.*and.*make|modify.*files?|update.*multiple)\b",
]


def _is_simple_task(goal: str) -> bool:
    """Detect if a task is simple enough to skip planning."""
    goal_lower = goal.lower().strip()

    # Very short messages are usually simple
    if len(goal_lower.split()) <= 5:
        return True

    for pattern in SIMPLE_TASK_PATTERNS:
        if re.search(pattern, goal_lower, re.IGNORECASE):
            return True

    return False


def _is_big_task(goal: str) -> bool:
    """Detect if a task is big enough to require planning."""
    goal_lower = goal.lower().strip()

    for pattern in BIG_TASK_PATTERNS:
        if re.search(pattern, goal_lower, re.IGNORECASE):
            return True

    # Long instructions are usually complex
    if len(goal_lower.split()) > 20:
        return True

    return False


async def supervisor_node(state: AgentState, config: RunnableConfig) -> Command:
    """Route the task through Plan → Approve → Execute phases."""

    goal = state.get("goal", "")
    phase = state.get("phase", "planning")
    plan_text = state.get("plan_text")
    plan_approved = state.get("plan_approved", False)
    is_finished = state.get("is_finished", False)
    error = state.get("error")
    coder_rounds = state.get("coder_rounds", 0)

    audit_entry = {
        "node": "supervisor",
        "action": "route",
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # ── 1. Task finished → completion ──
    if is_finished or phase == "complete":
        logger.info("Supervisor → completion (task finished)")
        audit_entry["route"] = "completion"
        audit_entry["reason"] = "is_finished"
        return Command(
            goto="completion",
            update={"phase": "complete", "audit_log": [audit_entry]},
        )

    # ── 2. Verification failed → retry coder once ──
    if phase == "verification_failed" and coder_rounds < MAX_CODER_RETRIES:
        logger.info(f"Supervisor → coder (verification failed, retry {coder_rounds + 1})")
        audit_entry["route"] = "coder"
        audit_entry["reason"] = "verification_retry"
        return Command(
            goto="coder",
            update={
                "phase": "executing",
                "coder_rounds": coder_rounds + 1,
                "error": None,  # Clear error so coder doesn't bail
                "audit_log": [audit_entry],
            },
        )

    # ── 3. Error or too many retries → completion ──
    if error or coder_rounds >= MAX_CODER_RETRIES:
        reason = f"error: {error}" if error else f"max retries ({coder_rounds})"
        logger.info(f"Supervisor → completion ({reason})")
        audit_entry["route"] = "completion"
        audit_entry["reason"] = reason
        return Command(
            goto="completion",
            update={"phase": "complete", "audit_log": [audit_entry]},
        )

    # ── 3. Plan exists and is approved → execute with coder ──
    if plan_text and plan_approved:
        logger.info(f"Supervisor → coder (plan approved, executing)")
        audit_entry["route"] = "coder"
        audit_entry["reason"] = "plan_approved"
        return Command(
            goto="coder",
            update={
                "phase": "executing",
                "coder_rounds": coder_rounds + 1,
                "audit_log": [audit_entry],
            },
        )

    # ── 4. Plan exists but NOT approved → return to UI for approval ──
    if plan_text and not plan_approved:
        logger.info("Supervisor → completion (plan awaiting approval, returning to UI)")
        audit_entry["route"] = "completion"
        audit_entry["reason"] = "awaiting_approval"
        return Command(
            goto="completion",
            update={"phase": "awaiting_approval", "audit_log": [audit_entry]},
        )

    # ── 5. No plan yet — decide if we need one ──

    # Simple tasks skip planning → go straight to coder
    if _is_simple_task(goal):
        logger.info(f"Supervisor → coder (simple task, skipping plan)")
        audit_entry["route"] = "coder"
        audit_entry["reason"] = "simple_task"
        return Command(
            goto="coder",
            update={
                "phase": "executing",
                "plan_approved": True,  # Skip approval for simple tasks
                "coder_rounds": coder_rounds + 1,
                "audit_log": [audit_entry],
            },
        )

    # Big tasks → go to planner first
    if _is_big_task(goal):
        logger.info(f"Supervisor → planner (big task: {goal[:80]})")
        audit_entry["route"] = "planner"
        audit_entry["reason"] = "big_task"
        return Command(
            goto="planner",
            update={"phase": "planning", "audit_log": [audit_entry]},
        )

    # Default: medium complexity → go to planner for safety
    logger.info(f"Supervisor → planner (default routing: {goal[:80]})")
    audit_entry["route"] = "planner"
    audit_entry["reason"] = "default"
    return Command(
        goto="planner",
        update={"phase": "planning", "audit_log": [audit_entry]},
    )
