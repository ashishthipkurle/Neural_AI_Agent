from duckduckgo_search import DDGS
import json

def test_search():
    print("Testing DuckDuckGo Search...")
    queries = [
        "who is the current president of united states",
        "current president of USA",
        "Donald Trump"
    ]
    
    backends = ['lite', 'html', 'api']
    
    with DDGS() as ddgs:
        for q in queries:
            print(f"\nQUERY: {q}")
            found = False
            for backend in backends:
                print(f"  Testing backend: {backend}...", end=" ")
                try:
                    results = list(ddgs.text(q, max_results=3, backend=backend))
                    if results:
                        print(f"[OK] Found {len(results)} results.")
                        print(f"  Title: {results[0]['title']}")
                        found = True
                        break
                    else:
                        print("[FAIL] Empty.")
                except Exception as e:
                    print(f"[ERROR] {e}")
            
            if not found:
                 print("  ❌ All backends failed.")

if __name__ == "__main__":
    test_search()
