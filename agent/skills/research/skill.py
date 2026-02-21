
import logging
import json
import os
import re
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
        
        # VISUAL: Show the user what we're researching (fire-and-forget, non-blocking)
        browser = self._get_browser()
        if browser:
            try:
                import asyncio
                # Use DuckDuckGo instead of Google — much lighter page.
                # IMPORTANT: do NOT wrap in a short wait_for timeout; cancelling mid-goto often leaves the window on about:blank.
                search_url = f"https://duckduckgo.com/?q={topic.replace(' ', '+')}"
                task = asyncio.create_task(browser.execute("browse", {"url": search_url}))
                task.add_done_callback(lambda t: None if t.cancelled() else t.exception())
            except Exception:
                pass  # Visual-only — never block research
        
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
            
            # Build rich message so researcher LLM gets actual findings
            summary = report_data.get('executive_summary', 'Research completed.')
            sources = []
            for item in report_data.get('detailed_findings', [])[:5]:
                t = item.get('title', 'Untitled')
                s = (item.get('snippet', '') or '')[:300]
                u = item.get('url', '')
                sources.append(f"- {t}: {s} ({u})")
            sources_text = "\n".join(sources) if sources else "No sources found."
            
            rich_msg = f"Research on '{topic}':\n\n{summary}\n\nKey sources:\n{sources_text}"
            
            return SkillResult(
                success=True,
                data={
                    "status": "completed",
                    "report_path": report_path,
                    "summary": summary
                },
                message=rich_msg
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
        import asyncio
        results = []
        browser = self._get_browser()
        nav_count = 0  # Track navigations for page recycling

        visualize = bool(self.config.get("research", {}).get("visualize_browser", True))

        capped_results = 1  # 1 per query × 3 queries = 3 total (fast enough for 90s timeout)

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

                # Skip browser scraping if DDGS already gave a good snippet
                is_search_page = self._is_search_page_url(url)
                has_good_snippet = len(content) > 200

                # VISUAL: Optionally visit URLs so the user can see the agent browsing.
                # SCRAPE: Only extract content if the snippet is weak (keeps runtime reasonable).
                if browser and not is_search_page and (visualize or not has_good_snippet):
                    try:
                        # Recycle page every 2 navigations to keep memory low
                        nav_count += 1
                        if nav_count % 2 == 0:
                            try:
                                await browser.execute("recycle_page", {})
                            except Exception:
                                pass

                        # Allow more time for the first visible navigation (Playwright startup + first page load).
                        # Use a shorter timeout when we're only visualizing (not scraping).
                        browse_timeout = 20 if not has_good_snippet else 12
                        browse_res = await asyncio.wait_for(browser.execute("browse", {"url": url}), timeout=browse_timeout)
                        if not browse_res.success:
                            self.logger.warning(f"Browse failed for {url}")
                        elif not has_good_snippet:
                            # Try content-focused selectors first, fall back to body
                            extracted = ""
                            for sel in ["article", "main", ".content", "#content", "body"]:
                                try:
                                    extract_res = await asyncio.wait_for(
                                        browser.execute("extract", {"selector": sel}), timeout=8
                                    )
                                    if extract_res.success and extract_res.data.get('content'):
                                        candidate = (extract_res.data.get('content') or "").strip()
                                        if len(candidate) > 100:
                                            extracted = candidate
                                            break
                                except Exception:
                                    continue

                            if extracted:
                                cleaned = self._clean_scraped_text(extracted)
                                if len(cleaned) > len(content):
                                    content = cleaned[:2000]
                    except Exception as e:
                        self.logger.warning(f"Failed to visit/scrape {url}: {e}")

                # Always clean the final content
                content = self._clean_scraped_text(content or "")

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": content[:2000],
                    "query": q
                })

                # Add delay so user can see each page being visited
                await asyncio.sleep(1.2)
            
        return results

    def _get_search_results(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Return search results with a crash-safe fallback path.

        DDGS is the preferred path (returns actual article URLs with snippets).
        Fallback returns search page URLs which skip browser scraping.
        """
        # DDGS enabled by default — it returns actual article URLs
        use_ddgs = bool(self.config.get("research", {}).get("use_ddgs", True))

        if use_ddgs and DDGS:
            try:
                # Fix Windows charmap encoding crash
                os.environ.setdefault("PYTHONIOENCODING", "utf-8")
                ddgs = DDGS()
                raw = ddgs.text(query, max_results=max_results)
                # Sanitize results to avoid encoding issues downstream
                results = []
                for item in raw:
                    clean = {}
                    for k, v in item.items():
                        if isinstance(v, str):
                            clean[k] = v.encode('utf-8', errors='replace').decode('utf-8')
                        else:
                            clean[k] = v
                    results.append(clean)
                if results:
                    self.logger.info(f"DDGS returned {len(results)} results for '{query}'")
                    return results
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

    def _is_search_page_url(self, url: str) -> bool:
        """Detect search engine result pages that crash the browser."""
        try:
            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
            path = (parsed.path or "").lower()
            # Google search pages
            if "google.com" in host and "/search" in path:
                return True
            # Wikipedia search pages
            if "wikipedia.org" in host and "search=" in (parsed.query or ""):
                return True
            # Bing search pages
            if "bing.com" in host and "/search" in path:
                return True
        except Exception:
            pass
        return False

    def _clean_scraped_text(self, text: str) -> str:
        """Remove navigation chrome, menus, accessibility text, and other page noise."""
        if not text:
            return ""

        # Lines/phrases to strip entirely
        noise_patterns = [
            r"^\s*Accessibility links\s*$",
            r"^\s*Skip to main content\s*$",
            r"^\s*Accessibility help\s*$",
            r"^\s*Accessibility feedback\s*$",
            r"^\s*Sign in\s*$",
            r"^\s*Filters and topics\s*$",
            r"^\s*AI Mode\s*$",
            r"^\s*Search Results\s*$",
            r"^\s*AI overview\s*$",
            r"^\s*Thinking\s*$",
            r"^\s*Feedback\s*$",
            r"^\s*View all\s*$",
            r"^\s*People also ask\s*$",
            r"^\s*More\s*$",
            r"^\s*Read more\s*$",
            r"^\s*Jump to content\s*$",
            r"^\s*Main menu\s*$",
            r"^\s*Create account\s*$",
            r"^\s*Log in\s*$",
            r"^\s*Donate\s*$",
            r"^\s*Search results\s*$",
            r"^\s*Help\s*$",
            r"^\s*Tools\s*$",
            r"^\s*Appearance hide\s*$",
            r"^\s*Search\s*$",
            r"^\s*\d+ items\s*$",  # "20 items", "50 items"
            r"^\s*Text\s*$",
            r"^\s*Small\s*$",
            r"^\s*Standard\s*$",
            r"^\s*Large\s*$",
            r"^\s*Wide\s*$",
            r"^\s*Color \(beta\)\s*$",
            r"^\s*Automatic\s*$",
            r"^\s*Light\s*$",
            r"^\s*Dark\s*$",
            r"^\s*Width\s*$",
            r"^\s*Advanced search:\s*$",
            r"^\s*Search in:\s*$",
            r"^\s*\(Article\)\s*$",
            r"^\s*Missing:.*\| Show results with:.*$",
        ]

        # Inline noise substrings to remove
        inline_noise = [
            "This page always uses small font size",
        ]

        # Tab-separated navigation lines (e.g.  "All\tImages\tVideos\tShopping")
        nav_tab_pattern = re.compile(
            r"^\s*(All|Images|Videos|Short videos|Shopping|Forums|News|More)"
            r"(\t|\s{2,})(All|Images|Videos|Short videos|Shopping|Forums|News|More)",
            re.IGNORECASE
        )

        compiled_noise = [re.compile(p, re.IGNORECASE) for p in noise_patterns]

        lines = text.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                # Collapse blank lines: only add if previous wasn't blank
                if cleaned and cleaned[-1] != "":
                    cleaned.append("")
                continue

            # Skip noise patterns
            if any(pat.match(stripped) for pat in compiled_noise):
                continue

            # Skip tab-nav lines
            if nav_tab_pattern.match(stripped):
                continue

            # Remove inline noise
            for noise in inline_noise:
                stripped = stripped.replace(noise, "")

            # Skip very short orphan lines (likely UI fragments)
            if len(stripped) < 4 and not stripped[0].isdigit():
                continue

            cleaned.append(stripped)

        result = "\n".join(cleaned).strip()
        # Remove leading/trailing blank lines
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result

    def _synthesize_findings(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create executive summary grouped by query topic."""
        if not sources:
            return {
                "executive_summary": "No relevant sources were found.",
                "detailed_findings": [],
                "source_count": 0
            }

        # Group findings by query
        grouped: Dict[str, List[Dict]] = {}
        for src in sources:
            q = src.get("query", "General")
            grouped.setdefault(q, []).append(src)

        # Build summary with key points from each source
        summary_parts = [f"Research synthesized from {len(sources)} sources across {len(grouped)} topic(s).\n"]
        for query, items in grouped.items():
            summary_parts.append(f"**{query}**: {len(items)} source(s) found.")
            for item in items:
                title = item.get('title', 'Untitled')
                snippet = item.get('snippet', '')
                # Extract first meaningful sentence as key point
                sentences = [s.strip() for s in snippet.split('.') if len(s.strip()) > 30]
                key_point = (sentences[0] + '.') if sentences else snippet[:150]
                summary_parts.append(f"  - {title}: {key_point}")

        return {
            "executive_summary": "\n".join(summary_parts),
            "detailed_findings": sources,
            "grouped_findings": grouped,
            "source_count": len(sources)
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

        content = "# Research Report\n\n"
        content += f"## Executive Summary\n\n{research_data.get('executive_summary', 'No summary available.')}\n\n"

        # Use grouped findings for structured output
        grouped = research_data.get("grouped_findings", {})
        if grouped:
            content += "---\n\n## Detailed Findings\n\n"
            for query, items in grouped.items():
                content += f"### {query}\n\n"
                for i, item in enumerate(items, 1):
                    title = item.get('title', 'Untitled')
                    url = item.get('url', '')
                    snippet = item.get('snippet', 'No content available.')
                    content += f"**{i}. [{title}]({url})**\n\n"
                    content += f"{snippet}\n\n"
                content += "---\n\n"
        else:
            # Fallback: flat list
            content += "## Findings\n\n"
            for i, item in enumerate(research_data.get('detailed_findings', []), 1):
                title = item.get('title', 'Untitled')
                url = item.get('url', '')
                snippet = item.get('snippet', 'No content available.')
                content += f"**{i}. [{title}]({url})**\n\n"
                content += f"{snippet}\n\n"

        content += f"\n*Report generated on {time.strftime('%Y-%m-%d %H:%M:%S')}*\n"

        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return path
        except Exception as e:
            self.logger.error(f"Failed to write report: {e}")
            return ""
