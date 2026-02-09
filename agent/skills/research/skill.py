from typing import Dict, Any, List
from agent.skills.base_skill import BaseSkill, SkillResult
from agent.tools.web_search import WebSearchTool
from agent.tools.browser_tools import BrowserTools

class ResearchSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "research"

    @property
    def manifest(self):
        from agent.skills.base_skill import SkillManifest
        return SkillManifest(
            name="research",
            version="1.0.0",
            description="Performs deep research using web search and browsing.",
            actions=["search", "browse", "deep_research"],
            permissions=["internet"]
        )

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if skill can handle intent."""
        intent = intent.lower()
        keywords = ["search", "google", "browse", "find info", "research"]
        if any(k in intent for k in keywords):
            return 0.9
        return 0.0

    def __init__(self):
        super().__init__()
        self.search_tool = WebSearchTool()
        self.browser_tools = BrowserTools()

    async def execute(self, action: str, params: Dict[str, Any], context: Dict[str, Any] = None) -> SkillResult:
        if action == "search":
            query = params.get("query")
            results = self.search_tool.search(query)
            return SkillResult(success=True, message=results, data={"results": results})
            
        elif action == "browse":
            url = params.get("url")
            content = await self.browser_tools.read_content(url) # Assuming async
            return SkillResult(success=True, message=content[:2000] + "...", data={"content": content})
            
        elif action == "deep_research":
            return await self._deep_research(params.get("topic"))
            
        else:
            return SkillResult(success=False, error=f"Unknown action: {action}")

    async def _deep_research(self, topic: str) -> SkillResult:
        """
        Multi-step research: Search -> Select Links -> Browse -> Summarize.
        This is a placeholder for the complex logic.
        """
        # 1. Search
        search_res = self.search_tool.search(topic)
        
        # 2. Browse first result (naive)
        # In a real implementation, we'd parse links and visit them.
        summary = f"Research on {topic}:\nBased on search results: {search_res[:500]}..."
        
        return SkillResult(success=True, message=summary)
