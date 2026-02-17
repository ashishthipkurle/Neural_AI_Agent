"""
Utility Nodes — non-LLM helper nodes for RAG, risk, approval, audit, verification.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from agent.graph.state import AgentState

logger = logging.getLogger("graph.utility")

# ---------------------------------------------------------------------------
# Module-level holders for subsystems (populated at runtime init)
# ---------------------------------------------------------------------------
_vector_store: Any = None
_personal_memory: Any = None
_safety_framework: Any = None
_history_manager: Any = None
_broadcast_fn: Any = None  # WebSocket broadcaster


def register_subsystems(
    vector_store=None,
    personal_memory=None,
    safety_framework=None,
    history_manager=None,
    broadcast_fn=None,
):
    """Called once during LangGraphRuntime init to inject live subsystems."""
    global _vector_store, _personal_memory, _safety_framework
    global _history_manager, _broadcast_fn
    _vector_store = vector_store
    _personal_memory = personal_memory
    _safety_framework = safety_framework
    _history_manager = history_manager
    _broadcast_fn = broadcast_fn


# ===================================================================
# 1. Memory RAG Node
# ===================================================================

async def memory_rag_node(state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Query VectorStore + PersonalMemoryManager for relevant context.

    Injects the result into ``state.memory_context`` so downstream
    nodes (planner, agents) have relevant background.
    """
    goal = state.get("metadata", {}).get("original_input", "")
    if not goal:
        return {}

    context_parts: list[str] = []

    # Vector store RAG
    if _vector_store:
        try:
            results = _vector_store.search(goal, top_k=3)
            if results:
                context_parts.append(
                    "VECTOR MEMORY:\n" + "\n".join(
                        r.get("text", str(r))[:200] for r in results
                    )
                )
        except Exception as exc:
            logger.warning(f"Vector search failed: {exc}")

    # Personal memory
    if _personal_memory:
        try:
            facts = _personal_memory.recall(goal)
            if facts:
                context_parts.append(f"PERSONAL MEMORY:\n{facts[:500]}")
        except Exception as exc:
            logger.warning(f"Personal memory recall failed: {exc}")

    memory_context = "\n\n".join(context_parts) if context_parts else ""
    logger.info(f"RAG injected {len(memory_context)} chars of context")

    return {"memory_context": memory_context}


# ===================================================================
# 2. Risk Assessment Node
# ===================================================================

async def risk_assessment_node(state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate the risk level of the current request.

    Uses the SafetyFramework if available, otherwise defaults to 'low'.
    """
    goal = state.get("metadata", {}).get("original_input", "")

    risk = "low"
    needs_approval = False

    if _safety_framework:
        try:
            assessment = _safety_framework.assess(goal)
            if hasattr(assessment, "risk_level"):
                risk = assessment.risk_level
            elif isinstance(assessment, dict):
                risk = assessment.get("risk_level", "low")
        except Exception as exc:
            logger.warning(f"Safety assessment failed: {exc}")

    # High/critical risk → require human approval
    if risk in ("high", "critical"):
        needs_approval = True

    logger.info(f"Risk assessment: {risk}, needs_approval={needs_approval}")
    return {"risk_level": risk, "needs_approval": needs_approval}


# ===================================================================
# 3. Human Approval Node
# ===================================================================

async def human_approval_node(state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Pause the graph for human-in-the-loop approval.

    Uses LangGraph's ``interrupt()`` to suspend execution.  The runtime
    sends an approval request over WebSocket; when the human responds,
    the graph is resumed with Command(resume=data).
    """
    goal = state.get("metadata", {}).get("original_input", "")
    risk = state.get("risk_level", "high")
    plan = state.get("plan", [])

    # Broadcast approval request to desktop UI
    if _broadcast_fn:
        try:
            _broadcast_fn(
                "approval_request", "system",
                json.dumps({
                    "mission_id": state.get("mission_id", ""),
                    "goal": goal,
                    "risk": risk,
                    "plan": plan,
                }),
            )
        except Exception as exc:
            logger.warning(f"Failed to broadcast approval request: {exc}")

    # Interrupt — graph suspends here until resumed
    approval = interrupt(
        {
            "type": "approval_request",
            "goal": goal,
            "risk": risk,
            "plan": plan,
        }
    )

    # When resumed, 'approval' contains the human's response
    approved = False
    feedback = ""
    if isinstance(approval, dict):
        approved = approval.get("approved", False)
        feedback = approval.get("feedback", "")
    elif isinstance(approval, str):
        approved = approval.lower() in ("yes", "approved", "true")
        feedback = approval

    logger.info(f"Human approval: approved={approved}, feedback={feedback}")

    if not approved:
        return {
            "approval_response": "rejected",
            "error": f"Human rejected: {feedback}",
            "needs_approval": False,
        }

    return {
        "approval_response": "approved",
        "needs_approval": False,
    }


# ===================================================================
# 4. Audit Node
# ===================================================================

async def audit_node(state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Log the completed graph execution to the audit trail.

    Persists the full interaction to HistoryManager + VectorStore.
    """
    goal = state.get("metadata", {}).get("original_input", "")
    results = state.get("tool_results", {})
    plan = state.get("plan", [])

    # Log summary
    summary = (
        f"Mission completed: {goal}\n"
        f"Plan: {json.dumps(plan)}\n"
        f"Results: {json.dumps(results, default=str)[:1000]}"
    )
    logger.info(f"AUDIT: {summary[:200]}")

    # Persist to history
    if _history_manager:
        try:
            _history_manager.add_message(
                role="assistant",
                content=summary,
            )
        except Exception as exc:
            logger.warning(f"History persistence failed: {exc}")

    # Index in vector store for future RAG
    if _vector_store:
        try:
            _vector_store.add(
                text=summary,
                metadata={
                    "type": "mission_audit",
                    "goal": goal,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except Exception as exc:
            logger.warning(f"Vector indexing failed: {exc}")

    return {}


# ===================================================================
# 5. Verification Node
# ===================================================================

async def verification_node(state: AgentState, config: Dict[str, Any]) -> Dict[str, Any]:
    """Check whether the executor's output meets success criteria.

    Simple heuristic: if no error, consider it verified.
    Can be enhanced with LLM-based evaluation later.
    """
    error = state.get("error")
    step_idx = state.get("current_step", 0)
    results = state.get("tool_results", {})

    if error:
        logger.warning(f"Verification failed: {error}")
        return {
            "messages": [AIMessage(content=f"[Verification] Failed: {error}")],
        }

    latest_result = results.get(str(step_idx - 1), "")
    if "error" in str(latest_result).lower():
        return {
            "error": f"Verification detected error in result: {latest_result[:200]}",
            "messages": [AIMessage(content=f"[Verification] Error detected in output")],
        }

    logger.info("Verification passed")
    return {
        "error": None,
        "messages": [AIMessage(content="[Verification] Step verified successfully")],
    }
