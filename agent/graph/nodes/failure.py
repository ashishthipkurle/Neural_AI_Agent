"""
Failure Classification + Retry Node — §8/§10 of Production Autonomous Agent Spec.

Classifies failures, increments retry counters, selects recovery strategy.
All loops reference retry counters from state. No infinite recursion.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from agent.core.failure_types import (
    FailureType,
    classify_failure,
    get_recovery,
    get_retry_delay,
    should_escalate,
    should_retry,
    should_switch_strategy,
)
from agent.graph.state import AgentState

logger = logging.getLogger("graph.failure")


async def failure_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Classify failure, update retry counters, determine recovery action.

    This node is entered when any agent/tool produces an error.
    It NEVER retries itself — it just updates state and returns to supervisor.
    """
    error = state.get("error", "")
    if not error:
        return {}

    # ── Classify ──
    failure_type = classify_failure(error)
    recovery = get_recovery(failure_type)

    # ── Update retry counters ──
    counters = dict(state.get("retry_counters", {}))
    per_subgoal = dict(counters.get("per_subgoal", {}))
    current_sg = state.get("current_subgoal", "default")

    sg_retries = per_subgoal.get(current_sg, 0)
    global_count = counters.get("global_retry_count", 0)

    # Increment
    per_subgoal[current_sg] = sg_retries + 1
    counters["per_subgoal"] = per_subgoal
    counters["global_retry_count"] = global_count + 1

    # ── Determine action ──
    action = "retry"
    agent_override = None

    if should_escalate(failure_type, counters["global_retry_count"]):
        action = "escalate"
    elif not should_retry(failure_type, sg_retries + 1):
        action = "skip_subgoal"
    elif should_switch_strategy(failure_type, sg_retries + 1):
        action = "switch"
        alternatives = recovery.alternative_agents
        current_agent = state.get("active_agent", "")
        for alt in alternatives:
            if alt != current_agent:
                agent_override = alt
                break
        if not agent_override:
            agent_override = "planner"  # Re-plan as last resort

    delay = get_retry_delay(failure_type, sg_retries)

    # ── Mark subgoal as failed if skipping ──
    plan_graph = state.get("plan_graph", {})
    if action == "skip_subgoal":
        nodes = plan_graph.get("nodes", [])
        for n in nodes:
            if n.get("id") == current_sg:
                n["status"] = "skipped"

    logger.info(
        f"Failure handled: type={failure_type.value}, action={action}, "
        f"retries={sg_retries + 1}, delay={delay:.1f}s"
    )

    return {
        "failure_type": failure_type.value,
        "retry_counters": counters,
        "plan_graph": plan_graph if action == "skip_subgoal" else state.get("plan_graph", {}),
        "failure_history": [{
            "subgoal": current_sg,
            "failure_type": failure_type.value,
            "error": str(error)[:500],
            "attempt": sg_retries + 1,
            "action": action,
            "agent_override": agent_override,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
        "audit_log": [{
            "node": "failure",
            "action": action,
            "failure_type": failure_type.value,
            "retries": sg_retries + 1,
            "global_retries": counters["global_retry_count"],
            "recovery_action": recovery.action,
            "requires_rollback": recovery.requires_rollback,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
        "metadata": {
            **state.get("metadata", {}),
            "last_failure_action": action,
            "last_agent_override": agent_override,
        },
    }
