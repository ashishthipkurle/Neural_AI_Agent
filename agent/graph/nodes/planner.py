"""
Structured Task Graph Planner — §2/§3 of Production Autonomous Agent Spec.

Builds a real task DAG: nodes = subgoals, edges = dependencies.
Each node annotated with required_tools, risk_score, validation_method.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.planner")

PLANNER_PROMPT = """\
You are a Task Graph Planner for an autonomous agent system.

Given an objective and structured intent, decompose it into
an ordered list of subgoals that form a task DAG (directed acyclic graph).

Available agents: planner, researcher, coder, executor, critic

For each subgoal, provide:
- id: unique string (e.g. "step_1")
- task: what to do (one clear sentence)
- agent: which agent should execute this
- tools: list of tool names needed
- risk: "low", "medium", "high"
- validation: how to verify this step is done
- depends_on: list of subgoal IDs this depends on (empty for first steps)

Respond with ONLY a JSON object:
{
  "nodes": [
    {"id": "step_1", "task": "...", "agent": "researcher", "tools": ["research_tool"], "risk": "low", "validation": "...", "depends_on": [], "status": "pending"},
    {"id": "step_2", "task": "...", "agent": "coder", "tools": ["coding_tool"], "risk": "medium", "validation": "...", "depends_on": ["step_1"], "status": "pending"}
  ],
  "edges": [["step_1", "step_2"]]
}

RULES:
1. NO circular dependencies.
2. Every step must be actionable by ONE agent.
3. Last step should always be verification/review by critic.
4. Maximum 8 steps.
5. No markdown wrapper. Only JSON.
"""


async def planner_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Build structured task graph — §2/§3."""
    from agent.core.llm_provider import get_llm

    plan = state.get("plan_graph", {})
    nodes = plan.get("nodes", [])

    # Skip if plan exists and hasn't been invalidated
    if nodes and not state.get("error"):
        # Just advance to next subgoal
        next_sg = _find_next_subgoal(nodes)
        if next_sg:
            return {
                "current_subgoal": next_sg["id"],
                "audit_log": [{
                    "node": "planner",
                    "action": "advance",
                    "subgoal": next_sg["id"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            }
        return {}

    app_config = config.get("configurable", {}).get("app_config", {})
    llm = get_llm(app_config, temperature=0.2)

    intent = state.get("intent", {})
    goal = state.get("goal", "")

    user_content = f"OBJECTIVE: {intent.get('objective', goal)}\n"
    if intent.get("constraints"):
        user_content += f"CONSTRAINTS: {json.dumps(intent['constraints'])}\n"
    if intent.get("assumptions"):
        user_content += f"ASSUMPTIONS: {json.dumps(intent['assumptions'])}\n"
    if intent.get("required_resources"):
        user_content += f"RESOURCES: {json.dumps(intent['required_resources'])}\n"
    if intent.get("success_criteria"):
        user_content += f"SUCCESS CRITERIA: {intent['success_criteria']}\n"

    # If there was a previous failure, provide context for re-planning
    if state.get("error"):
        user_content += f"\nPREVIOUS ATTEMPT FAILED: {state['error']}\n"
        user_content += "Adjust the plan to avoid this failure.\n"

    messages = [
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=user_content),
    ]

    logger.info("⏳ Planner: Sending task decomposition to LLM...")

    try:
        response = await llm.ainvoke(messages)
        text = response.content.strip()
        logger.info(f"✓ Planner: LLM response received ({len(text)} chars)")

        plan_data = json.loads(text)
        if not isinstance(plan_data, dict) or "nodes" not in plan_data:
            raise ValueError("Invalid plan structure")

        # Validate: no circular deps
        _validate_dag(plan_data)

        # Mark all nodes as pending
        for node in plan_data.get("nodes", []):
            node.setdefault("status", "pending")

    except Exception as exc:
        logger.warning(f"Plan generation failed: {exc}")
        # Fallback: single-step plan
        plan_data = {
            "nodes": [
                {
                    "id": "step_1",
                    "task": intent.get("objective", goal),
                    "agent": "executor",
                    "tools": [],
                    "risk": "medium",
                    "validation": "check result",
                    "depends_on": [],
                    "status": "pending",
                },
                {
                    "id": "step_2",
                    "task": "Review and verify the result",
                    "agent": "critic",
                    "tools": [],
                    "risk": "low",
                    "validation": "critic approved",
                    "depends_on": ["step_1"],
                    "status": "pending",
                },
            ],
            "edges": [["step_1", "step_2"]],
        }

    first_subgoal = plan_data["nodes"][0]["id"] if plan_data["nodes"] else ""

    logger.info(f"Plan created: {len(plan_data['nodes'])} subgoals")

    return {
        "plan_graph": plan_data,
        "current_subgoal": first_subgoal,
        "current_subgoal_index": 0,
        "messages": [AIMessage(content=f"Plan created with {len(plan_data['nodes'])} steps.")],
        "audit_log": [{
            "node": "planner",
            "action": "create_plan",
            "subgoals": len(plan_data["nodes"]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }


def _find_next_subgoal(nodes: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """Find next pending subgoal with all dependencies met."""
    for node in nodes:
        if node.get("status") not in ("done", "skipped"):
            deps = node.get("depends_on", [])
            all_done = all(
                any(n.get("id") == d and n.get("status") in ("done", "skipped") for n in nodes)
                for d in deps
            )
            if all_done:
                return node
    return None


def _validate_dag(plan: Dict[str, Any]) -> None:
    """Validate that plan has no circular dependencies."""
    nodes = {n["id"] for n in plan.get("nodes", [])}
    edges = plan.get("edges", [])

    # Simple cycle detection via DFS
    adj: Dict[str, List[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        adj.setdefault(src, []).append(dst)

    visited = set()
    stack = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor in stack:
                raise ValueError(f"Circular dependency detected: {node} → {neighbor}")
            if neighbor not in visited:
                dfs(neighbor)
        stack.discard(node)

    for n in nodes:
        if n not in visited:
            dfs(n)
