"""
Web Search Tool with Wikipedia Fallback.

Since DuckDuckGo is often rate-limited/blocked, this tool prioritizes Wikipedia
for factual queries (who is, what is) and uses DDG as a fallback.
"""
import logging
import json
import wikipedia
from typing import Optional

logger = logging.getLogger("WebSearchTool")

class WebSearchTool:
    """
    Tool for searching the web using Wikipedia and DuckDuckGo.
    """
    def __init__(self):
        try:
            from duckduckgo_search import DDGS
            self.ddgs = DDGS()
        except ImportError:
            logger.warning("duckduckgo_search not installed, DDG fallback disabled")
            self.ddgs = None

    def search(self, query: str, max_results: int = 3) -> str:
        """
        Perform a web search for the given query.
        
        Strategy:
        1. Try Wikipedia first for factual "who is / what is" questions.
        2. Fall back to DuckDuckGo if Wikipedia fails or for news-type queries.
        
        Args:
            query: The search query.
            max_results: Max number of results to return.
            
        Returns:
            JSON string of search results.
        """
        logger.info(f"🔎 Searching for: {query}")
        all_results = []
        
        # Clean the query for Wikipedia
        wiki_query = query.lower()
        for prefix in ["who is the", "who is", "what is the", "what is", "current", "latest"]:
            wiki_query = wiki_query.replace(prefix, "").strip()
        
        # 1. WIKIPEDIA (Primary for factual queries)
        try:
            # Search for page titles first
            search_results = wikipedia.search(wiki_query, results=2)
            logger.info(f"Wikipedia search results: {search_results}")
            
            if search_results:
                page_title = search_results[0]
                try:
                    summary = wikipedia.summary(page_title, sentences=3)
                    all_results.append({
                        "source": "Wikipedia",
                        "title": f"Wikipedia: {page_title}",
                        "link": f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}",
                        "snippet": summary
                    })
                    logger.info(f"✅ Wikipedia found: {page_title}")
                except wikipedia.exceptions.DisambiguationError as e:
                    # Handle disambiguation by picking the first option
                    if e.options:
                        try:
                            summary = wikipedia.summary(e.options[0], sentences=3)
                            all_results.append({
                                "source": "Wikipedia",
                                "title": f"Wikipedia: {e.options[0]}",
                                "link": f"https://en.wikipedia.org/wiki/{e.options[0].replace(' ', '_')}",
                                "snippet": summary
                            })
                        except Exception:
                            pass
                except wikipedia.exceptions.PageError:
                    logger.warning(f"Wikipedia page not found: {page_title}")
                    
        except Exception as e:
            logger.warning(f"Wikipedia search failed: {e}")
        
        # 2. DUCKDUCKGO (Fallback if Wikipedia didn't find anything)
        if not all_results and self.ddgs:
            try:
                # Try different backends
                backends = ['api', 'html', 'lite']
                for backend in backends:
                    try:
                        results = list(self.ddgs.text(query, max_results=max_results, backend=backend))
                        if results:
                            for res in results:
                                all_results.append({
                                    "source": "DuckDuckGo",
                                    "title": res.get("title", ""),
                                    "link": res.get("href", ""),
                                    "snippet": res.get("body", "")
                                })
                            logger.info(f"✅ DuckDuckGo found {len(results)} results")
                            break
                    except Exception as be:
                        logger.debug(f"DDG backend '{backend}' failed: {be}")
                        continue
            except Exception as e:
                logger.warning(f"DuckDuckGo search failed: {e}")
        
        # Return results
        if not all_results:
            return "No results found for your query. Please try rephrasing."
            
        return json.dumps(all_results, indent=2)



# Standalone execution for testing
if __name__ == "__main__":
    tool = WebSearchTool()
    print(tool.search("who is the current president of america"))
