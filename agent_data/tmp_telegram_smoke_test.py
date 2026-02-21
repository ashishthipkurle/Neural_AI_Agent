import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import asyncio
from agent.main import NeuralAgent

async def main():
    a = NeuralAgent()
    resp = await a.process_input('research the top 3 AI frameworks and write a summary', source='telegram')
    print('---RESPONSE START---')
    print(resp)
    print('---RESPONSE END---')

asyncio.run(main())
