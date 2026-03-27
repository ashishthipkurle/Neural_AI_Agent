import asyncio
from agent.graph.nodes.coder import coder_node
from agent.graph.state import initial_state
from langchain_core.runnables.config import RunnableConfig

async def main():
    state = initial_state(goal="Write a simple python script that prints 'hello world' using your bash tool.", mission_id="test1")
    config = RunnableConfig(configurable={"app_config": {}})
    
    # Run the loop
    res = await coder_node(state, config)
    
    print("\n--- Final Messages ---")
    for m in res.get("messages", []):
        print(type(m).__name__, ":", getattr(m, 'content', str(m)))
        
    print("\n--- Audit Log ---")
    print(res.get("audit_log", []))

if __name__ == "__main__":
    asyncio.run(main())
