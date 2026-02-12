import re
import logging
import webbrowser
from typing import Dict, Any, List, Tuple
from agent.tools.os_tools import OSTools

class CommandRouter:
    """
    Routes simple voice commands directly to tools using regex patterns,
    bypassing the heavy LLM inference for speed.
    
    Handles compound commands like "open chrome and search youtube"
    """
    
    def __init__(self):
        self.logger = logging.getLogger("CommandRouter")
        self.os_tools = OSTools()
        
        # Known app names for better extraction
        self.known_apps = [
            "notepad", "calculator", "chrome", "firefox", "edge", 
            "word", "excel", "powerpoint", "outlook", "teams",
            "spotify", "discord", "slack", "vscode", "code",
            "explorer", "file explorer", "terminal", "cmd", "powershell"
        ]
        
        # Known websites (treat as navigation, not app launch)
        self.known_websites = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "facebook": "https://www.facebook.com",
            "twitter": "https://www.twitter.com",
            "instagram": "https://www.instagram.com",
            "github": "https://www.github.com",
            "reddit": "https://www.reddit.com",
            "linkedin": "https://www.linkedin.com",
            "amazon": "https://www.amazon.com",
            "netflix": "https://www.netflix.com",
            "whatsapp": "https://web.whatsapp.com",
            "gmail": "https://mail.google.com",
        }

    def can_handle(self, user_input: str) -> bool:
        """Check if the input matches any known fast patterns."""
        u = user_input.lower().strip()
        
        # EXCEPTION: If input looks like "search X on Y" (browser specific), let IntentParser handle it.
        # This prevents this simple regex router from stealing complex browser-launch intents.
        if "search" in u and (" on " in u or " using " in u):
            return False
        
        # EXCEPTION: Mission mode commands go to SkillRouter
        if "start mission" in u or "mission mode" in u:
            return False
        
        # EXCEPTION: Telegram commands go to ToolRouter/SkillRouter
        if "telegram" in u or "check telegram" in u:
            return False
        
        # EXCEPTION: Compound commands with conversational/complex actions go to LLM
        # e.g. "go to chatgpt and chat with him" — "chat" needs LLM understanding
        if " and " in u and any(k in u for k in ["chat ", "talk ", "ask ", "tell ", "discuss ", "message "]):
            return False
        
        # Check for simple patterns we can handle fast
        if re.search(r"^(open|launch|start)\s+", u):
            return True
        if re.search(r"^(go\s+to|navigate\s+to|visit)\s+", u):
            return True
        if re.search(r"^(search|google)\s+", u):
            return True
            
        return False

    async def execute(self, user_input: str) -> Dict[str, Any]:
        """Execute the command, handling compound commands."""
        u = user_input.lower().strip()
        self.logger.info(f"Fast routing: '{u}'")
        
        # Split compound commands on " and "
        parts = re.split(r'\s+and\s+', u)
        
        results = []
        for part in parts:
            part = part.strip()
            result = await self._execute_single(part)
            results.append(result)
        
        # Combine responses
        if len(results) == 1:
            return results[0]
        else:
            combined_response = " and ".join([r.get("response", "Done") for r in results])
            return {
                "response": combined_response,
                "action_taken": True,
                "results": results
            }

    async def _execute_single(self, command: str) -> Dict[str, Any]:
        """Execute a single command (no 'and' splits)."""
        
        # 1. App Launch: "open notepad", "launch chrome"
        match = re.match(r"^(open|launch|start)\s+(.+)$", command)
        if match:
            target = match.group(2).strip()
            return await self._handle_open(target)
        
        # 2. Navigation: "go to youtube.com"
        match = re.match(r"^(go\s+to|navigate\s+to|visit)\s+(.+)$", command)
        if match:
            url = match.group(2).strip()
            return await self._navigate(url)
        
        # 3. Search: "search python tutorials", "google cats"
        match = re.match(r"^(search|google)\s+(?:for\s+)?(.+)$", command)
        if match:
            query = match.group(2).strip()
            return await self._search(query)
        
        # Fallback - couldn't parse
        return {"response": f"Couldn't parse: {command}", "action_taken": False}

    async def _handle_open(self, target: str) -> Dict[str, Any]:
        """Handle 'open X' command."""
        target_lower = target.lower().strip()
        
        # 1. Check if it's a known website name (e.g., "youtube" -> youtube.com)
        for site_name, site_url in self.known_websites.items():
            if target_lower.startswith(site_name):
                return await self._navigate(site_url)
        
        # 2. Check if target is a URL (contains domain)
        if "." in target and not target.endswith(".exe"):
            return await self._navigate(target)
        
        # 3. It's an app - extract just the app name
        app_name = self._extract_app_name(target)
        
        self.logger.info(f"Opening app: {app_name}")
        try:
            result = self.os_tools.launch_app(app_name)
            return {
                "response": f"Opening {app_name}",
                "action_taken": True,
                "tool_output": result
            }
        except Exception as e:
            self.logger.error(f"Failed to open {app_name}: {e}")
            return {"response": f"Failed to open {app_name}: {e}", "action_taken": False}

    def _extract_app_name(self, target: str) -> str:
        """Extract the actual app name from a phrase."""
        target = target.lower().strip()
        
        # Check for known apps first
        for app in self.known_apps:
            if target.startswith(app):
                return app
        
        # Otherwise, take first word as app name
        words = target.split()
        if words:
            return words[0]
        return target

    async def _navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL."""
        # Resolve known site shorthand names (e.g. "chatgpt" -> "https://chatgpt.com")
        url_lower = url.lower().strip()
        if url_lower in self.known_websites:
            url = self.known_websites[url_lower]
        elif not url.startswith("http"):
            # If it's a bare word with no dots, append .com
            if "." not in url:
                url = "https://www." + url + ".com"
            else:
                url = "https://" + url
            
        self.logger.info(f"Navigating to: {url}")
        try:
            webbrowser.open(url)
            return {
                "response": f"Opening {url}",
                "action_taken": True,
                "tool_output": f"Navigated to {url}"
            }
        except Exception as e:
            return {"response": f"Failed to navigate: {e}", "action_taken": False}

    async def _search(self, query: str) -> Dict[str, Any]:
        """Perform a web search using DuckDuckGo and return summary."""
        # Special case: explicit browser request
        if query.lower().startswith("youtube"):
            url = f"https://www.youtube.com/results?search_query={query.replace('youtube', '').strip().replace(' ', '+')}"
            webbrowser.open(url)
            return {"response": f"Opening YouTube search for {query}", "action_taken": True}
            
        self.logger.info(f"Searching web for: {query}")
        try:
            # Use WebSearchTool for direct answers
            from agent.tools.web_search import WebSearchTool
            tool = WebSearchTool()
            # Get top result execution
            results_json = tool.search(query, max_results=1)
            
            # Simple parsing if it looks like a list
            import json
            try:
                data = json.loads(results_json)
                if isinstance(data, list) and len(data) > 0:
                    snippet = data[0].get('snippet', '')
                    title = data[0].get('title', '')
                    return {
                        "response": f"According to {title}: {snippet}",
                        "action_taken": True,
                        "tool_output": results_json
                    }
            except:
                pass
                
            # Fallback if no clean result
            return {
                "response": f"Here is what I found for {query}: {results_json[:200]}...", 
                "action_taken": True
            }
            
        except Exception as e:
            # Fallback to browser if API fails
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(url)
            return {
                "response": f"I opened a google search for {query}", 
                "action_taken": True
            }
