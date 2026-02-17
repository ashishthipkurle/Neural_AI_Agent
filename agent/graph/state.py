"""
AgentState — §4 Production State Schema.

Strict structure. Immutable except through controlled node updates.
All fields typed. Retry counters, world state, plan graph all graph-level enforced.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional

from langgraph.graph import add_messages


class AgentState(dict):
    """Production-grade state schema — §4.

    Every field is explicitly declared. State is only mutated by
    node return values merged by LangGraph's reducer system.
    """

    __annotations__ = {
        # ── Core ──
        "messages": Annotated[list, add_messages],
        "goal": str,
        "mission_id": str,

        # ── Intent Decomposition (§2) ──
        "intent": Dict[str, Any],
        # Structure: {objective, constraints, assumptions, required_resources,
        #             risk_level, success_criteria}

        # ── World State (§2) ──
        "world_state": Dict[str, Any],
        # Structure: {environment_state, ui_state, system_state,
        #             network_state, user_context, memory_context}

        # ── Planning (§3) ──
        "plan_graph": Dict[str, Any],
        # Structure: {nodes: [{id, task, agent, tools, risk, status, depends_on}],
        #             edges: [[from, to]]}
        "current_subgoal": str,
        "current_subgoal_index": int,

        # ── Retry System (§8) ──
        "retry_counters": Dict[str, Any],
        # Structure: {per_subgoal: {subgoal_id: int}, global_retry_count: int}
        "retry_limits": Dict[str, Any],
        # Structure: {per_subgoal_max: int, global_max: int, strategy_switch_at: int}

        # ── Failure System (§10) ──
        "failure_type": Optional[str],
        "failure_history": Annotated[List[Dict[str, Any]], operator.add],
        # Each: {subgoal, failure_type, error, timestamp, attempt}

        # ── Rollback (§9) ──
        "rollback_snapshot_id": Optional[str],

        # ── Memory References (§5) ──
        "memory_refs": Dict[str, Any],
        # Structure: {stm_id, ltm_id, kg_id}

        # ── Verification (§10) ──
        "verification_status": bool,
        "verification_confidence": float,

        # ── Execution Results ──
        "tool_results": Dict[str, Any],
        "active_agent": str,

        # ── Approval (§12) ──
        "needs_approval": bool,
        "approval_response": Optional[str],

        # ── Audit (§1) ──
        "audit_log": Annotated[List[Dict[str, Any]], operator.add],

        # ── Metadata ──
        "metadata": Dict[str, Any],
        "error": Optional[str],
    }


def initial_state(
    goal: str,
    mission_id: str,
    source: str = "local",
    image_data: str | None = None,
) -> Dict[str, Any]:
    """Create a valid initial state with all required fields populated.

    This is the ONLY way to create state — prevents missing-field errors.
    """
    return {
        "messages": [],
        "goal": goal,
        "mission_id": mission_id,

        "intent": {},
        "world_state": {
            "environment_state": {},
            "ui_state": {},
            "system_state": {},
            "network_state": {},
            "user_context": {"source": source},
            "memory_context": "",
        },

        "plan_graph": {"nodes": [], "edges": []},
        "current_subgoal": "",
        "current_subgoal_index": 0,

        "retry_counters": {"per_subgoal": {}, "global_retry_count": 0},
        "retry_limits": {
            "per_subgoal_max": 3,
            "global_max": 25,
            "strategy_switch_at": 2,
        },

        "failure_type": None,
        "failure_history": [],

        "rollback_snapshot_id": None,

        "memory_refs": {"stm_id": None, "ltm_id": None, "kg_id": None},

        "verification_status": False,
        "verification_confidence": 0.0,

        "tool_results": {},
        "active_agent": "",

        "needs_approval": False,
        "approval_response": None,

        "audit_log": [],

        "metadata": {
            "original_input": goal,
            "source": source,
            "image_data": image_data,
        },
        "error": None,
    }
