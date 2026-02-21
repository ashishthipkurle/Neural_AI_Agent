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
import re
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.completion")

COMPLETION_PROMPT = """\
You are the completion stage of an autonomous agent.

Given the original objective, the worker reports, and the accumulated results,
compose a clear summary of what was accomplished.

RULES:
1. Base your answer on WORKER REPORTS and KEY RESULTS — these contain the actual outcomes.
2. Include specific data values, version numbers, file paths, and status results.
3. If a worker report says something was done, report it as done.
4. Be direct. Tell the user what was done and the outcome.
5. Do NOT contradict the worker reports.
6. Do NOT mention internal agent names, graph nodes, or technical internals.
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

    # Detect request source and whether this looks like a "deliverable" task.
    try:
        source = (
            (state.get("metadata", {}) or {}).get("source")
            or (state.get("world_state", {}) or {}).get("user_context", {}).get("source")
            or "local"
        )
    except Exception:
        source = "local"

    objective_text = str(intent.get("objective") or goal or "")
    objective_lc = objective_text.lower()
    is_summary_deliverable = any(k in objective_lc for k in (
        "write a summary",
        "summarize",
        "summary",
        "write-up",
        "report",
        "draft",
    ))

    def _select_deliverable_from_messages() -> str | None:
        all_messages = state.get("messages", [])
        candidates = []
        for msg in all_messages:
            if not isinstance(msg, AIMessage) or not msg.content:
                continue
            text = msg.content.strip()
            if len(text) < 120:
                continue
            # Skip meta/status chatter
            if text.lower().startswith("plan created"):
                continue
            if "accomplishment summary" in text.lower():
                continue
            # Skip tool JSON-ish payloads
            if text.startswith("{") and "\n" in text and ":" in text[:80]:
                continue

            score = 0
            # Prefer framework-style summaries for the common research prompt
            for kw in ("pytorch", "tensorflow", "jax"):
                if kw in text.lower():
                    score += 2
            # Prefer structured, user-facing formatting
            if "**" in text or "##" in text:
                score += 1
            if "- " in text or "\n•" in text:
                score += 1

            # Penalize internal phrasing
            if "graph" in text.lower() or "subgoal" in text.lower() or "tool" in text.lower():
                score -= 2

            candidates.append((score, len(text), text))

        if not candidates:
            return None

        # Highest score wins; if tie, prefer longer (more complete) but cap size.
        candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
        best = candidates[0][2]
        return best[:6000]

    # Collect what was done from plan
    done_steps = []
    for node in plan.get("nodes", []):
        if node.get("status") == "done":
            done_steps.append(node.get("task", "unknown step"))

    # Extract worker summaries from messages (each worker adds an AIMessage)
    all_messages = state.get("messages", [])
    worker_summaries = []
    for msg in all_messages:
        if isinstance(msg, AIMessage) and msg.content:
            text = msg.content.strip()
            # Skip very short or review-only messages
            if len(text) > 20 and not text.startswith("Review:"):
                worker_summaries.append(text[:300])

    # Keep only the most recent worker summaries (last 8)
    worker_summaries = worker_summaries[-8:]

    # Filter tool_results: prioritize actual work over file listings
    filtered_results = {}
    for key, val in results.items():
        val_str = str(val)
        # Skip raw directory listings and search-miss noise
        if any(skip in val_str for skip in ("No files matching", ".gitignore", ".pytest_cache")):
            continue
        filtered_results[key] = val_str[:200]

    context = f"""OBJECTIVE: {intent.get('objective', goal)}

COMPLETED STEPS ({len(done_steps)} total):
{chr(10).join(f'- {s}' for s in done_steps)}

WORKER REPORTS:
{chr(10).join(f'--- Worker Report ---{chr(10)}{s}' for s in worker_summaries) if worker_summaries else '(none)'}

KEY RESULTS:
{json.dumps(filtered_results, default=str)[:2000]}

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

    # If the user asked for a deliverable (summary/report), prefer returning the actual deliverable
    # rather than a "what I did" accomplishment log — especially for Telegram.
    if is_summary_deliverable and source in ("telegram", "local"):
        deliverable = _select_deliverable_from_messages()
        if deliverable:
            audit_log = state.get("audit_log", [])
            _persist_audit(audit_log, goal)
            await _update_memory(state, deliverable, config)
            return {
                "messages": [AIMessage(content=deliverable)],
                "verification_status": True,
                "audit_log": [{
                    "node": "completion",
                    "action": "deliverable_passthrough",
                    "response_len": len(deliverable),
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
