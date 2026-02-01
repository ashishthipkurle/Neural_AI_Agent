import wikipedia

def test_wiki():
    query = "President of the United States"
    print(f"--- Fetching Content for: '{query}' ---")
    try:
        # Check summary first
        print("\n[SUMMARY]")
        print(wikipedia.summary(query, sentences=3))
        
        # Check Content (first 2000 chars)
        print("\n\n[CONTENT (First 2000 chars)]")
        page = wikipedia.page(query)
        print(page.content[:2000])
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_wiki()
