"""
INDRA OS -- Agent Memory (KV Cache Implementation)

Each agent gets a paged memory system inspired by KV cache and paged attention:

- HotPages: Last N interactions at full detail (like KV cache -- instant recall)
- WarmPages: Older interactions auto-summarized (like evicted cache lines)
- ColdStore: Persistent disk storage, keyword-searchable
- SharedMemory: Cross-agent context injected by INDRA (like cross-attention)

Memory flows: Hot -> (summarize) -> Warm -> (compress) -> Cold -> (disk)
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("AgentMemory")

MEMORY_DIR = Path("d:/All Projects/My AI Agent/data/memory")
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MemoryPage:
    """
    A single page of memory -- one interaction/event.
    Equivalent to a KV cache entry in attention.
    """
    page_id: str                    # unique identifier
    timestamp: float                # when this happened
    role: str                       # "user", "agent", "system", "indra"
    content: str                    # the actual content (full or summarized)
    metadata: dict = field(default_factory=dict)  # extra context
    # KV cache analogy:
    #   key   = the topic/intent of this interaction
    #   value = the actual content/result
    key: str = ""                   # topic/intent (for retrieval)
    importance: float = 0.5         # 0.0 (trivial) to 1.0 (critical)
    is_summary: bool = False        # True if this is a compressed summary
    token_estimate: int = 0         # rough token count for budget tracking

    def to_dict(self) -> dict:
        return {
            "page_id": self.page_id,
            "timestamp": self.timestamp,
            "role": self.role,
            "content": self.content,
            "metadata": self.metadata,
            "key": self.key,
            "importance": self.importance,
            "is_summary": self.is_summary,
            "token_estimate": self.token_estimate,
        }

    @staticmethod
    def from_dict(d: dict) -> "MemoryPage":
        return MemoryPage(
            page_id=d["page_id"],
            timestamp=d["timestamp"],
            role=d["role"],
            content=d["content"],
            metadata=d.get("metadata", {}),
            key=d.get("key", ""),
            importance=d.get("importance", 0.5),
            is_summary=d.get("is_summary", False),
            token_estimate=d.get("token_estimate", 0),
        )


class AgentMemory:
    """
    Paged memory system for a single agent.
    Manages hot/warm/cold tiers like a CPU cache hierarchy.
    """

    def __init__(
        self,
        agent_name: str,
        hot_page_limit: int = 10,       # keep last 10 interactions at full detail
        warm_page_limit: int = 30,       # keep 30 summarized interactions
        max_context_tokens: int = 4000,  # token budget for LLM context injection
        llm_func=None,                   # for auto-summarization
    ):
        self.agent_name = agent_name
        self.hot_page_limit = hot_page_limit
        self.warm_page_limit = warm_page_limit
        self.max_context_tokens = max_context_tokens
        self._llm = llm_func

        # Memory tiers (like cache levels)
        self.hot_pages: list[MemoryPage] = []    # L1 -- full detail, in-prompt
        self.warm_pages: list[MemoryPage] = []   # L2 -- summarized, in-prompt if needed
        self.cold_store_path = MEMORY_DIR / f"{agent_name}_cold.jsonl"

        # Cross-agent shared memory (injected by INDRA)
        self.shared_context: list[MemoryPage] = []

        # Stats
        self._total_pages_created = 0
        self._total_evictions = 0

        # Load warm pages from disk on startup
        self._load_warm_from_disk()

    # -- Write (Add new memories) -----------------------------------------

    def add(
        self,
        role: str,
        content: str,
        key: str = "",
        importance: float = 0.5,
        metadata: Optional[dict] = None,
    ) -> MemoryPage:
        """
        Add a new memory page to hot storage.
        If hot storage is full, oldest page gets evicted to warm tier.
        """
        self._total_pages_created += 1
        page = MemoryPage(
            page_id=f"{self.agent_name}_{self._total_pages_created}",
            timestamp=time.time(),
            role=role,
            content=content,
            key=key or self._extract_key(content),
            importance=importance,
            metadata=metadata or {},
            token_estimate=self._estimate_tokens(content),
        )

        self.hot_pages.append(page)

        # Evict oldest hot page if over limit
        if len(self.hot_pages) > self.hot_page_limit:
            self._evict_hot_to_warm()

        return page

    def add_interaction(self, user_input: str, agent_response: str, task_result: Optional[dict] = None):
        """
        Convenience: add a full interaction (user + agent response) as two pages.
        """
        self.add(
            role="user",
            content=user_input,
            importance=0.6,
            metadata={"type": "input"},
        )
        self.add(
            role="agent",
            content=agent_response,
            importance=0.5,
            metadata={"type": "response", "task_result": task_result},
        )

    # -- Read (Build context for LLM) ------------------------------------

    def get_context_for_prompt(self, current_query: str = "") -> str:
        """
        Build memory context to inject into an LLM prompt.
        Respects the token budget. Prioritizes:
        1. Shared cross-agent context (highest priority)
        2. Hot pages (most recent, full detail)
        3. Relevant warm pages (older but potentially relevant)

        This is the paged attention mechanism -- we "attend" to the
        most relevant pages within our budget.
        """
        parts = []
        tokens_used = 0

        # 1. Shared context from other agents (cross-attention)
        if self.shared_context:
            parts.append("=== Context from other agents ===")
            for page in self.shared_context[-5:]:  # last 5 shared items
                if tokens_used + page.token_estimate < self.max_context_tokens:
                    parts.append(f"[{page.role}] {page.content}")
                    tokens_used += page.token_estimate

        # 2. Hot pages (most recent interactions -- full detail)
        if self.hot_pages:
            parts.append("\n=== Recent conversation ===")
            for page in self.hot_pages:
                if tokens_used + page.token_estimate < self.max_context_tokens:
                    prefix = "User" if page.role == "user" else "INDRA"
                    parts.append(f"{prefix}: {page.content}")
                    tokens_used += page.token_estimate

        # 3. Warm pages -- only include relevant ones (attention scoring)
        if self.warm_pages and current_query:
            relevant = self._find_relevant_warm(current_query, budget=self.max_context_tokens - tokens_used)
            if relevant:
                parts.append("\n=== Relevant past context ===")
                for page in relevant:
                    parts.append(f"[Earlier] {page.content}")
                    tokens_used += page.token_estimate

        return "\n".join(parts) if parts else ""

    def get_hot_as_messages(self) -> list[dict]:
        """
        Return hot pages formatted as chat messages for LLM APIs.
        Useful for chat-completion style APIs.
        """
        messages = []
        for page in self.hot_pages:
            if page.role == "user":
                messages.append({"role": "user", "content": page.content})
            elif page.role == "agent":
                messages.append({"role": "assistant", "content": page.content})
            elif page.role == "system":
                messages.append({"role": "system", "content": page.content})
        return messages

    # -- Eviction (Hot -> Warm -> Cold) -----------------------------------

    def _evict_hot_to_warm(self):
        """
        Evict the oldest hot page to warm tier.
        If auto-summarization is available, summarize before evicting.
        """
        if not self.hot_pages:
            return

        evicted = self.hot_pages.pop(0)  # oldest first
        self._total_evictions += 1

        # Create a summarized version for warm storage
        warm_page = MemoryPage(
            page_id=evicted.page_id + "_warm",
            timestamp=evicted.timestamp,
            role=evicted.role,
            content=self._compress(evicted.content),
            key=evicted.key,
            importance=evicted.importance,
            metadata=evicted.metadata,
            is_summary=True,
            token_estimate=self._estimate_tokens(self._compress(evicted.content)),
        )

        self.warm_pages.append(warm_page)

        # Evict oldest warm to cold if over limit
        if len(self.warm_pages) > self.warm_page_limit:
            self._evict_warm_to_cold()

    def _evict_warm_to_cold(self):
        """Move oldest warm page to cold store (disk)."""
        if not self.warm_pages:
            return

        evicted = self.warm_pages.pop(0)

        # Append to cold store file
        try:
            with open(self.cold_store_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(evicted.to_dict()) + "\n")
        except Exception as e:
            logger.warning(f"Cold store write failed: {e}")

    # -- Retrieval (Search cold store) ------------------------------------

    def search_cold(self, query: str, limit: int = 5) -> list[MemoryPage]:
        """
        Search cold store by keyword matching.
        Returns most relevant pages from disk.
        """
        if not self.cold_store_path.exists():
            return []

        query_words = set(query.lower().split())
        scored: list[tuple[float, MemoryPage]] = []

        try:
            with open(self.cold_store_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        page = MemoryPage.from_dict(json.loads(line))
                        # Score by keyword overlap
                        page_words = set(page.content.lower().split())
                        overlap = len(query_words & page_words)
                        if overlap > 0:
                            score = overlap * page.importance
                            scored.append((score, page))
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Cold store read failed: {e}")

        scored.sort(key=lambda x: x[0], reverse=True)
        return [page for _, page in scored[:limit]]

    # -- Cross-Agent Shared Memory ----------------------------------------

    def inject_shared(self, from_agent: str, content: str, key: str = ""):
        """
        INDRA injects context from another agent.
        This is the cross-attention mechanism.
        """
        page = MemoryPage(
            page_id=f"shared_{from_agent}_{int(time.time())}",
            timestamp=time.time(),
            role=f"shared_from_{from_agent}",
            content=content,
            key=key,
            importance=0.7,
            metadata={"source_agent": from_agent},
            token_estimate=self._estimate_tokens(content),
        )
        self.shared_context.append(page)

        # Keep shared context bounded
        if len(self.shared_context) > 10:
            self.shared_context = self.shared_context[-10:]

    def clear_shared(self):
        """Clear shared context after it's been consumed."""
        self.shared_context.clear()

    # -- Async Summarization (LLM-powered) --------------------------------

    async def summarize_warm_pages(self):
        """
        Use LLM to create a high-quality summary of warm pages.
        Called periodically to keep warm tier compact.
        """
        if not self._llm or len(self.warm_pages) < 5:
            return

        # Gather warm content
        warm_text = "\n".join(
            f"[{p.role}] {p.content}" for p in self.warm_pages[:10]
        )

        prompt = (
            f"Summarize these past interactions for the {self.agent_name} agent "
            f"in 3-4 concise bullet points. Focus on key decisions, outcomes, "
            f"and user preferences:\n\n{warm_text}"
        )

        try:
            summary = await self._llm(prompt)
            # Replace the summarized warm pages with one summary page
            self.warm_pages = self.warm_pages[10:]  # keep unsummarized ones
            self.warm_pages.insert(0, MemoryPage(
                page_id=f"summary_{int(time.time())}",
                timestamp=time.time(),
                role="system",
                content=f"Session summary: {summary}",
                key="session_summary",
                importance=0.8,
                is_summary=True,
                token_estimate=self._estimate_tokens(summary),
            ))
        except Exception as e:
            logger.warning(f"Summarization failed: {e}")

    # -- Internal Helpers -------------------------------------------------

    def _compress(self, text: str) -> str:
        """
        Simple compression: truncate to first 200 chars.
        Full LLM summarization is done in summarize_warm_pages().
        """
        if len(text) <= 200:
            return text
        return text[:197] + "..."

    def _extract_key(self, content: str) -> str:
        """Extract a rough topic key from content."""
        words = content.lower().split()[:5]
        return " ".join(words)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate (1 token ~ 4 chars for English)."""
        return max(1, len(text) // 4)

    def _find_relevant_warm(self, query: str, budget: int) -> list[MemoryPage]:
        """
        Find warm pages relevant to current query.
        This is the "attention scoring" -- we score each warm page
        against the current query and return top matches within budget.
        """
        query_words = set(query.lower().split())
        scored: list[tuple[float, MemoryPage]] = []

        for page in self.warm_pages:
            page_words = set(page.content.lower().split())
            overlap = len(query_words & page_words)
            if overlap > 0:
                score = overlap * page.importance
                scored.append((score, page))

        scored.sort(key=lambda x: x[0], reverse=True)

        result = []
        tokens = 0
        for _, page in scored:
            if tokens + page.token_estimate > budget:
                break
            result.append(page)
            tokens += page.token_estimate

        return result

    # -- Persistence ------------------------------------------------------

    def _load_warm_from_disk(self):
        """Load warm pages from the warm cache file."""
        warm_path = MEMORY_DIR / f"{self.agent_name}_warm.json"
        if warm_path.exists():
            try:
                data = json.loads(warm_path.read_text(encoding="utf-8"))
                self.warm_pages = [MemoryPage.from_dict(d) for d in data]
                logger.info(
                    f"Loaded {len(self.warm_pages)} warm pages for {self.agent_name}"
                )
            except Exception as e:
                logger.warning(f"Failed to load warm pages: {e}")

    def save_to_disk(self):
        """Persist warm pages to disk (called on shutdown)."""
        warm_path = MEMORY_DIR / f"{self.agent_name}_warm.json"
        try:
            data = [p.to_dict() for p in self.warm_pages]
            warm_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save warm pages: {e}")

    # -- Stats ------------------------------------------------------------

    def get_stats(self) -> dict:
        return {
            "agent": self.agent_name,
            "hot_pages": len(self.hot_pages),
            "warm_pages": len(self.warm_pages),
            "shared_context": len(self.shared_context),
            "total_created": self._total_pages_created,
            "total_evictions": self._total_evictions,
            "hot_tokens": sum(p.token_estimate for p in self.hot_pages),
            "warm_tokens": sum(p.token_estimate for p in self.warm_pages),
            "cold_store_exists": self.cold_store_path.exists(),
        }

    def clear_all(self):
        """Nuclear option: clear all memory."""
        self.hot_pages.clear()
        self.warm_pages.clear()
        self.shared_context.clear()
        if self.cold_store_path.exists():
            self.cold_store_path.unlink()
