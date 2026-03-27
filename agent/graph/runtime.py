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
        proposal_mode: bool = False,
    ) -> Any:
        """Execute the full graph for a user input.

        Returns the final response text, or a dict if proposal_mode is True.
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
            "supervisor": "Routing task...",
            "planner": "Scanning project & creating plan...",
            "coder": "Implementing changes...",
            "completion": "Completing task...",
        }

        try:
            # Execute graph with streaming to emit progress
            final_state = None
            accumulated_state = dict(state)

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
                        # Accumulate state updates
                        if isinstance(node_output, dict):
                            accumulated_state.update(node_output)
                            final_state = accumulated_state

            # If stream didn't give us a final state, fall back
            if final_state is None:
                final_state = state

            # ── Check if graph paused for plan approval ──
            phase = final_state.get("phase", "")
            plan_text = final_state.get("plan_text")

            if phase == "awaiting_approval" and plan_text:
                logger.info(f"Graph paused: plan awaiting approval ({len(plan_text)} chars)")
                if self.broadcast_fn:
                    try:
                        self.broadcast_fn("step", "system", "📋 Plan created — awaiting your approval", None)
                    except Exception:
                        pass

                # Store the thread_id so we can resume later
                self._pending_plans = getattr(self, '_pending_plans', {})
                self._pending_plans[thread_id] = {
                    "state": final_state,
                    "config": config,
                }

                return {
                    "needs_approval": True,
                    "plan_text": plan_text,
                    "thread_id": thread_id,
                    "response": plan_text,
                }

            # ── Normal completion ──
            patches = []
            if proposal_mode:
                patches = self._compute_patches_and_rollback(final_state)

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
            if proposal_mode:
                return {"response": response, "patches": patches}
            return response

        except Exception as exc:
            logger.error(f"Graph execution failed: {exc}")
            return f"I encountered an error processing your request: {exc}"

    async def approve_plan(
        self,
        thread_id: str,
        approved: bool = True,
        feedback: str = "",
        proposal_mode: bool = False,
    ) -> Any:
        """Resume the graph after user approves (or rejects) the plan.

        Args:
            thread_id: The thread ID from the plan response.
            approved: Whether user approved the plan.
            feedback: Optional user feedback to refine the plan.
            proposal_mode: Whether to return patches for UI review.
        """
        await self._ensure_graph()

        pending = getattr(self, '_pending_plans', {}).get(thread_id)
        if not pending:
            return "No pending plan found for this thread. Please submit your request again."

        saved_state = pending["state"]

        if not approved:
            # Remove the pending plan
            self._pending_plans.pop(thread_id, None)
            return "Plan rejected. I'll wait for your next request."

        # Re-run the graph with plan approved
        state = dict(saved_state)
        state["plan_approved"] = True
        state["phase"] = "executing"

        if feedback:
            state["goal"] = state.get("goal", "") + f"\n\nUser feedback on plan: {feedback}"

        # ── CRITICAL: use a FRESH thread_id for the resumed run ──
        # The original graph run already completed (hit the END node) under
        # the old thread_id.  If we reuse it, the SQLite checkpointer sees
        # the graph as done and `astream` yields zero events → hang.
        import uuid as _uuid
        exec_thread_id = f"{thread_id}_exec_{_uuid.uuid4().hex[:8]}"
        config = self._make_config(exec_thread_id)

        logger.info(f"Resuming graph with approved plan for thread {thread_id} "
                     f"(new execution thread: {exec_thread_id})")
        if self.broadcast_fn:
            try:
                self.broadcast_fn("step", "system", "✅ Plan approved — starting execution...", None)
            except Exception:
                pass

        try:
            final_state = None
            accumulated_state = dict(state)

            logger.info(f"🚀 Starting graph astream for exec thread {exec_thread_id}...")
            event_count = 0
            async for event in self._graph.astream(state, config):
                event_count += 1
                logger.info(f"📡 Graph event #{event_count}: {type(event).__name__}")
                if isinstance(event, dict):
                    for node_name, node_output in event.items():
                        NODE_LABELS = {
                            "supervisor": "Routing...",
                            "planner": "Planning...",
                            "coder": "Implementing changes...",
                            "completion": "Completing...",
                        }
                        label = NODE_LABELS.get(node_name, f"Running: {node_name}")
                        logger.info(f"🟢 Graph node completed: {node_name}")
                        if self.broadcast_fn:
                            try:
                                self.broadcast_fn("step", "system", f"✓ {label}", None)
                            except Exception:
                                pass
                        if isinstance(node_output, dict):
                            accumulated_state.update(node_output)
                            final_state = accumulated_state

            logger.info(f"🏁 Graph astream finished. Total events: {event_count}")

            if final_state is None:
                logger.warning(f"⚠️ astream yielded 0 events — using passed-in state as fallback")
                final_state = state

            # Clean up pending plan
            self._pending_plans.pop(thread_id, None)

            patches = []
            if proposal_mode:
                patches = self._compute_patches_and_rollback(final_state)

            response = self._extract_response(final_state)

            if self.stm:
                self.stm.add_message("assistant", response)

            logger.info(f"Plan execution completed: {len(response)} chars, {len(patches)} patches")

            if proposal_mode:
                return {"response": response, "patches": patches}
            return response

        except Exception as exc:
            logger.error(f"Plan execution failed: {exc}", exc_info=True)
            self._pending_plans.pop(thread_id, None)
            return f"Error executing plan: {exc}"

    async def resume(
        self,
        thread_id: str,
        approval_data: Dict[str, Any],
    ) -> str:
        """Resume a graph paused at human approval (legacy compatibility)."""
        return await self.approve_plan(
            thread_id=thread_id,
            approved=approval_data.get("approved", False),
            feedback=approval_data.get("feedback", ""),
        )

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
    def _compute_patches_and_rollback(state: Dict[str, Any]) -> List[Dict[str, Any]]:
        import difflib
        import os
        patches = []
        original_contents = state.get("original_file_contents", {})
        
        for path_str, orig_content in original_contents.items():
            try:
                if os.path.exists(path_str):
                    with open(path_str, "r", encoding="utf-8") as f:
                        new_content = f.read()
                else:
                    new_content = None
                    
                if orig_content is None and new_content is None:
                    continue
                if orig_content == new_content:
                    continue
                    
                is_new = (orig_content is None)
                
                orig_lines = orig_content.splitlines(keepends=True) if orig_content else []
                new_lines = new_content.splitlines(keepends=True) if new_content else []
                diff = "".join(difflib.unified_diff(
                    orig_lines,
                    new_lines,
                    fromfile=path_str,
                    tofile=path_str
                ))
                
                patches.append({
                    "file_path": path_str,
                    "diff": diff,
                    "is_new": is_new,
                    "new_content": new_content 
                })
                
                if orig_content is None:
                    if os.path.exists(path_str):
                        os.remove(path_str)
                else:
                    with open(path_str, "w", encoding="utf-8") as f:
                        f.write(orig_content)
                logger.info(f"Rolled back {path_str} to original state for proposal")
                
            except Exception as e:
                logger.error(f"Error computing patch or rolling back {path_str}: {e}")
                
        return patches

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
