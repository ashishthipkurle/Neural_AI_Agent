
import logging
import json
import os
import time
from urllib.parse import quote_plus, urlparse
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
            output_path = params.get('output_path')
            report_path = self.generate_report(report_data, output_path=output_path)
            
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
        """Search DuckDuckGo, visit results visually. Recycles browser page periodically to prevent memory buildup."""
        results = []
        browser = self._get_browser()
        nav_count = 0  # Track navigations for page recycling

        capped_results = max(1, min(max_results, 2))

        for q in queries:
            search_results = self._get_search_results(q, capped_results)

            for r in search_results:
                url = r.get('href')
                title = r.get('title')
                snippet = (r.get('body') or "")[:1200]

                if not url:
                    continue

                if self._is_blocked_research_url(url):
                    self.logger.info(f"Skipping heavy/blocked research URL: {url}")
                    continue

                content = snippet

                # VISUAL & SCRAPE: Visit valid URLs
                if browser:
                    try:
                        # Recycle page every 2 navigations to keep memory low
                        nav_count += 1
                        if nav_count % 2 == 0:
                            try:
                                await browser.execute("recycle_page", {})
                                self.logger.info("Recycled browser page to free memory.")
                            except Exception:
                                pass

                        browse_res = await browser.execute("browse", {"url": url})
                        if not browse_res.success:
                            self.logger.warning(f"Browse failed for {url}: {browse_res.error}")
                            continue

                        # Extract content (Scrape)
                        extract_res = await browser.execute("extract", {"selector": "body"})
                        if extract_res.success and extract_res.data.get('content'):
                            extracted = extract_res.data.get('content') or ""
                            extracted = extracted[:1600]
                            if len(extracted) > len(content):
                                content = extracted
                    except Exception as e:
                        self.logger.warning(f"Failed to visit/scrape {url}: {e}")

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": (content or "")[:1600],
                    "query": q
                })

                # Add delay so user can see each page being visited
                import asyncio
                await asyncio.sleep(1.2)
            
        return results

    def _get_search_results(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Return search results with a crash-safe fallback path.

        DDGS can be unstable under some environments; keep it opt-in and fail-safe.
        """
        use_ddgs = bool(self.config.get("research", {}).get("use_ddgs", False))

        if use_ddgs and DDGS:
            try:
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))
            except Exception as exc:
                self.logger.warning(f"DDGS search failed for '{query}', using fallback search: {exc}")

        return self._fallback_search_results(query, max_results)

    def _fallback_search_results(self, query: str, max_results: int) -> List[Dict[str, str]]:
        encoded = quote_plus(query)
        candidates = [
            {
                "title": f"Google results for {query}",
                "href": f"https://www.google.com/search?q={encoded}",
                "body": f"Search results page for: {query}",
            },
            {
                "title": f"Wikipedia search for {query}",
                "href": f"https://en.wikipedia.org/w/index.php?search={encoded}",
                "body": f"Wikipedia index and related pages for: {query}",
            },
            {
                "title": f"Bing results for {query}",
                "href": f"https://www.bing.com/search?q={encoded}",
                "body": f"Bing results page for: {query}",
            },
        ]
        return candidates[:max_results]

    def _is_blocked_research_url(self, url: str) -> bool:
        blocked_domains = {
            "cnn.com",
            "nbcnews.com",
            "zoominfo.com",
            "rocketreach.co",
        }
        try:
            host = (urlparse(url).netloc or "").lower()
        except Exception:
            return False
        return any(domain in host for domain in blocked_domains)

    def _synthesize_findings(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create executive summary and details."""
        summary = "Synthesized from {} sources.".format(len(sources))
        return {
            "executive_summary": summary,
            "detailed_findings": sources
        }

    def generate_report(self, research_data: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """Markdown report. Save to output_path if provided, otherwise workspace/reports/."""
        if output_path:
            normalized = str(output_path).replace('\\\\', '/').replace('\\', '/')
            path = normalized
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        else:
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
