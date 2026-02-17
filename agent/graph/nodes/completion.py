"""
Completion + Audit Node — §1/§12 of Production Autonomous Agent Spec.

Final node before graph exit.
1. Generates final response from accumulated results
2. Persists audit trail
3. Updates memory
4. Returns structured completion
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

COMPLETION_PROMPT = """\
You are the completion stage of an autonomous agent.

Given the original objective and the accumulated results,
compose a clear, natural-language summary of what was accomplished.

Be direct. Tell the user what was done, what the outcome is,
and if anything needs their attention.

Do NOT mention internal agent names, graph nodes, or technical internals.
"""


async def completion_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Final graph node — synthesize results, persist audit, return final message."""
    from agent.core.llm_provider import get_llm

    app_config = config.get("configurable", {}).get("app_config", {})

    # ── Build context ──
    goal = state.get("goal", "")
    intent = state.get("intent", {})
    plan = state.get("plan_graph", {})
    results = state.get("tool_results", {})
    error = state.get("error")
    verification = state.get("verification_status", False)
    confidence = state.get("verification_confidence", 0.0)

    # Collect what was done from plan
    done_steps = []
    for node in plan.get("nodes", []):
        if node.get("status") == "done":
            done_steps.append(node.get("task", "unknown step"))

    context = f"""OBJECTIVE: {intent.get('objective', goal)}
COMPLETED STEPS: {json.dumps(done_steps, default=str)}
RESULTS: {json.dumps(results, default=str)[:800]}
VERIFICATION: {'passed' if verification else 'not verified'} (confidence: {confidence:.2f})
ERROR: {error or 'none'}
"""

    # Check if this is a simple chat (no plan was needed)
    if not plan.get("nodes"):
        # No plan = simple conversational query, use last message
        messages = state.get("messages", [])
        if messages:
            last_ai = [m for m in messages if isinstance(m, AIMessage)]
            if last_ai:
                return {
                    "messages": [last_ai[-1]],
                    "verification_status": True,
                    "audit_log": [{
                        "node": "completion",
                        "action": "passthrough",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }],
                }

    # ── Synthesize response ──
    try:
        llm = get_llm(app_config, temperature=0.3)
        messages = [
            SystemMessage(content=COMPLETION_PROMPT),
            HumanMessage(content=context),
        ]
        response = await llm.ainvoke(messages)
        final_text = response.content.strip()
    except Exception as exc:
        logger.warning(f"Completion synthesis failed: {exc}")
        if done_steps:
            final_text = f"I completed the following: {', '.join(done_steps)}"
        elif error:
            final_text = f"I encountered an issue: {error}"
        else:
            final_text = "Task processing complete."

    # ── Persist audit ──
    audit_log = state.get("audit_log", [])
    _persist_audit(audit_log, goal)

    # ── Persist to memory ──
    await _update_memory(state, final_text, config)

    return {
        "messages": [AIMessage(content=final_text)],
        "verification_status": True,
        "audit_log": [{
            "node": "completion",
            "action": "complete",
            "response_len": len(final_text),
            "steps_done": len(done_steps),
            "verified": verification,
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
            # Store completed task in long-term memory using record_action
            personal_memory.record_action(
                action_type="completed_task",
                description=f"Completed task: {goal}",
                outcome=response[:500],
            )
    except Exception as e:
        logger.warning(f"Memory update failed: {e}")
