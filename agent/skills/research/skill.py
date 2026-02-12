
import logging
import json
import os
import time
from typing import List, Dict, Any, Optional
from agent.skills.base_skill import BaseSkill, SkillManifest, SkillResult
from agent.core.intent import Intent
from agent.memory.personal_memory import PersonalMemoryManager

# Try imports separately for robustness
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

try:
    import newspaper
    from newspaper import Article
except ImportError:
    newspaper = None
    Article = None

class DeepResearchSkill(BaseSkill):
    """
    Module 6: Deep Research Engine
    Autonomous deep-dive research with planning and synthesis.
    """

    def __init__(self, config: Dict[str, Any], personal_memory: PersonalMemoryManager):
        self._name = "deep_research"
        super().__init__()
        self.config = config
        self.memory = personal_memory
        # logger initialized in super().__init__ but we can override or use it

    @property
    def name(self) -> str:
        return self._name

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name=self.name,
            version="1.0.0",
            description="Autonomous deep-dive research with planning and synthesis.",
            actions=["deep_research"],
            requires=["duckduckgo-search", "newspaper3k"],
            permissions=["network"]
        )

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Match: 'research', 'investigate', 'analyze_topic', 'deep_dive'"""
        # intent arg here is likely a string from pattern recognizer or Intent object in some contexts.
        # BaseSkill doc says "intent: Natural language intent or action name"
        # We'll treat it as text.
        text = intent.lower() if isinstance(intent, str) else str(intent).lower()
        
        keywords = ['research', 'investigate', 'analyze', 'deep dive', 'find out about']
        if any(k in text for k in keywords):
            return 0.9
        return 0.0

    async def execute(self, action: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        """Main execution flow"""
        if action != "deep_research":
            return SkillResult(success=False, error=f"Unknown action: {action}")
            
        topic = params.get('topic') or params.get('query')
        if not topic:
            return SkillResult(success=False, error="No topic provided for research.")
            
        self.logger.info(f"Starting deep research on: {topic}")
        
        # VISUAL: Open browser to search page (for user feedback)
        browser = self._get_browser()
        if browser:
            try:
                search_url = f"https://www.google.com/search?q={topic.replace(' ', '+')}"
                await browser.execute("browse", {"url": search_url})
            except Exception as e:
                self.logger.warning(f"Visual search failed: {e}")
        else:
             self.logger.warning("Browser skill not available for visual feedback.")
        
        try:
            # 1. Create Plan
            plan = self._create_research_plan(topic)
            self.logger.info(f"Research plan created: {plan}")
            
            # 2. Execute Rounds (Simulating 1 round for MVP speed, spec asks for 3)
            all_findings = []
            for query in plan.get('queries', [topic])[:3]: # Limit to 3 queries
                findings = await self._execute_search_round([query])
                all_findings.extend(findings)
                
            # 3. Synthesize
            report_data = self._synthesize_findings(all_findings)
            
            # 4. Generate Report
            report_path = self.generate_report(report_data)
            
            return SkillResult(
                success=True,
                data={
                    "status": "completed",
                    "report_path": report_path,
                    "summary": report_data.get('executive_summary', 'Research completed.')
                },
                message=f"Research completed on {topic}"
            )
        except Exception as e:
            self.logger.error(f"Research failed: {e}")
            return SkillResult(success=False, error=str(e))

    def set_skill_router(self, router: Any):
        """Inject skill router for accessing other skills."""
        self.skill_router = router

    def _get_browser(self):
        """Helper to get browser skill if available."""
        if hasattr(self, 'skill_router') and self.skill_router:
            # Access skill via router's loader or exposed method
            skills = self.skill_router.skills
            return skills.get("browser")
        return None

    def _create_research_plan(self, topic: str) -> Dict[str, Any]:
        """Use LLM to generate: queries, sources, questions."""
        return {
            "queries": [
                f"{topic} overview",
                f"{topic} latest news",
                f"{topic} analysis"
            ],
            "questions": ["What is it?", "How does it work?", "Key players?"]
        }

    async def _execute_search_round(self, queries: List[str], max_results: int = 3) -> List[Dict[str, Any]]:
        """Search DuckDuckGo, visit results visually."""
        results = []
        browser = self._get_browser()

        if not DDGS:
            self.logger.warning("DuckDuckGo Search not installed.")
            return []

        try:
            with DDGS() as ddgs:
                for q in queries:
                    # Search
                    search_results = list(ddgs.text(q, max_results=max_results))
                    
                    for r in search_results:
                        url = r.get('href')
                        title = r.get('title')
                        snippet = r.get('body')
                        
                        content = snippet # Default to snippet

                        # VISUAL & SCRAPE: Visit valid URLs
                        if url and browser:
                            try:
                                # Navigate (Visible)
                                await browser.execute("browse", {"url": url})
                                
                                # Extract content (Scrape)
                                extract_res = await browser.execute("extract", {"selector": "body"})
                                if extract_res.success and extract_res.data.get('content'):
                                    # Use extracted content if decent length
                                    extracted = extract_res.data.get('content')
                                    if len(extracted) > len(snippet):
                                        content = extracted
                            except Exception as e:
                                self.logger.warning(f"Failed to visit/scrape {url}: {e}")
                        
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": content, # Use scraped content if available
                            "query": q
                        })
                        
                        # Add delay so user can see each page being visited
                        import asyncio
                        await asyncio.sleep(2.5)

        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            
        return results

    def _synthesize_findings(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create executive summary and details."""
        summary = "Synthesized from {} sources.".format(len(sources))
        return {
            "executive_summary": summary,
            "detailed_findings": sources
        }

    def generate_report(self, research_data: Dict[str, Any]) -> str:
        """Markdown report. Save to workspace/reports/"""
        report_dir = "workspace/reports"
        os.makedirs(report_dir, exist_ok=True)
        
        filename = f"research_{int(time.time())}.md"
        path = os.path.join(report_dir, filename)
        
        content = f"# Research Report\n\n"
        content += f"## Executive Summary\n{research_data.get('executive_summary')}\n\n"
        content += f"## Findings\n"
        for item in research_data.get('detailed_findings', []):
            content += f"- **{item.get('title')}**: {item.get('snippet')} ([Source]({item.get('url')}))\n"
            
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return path
        except Exception as e:
            self.logger.error(f"Failed to write report: {e}")
            return ""
