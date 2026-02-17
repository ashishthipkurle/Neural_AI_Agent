"""
LangGraph Runtime — Production Autonomous Agent.

Unified entry point. Replaces NeuralAgent.process_input().
Wires all subsystems, creates graph, manages execution lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage

from agent.graph.state import AgentState, initial_state

logger = logging.getLogger("graph.runtime")


class LangGraphRuntime:
    """Production runtime for the autonomous agent graph.

    Lifecycle:
    1. __init__: Wire subsystems, compile graph
    2. process(): Execute full graph for a user input
    3. resume(): Resume a paused graph (human-in-the-loop)
    4. stream(): Stream execution events
    5. get_state(): Inspect current graph state
    """

    def __init__(
        self,
        app_config: Dict[str, Any],
        skill_router=None,
        tool_router=None,
        personal_memory=None,
        safety_framework=None,
        history_manager=None,
        broadcast_fn: Optional[Callable] = None,
        checkpoint_path: str = "agent_data/checkpoints.db",
    ):
        self.app_config = app_config
        self.skill_router = skill_router
        self.tool_router = tool_router
        self.personal_memory = personal_memory
        self.safety_framework = safety_framework
        self.history_manager = history_manager
        self.broadcast_fn = broadcast_fn
        self.checkpoint_path = checkpoint_path

        self._graph = None
        self._initialized = False

        # Initialize memory systems
        self._init_memory()
        # Register tools
        self._register_tools()

    def _init_memory(self):
        """Initialize physically separated memory systems — §5."""
        try:
            from agent.memory.stm import ShortTermWorkingMemory
            from agent.memory.ltm import VersionedLTM
            from agent.memory.knowledge_graph import KnowledgeGraph
            from agent.memory.memory_gate import MemoryGate

            self.stm = ShortTermWorkingMemory()
            self.ltm = VersionedLTM()
            self.kg = KnowledgeGraph()
            self.memory_gate = MemoryGate(self.stm, self.ltm, self.kg)
            logger.info("✓ Memory systems initialized (STM/LTM/KG)")
        except Exception as e:
            logger.warning(f"Memory init partial: {e}")
            self.stm = None
            self.ltm = None
            self.kg = None
            self.memory_gate = None

    def _register_tools(self):
        """Register existing skills as graph tools."""
        try:
            from agent.graph.tools import register_skills
            register_skills(self.skill_router, self.tool_router)
            logger.info("✓ Tools registered for graph")
        except Exception as e:
            logger.warning(f"Tool registration partial: {e}")

    async def _ensure_graph(self):
        """Lazy-compile the graph on first use."""
        if self._graph is None:
            from agent.graph.builder import compile_graph
            self._graph = await compile_graph({
                "checkpoint_path": self.checkpoint_path,
            })
            self._initialized = True
            logger.info("✓ Graph compiled and ready")

    def _make_config(self, thread_id: str) -> Dict[str, Any]:
        """Build per-invocation config with all subsystem refs."""
        return {
            "configurable": {
                "thread_id": thread_id,
                "app_config": self.app_config,
                "personal_memory": self.personal_memory,
                "history_manager": self.history_manager,
                "safety_framework": self.safety_framework,
                "memory_gate": self.memory_gate,
                "broadcast_fn": self.broadcast_fn,
            }
        }

    async def process(
        self,
        user_input: str,
        image_data: str = None,
        source: str = "local",
        thread_id: str = None,
    ) -> str:
        """Execute the full graph for a user input.

        Returns the final response text.
        """
        await self._ensure_graph()

        if not thread_id:
            thread_id = str(uuid.uuid4())

        # Build initial state
        state = initial_state(
            goal=user_input,
            mission_id=thread_id,
            source=source,
            image_data=image_data,
        )

        # Add user message
        state["messages"] = [HumanMessage(content=user_input)]

        # Inject memory context
        if self.stm:
            self.stm.add_message("user", user_input)
            state["world_state"]["memory_context"] = self.stm.get_context_window()

        if self.memory_gate:
            state["memory_refs"] = self.memory_gate.get_memory_refs()

        config = self._make_config(thread_id)

        logger.info(f"Graph processing: {user_input[:80]}...")

        # Human-friendly node labels for UI
        NODE_LABELS = {
            "intent": "Analyzing intent...",
            "policy": "Checking safety policy...",
            "rollback_check": "Preparing rollback checkpoint...",
            "supervisor": "Supervisor routing task...",
            "planner": "Building task plan (LLM)...",
            "researcher": "Researching information (LLM)...",
            "coder": "Writing code (LLM)...",
            "executor": "Executing tools...",
            "critic": "Reviewing results (LLM)...",
            "verification": "Verifying output...",
            "failure": "Handling failure...",
            "completion": "Completing task...",
        }

        try:
            # Execute graph with streaming to emit progress
            final_state = None
            async for event in self._graph.astream(state, config):
                # event is a dict like {"node_name": {state_updates}}
                if isinstance(event, dict):
                    for node_name, node_output in event.items():
                        label = NODE_LABELS.get(node_name, f"Running: {node_name}")
                        logger.info(f"🟢 Graph node completed: {node_name}")
                        # broadcast_fn is sync_broadcast(event_type, role, text, task_id)
                        if self.broadcast_fn:
                            try:
                                self.broadcast_fn("step", "system", f"✓ {label}", None)
                            except Exception:
                                pass
                        # Keep accumulating last state
                        if isinstance(node_output, dict):
                            final_state = node_output

            # If stream didn't give us a final state, fall back
            if final_state is None:
                final_state = state

            # Extract response
            response = self._extract_response(final_state)

            # Post-processing: update memory
            if self.stm:
                self.stm.add_message("assistant", response)

            # Promote important observations to LTM
            if self.memory_gate:
                audit = final_state.get("audit_log", [])
                if len(audit) > 3:  # Non-trivial task
                    self.memory_gate.promote_stm_to_ltm(
                        key=f"task_{thread_id}",
                        category="completed_tasks",
                    )

            logger.info(f"Graph completed: {len(response)} chars")
            return response

        except Exception as exc:
            logger.error(f"Graph execution failed: {exc}")
            return f"I encountered an error processing your request: {exc}"

    async def resume(
        self,
        thread_id: str,
        approval_data: Dict[str, Any],
    ) -> str:
        """Resume a graph paused at human approval.

        Args:
            thread_id: The mission/thread ID.
            approval_data: {"approved": bool, "feedback": str}
        """
        await self._ensure_graph()

        config = self._make_config(thread_id)

        try:
            # Update state with approval response
            update = {
                "approval_response": "approved" if approval_data.get("approved") else "rejected",
                "needs_approval": False,
            }

            final_state = await self._graph.ainvoke(update, config)
            response = self._extract_response(final_state)
            return response

        except Exception as exc:
            logger.error(f"Graph resume failed: {exc}")
            return f"Error resuming task: {exc}"

    async def stream(
        self,
        user_input: str,
        thread_id: str = None,
    ):
        """Stream graph execution events.

        Yields state updates as they happen.
        """
        await self._ensure_graph()

        if not thread_id:
            thread_id = str(uuid.uuid4())

        state = initial_state(goal=user_input, mission_id=thread_id)
        state["messages"] = [HumanMessage(content=user_input)]

        config = self._make_config(thread_id)

        async for event in self._graph.astream(state, config):
            yield event

    async def get_state(self, thread_id: str) -> Dict[str, Any]:
        """Get current graph state for a thread."""
        await self._ensure_graph()
        config = self._make_config(thread_id)

        try:
            state = await self._graph.aget_state(config)
            return state.values if state else {}
        except Exception:
            return {}

    @staticmethod
    def _extract_response(state: Dict[str, Any]) -> str:
        """Extract the final response text from graph state."""
        messages = state.get("messages", [])
        if messages:
            # Find last AI message
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    return msg.content

        # Fallback to tool results
        results = state.get("tool_results", {})
        if results:
            return str(results)

        error = state.get("error")
        if error:
            return f"I encountered an issue: {error}"

        return "Task completed."
