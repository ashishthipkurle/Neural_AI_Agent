"""
AgentState — State Schema with Planning Support.

Supports Plan → Approve → Execute workflow.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional

from langgraph.graph import add_messages


class AgentState(dict):
    """State schema — supports planning + execution phases."""

    __annotations__ = {
        # ── Core ──
        "messages": Annotated[list, add_messages],
        "goal": str,
        "mission_id": str,

        # ── World State ──
        "world_state": Dict[str, Any],

        # ── Planning Phase ──
        "phase": str,  # "planning" | "executing" | "complete"
        "plan_text": Optional[str],  # The implementation plan
        "plan_approved": bool,  # Whether user approved

        # ── Execution Results ──
        "tool_results": Dict[str, Any],
        "error": Optional[str],
        "is_finished": bool,

        # ── Coder State ──
        "todo_list": Annotated[List[Dict[str, Any]], operator.add],
        "allowed_bash_prefixes": List[str],
        "files_read": List[str],
        "coder_rounds": int,
        "original_file_contents": Dict[str, Optional[str]],

        # ── Audit ──
        "audit_log": Annotated[List[Dict[str, Any]], operator.add],

        # ── Metadata ──
        "metadata": Dict[str, Any],
    }


def initial_state(
    goal: str,
    mission_id: str,
    source: str = "local",
    image_data: str | None = None,
) -> Dict[str, Any]:
    """Create a valid initial state with all required fields populated."""
    return {
        "messages": [],
        "goal": goal,
        "mission_id": mission_id,

        "world_state": {
            "environment_state": {},
            "ui_state": {},
            "system_state": {},
            "network_state": {},
            "user_context": {"source": source},
            "memory_context": "",
        },

        # Planning
        "phase": "planning",
        "plan_text": None,
        "plan_approved": False,

        "tool_results": {},
        "error": None,
        "is_finished": False,

        "todo_list": [],
        "allowed_bash_prefixes": [],
        "files_read": [],
        "coder_rounds": 0,
        "original_file_contents": {},

        "audit_log": [],

        "metadata": {
            "original_input": goal,
            "source": source,
            "image_data": image_data,
        },
    }
