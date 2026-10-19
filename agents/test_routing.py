"""Quick integration test for INDRA OS routing."""
import asyncio, sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"

from agents.agent_registry import AgentRegistry
from agents.message_bus import MessageBus
from agents.orchestrator import IndraOrchestrator
from agents.workers.general_worker import GeneralWorker
from agents.workers.trading_worker import TradingWorker
from agents.workers.coding_worker import CodingWorker
from agents.workers.hacking_worker import HackingWorker
from agents.workers.computer_control_worker import ComputerControlWorker
from agents.workers.workflow_worker import WorkflowWorker
from agents.workers.content_creator_worker import ContentCreatorWorker

async def test():
    bus = MessageBus()
    await bus.start()
    reg = AgentRegistry()
    agents = [
        GeneralWorker(), TradingWorker(), CodingWorker(),
        HackingWorker(), ComputerControlWorker(),
        WorkflowWorker(), ContentCreatorWorker(),
    ]
    for a in agents:
        a._message_bus = bus
        reg.register(a)
    results = await reg.initialize_all()
    for name, ok in results.items():
        print(f"  [{'OK' if ok else 'FAIL'}] {name}")
    
    orch = IndraOrchestrator(reg, bus)

    tests = [
        ("buy 10 shares of reliance", "trading"),
        ("write a python script to sort files", "coding"),
        ("scan my network for devices", "hacking"),
        ("open chrome and go to youtube", "computer_control"),
        ("automate my daily backup", "workflow"),
        ("create an instagram post about AI", "content_creator"),
        ("hello how are you", "chat"),
        ("what is quantum computing", "chat"),
        ("sell all my TATA shares", "trading"),
        ("build me a portfolio website", "coding"),
        ("check wifi networks around me", "hacking"),
        ("minimize all windows", "computer_control"),
        ("every morning check my emails", "workflow"),
        ("write a linkedin post about startups", "content_creator"),
    ]

    passed = 0
    for text, expected in tests:
        result = orch._fast_route(text)
        actual = result.get("agent", result.get("action", "?")) if result else "?"
        match = actual == expected
        icon = "PASS" if match else "FAIL"
        print(f"  [{icon}] \"{text[:45]}\" -> {actual} (expected {expected})")
        if match:
            passed += 1

    print(f"\nRouting: {passed}/{len(tests)} passed")

    status = orch.get_system_status()
    print(f"System: {status['total_agents']} agents registered, {status['active_agents']} active")
    print("\nAll agents:")
    for agent_info in status["agents"]:
        print(f"  - {agent_info['name']}: {agent_info['status']} ({len(agent_info['capabilities'])} capabilities)")

asyncio.run(test())
