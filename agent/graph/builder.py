"""
Graph Assembly — Plan → Approve → Execute Pipeline.

4-node graph: supervisor → planner → coder → completion
Supervisor routes based on phase: planning → approval → execution.
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
    """Build the agent StateGraph with Plan → Approve → Execute support.

    Node topology:
        supervisor → planner → supervisor (loop back with plan)
        supervisor → coder → supervisor (loop back after execution)
        supervisor → completion → END
    """
    from agent.graph.nodes.supervisor import supervisor_node
    from agent.graph.nodes.planner import planner_node
    from agent.graph.nodes.coder import coder_node
    from agent.graph.nodes.verifier import verifier_node
    from agent.graph.nodes.completion import completion_node

    graph = StateGraph(AgentState)

    # ── Register nodes ──
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("planner", _wrap_safe(planner_node, "planner"))
    graph.add_node("coder", _wrap_safe(coder_node, "coder"))
    graph.add_node("verifier", _wrap_safe(verifier_node, "verifier"))
    graph.add_node("completion", completion_node)

    # ── Entry → Supervisor ──
    graph.set_entry_point("supervisor")

    # ── Supervisor dispatches via Command(goto=...) ──
    # Supervisor returns Command objects pointing to "planner", "coder", "verifier", or "completion"

    # ── Planner → Supervisor (loop back with plan for approval routing) ──
    graph.add_edge("planner", "supervisor")

    # ── Coder → Verifier (verify changes after coding) ──
    graph.add_edge("coder", "verifier")

    # ── Verifier → Supervisor (routes to completion or back to coder) ──
    graph.add_edge("verifier", "supervisor")

    # ── Completion → END ──
    graph.add_edge("completion", END)

    logger.info("StateGraph built: 5 nodes (supervisor → planner/coder → verifier → completion)")
    return graph


def _wrap_safe(node_fn: Callable, node_name: str) -> Callable:
    """Wrap agent node to catch exceptions gracefully."""
    async def safe_wrapper(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
        try:
            return await node_fn(state, config)
        except Exception as exc:
            logger.error(f"Node '{node_name}' crashed: {exc}")
            from langchain_core.messages import AIMessage
            return {
                "messages": [AIMessage(content=f"Error in {node_name}: {str(exc)[:500]}")],
                "error": f"{node_name} failed: {str(exc)[:300]}",
                "is_finished": True,
                "audit_log": [{
                    "node": node_name,
                    "action": "crash",
                    "error": str(exc)[:500],
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
