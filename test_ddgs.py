
from duckduckgo_search import DDGS
import json

print("Testing DDGS...")
try:
    with DDGS() as ddgs:
        results = list(ddgs.text("bikes overview", max_results=3))
        print(f"Found {len(results)} results")
        print(json.dumps(results, indent=2))
except Exception as e:
    print(f"Error: {e}")
