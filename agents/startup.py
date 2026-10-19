"""
INDRA OS -- System Startup

Initializes all agents, memory system, message bus, orchestrator, and emotional engine.
This is the single entry point for the entire multi-agent system.

Usage:
    from agents.startup import start_indra_os
    orchestrator, registry, bus, emotional, memory_mgr = await start_indra_os(llm_func, speak_func)
"""

import asyncio
import logging
from typing import Callable, Optional

from agents.agent_registry import AgentRegistry
from agents.message_bus import MessageBus
from agents.orchestrator import IndraOrchestrator
from agents.indra.emotional_engine import EmotionalEngine
from agents.memory.memory_manager import MemoryManager

# Workers
from agents.workers.general_worker import GeneralWorker
from agents.workers.trading_worker import TradingWorker
from agents.workers.coding_worker import CodingWorker
from agents.workers.hacking_worker import HackingWorker
from agents.workers.computer_control_worker import ComputerControlWorker
from agents.workers.workflow_worker import WorkflowWorker
from agents.workers.content_creator_worker import ContentCreatorWorker

logger = logging.getLogger("INDRA.Startup")


async def start_indra_os(
    llm_func: Optional[Callable] = None,
    speak_func: Optional[Callable] = None,
    vision_func: Optional[Callable] = None,
    search_func: Optional[Callable] = None,
) -> tuple:
    """
    Boot up the entire INDRA OS multi-agent system.

    Args:
        llm_func: async callable(prompt: str) -> str for LLM queries
        speak_func: callable(text: str) for TTS output
        vision_func: async callable(prompt, screenshot_b64) -> str for vision
        search_func: async callable(query: str) -> str for web search

    Returns:
        (orchestrator, registry, bus, emotional_engine, memory_manager)
    """
    logger.info("=" * 50)
    logger.info("  INDRA OS -- Starting Multi-Agent System")
    logger.info("=" * 50)

    # 1. Message Bus
    bus = MessageBus()
    await bus.start()
    logger.info("[OK] Message bus started")

    # 2. Memory Manager (KV Cache + Paged Attention)
    memory_mgr = MemoryManager(llm_func=llm_func)
    memory_mgr.load_all()
    logger.info("[OK] Memory manager started")

    # 3. Agent Registry
    registry = AgentRegistry()

    # 4. Create all agents
    agents = [
        GeneralWorker(llm_func=llm_func, speak_func=speak_func, search_func=search_func),
        TradingWorker(llm_func=llm_func, speak_func=speak_func),
        CodingWorker(llm_func=llm_func, speak_func=speak_func),
        HackingWorker(llm_func=llm_func, speak_func=speak_func),
        ComputerControlWorker(llm_func=llm_func, vision_func=vision_func, speak_func=speak_func),
        WorkflowWorker(llm_func=llm_func, speak_func=speak_func, message_bus=bus),
        ContentCreatorWorker(llm_func=llm_func, speak_func=speak_func),
    ]

    # 5. Register all agents, connect message bus, allocate memory
    for agent in agents:
        agent._message_bus = bus
        agent.memory = memory_mgr.create_memory(agent.name)
        registry.register(agent)

    # 6. Initialize all agents
    results = await registry.initialize_all()
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    logger.info(f"[OK] Agents initialized: {success_count}/{total_count}")

    for name, ok in results.items():
        status = "[OK]" if ok else "[FAIL]"
        logger.info(f"  {status} {name}")

    # 7. Start memory maintenance (background summarization + eviction)
    await memory_mgr.start_maintenance(interval_seconds=300)
    logger.info("[OK] Memory maintenance scheduler started")

    # 8. Emotional Engine
    emotional = EmotionalEngine()
    logger.info("[OK] Emotional engine initialized")

    # 9. Orchestrator
    orchestrator = IndraOrchestrator(
        registry=registry,
        bus=bus,
        llm_func=llm_func,
        speak_func=speak_func,
    )
    logger.info("[OK] Orchestrator initialized")

    logger.info("=" * 50)
    logger.info(f"  INDRA OS READY -- {success_count} agents online, memory active")
    logger.info("=" * 50)

    return orchestrator, registry, bus, emotional, memory_mgr

