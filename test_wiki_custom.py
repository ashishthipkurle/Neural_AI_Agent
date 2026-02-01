import requests

def test_custom_wiki():
    queries = ["List of presidents of the United States"]
    url = "https://en.wikipedia.org/w/api.php"
    headers = {
        "User-Agent": "MyDataScraper/1.0 (contact@example.com)"
    }
    
    for query in queries:
        print(f"\n--- Fetching Content for: '{query}' ---")
        params = {
            "action": "query",
            "format": "json",
            "titles": query,
            "prop": "extracts",
            "explaintext": True,
            "exintro": True, # Intro usually has key facts
            "exchars": 2000
        }
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()
            
            pages = data["query"]["pages"]
            for page_id, page_data in pages.items():
                content = page_data.get("extract", "No content")
                print(content[:500]) # First 500 chars 
                if "Biden" in content or "Trump" in content:
                    print(f"✅ FOUND PRESIDENT NAME in {query}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_custom_wiki()
