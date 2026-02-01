from duckduckgo_search import DDGS
import logging

# Configure logging to see internal errors if any
logging.basicConfig(level=logging.DEBUG)

def test_ddg():
    ddgs = DDGS()
    query = "current president of USA"
    
    print(f"--- Testing Query: '{query}' ---")

    backends = ['lite', 'html', 'api', 'auto']
    
    for backend in backends:
        print(f"\n[Testing Backend: {backend}]")
        try:
            # We use 'us-en' to ensure English results if possible, or default
            results = list(ddgs.text(query, max_results=3, backend=backend, region='us-en'))
            if results:
                print(f"[SUCCESS] ({len(results)} results)")
                print(f"Title: {results[0].get('title')}")
                print(f"Snippet: {results[0].get('body')}")
            else:
                print("[FAILED] Returned 0 results")
        except Exception as e:
            print(f"[ERROR] {e}")

    print("\n[Testing Backend: lite (NO REGION)]")
    try:
        results = list(ddgs.text(query, max_results=3, backend='lite'))
        if results:
            print(f"[SUCCESS] ({len(results)} results)")
            print(f"Title: {results[0].get('title')}")
        else:
            print("[FAILED] Returned 0 results")
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    test_ddg()
