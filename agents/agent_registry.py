"""
INDRA OS — Agent Registry

Central registry where all agents register at startup.
INDRA uses this to discover, route to, and manage agents.

Usage:
    registry = AgentRegistry()
    registry.register(TradingWorker())
    registry.register(CodingWorker())

    best = await registry.find_best("buy 10 shares of RELIANCE")
    # → TradingWorker (confidence: 0.95)
"""

import logging
from typing import Optional

from agents.base_agent import BaseAgent, AgentStatus

logger = logging.getLogger("AgentRegistry")


class AgentRegistry:
    """
    Central directory of all registered agents.
    Provides lookup by name, capability matching, and health monitoring.
    """

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Register an agent. Overwrites if name already exists."""
        if agent.name in self._agents:
            logger.warning(f"Overwriting existing agent: {agent.name}")
        self._agents[agent.name] = agent
        logger.info(
            f"Registered agent: {agent.name} "
            f"(capabilities: {', '.join(agent.capabilities[:5])})"
        )

    def unregister(self, name: str) -> None:
        """Remove an agent from the registry."""
        if name in self._agents:
            del self._agents[name]
            logger.info(f"Unregistered agent: {name}")

    def get(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self._agents.get(name)

    def get_all(self) -> list[BaseAgent]:
        """Get all registered agents."""
        return list(self._agents.values())

    def get_available(self) -> list[BaseAgent]:
        """Get all agents that are idle or capable of accepting work."""
        return [
            a for a in self._agents.values()
            if a.status in (AgentStatus.IDLE,)
        ]

    def get_by_capability(self, capability: str) -> list[BaseAgent]:
        """Find agents that list a specific capability."""
        return [
            a for a in self._agents.values()
            if capability in a.capabilities
        ]

    async def find_best(self, task_description: str) -> Optional[BaseAgent]:
        """
        Ask all available agents how confident they are at handling the task.
        Returns the most confident agent, or None if no one can handle it.
        """
        candidates = []

        for agent in self.get_available():
            try:
                confidence = await agent.can_handle(task_description)
                if confidence > 0.1:  # ignore near-zero confidence
                    candidates.append((agent, confidence))
            except Exception as e:
                logger.warning(f"{agent.name} failed can_handle check: {e}")

        if not candidates:
            # Also check busy agents — they might queue the task
            for agent in self._agents.values():
                if agent.status == AgentStatus.WORKING:
                    try:
                        confidence = await agent.can_handle(task_description)
                        if confidence > 0.7:  # only if very confident
                            candidates.append((agent, confidence * 0.5))  # penalize busy
                    except Exception:
                        pass

        if not candidates:
            logger.warning(f"No agent can handle: {task_description[:60]}")
            return None

        # Sort by confidence descending
        candidates.sort(key=lambda x: x[1], reverse=True)

        best_agent, best_confidence = candidates[0]
        logger.info(
            f"Best agent for '{task_description[:40]}...': "
            f"{best_agent.name} (confidence: {best_confidence:.2f})"
        )

        return best_agent

    async def initialize_all(self) -> dict[str, bool]:
        """
        Initialize all registered agents.
        Returns dict of {agent_name: success}.
        """
        results = {}
        for name, agent in self._agents.items():
            try:
                ok = await agent.initialize()
                results[name] = ok
                if ok:
                    logger.info(f"[OK] {name} initialized")
                else:
                    logger.error(f"✗ {name} failed to initialize")
            except Exception as e:
                results[name] = False
                logger.error(f"✗ {name} crashed during init: {e}")
        return results

    async def shutdown_all(self) -> None:
        """Shutdown all agents gracefully."""
        for name, agent in self._agents.items():
            try:
                await agent.shutdown()
                logger.info(f"[OK] {name} shut down")
            except Exception as e:
                logger.warning(f"✗ {name} shutdown error: {e}")

    def get_status_report(self) -> list[dict]:
        """Get status of all agents for dashboard/API."""
        return [agent.to_dict() for agent in self._agents.values()]

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    @property
    def active_count(self) -> int:
        return sum(
            1 for a in self._agents.values()
            if a.status == AgentStatus.WORKING
        )
