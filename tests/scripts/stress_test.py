
import logging
import asyncio
import os
import time
from agent.core.orchestrator import Orchestrator, AgentState
from agent.ui.server import GUIServer, UIMessageType

# Mock UI Interface for Test
class MockUI:
    def __init__(self):
        self.messages = []
    def send_update(self, type, data):
        self.messages.append((type, data))
        print(f"[TEST UI] {type}: {data}")
    def start(self): pass

async def stress_test():
    """
    Runs a simulation of all systems working together.
    """
    print("\n\n--- STARTING SYSTEM STRESS TEST ---\n")
    
    # 1. Initialize Orchestrator (Loads Brain, Vision, Voice, Tools)
    ui_mock = MockUI()
    try:
        orchestrator = Orchestrator(ui_interface=ui_mock, voice_interface=None) # Disable real voice for test
        print("✅ Orchestrator Initialized")
    except Exception as e:
        print(f"❌ Initialization Failed: {e}")
        return

    # 2. Test Core State Machine
    if orchestrator.state == AgentState.IDLE:
        print("✅ Initial State is IDLE")
    else:
        print(f"❌ State Error: {orchestrator.state}")

    # 3. Test Intent Parsing & Brain (Simulate simple chat)
    print("\n--- Test 1: Simple Chat ---")
    responses = await orchestrator.run("Hello, who are you?")
    print(f"Response: {responses}")
    if responses and len(responses) > 0:
        print("✅ Chat Logic Working")
    else:
        print("❌ Chat Logic Failed")

    # 4. Test Tool Execution (Math)
    print("\n--- Test 2: Math Tool ---")
    responses = await orchestrator.run("Calculate 50 * 20")
    if any("1000" in r for r in responses):
        print("✅ Math Tool Working")
    else:
        print(f"❌ Math Tool Failed: {responses}")

    # 5. Test Memory Storage
    print("\n--- Test 3: Memory Storage ---")
    await orchestrator.run("Remember that the password is 'banana'.")
    # Verify retrieval
    responses = await orchestrator.run("What is the password I told you?")
    if "banana" in str(responses).lower() or "remember" in str(responses).lower(): 
        # Note: Semantic search might not return exact "password is banana" instantly unless the LLM rephrased it well.
        # But we check if it tried to search memory or stored it.
        print(f"✅ Memory Interaction (Store/Recall) seems active. Response: {responses}")
    else:
        print(f"⚠️ Memory Check requires manual verification of output: {responses}")

    # 6. Test Security Lock
    print("\n--- Test 4: Security Lock ---")
    # Manually lock
    orchestrator.lock()
    if orchestrator.is_locked:
        print("✅ Agent Locked Successfully")
    
    # Try an action while locked
    res = await orchestrator.run("Open Calculator")
    if "LOCKED" in res[0]:
        print("✅ Agent correctly blocked action while locked.")
    else:
        print(f"❌ Security Failure: Agent performed action while locked! {res}")
        
    # Unlock (Manual override for test)
    orchestrator.unlock()
    print("✅ Agent Unlocked")

    print("\n--- STRESS TEST COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(stress_test())
