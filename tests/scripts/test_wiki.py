import wikipedia

def test_wiki():
    queries = [
        "President of the United States",
        "current president of India"
    ]
    
    for q in queries:
        print(f"\nQUERY: {q}")
        try:
            # Search first
            search_results = wikipedia.search(q)
            print(f"Search Results: {search_results}")
            
            if search_results:
                # Get summary of first result
                page = wikipedia.summary(search_results[0], sentences=3)
                print(f"Summary: {page}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_wiki()
