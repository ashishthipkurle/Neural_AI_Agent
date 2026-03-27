"""
Completion Node — Final graph node before exit.

Simplified: just returns the coder's output as the final response.
Persists audit trail and updates memory.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.completion")


async def completion_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Final graph node — return coder's output, persist audit, update memory."""
    goal = state.get("goal", "")
    error = state.get("error")

    # Get the last AI message from the coder
    messages = state.get("messages", [])
    last_ai = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and len(msg.content.strip()) > 5:
            last_ai = msg
            break

    if last_ai:
        final_text = last_ai.content.strip()
    elif error:
        final_text = f"I encountered an issue: {error}"
    else:
        final_text = "Task processing complete."

    # Persist audit log
    audit_log = state.get("audit_log", [])
    _persist_audit(audit_log, goal)

    # Update memory
    await _update_memory(state, final_text, config)

    return {
        "messages": [AIMessage(content=final_text)],
        "audit_log": [{
            "node": "completion",
            "action": "complete",
            "response_len": len(final_text),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }


def _persist_audit(audit_log: list, goal: str) -> None:
    """Save audit log to disk."""
    import os
    audit_dir = os.path.join("agent_data", "audit_logs")
    os.makedirs(audit_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(audit_dir, f"audit_{timestamp}.json")

    try:
        with open(filename, "w") as f:
            json.dump({"goal": goal, "log": audit_log}, f, indent=2, default=str)
        logger.info(f"Audit log saved: {filename}")
    except Exception as e:
        logger.warning(f"Failed to save audit log: {e}")


async def _update_memory(state: AgentState, response: str, config: RunnableConfig) -> None:
    """Update memory systems after completion."""
    try:
        configurable = config.get("configurable", {})
        history_manager = configurable.get("history_manager")
        personal_memory = configurable.get("personal_memory")

        if history_manager:
            mission_id = state.get("mission_id", "")
            if mission_id:
                history_manager.add_message(mission_id, "assistant", response)

        if personal_memory:
            goal = state.get("goal", "")
            personal_memory.record_action(
                action_type="completed_task",
                description=f"Completed task: {goal}",
                outcome=response[:500],
            )
    except Exception as e:
        logger.warning(f"Memory update failed: {e}")
