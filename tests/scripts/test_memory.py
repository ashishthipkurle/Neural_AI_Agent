
from agent.memory.memory_manager import MemoryManager
import time

def test_memory():
    print("Initializing Memory Manager...")
    mm = MemoryManager()
    
    print("\n--- Testing Storage ---")
    fact = "The user is testing the memory system at " + str(time.time())
    print(f"Storing: {fact}")
    mm.remember_fact(fact)
    
    print("\n--- Testing Recall ---")
    query = "testing memory"
    print(f"Querying: {query}")
    result = mm.recall(query)
    print(f"Result:\n{result}")
    
    if fact in result:
        print("\nSUCCESS: Retrieved stored memory.")
    else:
        print("\nFAILURE: Could not retrieve memory.")

if __name__ == "__main__":
    test_memory()
