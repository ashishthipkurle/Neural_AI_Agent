"""
INDRA OS -- Memory Manager (Paged Attention Controller)

Central controller that manages memory across ALL agents.
Like a virtual memory manager in an OS:
- Allocates memory pages per agent
- Handles cross-agent context sharing (cross-attention)
- Runs periodic maintenance (summarization, eviction)
- Provides global search across all agent memories
- Tracks memory budget (total tokens across all agents)
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional

from agents.memory.agent_memory import AgentMemory, MemoryPage, MEMORY_DIR

logger = logging.getLogger("MemoryManager")


class MemoryManager:
    """
    Global memory manager for INDRA OS.
    Manages all agent memories and cross-agent context sharing.

    Analogies:
    - This is the MMU (Memory Management Unit) of the system
    - Each agent's memory is like a process's virtual address space
    - Cross-agent sharing is like shared memory / IPC
    - Maintenance is like garbage collection
    """

    def __init__(
        self,
        llm_func=None,
        hot_limit: int = 10,
        warm_limit: int = 30,
        max_context_tokens: int = 4000,
        global_token_budget: int = 50000,
    ):
        self._llm = llm_func
        self._hot_limit = hot_limit
        self._warm_limit = warm_limit
        self._max_context_tokens = max_context_tokens
        self._global_token_budget = global_token_budget

        # Agent name -> AgentMemory
        self._memories: dict[str, AgentMemory] = {}

        # Global event log (INDRA's own memory of what happened)
        self._event_log: list[dict] = []
        self._max_events = 200

        # Maintenance task
        self._maintenance_task: Optional[asyncio.Task] = None

    # -- Memory Allocation ------------------------------------------------

    def create_memory(self, agent_name: str) -> AgentMemory:
        """
        Create and register a memory instance for an agent.
        Called during agent registration.
        """
        if agent_name in self._memories:
            logger.info(f"Memory already exists for {agent_name}, reusing")
            return self._memories[agent_name]

        memory = AgentMemory(
            agent_name=agent_name,
            hot_page_limit=self._hot_limit,
            warm_page_limit=self._warm_limit,
            max_context_tokens=self._max_context_tokens,
            llm_func=self._llm,
        )

        self._memories[agent_name] = memory
        logger.info(f"Memory allocated for agent: {agent_name}")
        return memory

    def get_memory(self, agent_name: str) -> Optional[AgentMemory]:
        """Get an agent's memory."""
        return self._memories.get(agent_name)

    # -- Cross-Agent Sharing (Cross-Attention) ----------------------------

    def share_context(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        key: str = "",
    ):
        """
        Share context from one agent to another.
        INDRA calls this when agents are collaborating on a task.

        This is the cross-attention mechanism:
        - Agent A produces a key-value (result)
        - INDRA decides Agent B needs to "attend" to it
        - Agent B's next prompt includes this shared context
        """
        target_memory = self._memories.get(to_agent)
        if target_memory:
            target_memory.inject_shared(from_agent, content, key)
            logger.info(f"Shared context: {from_agent} -> {to_agent} ({len(content)} chars)")

            self._log_event("share", {
                "from": from_agent,
                "to": to_agent,
                "key": key,
                "content_length": len(content),
            })
        else:
            logger.warning(f"Cannot share to {to_agent}: no memory allocated")

    def broadcast_context(self, from_agent: str, content: str, key: str = ""):
        """
        Share context from one agent to ALL other agents.
        Used for system-wide announcements.
        """
        for name, memory in self._memories.items():
            if name != from_agent:
                memory.inject_shared(from_agent, content, key)

        self._log_event("broadcast", {
            "from": from_agent,
            "key": key,
            "recipients": [n for n in self._memories if n != from_agent],
        })

    def share_task_result(self, from_agent: str, task_description: str, result_summary: str):
        """
        After an agent completes a task, share a concise summary
        with agents that might benefit from knowing.
        """
        content = f"[{from_agent} completed] {task_description}: {result_summary[:200]}"
        # Add to INDRA's global memory
        self._log_event("task_complete", {
            "agent": from_agent,
            "task": task_description[:100],
            "result": result_summary[:200],
        })

    # -- Global Search (Across All Agent Memories) ------------------------

    def search_all(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search across all agent memories (hot + warm + cold).
        Returns results ranked by relevance with source agent info.
        """
        all_results: list[tuple[float, str, MemoryPage]] = []

        query_words = set(query.lower().split())

        for agent_name, memory in self._memories.items():
            # Search hot pages
            for page in memory.hot_pages:
                score = self._score_page(page, query_words)
                if score > 0:
                    all_results.append((score * 1.5, agent_name, page))  # hot bonus

            # Search warm pages
            for page in memory.warm_pages:
                score = self._score_page(page, query_words)
                if score > 0:
                    all_results.append((score, agent_name, page))

            # Search cold store
            cold_results = memory.search_cold(query, limit=3)
            for page in cold_results:
                score = self._score_page(page, query_words) * 0.8  # cold penalty
                all_results.append((score, agent_name, page))

        # Sort by score
        all_results.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "agent": agent_name,
                "content": page.content,
                "key": page.key,
                "timestamp": page.timestamp,
                "importance": page.importance,
                "score": score,
            }
            for score, agent_name, page in all_results[:limit]
        ]

    @staticmethod
    def _score_page(page: MemoryPage, query_words: set) -> float:
        """Score a page against query words (attention score)."""
        page_words = set(page.content.lower().split())
        key_words = set(page.key.lower().split())
        content_overlap = len(query_words & page_words)
        key_overlap = len(query_words & key_words) * 3  # key matches worth more
        return (content_overlap + key_overlap) * page.importance

    # -- Maintenance (Garbage Collection) ---------------------------------

    async def start_maintenance(self, interval_seconds: int = 300):
        """
        Start periodic maintenance loop.
        Runs every N seconds to summarize, evict, and compact memory.
        """
        self._maintenance_task = asyncio.create_task(
            self._maintenance_loop(interval_seconds)
        )
        logger.info(f"Memory maintenance started (interval: {interval_seconds}s)")

    async def stop_maintenance(self):
        """Stop the maintenance loop."""
        if self._maintenance_task:
            self._maintenance_task.cancel()
            self._maintenance_task = None

    async def _maintenance_loop(self, interval: int):
        """Periodic maintenance: summarize warm pages, check budgets."""
        while True:
            try:
                await asyncio.sleep(interval)
                await self.run_maintenance()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Maintenance error: {e}")

    async def run_maintenance(self):
        """
        Run one maintenance cycle:
        1. Summarize bloated warm tiers (LLM compression)
        2. Evict excess warm pages to cold
        3. Check global token budget
        """
        logger.info("Running memory maintenance...")

        for name, memory in self._memories.items():
            # Auto-summarize warm pages if they're getting large
            if len(memory.warm_pages) > memory.warm_page_limit * 0.7:
                await memory.summarize_warm_pages()

        # Check global token budget
        total_tokens = self.get_total_tokens()
        if total_tokens > self._global_token_budget:
            logger.warning(
                f"Token budget exceeded: {total_tokens}/{self._global_token_budget}. "
                "Forcing eviction."
            )
            self._force_eviction()

        logger.info(f"Maintenance complete. Total tokens: {total_tokens}")

    def _force_eviction(self):
        """Force-evict warm pages from the largest memory to stay within budget."""
        # Find agent with most tokens
        agent_tokens = {
            name: sum(p.token_estimate for p in m.hot_pages) +
                  sum(p.token_estimate for p in m.warm_pages)
            for name, m in self._memories.items()
        }
        if not agent_tokens:
            return

        biggest = max(agent_tokens, key=agent_tokens.get)
        memory = self._memories[biggest]

        # Evict half the warm pages
        evict_count = len(memory.warm_pages) // 2
        for _ in range(evict_count):
            memory._evict_warm_to_cold()

        logger.info(f"Force-evicted {evict_count} warm pages from {biggest}")

    # -- Persistence (Save/Load All) --------------------------------------

    def save_all(self):
        """Save all agent memories to disk. Called on shutdown."""
        for name, memory in self._memories.items():
            memory.save_to_disk()
        logger.info(f"Saved memory for {len(self._memories)} agents")

        # Save event log
        event_path = MEMORY_DIR / "event_log.json"
        try:
            event_path.write_text(
                json.dumps(self._event_log[-100:], indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Event log save failed: {e}")

    def load_all(self):
        """Load event log from disk. Agent memories self-load in __init__."""
        event_path = MEMORY_DIR / "event_log.json"
        if event_path.exists():
            try:
                self._event_log = json.loads(event_path.read_text(encoding="utf-8"))
            except Exception:
                pass

    # -- Stats & Introspection --------------------------------------------

    def get_total_tokens(self) -> int:
        """Total token count across all agent memories."""
        total = 0
        for memory in self._memories.values():
            total += sum(p.token_estimate for p in memory.hot_pages)
            total += sum(p.token_estimate for p in memory.warm_pages)
        return total

    def get_stats(self) -> dict:
        """Get global memory stats for dashboard."""
        agent_stats = {}
        for name, memory in self._memories.items():
            agent_stats[name] = memory.get_stats()

        return {
            "total_agents": len(self._memories),
            "total_tokens": self.get_total_tokens(),
            "global_budget": self._global_token_budget,
            "budget_usage": self.get_total_tokens() / self._global_token_budget if self._global_token_budget else 0,
            "event_count": len(self._event_log),
            "agents": agent_stats,
        }

    # -- Internal ---------------------------------------------------------

    def _log_event(self, event_type: str, data: dict):
        """Log a memory system event."""
        self._event_log.append({
            "type": event_type,
            "timestamp": time.time(),
            "data": data,
        })
        if len(self._event_log) > self._max_events:
            self._event_log = self._event_log[-self._max_events // 2:]
