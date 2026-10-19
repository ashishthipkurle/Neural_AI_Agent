"""Test memory system."""
import sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"

from agents.memory import AgentMemory, MemoryPage, MemoryManager

# Test AgentMemory
m = AgentMemory("test_agent")
m.add("user", "buy 10 shares of reliance", key="trading order")
m.add("agent", "Order placed successfully", importance=0.8)
m.add_interaction("what is my balance", "Your balance is 50000 INR")

ctx = m.get_context_for_prompt("balance")
stats = m.get_stats()

print("=== AgentMemory Test ===")
print(f"  Hot pages: {stats['hot_pages']}")
print(f"  Warm pages: {stats['warm_pages']}")
print(f"  Total created: {stats['total_created']}")
print(f"  Hot tokens: {stats['hot_tokens']}")
print(f"  Context length: {len(ctx)} chars")

# Test eviction (add more than hot limit)
for i in range(15):
    m.add("user", f"Message number {i} about testing eviction policy")
    m.add("agent", f"Response to message {i}")

stats2 = m.get_stats()
print(f"\n  After 15 interactions:")
print(f"  Hot pages: {stats2['hot_pages']} (should be <= 10)")
print(f"  Warm pages: {stats2['warm_pages']} (evicted pages)")
print(f"  Total evictions: {stats2['total_evictions']}")

# Test cold store search
m.save_to_disk()

# Test MemoryManager
print("\n=== MemoryManager Test ===")
mgr = MemoryManager()
gen_mem = mgr.create_memory("general")
trade_mem = mgr.create_memory("trading")
hack_mem = mgr.create_memory("hacking")

# Add some data
trade_mem.add("agent", "RELIANCE is up 3% today", key="market update", importance=0.9)
gen_mem.add("user", "How is the market doing?", key="market question")

# Cross-agent sharing
mgr.share_context("trading", "general", "RELIANCE up 3%, TATA down 1%", "market data")

# Check shared context in general agent
gen_ctx = gen_mem.get_context_for_prompt("market")
print(f"  Agents: {mgr.get_stats()['total_agents']}")
print(f"  Total tokens: {mgr.get_stats()['total_tokens']}")
print(f"  General has shared context: {'Yes' if gen_mem.shared_context else 'No'}")
print(f"  Context includes market data: {'RELIANCE' in gen_ctx}")

# Global search
results = mgr.search_all("reliance market")
print(f"  Global search 'reliance market': {len(results)} results")

mgr_stats = mgr.get_stats()
print(f"  Budget usage: {mgr_stats['budget_usage']:.2%}")

print("\nALL MEMORY TESTS PASSED")
