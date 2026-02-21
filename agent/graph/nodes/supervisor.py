"""
SupervisorController — §2 + §11 of Production Autonomous Agent Spec.

Real class. Real methods. Not a prompt wrapper.
Operates as root node of LangGraph. Enforces bounded execution.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from agent.core.failure_types import (
    FailureType,
    classify_failure,
    get_recovery,
    should_escalate,
    should_retry,
    should_switch_strategy,
)
from agent.graph.state import AgentState

logger = logging.getLogger("graph.supervisor")

# Agent capabilities — used by LLM to select next worker
AGENT_CAPABILITIES = {
    "planner": "Breaks goals into ordered task graphs. Use when no plan exists or re-planning needed.",
    "researcher": "Gathers information via web search, memory, browsing. Use for information gathering.",
    "coder": "Writes, edits, executes code. Manages files. Use for programming tasks.",
    "executor": "Controls desktop, launches apps, types, clicks, speaks, sends Telegram. Use for real-world actions.",
    "critic": "Reviews work quality, flags issues. Use after execution to verify work.",
}

SUPERVISOR_SYSTEM_PROMPT = """\
You are the Supervisor Controller of a team of autonomous agents.

AVAILABLE AGENTS:
{agent_list}

RULES:
1. Study the current state carefully.
2. If there is no plan yet, select "planner".
3. If all subgoals are complete, select "FINISH".
4. If the last action failed and retries remain, select the same or alternative agent.
5. If retries are exhausted, select "ESCALATE".
6. Pick a SINGLE agent. Respond with ONE JSON object:
   {{"next": "<agent_name | FINISH | ESCALATE>", "reason": "<one line>"}}

Do NOT wrap in markdown.
"""


class SupervisorController:
    """Production supervisor with real methods — §2.

    All decisions go through deterministic logic first.
    LLM is only consulted when deterministic rules don't apply.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    # ── §2: decompose_goal ──
    def decompose_goal(self, state: AgentState) -> Dict[str, Any]:
        """Check if goal needs decomposition into task graph."""
        plan = state.get("plan_graph", {})
        nodes = plan.get("nodes", [])

        if not nodes:
            # No plan exists — must go to planner
            return {"next": "planner", "reason": "no plan exists"}

        return {"next": None, "reason": "plan exists"}

    # ── §2: _infer_worker_agent ──
    def _infer_worker_agent(self, subgoal: Dict[str, Any]) -> str:
        """Infer the correct worker agent from subgoal tools/task text.
        
        Used when the LLM incorrectly assigns 'planner' to an action subgoal.
        """
        tools = subgoal.get("tools", [])
        task = subgoal.get("task", "").lower()
        
        # Check tool-based hints
        tool_str = " ".join(tools).lower()
        if any(t in tool_str for t in ["research", "browser", "memory_tool", "search"]):
            return "researcher"
        if any(t in tool_str for t in ["coding", "code", "file_ops"]):
            return "coder"
        
        # Check task text hints
        if any(kw in task for kw in ["research", "search", "find", "look up", "retrieve", "gather"]):
            return "researcher"
        if any(kw in task for kw in ["write code", "edit code", "generate code", "script", "program"]):
            return "coder"
        if any(kw in task for kw in ["review", "verify", "validate", "check", "critic"]):
            return "critic"
        
        # Default to executor for real-world actions
        return "executor"

    # ── §2: select_next_subgoal ──
    def select_next_subgoal(self, state: AgentState) -> Optional[Dict[str, Any]]:
        """Select the next incomplete subgoal from the plan graph."""
        plan = state.get("plan_graph", {})
        nodes = plan.get("nodes", [])
        counters = state.get("retry_counters", {})
        limits = state.get("retry_limits", {})
        per_sg = counters.get("per_subgoal", {})
        per_max = limits.get("per_subgoal_max", 3)

        for node in nodes:
            if node.get("status") not in ("done", "skipped"):
                # Skip subgoals that have exhausted their retries
                node_id = node.get("id", "")
                if per_sg.get(node_id, 0) >= per_max:
                    logger.info(f"Skipping exhausted subgoal: {node_id} ({per_sg[node_id]}/{per_max})")
                    node["status"] = "skipped"
                    continue

                # Check dependencies are met
                deps = node.get("depends_on", [])
                all_deps_done = all(
                    any(n.get("id") == dep and n.get("status") in ("done", "skipped") for n in nodes)
                    for dep in deps
                )
                if all_deps_done:
                    return node

        return None  # All done

    # ── §8: enforce_retry_bounds ──
    def enforce_retry_bounds(self, state: AgentState) -> Dict[str, Any]:
        """Check retry limits. Returns action to take."""
        counters = state.get("retry_counters", {})
        limits = state.get("retry_limits", {})
        global_count = counters.get("global_retry_count", 0)
        global_max = limits.get("global_max", 25)

        # Global limit check
        if global_count >= global_max:
            return {
                "action": "terminate",
                "reason": f"Global retry limit reached ({global_count}/{global_max})",
            }

        # Per-subgoal limit check
        current = state.get("current_subgoal", "")
        per_subgoal = counters.get("per_subgoal", {})
        subgoal_retries = per_subgoal.get(current, 0)
        per_max = limits.get("per_subgoal_max", 3)

        if subgoal_retries >= per_max:
            return {
                "action": "switch_strategy",
                "reason": f"Subgoal '{current}' exhausted retries ({subgoal_retries}/{per_max})",
            }

        return {"action": "continue", "reason": "within limits"}

    # ── §10: classify_failure ──
    def classify_failure_from_state(self, state: AgentState) -> Optional[FailureType]:
        """Extract and classify the current failure from state."""
        error = state.get("error")
        if not error:
            return None
        # Critic review errors are quality feedback about task content,
        # NOT actual system failures. Skip classification to prevent
        # task-content keywords (e.g. "corrupt", "invalid") from
        # triggering false STATE_CORRUPTION escalation.
        if str(error).startswith("Critic flagged"):
            return None
        return classify_failure(error)

    # ── §2: switch_strategy ──
    def switch_strategy(self, state: AgentState, failure_type: FailureType) -> str:
        """Pick an alternative agent when current one fails."""
        recovery = get_recovery(failure_type)
        alternatives = recovery.alternative_agents
        current = state.get("active_agent", "")

        for alt in alternatives:
            if alt != current and alt in AGENT_CAPABILITIES:
                return alt

        # Default: re-plan
        return "planner"

    # ── §10: verify_goal_completion ──
    def verify_goal_completion(self, state: AgentState) -> bool:
        """Check if the goal is fully achieved."""
        plan = state.get("plan_graph", {})
        nodes = plan.get("nodes", [])

        if not nodes:
            return False

        return all(n.get("status") in ("done", "skipped") for n in nodes)

    # ── §11: terminate_or_continue ──
    def terminate_or_continue(self, state: AgentState) -> Dict[str, Any]:
        """Master decision: continue, escalate, or terminate."""
        # 1. Check if goal is complete
        if self.verify_goal_completion(state):
            return {"action": "finish", "reason": "all subgoals complete"}

        # 2. Check retry bounds
        bounds = self.enforce_retry_bounds(state)
        if bounds["action"] == "terminate":
            return {"action": "finish", "reason": bounds["reason"]}

        # 3. Check if there's a failure needing handling
        failure = self.classify_failure_from_state(state)
        if failure:
            counters = state.get("retry_counters", {})
            global_count = counters.get("global_retry_count", 0)

            if should_escalate(failure, global_count):
                return {"action": "escalate", "reason": f"Escalating {failure.value}"}

            if bounds["action"] == "switch_strategy":
                alt = self.switch_strategy(state, failure)
                return {"action": "dispatch", "agent": alt, "reason": f"Strategy switch → {alt}"}

            if should_retry(failure, counters.get("per_subgoal", {}).get(state.get("current_subgoal", ""), 0)):
                return {"action": "retry", "reason": f"Retrying after {failure.value}"}

        # 4. No failure — select next subgoal
        decomp = self.decompose_goal(state)
        if decomp["next"]:
            return {"action": "dispatch", "agent": decomp["next"], "reason": decomp["reason"]}

        next_sg = self.select_next_subgoal(state)
        if next_sg:
            agent = next_sg.get("agent", "executor")
            # Prevent no-op loop: if subgoal is assigned to planner but plan
            # already exists, remap to the appropriate worker agent.
            if agent == "planner":
                agent = self._infer_worker_agent(next_sg)
                logger.info(f"Remapped subgoal agent from 'planner' → '{agent}'")
            return {
                "action": "dispatch",
                "agent": agent,
                "reason": f"Next subgoal: {next_sg.get('task', '')}",
                "subgoal_id": next_sg.get("id", ""),
            }

        return {"action": "finish", "reason": "no more subgoals"}


async def supervisor_node(state: AgentState, config: RunnableConfig) -> Command:
    """LangGraph node wrapper around SupervisorController.

    Decision flow:
    1. Deterministic rules first (retry bounds, completion check, failure handling)
    2. LLM only if deterministic rules don't produce a clear decision
    """
    app_config = config.get("configurable", {}).get("app_config", {})
    controller = SupervisorController(app_config)

    # ── Deterministic decision ──
    decision = controller.terminate_or_continue(state)
    action = decision["action"]
    reason = decision["reason"]

    # Build audit entry
    audit_entry = {
        "node": "supervisor",
        "action": action,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "retry_counters": state.get("retry_counters", {}),
    }

    if action == "finish":
        logger.info(f"Supervisor → FINISH ({reason})")
        return Command(
            goto="completion",
            update={
                "active_agent": "completion",
                "audit_log": [audit_entry],
            },
        )

    if action == "escalate":
        logger.info(f"Supervisor → ESCALATE ({reason})")
        return Command(
            goto="__end__",
            update={
                "active_agent": "escalated",
                "error": f"Escalated: {reason}",
                "audit_log": [audit_entry],
            },
        )

    if action in ("dispatch", "retry"):
        agent = decision.get("agent", "")

        if agent and agent in AGENT_CAPABILITIES:
            # Increment retry counter
            counters = dict(state.get("retry_counters", {}))
            counters["global_retry_count"] = counters.get("global_retry_count", 0) + 1
            
            # Set current_subgoal to the node ID so workers can mark it done
            subgoal_id = decision.get("subgoal_id", state.get("current_subgoal", "default"))
            
            per_sg = dict(counters.get("per_subgoal", {}))
            per_sg[subgoal_id] = per_sg.get(subgoal_id, 0) + 1
            counters["per_subgoal"] = per_sg

            logger.info(f"Supervisor → {agent} ({reason})")
            return Command(
                goto=agent,
                update={
                    "active_agent": agent,
                    "current_subgoal": subgoal_id,
                    "error": None,  # Clear error on dispatch
                    "retry_counters": counters,
                    "audit_log": [audit_entry],
                },
            )

    # ── Fallback: LLM-based decision (only if deterministic rules didn't resolve) ──
    logger.info("⏳ Supervisor: Deterministic rules inconclusive, consulting LLM...")
    from agent.core.llm_provider import get_llm

    llm = get_llm(app_config, temperature=0.0)

    agent_list = "\n".join(f"- {name}: {desc}" for name, desc in AGENT_CAPABILITIES.items())
    context = _build_context(state)

    messages = [
        SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT.format(agent_list=agent_list)),
        HumanMessage(content=context),
    ]

    response = await llm.ainvoke(messages)
    text = response.content.strip()
    logger.info(f"✓ Supervisor: LLM decision received")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        if "FINISH" in text.upper():
            parsed = {"next": "FINISH", "reason": "LLM says done"}
        else:
            parsed = {"next": "planner", "reason": "LLM fallback"}

    next_agent = parsed.get("next", "FINISH")
    llm_reason = parsed.get("reason", "")

    audit_entry["llm_decision"] = parsed

    if next_agent.upper() in ("FINISH", "ESCALATE"):
        return Command(
            goto="completion",
            update={"active_agent": "completion", "audit_log": [audit_entry]},
        )

    if next_agent in AGENT_CAPABILITIES:
        counters = dict(state.get("retry_counters", {}))
        counters["global_retry_count"] = counters.get("global_retry_count", 0) + 1
        return Command(
            goto=next_agent,
            update={
                "active_agent": next_agent,
                "retry_counters": counters,
                "audit_log": [audit_entry],
            },
        )

    # Absolute fallback
    return Command(goto="planner", update={"active_agent": "planner", "audit_log": [audit_entry]})


def _build_context(state: AgentState) -> str:
    """Summarise state for LLM consumption."""
    parts = [f"GOAL: {state.get('goal', 'unknown')}"]

    plan = state.get("plan_graph", {})
    nodes = plan.get("nodes", [])
    if nodes:
        parts.append(f"PLAN ({len(nodes)} subgoals):")
        for n in nodes:
            status = n.get("status", "pending")
            parts.append(f"  [{status}] {n.get('task', '?')} → agent={n.get('agent', '?')}")

    counters = state.get("retry_counters", {})
    parts.append(f"RETRIES: global={counters.get('global_retry_count', 0)}, per_subgoal={counters.get('per_subgoal', {})}")

    error = state.get("error")
    if error:
        parts.append(f"LAST ERROR: {error}")

    results = state.get("tool_results", {})
    if results:
        parts.append(f"RESULTS: {json.dumps(results, default=str)[:500]}")

    return "\n".join(parts)
