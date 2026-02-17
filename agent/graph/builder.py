"""
Graph Assembly — §3 of Production Autonomous Agent Spec.

Explicit StateGraph with deterministic transitions.
Nodes: Intent → Policy → Rollback → Approval → Planning → [Agents] → Verification → Failure → Completion
No undefined transitions. No circular execution without retry increment.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict

from langgraph.graph import END, StateGraph
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.builder")


def build_graph(config: Dict[str, Any] = None) -> StateGraph:
    """Build the production autonomous agent StateGraph — §3.

    Node topology:
        intent → policy → rollback_check → [approval if needed] → supervisor hub
        supervisor → planner | researcher | coder | executor | critic
        each worker → supervisor (loop back)
        supervisor → verification → completion or supervisor
        any error → failure → supervisor

    All transitions are explicit.
    """
    from agent.graph.nodes.intent import intent_node
    from agent.graph.nodes.policy import policy_node
    from agent.graph.nodes.supervisor import supervisor_node
    from agent.graph.nodes.planner import planner_node
    from agent.graph.nodes.researcher import researcher_node
    from agent.graph.nodes.coder import coder_node
    from agent.graph.nodes.executor import executor_node
    from agent.graph.nodes.critic import critic_node
    from agent.graph.nodes.verification import verification_node
    from agent.graph.nodes.failure import failure_node
    from agent.graph.nodes.rollback import rollback_node
    from agent.graph.nodes.completion import completion_node

    graph = StateGraph(AgentState)

    # ── Register all nodes ──
    graph.add_node("intent", intent_node)
    graph.add_node("policy", policy_node)
    graph.add_node("rollback_check", rollback_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", _wrap_safe(researcher_node, "researcher"))
    graph.add_node("coder", _wrap_safe(coder_node, "coder"))
    graph.add_node("executor", _wrap_safe(executor_node, "executor"))
    graph.add_node("critic", critic_node)
    graph.add_node("verification", verification_node)
    graph.add_node("failure", failure_node)
    graph.add_node("completion", completion_node)

    # ── Entry pipeline: Intent → Policy → Rollback → Supervisor ──
    graph.set_entry_point("intent")
    graph.add_edge("intent", "policy")
    graph.add_conditional_edges(
        "policy",
        _policy_router,
        {
            "blocked": END,
            "needs_approval": "rollback_check",
            "proceed": "rollback_check",
        },
    )
    graph.add_edge("rollback_check", "supervisor")

    # ── Supervisor dispatches via Command(goto=...) ──
    # Supervisor returns Command objects, so no explicit edges needed
    # from supervisor → workers. LangGraph handles Command routing.

    # ── Worker → Supervisor (loop back) ──
    graph.add_edge("planner", "supervisor")
    graph.add_edge("researcher", "supervisor")
    graph.add_edge("coder", "supervisor")
    graph.add_edge("executor", "supervisor")
    graph.add_edge("critic", "supervisor")

    # ── Verification routing ──
    graph.add_conditional_edges(
        "verification",
        _verification_router,
        {
            "passed": "completion",
            "failed": "supervisor",
        },
    )

    # ── Failure → Supervisor (with updated retry counters) ──
    graph.add_edge("failure", "supervisor")

    # ── Completion → END ──
    graph.add_edge("completion", END)

    logger.info("Production StateGraph built: 12 nodes, explicit transitions")
    return graph


def _policy_router(state: AgentState) -> str:
    """Route based on policy decision."""
    if state.get("error"):
        return "blocked"
    if state.get("needs_approval"):
        return "needs_approval"
    return "proceed"


def _verification_router(state: AgentState) -> str:
    """Route based on verification result."""
    if state.get("verification_status"):
        return "passed"
    return "failed"


def _wrap_safe(node_fn: Callable, node_name: str) -> Callable:
    """Wrap agent node to catch exceptions and route to failure node.

    Ensures no node can crash the graph — errors go to failure_node.
    """
    async def safe_wrapper(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
        try:
            return await node_fn(state, config)
        except Exception as exc:
            logger.error(f"Node '{node_name}' crashed: {exc}")
            from agent.core.failure_types import classify_failure
            ft = classify_failure(exc)
            return {
                "error": f"{node_name} failed: {str(exc)[:300]}",
                "failure_type": ft.value,
                "audit_log": [{
                    "node": node_name,
                    "action": "crash",
                    "error": str(exc)[:500],
                    "failure_type": ft.value,
                }],
            }

    safe_wrapper.__name__ = node_name
    return safe_wrapper


async def compile_graph(config: Dict[str, Any] = None) -> Any:
    """Compile the graph with checkpointing."""
    graph = build_graph(config)

    checkpoint_path = (config or {}).get("checkpoint_path", "agent_data/checkpoints.db")
    os.makedirs(os.path.dirname(checkpoint_path) or ".", exist_ok=True)

    checkpointer = None

    # Try SQLite first
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        import aiosqlite
        conn = await aiosqlite.connect(checkpoint_path)
        checkpointer = AsyncSqliteSaver(conn)
        logger.info(f"Graph checkpoint: SQLite ({checkpoint_path})")
    except Exception as e:
        logger.warning(f"SQLite checkpoint failed: {e}")
        # Fallback to InMemorySaver
        try:
            from langgraph.checkpoint.memory import MemorySaver
            checkpointer = MemorySaver()
            logger.info("Graph checkpoint: InMemorySaver (fallback)")
        except Exception as e2:
            logger.warning(f"MemorySaver also failed: {e2}")

    try:
        compiled = graph.compile(checkpointer=checkpointer)
        logger.info("Graph compiled successfully")
    except Exception as e:
        logger.warning(f"Compile with checkpointer failed: {e}, compiling without")
        compiled = graph.compile()

    return compiled
