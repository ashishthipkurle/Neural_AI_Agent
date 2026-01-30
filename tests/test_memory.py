import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.memory.memory_manager import MemoryManager

def test_memory():
    print("Initializing MemoryManager...")
    try:
        mm = MemoryManager()
        
        print("Storing fact: 'My name is Ashish'")
        mm.remember_fact("My name is Ashish")
        
        print("Storing fact: 'I like coding Python'")
        mm.remember_fact("I like coding Python")
        
        print("Searching for: 'What do I like?'")
        result = mm.recall("What do I like?")
        print(f"Result:\n{result}")
        
        if "Python" in result:
            print("SUCCESS: Memory recall worked.")
        else:
            print("FAILURE: Could not recall fact.")
            
    except Exception as e:
        print(f"CRITICAL FAILURE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_memory()
