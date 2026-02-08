"""
Browser Skill - Deep browser automation with Playwright.

This version uses a HYBRID approach:
- Playwright runs in a THREAD POOL (sync API) to avoid Windows asyncio subprocess issues
- Skill interface is async for compatibility with the rest of the system

IMPORTANT: This skill manages its own Playwright instance.
The router calls this skill, NOT individual browser tools.
"""

import os
import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth


@dataclass
class BrowserSession:
    """Represents a browser session with context."""
    name: str
    profile_path: Path
    context: Any  # BrowserContext
    page: Any  # Page
    

class BrowserSkill(BaseSkill):
    """
    Deep browser automation skill using Playwright (thread pool hybrid).
    
    Actions:
    - navigate: Go to URL
    - click: Click element by selector
    - fill: Fill form field
    - type: Type text (with keyboard simulation)
    - scrape: Extract content from page
    - scrape_table: Extract table as structured data
    - screenshot: Capture page
    - login: Handle login flow
    - download: Download file
    - wait: Wait for element/condition
    - scroll: Scroll page
    - run_script: Execute JavaScript
    """
    
    PROFILE_DIR = Path("agent/data/browser/profiles")
    
    # AI Platform configurations for AI-to-AI research
    AI_PLATFORMS = {
        "chat.openai.com": {
            "name": "ChatGPT",
            "input_selector": "#prompt-textarea, textarea[placeholder*='Message']",
            "submit_selector": "button[data-testid='send-button'], button[aria-label*='Send']",
            "response_selector": "div[data-message-author-role='assistant'], .agent-turn",
            "wait_indicator": "button[aria-label='Stop generating']"
        },
        "chatgpt.com": {
            "name": "ChatGPT",
            "input_selector": "#prompt-textarea, textarea[placeholder*='Message']",
            "submit_selector": "button[data-testid='send-button'], button[aria-label*='Send']",
            "response_selector": "div[data-message-author-role='assistant'], .agent-turn",
            "wait_indicator": "button[aria-label='Stop generating']"
        },
        "gemini.google.com": {
            "name": "Gemini",
            "input_selector": "div[role='textbox'], rich-textarea, div[contenteditable='true']",
            "submit_selector": "button[aria-label*='Send'], button.send-button, mat-icon[data-mat-icon-name='send']",
            "response_selector": ".model-response-text, .response-container, message-content",
            "wait_indicator": ".loading-indicator, .running-indicator"
        },
        "claude.ai": {
            "name": "Claude",
            "input_selector": "div[contenteditable='true'], textarea",
            "submit_selector": "button[aria-label*='Send'], button.send-button",
            "response_selector": ".claude-response, div[data-role='assistant'], .font-claude-message",
            "wait_indicator": ".generating-indicator"
        },
        "poe.com": {
            "name": "Poe",
            "input_selector": "textarea[placeholder*='Message'], div[class*='ChatMessageInput']",
            "submit_selector": "button[aria-label='Send'], button[class*='ChatMessageInput']",
            "response_selector": ".ChatMessage_botMessageBubble, div[class*='Message_botMessage']",
            "wait_indicator": ".ChatMessage_loading"
        },
        # Marketing domains that should redirect to app
        "openai.com": {
            "name": "ChatGPT",
            "redirect_url": "https://chatgpt.com",
            # Inherit selectors from chatgpt.com
            "input_selector": "#prompt-textarea, textarea[placeholder*='Message']",
            "submit_selector": "button[data-testid='send-button'], button[aria-label*='Send']",
            "response_selector": "div[data-message-author-role='assistant'], .agent-turn",
            "wait_indicator": "button[aria-label='Stop generating']"
        },
        "anthropic.com": {
            "name": "Claude",
            "redirect_url": "https://claude.ai",
            # Inherit from claude.ai
            "input_selector": "div[contenteditable='true'], textarea",
            "submit_selector": "button[aria-label*='Send'], button.send-button",
            "response_selector": ".claude-response, div[data-role='assistant']",
            "wait_indicator": ".generating-indicator"
        },
        "ai.google": {
            "name": "Gemini",
            "redirect_url": "https://gemini.google.com",
            "input_selector": "div[role='textbox'], rich-textarea",
            "submit_selector": "button[aria-label*='Send']",
            "response_selector": ".model-response-text",
            "wait_indicator": ".loading-indicator"
        },
        "deepmind.google": {
            "name": "Gemini",
            "redirect_url": "https://gemini.google.com",
            "input_selector": "div[role='textbox'], rich-textarea",
            "submit_selector": "button[aria-label*='Send']",
            "response_selector": ".model-response-text",
            "wait_indicator": ".loading-indicator"
        },
        # Additional AI Platforms
        "perplexity.ai": {
            "name": "Perplexity",
            "input_selector": "textarea[placeholder*='Ask'], textarea",
            "submit_selector": "button[aria-label*='Submit'], button[aria-label*='Send']",
            "response_selector": "div[class*='prose'], div[class*='Answer']",
            "wait_indicator": "div[class*='animate-pulse']"
        },
        "copilot.microsoft.com": {
            "name": "Copilot",
            "input_selector": "#searchbox, textarea[aria-label*='Ask'], div[role='textbox']",
            "submit_selector": "button[aria-label*='Submit'], button[aria-label*='Send']",
            "response_selector": ".message-content, div[class*='ac-textBlock']",
            "wait_indicator": ".typing-indicator"
        },
        "bing.com": {
            "name": "Copilot",
            "redirect_url": "https://copilot.microsoft.com",
            "input_selector": "#searchbox",
            "submit_selector": "button[aria-label*='Submit']",
            "response_selector": ".message-content",
            "wait_indicator": ".typing-indicator"
        },
        "chat.deepseek.com": {
            "name": "DeepSeek",
            "input_selector": "textarea",
            "submit_selector": "div[role='button']",
            "response_selector": ".markdown-body",
            "wait_indicator": ".status-text"
        },
        "chat.mistral.ai": {
            "name": "Mistral",
            "input_selector": "textarea",
            "submit_selector": "button[type='submit']",
            "response_selector": "div[class*='prose']",
            "wait_indicator": "div[class*='animate-pulse']"
        },
        "huggingface.co": {
            "name": "HuggingChat",
            "input_selector": "textarea",
            "submit_selector": "button[type='submit']",
            "response_selector": "div[class*='prose']",
            "wait_indicator": "div[class*='typing']"
        },
        "meta.ai": {
            "name": "Meta AI",
            "input_selector": "textarea, div[role='textbox']",
            "submit_selector": "button[aria-label*='Send']",
            "response_selector": "div[class*='markdown'], div[dir='auto']",
            "wait_indicator": "div[role='progressbar']"
        }
    }
    
    def __init__(self):
        super().__init__()
        self._playwright = None
        self._browser = None
        self._sessions: Dict[str, BrowserSession] = {}
        self._current_session: Optional[str] = None
        self._initialized = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")
    
    @property
    def name(self) -> str:
        return "browser"
    
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="browser",
            version="2.1.0",  # Thread pool hybrid version
            description="Deep browser automation with persistent sessions",
            actions=[
                "navigate", "click", "fill", "type", "scrape", "scrape_table",
                "screenshot", "login", "download", "wait", "scroll", "run_script",
                "new_session", "switch_session", "close_session", "google_search", "deep_research"
            ],
            requires=["playwright"],
            permissions=["network", "cookies", "filesystem"]
        )
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """Mark skill as loaded - actual browser init happens lazily on first use."""
        super().on_load()
        self.logger.info("Browser skill loaded (thread pool hybrid, lazy init).")
    
    def _sync_initialize(self) -> bool:
        """Initialize Playwright synchronously (runs in thread pool)."""
        try:
            from playwright.sync_api import sync_playwright
            
            self._playwright = sync_playwright().start()
            
            # Launch browser
            self._browser = self._playwright.chromium.launch(
                headless=False,  # Set to True for production
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            # Ensure profile directories exist
            self.PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            
            # Create default session
            self._sync_create_session("default")
            
            self._initialized = True
            self._health = SkillHealth.READY
            self.logger.info("Browser skill initialized with Playwright (thread pool).")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize browser skill: {e}")
            self._health = SkillHealth.UNAVAILABLE
            return False
    
    async def _ensure_initialized(self) -> bool:
        """Lazily initialize Playwright on first use."""
        if self._initialized:
            return True
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._sync_initialize)
    
    def on_unload(self) -> None:
        """Cleanup browser and save session states."""
        try:
            self._sync_cleanup()
        except Exception as e:
            self.logger.error(f"Error during browser cleanup: {e}")
        
        self._executor.shutdown(wait=False)
        super().on_unload()
    
    def _sync_cleanup(self) -> None:
        """Synchronous cleanup of browser resources."""
        try:
            # Save all session cookies
            for session in self._sessions.values():
                self._sync_save_session_state(session)
                session.context.close()
            
            if self._browser:
                self._browser.close()
            
            if self._playwright:
                self._playwright.stop()
            
        except Exception as e:
            self.logger.error(f"Error during browser cleanup: {e}")
    
    # ==================== INTENT MATCHING ====================
    
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill can handle the intent."""
        intent_lower = intent.lower()
        
        # High confidence patterns
        high_patterns = [
            "open website", "go to", "navigate to", "browse",
            "click on", "fill form", "fill out",
            "login to", "log in to", "sign in",
            "scrape", "extract from", "download from",
            "search on", "read page"
        ]
        
        for pattern in high_patterns:
            if pattern in intent_lower:
                return 0.9
        
        # Medium confidence
        medium_patterns = ["website", "webpage", "browser", "online", "web"]
        for pattern in medium_patterns:
            if pattern in intent_lower:
                return 0.6
        
        # Check for URL patterns
        if any(x in intent_lower for x in [".com", ".org", ".net", "http", "www"]):
            return 0.85
        
        return 0.0
    
    # ==================== EXECUTION ====================
    
    async def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Execute a browser action (async wrapper around sync operations)."""
        
        # Ensure browser is initialized
        if not await self._ensure_initialized():
            return SkillResult(success=False, error="Browser not initialized")
        
        # Route to appropriate handler
        handlers = {
            "navigate": self._sync_action_navigate,
            "click": self._sync_action_click,
            "fill": self._sync_action_fill,
            "type": self._sync_action_type,
            "scrape": self._sync_action_scrape,
            "scrape_table": self._sync_action_scrape_table,
            "screenshot": self._sync_action_screenshot,
            "login": self._sync_action_login,
            "google_search": self._sync_action_google_search,
            "download": self._sync_action_download,
            "wait": self._sync_action_wait,
            "scroll": self._sync_action_scroll,
            "run_script": self._sync_action_run_script,
            "new_session": self._sync_action_new_session,
            "switch_session": self._sync_action_switch_session,
            "close_session": self._sync_action_close_session,
            "deep_research": self._sync_action_deep_research,
        }
        
        handler = handlers.get(action)
        if not handler:
            # Try to interpret natural language as an action
            handler = self._interpret_action(action)
            if not handler:
                return SkillResult(success=False, error=f"Unknown action: {action}")
        
        try:
            # Run sync handler in thread pool
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self._executor, 
                handler, 
                params, 
                context or {}
            )
        except Exception as e:
            self.logger.error(f"Browser action '{action}' failed: {e}")
            return SkillResult(success=False, error=str(e))
    
    def _interpret_action(self, intent: str):
        """Try to interpret natural language intent as an action."""
        intent_lower = intent.lower()
        
        if any(x in intent_lower for x in ["go to", "open", "navigate"]):
            return self._sync_action_navigate
        if "click" in intent_lower:
            return self._sync_action_click
        if any(x in intent_lower for x in ["fill", "type", "enter"]):
            return self._sync_action_fill
        if any(x in intent_lower for x in ["scrape", "extract", "read", "get content"]):
            return self._sync_action_scrape
        if "screenshot" in intent_lower:
            return self._sync_action_screenshot
        if any(x in intent_lower for x in ["login", "log in", "sign in"]):
            return self._sync_action_login
        
        return None
    
    # ==================== SYNC ACTIONS (run in thread pool) ====================
    
    def _get_current_page(self) -> Any:
        """Get the current page from active session."""
        if not self._current_session or self._current_session not in self._sessions:
            raise ValueError("No active browser session")
        return self._sessions[self._current_session].page
    
    def _sync_action_navigate(self, params: Dict, context: Dict) -> SkillResult:
        """Navigate to a URL."""
        url = params.get("url")
        if not url:
            # Try to extract URL from natural language
            for key in ["to", "site", "website", "page"]:
                if key in params:
                    url = params[key]
                    break
        
        if not url:
            return SkillResult(success=False, error="URL required")
        
        if not url.startswith("http"):
            url = f"https://{url}"
        
        page = self._get_current_page()
        page.goto(url, wait_until="domcontentloaded")
        
        return SkillResult(
            success=True, 
            data={"url": url, "title": page.title()},
            message=f"Navigated to {url}"
        )
    
    def _sync_action_click(self, params: Dict, context: Dict) -> SkillResult:
        """Click an element."""
        selector = params.get("selector")
        text = params.get("text")
        
        page = self._get_current_page()
        
        if selector:
            page.click(selector)
        elif text:
            # Click by text content
            page.get_by_text(text).click()
        else:
            return SkillResult(success=False, error="Selector or text required")
        
        return SkillResult(success=True, message=f"Clicked: {selector or text}")
    
    def _sync_action_fill(self, params: Dict, context: Dict) -> SkillResult:
        """Fill a form field."""
        selector = params.get("selector")
        label = params.get("label")
        value = params.get("value", "")
        
        page = self._get_current_page()
        
        if selector:
            page.fill(selector, value)
        elif label:
            page.get_by_label(label).fill(value)
        else:
            return SkillResult(success=False, error="Selector or label required")
        
        return SkillResult(success=True, message=f"Filled field with: {value[:20]}...")
    
    def _sync_action_type(self, params: Dict, context: Dict) -> SkillResult:
        """Type text with keyboard simulation."""
        text = params.get("text", "")
        selector = params.get("selector")
        
        page = self._get_current_page()
        
        if selector:
            page.click(selector)
        
        page.keyboard.type(text)
        
        return SkillResult(success=True, message=f"Typed: {text[:20]}...")
    
    def _sync_action_scrape(self, params: Dict, context: Dict) -> SkillResult:
        """Scrape main content from page, filtering navigation/footer junk."""
        selector = params.get("selector", "body")
        attribute = params.get("attribute", "innerText")
        clean = params.get("clean", True)  # Default to cleaning junk
        
        page = self._get_current_page()
        
        if clean and attribute == "innerText":
            # Use JavaScript to extract only main content, removing junk
            content = page.evaluate("""
                () => {
                    // Helper to clean text
                    function cleanText(text) {
                        if (!text) return '';
                        // Remove excessive newlines (3+ becomes 2)
                        text = text.replace(/\\n{3,}/g, '\\n\\n');
                        // Remove lines with only whitespace
                        text = text.replace(/^\\s*$/gm, '');
                        // Remove excessive spaces
                        text = text.replace(/[ \\t]+/g, ' ');
                        // Trim each line
                        text = text.split('\\n').map(l => l.trim()).join('\\n');
                        // Clean up multiple blank lines again
                        text = text.replace(/\\n{3,}/g, '\\n\\n');
                        return text.trim();
                    }
                    
                    // Clone body to avoid modifying the actual page
                    const clone = document.body.cloneNode(true);
                    
                    // Remove navigation, headers, footers, sidebars, ads, etc.
                    const junkSelectors = [
                        'nav', 'header', 'footer', 'aside',
                        '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]',
                        '.nav', '.navbar', '.navigation', '.menu', '.header', '.footer',
                        '.sidebar', '.side-bar', '.advertisement', '.ad', '.ads',
                        '.cookie-banner', '.cookie-notice', '.popup', '.modal',
                        '.social-share', '.share-buttons', '.social-links',
                        '.comments', '.comment-section', '#comments',
                        '.related-posts', '.related-articles', '.recommended',
                        '.newsletter', '.subscribe', '.signup',
                        '[class*="footer"]', '[class*="header"]', '[class*="nav"]',
                        '[id*="footer"]', '[id*="header"]', '[id*="nav"]',
                        'script', 'style', 'noscript', 'iframe', 'svg',
                    ];
                    
                    junkSelectors.forEach(sel => {
                        clone.querySelectorAll(sel).forEach(el => el.remove());
                    });
                    
                    // Try to find main content container
                    const mainSelectors = ['main', 'article', '[role="main"]', '.content', '.post', '.entry', '#content', '#main'];
                    for (let sel of mainSelectors) {
                        const main = clone.querySelector(sel);
                        if (main && main.innerText.trim().length > 200) {
                            return cleanText(main.innerText);
                        }
                    }
                    
                    // Fallback: get cleaned body text
                    return cleanText(clone.innerText);
                }
            """)
        elif attribute == "innerText":
            content = page.inner_text(selector)
        elif attribute == "innerHTML":
            content = page.inner_html(selector)
        else:
            element = page.query_selector(selector)
            content = element.get_attribute(attribute) if element else None
        
        return SkillResult(
            success=True, 
            data={"content": content, "selector": selector},
            message=f"Scraped {len(content) if content else 0} characters"
        )
    
    def _sync_action_scrape_table(self, params: Dict, context: Dict) -> SkillResult:
        """Scrape a table as structured data."""
        selector = params.get("selector", "table")
        
        page = self._get_current_page()
        
        # Use JavaScript to extract table
        table_data = page.evaluate(f"""
            (() => {{
                const table = document.querySelector('{selector}');
                if (!table) return null;
                
                const rows = [];
                const headers = [];
                
                // Get headers
                table.querySelectorAll('th').forEach(th => {{
                    headers.push(th.innerText.trim());
                }});
                
                // Get rows
                table.querySelectorAll('tr').forEach(tr => {{
                    const cells = [];
                    tr.querySelectorAll('td').forEach(td => {{
                        cells.push(td.innerText.trim());
                    }});
                    if (cells.length > 0) rows.push(cells);
                }});
                
                return {{ headers, rows }};
            }})()
        """)
        
        if not table_data:
            return SkillResult(success=False, error="Table not found")
        
        return SkillResult(
            success=True,
            data=table_data,
            message=f"Extracted {len(table_data.get('rows', []))} rows"
        )
    
    def _sync_action_screenshot(self, params: Dict, context: Dict) -> SkillResult:
        """Take a screenshot."""
        import time
        path = params.get("path", f"agent/data/browser/screenshots/screenshot_{int(time.time())}.png")
        full_page = params.get("full_page", False)
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        page = self._get_current_page()
        page.screenshot(path=path, full_page=full_page)
        
        return SkillResult(
            success=True,
            data={"path": path},
            message=f"Screenshot saved to {path}"
        )
    
    def _sync_action_login(self, params: Dict, context: Dict) -> SkillResult:
        """Handle login flow."""
        url = params.get("url")
        username = params.get("username")
        password = params.get("password")
        
        if not url or not username or not password:
            return SkillResult(success=False, error="URL, username, and password required")
        
        page = self._get_current_page()
        page.goto(url)
        
        # Smart field detection
        page.fill("input[type=email], input[name=email], input[name=username]", username)
        page.fill("input[type=password], input[name=password]", password)
        page.click("button[type=submit], input[type=submit]")
        
        # Wait for navigation
        page.wait_for_load_state("networkidle")
        
        return SkillResult(success=True, message="Login submitted")
    
    def _detect_ai_platform(self, url: str) -> Optional[Dict]:
        """
        Detect if a URL belongs to an AI chatbot platform.
        Returns the platform config if detected, None otherwise.
        """
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            
            for platform_domain, config in self.AI_PLATFORMS.items():
                if platform_domain in domain:
                    return config
        except:
            pass
        return None
    
    def _sync_consult_ai_platform(self, page: Any, platform_config: Dict, query: str) -> Optional[str]:
        """
        Interact with an AI chatbot platform to ask a question and get a response.
        
        Args:
            page: Playwright page object
            platform_config: Dict with selectors for the platform
            query: Question to ask the AI
            
        Returns:
            The AI's response text, or None if failed
        """
        import time
        platform_name = platform_config.get("name", "AI")
        
        try:
            self.logger.info(f"Consulting {platform_name} with query: {query[:50]}...")
            
            # Find the input field
            input_selector = platform_config.get("input_selector")
            submit_selector = platform_config.get("submit_selector")
            response_selector = platform_config.get("response_selector")
            
            # Try to find and click the input
            try:
                input_elem = page.locator(input_selector).first
                input_elem.click()
                time.sleep(0.5)
            except Exception as e:
                self.logger.warning(f"Could not find input on {platform_name}: {e}")
                return None
            
            # Type the query
            try:
                # Clear any existing text and type new query
                input_elem.fill("")
                time.sleep(0.2)
                
                # Format the query for AI consultation
                ai_query = f"Please provide a comprehensive, factual summary about: {query}. Include key facts, important details, and cite sources if possible."
                input_elem.type(ai_query, delay=20)
                time.sleep(0.5)
            except Exception as e:
                self.logger.warning(f"Could not type query on {platform_name}: {e}")
                return None
            
            # Click submit
            try:
                submit_btn = page.locator(submit_selector).first
                submit_btn.click()
            except Exception as e:
                # Try pressing Enter as fallback
                self.logger.info(f"Submit button failed, pressing Enter: {e}")
                page.keyboard.press("Enter")
            
            # Wait for response to generate
            self.logger.info(f"Waiting for {platform_name} response...")
            
            # Wait for response (up to 60 seconds)
            wait_indicator = platform_config.get("wait_indicator")
            
            # First wait for generating indicator to appear (or timeout)
            try:
                if wait_indicator:
                    page.wait_for_selector(wait_indicator, timeout=5000)
            except:
                pass  # Indicator may not appear
            
            # Then wait for it to disappear (response complete)
            try:
                if wait_indicator:
                    page.wait_for_function(
                        f"() => !document.querySelector('{wait_indicator}')",
                        timeout=60000
                    )
            except:
                # Just wait a fixed time as fallback
                time.sleep(15)
            
            # Additional settling time
            time.sleep(2)
            
            # Extract the response
            try:
                response_elems = page.locator(response_selector).all()
                if response_elems:
                    # Get the last response (most recent)
                    response_text = response_elems[-1].inner_text()
                    self.logger.info(f"Got response from {platform_name}: {len(response_text)} chars")
                    return response_text
            except Exception as e:
                self.logger.warning(f"Could not extract response from {platform_name}: {e}")
            
            # Fallback: get all text from page
            try:
                page_text = page.inner_text("body")
                if len(page_text) > 500:
                    return page_text
            except:
                pass
            
            return None
            
        except Exception as e:
            self.logger.error(f"AI consultation failed on {platform_name}: {e}")
            return None
    
    def _should_consult_ai(self, content: str) -> bool:
        """
        Determine if scraped content is low-quality and we should consult AI instead.
        """
        if not content:
            return True
        
        # Low quality indicators
        low_quality_indicators = [
            len(content) < 200,  # Too short
            "cookie" in content.lower() and len(content) < 500,  # Just cookie notice
            "accept all" in content.lower() and len(content) < 300,  # Just consent popup
            "sign in" in content.lower() and len(content) < 400,  # Login wall
            content.count("\n") < 3 and len(content) < 300,  # No real paragraphs
        ]
        
        return any(low_quality_indicators)

    def _sync_action_deep_research(self, params: Dict, context: Dict) -> SkillResult:
        """
        Perform deep research using HUMAN-LIKE browser interaction.
        
        Instead of JavaScript extraction, this method:
        1. Types query in Google search box like a human
        2. CLICKS on search result titles directly
        3. SCROLLS pages to read content
        4. Goes BACK to results after each visit
        5. Compiles a report from all visited sites
        """
        query = params.get("query")
        limit = params.get("limit", 3)
        report_callback = params.get("report_callback")  # Optional callback for Telegram updates
        
        if not query:
            return SkillResult(success=False, error="Query required")
        
        import time
        
        # Ensure browser is initialized and page is valid
        # If page is stale from previous research, reinitialize
        try:
            page = self._get_current_page()
            # Test if page is still valid by checking URL
            _ = page.url
        except Exception as e:
            self.logger.warning(f"Browser page invalid ({e}), reinitializing...")
            # Force reinitialize
            self._initialized = False
            self._sessions.clear()
            self._current_session = None
            
            # Synchronously reinitialize
            if not self._sync_initialize():
                return SkillResult(success=False, error="Failed to reinitialize browser")
            
            page = self._get_current_page()
        
        def report(msg: str):
            """Helper to log and optionally report to Telegram."""
            self.logger.info(f"Deep research: {msg}")
            if report_callback and callable(report_callback):
                try:
                    report_callback(msg)
                except:
                    pass
        
        # ============================================================
        # PHASE 1: SEARCH (Human-like)
        # ============================================================
        report(f"Starting research on '{query}'...")
        
        # Navigate to Google homepage
        page.goto("https://www.google.com")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        
        # Find and click the search box
        try:
            search_box = page.locator("textarea[name='q'], input[name='q']").first
            search_box.click()
            time.sleep(0.3)
            
            # Type query like a human (character by character)
            search_box.fill("")  # Clear any existing text
            search_box.type(query, delay=50)  # 50ms delay between characters
            time.sleep(0.5)
            
            # Press Enter to search
            page.keyboard.press("Enter")
            report(f"Searching Google for '{query}'...")
        except Exception as e:
            self.logger.error(f"Failed to interact with search box: {e}")
            # Fallback to direct URL
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            page.goto(url)
        
        # Wait for results to load
        page.wait_for_load_state("networkidle")
        
        # Wait for search result titles to appear
        try:
            page.wait_for_selector("h3", timeout=15000)
            report("Search results loaded.")
        except:
            report("Waiting for results timed out, continuing...")
        
        time.sleep(1)
        
        # ============================================================
        # PHASE 2: BROWSE RESULTS (Click-based)
        # ============================================================
        combined_report = f"# Deep Research Report: {query}\n\n"
        combined_report += f"*Researched on {time.strftime('%Y-%m-%d %H:%M')}*\n\n---\n\n"
        
        visited_count = 0
        
        for i in range(limit):
            try:
                # Find all result titles (h3 elements)
                result_titles = page.locator("h3").all()
                
                if i >= len(result_titles):
                    report(f"Only {len(result_titles)} results available, stopping.")
                    break
                
                # Get the title text before clicking
                title_text = result_titles[i].inner_text()
                report(f"Opening result {i+1}: '{title_text}'...")
                
                # CLICK on the result title
                result_titles[i].click()
                
                # Wait for page to load
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                time.sleep(1)
                
                # Get the current URL
                current_url = page.url
                page_title = page.title()
                report(f"Reading: {page_title[:50]}...")
                
                # ============================================================
                # CHECK IF THIS IS AN AI PLATFORM
                # ============================================================
                ai_platform = self._detect_ai_platform(current_url)
                
                if ai_platform:
                    # check for redirect (e.g. openai.com -> chatgpt.com)
                    redirect_url = ai_platform.get("redirect_url")
                    if redirect_url:
                        report(f"Redirecting to AI app: {redirect_url}...")
                        page.goto(redirect_url)
                        page.wait_for_load_state("networkidle", timeout=15000)
                        time.sleep(2)
                        
                        # Re-detect platform config for the new URL (optional, but safely uses current config)
                        # We use the config we found for the marketing site which inherits/copies correct selectors
                    
                    # This is an AI chatbot! Consult it instead of just scraping
                    platform_name = ai_platform.get("name", "AI")
                    report(f"🤖 Detected {platform_name}! Consulting for information...")
                    
                    ai_response = self._sync_consult_ai_platform(page, ai_platform, query)
                    
                    if ai_response and len(ai_response) > 100:
                        content = ai_response
                        # Mark as AI-generated content
                        combined_report += f"## Source {i+1}: {platform_name} (AI Consultation)\n"
                        combined_report += f"**URL:** {current_url}\n"
                        combined_report += f"**Type:** 🤖 AI-Generated Response\n\n"
                        combined_report += f"{content}\n\n---\n\n"
                        visited_count += 1
                        
                        # Go back to search (AI consultation done)
                        page.go_back()
                        if redirect_url:
                            # If we redirected, we need to go back TWICE to get to search results
                            time.sleep(1)
                            page.go_back()
                            
                        page.wait_for_load_state("networkidle", timeout=15000)
                        time.sleep(1)
                        continue
                    else:
                        report(f"Could not get response from {platform_name}, scraping page...")
                        # If redirect failed to get info, we are still at the app page
                        # We should go back to the marketing page to try scraping that as fallback?
                        if redirect_url:
                             page.go_back() # Back to marketing page
                             # Proceed to scraping logic below...
                
                # ============================================================
                # SCROLL AND READ (Human-like)
                # ============================================================
                # Scroll down gradually to load lazy content
                for scroll_step in range(3):
                    page.mouse.wheel(0, 400)
                    time.sleep(0.3)
                
                # Scrape the page content
                scrape_result = self._sync_action_scrape({"clean": True}, context)
                
                if scrape_result.success and scrape_result.data:
                    content = scrape_result.data.get("content", "")
                else:
                    # Fallback: get body text directly
                    content = page.inner_text("body")
                
                # Check if content is low-quality
                if self._should_consult_ai(content):
                    report(f"Content is low-quality, attempting AI fallback...")
                    # Don't count this as a good source
                    combined_report += f"## Source {i+1}: {page_title}\n"
                    combined_report += f"**URL:** {current_url}\n"
                    combined_report += f"**Note:** Limited content (login wall/cookie notice)\n\n---\n\n"
                else:
                    # Limit content per source (increased for more detail)
                    if len(content) > 8000:
                        content = content[:8000] + "... (more)"
                    
                    # Add to report
                    combined_report += f"## Source {i+1}: {page_title}\n"
                    combined_report += f"**URL:** {current_url}\n\n"
                    combined_report += f"{content}\n\n---\n\n"
                    
                    visited_count += 1
                
                # ============================================================
                # GO BACK to search results
                # ============================================================
                page.go_back()
                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(1)
                
                # Re-wait for results to ensure they're visible
                try:
                    page.wait_for_selector("h3", timeout=5000)
                except:
                    pass
                
            except Exception as e:
                self.logger.error(f"Error processing result {i+1}: {e}")
                combined_report += f"## Source {i+1}: [Error]\n{str(e)}\n\n---\n\n"
                
                # Try to recover by navigating back to search
                try:
                    page.go_back()
                    page.wait_for_load_state("networkidle", timeout=10000)
                    time.sleep(1)
                except:
                    # Navigate to search again
                    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                    page.goto(url)
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
        
        # ============================================================
        # PHASE 3: COMPILE REPORT
        # ============================================================
        report(f"Research complete. Visited {visited_count} sites.")
        
        # ============================================================
        # PHASE 3.5: AI FALLBACK if insufficient sources
        # ============================================================
        if visited_count < 2:
            report("Insufficient quality sources, attempting AI fallback...")
            
            # Try to consult an AI platform directly
            # Prioritize platforms that are more likely to work without login
            fallback_platforms = [
                ("https://gemini.google.com/", self.AI_PLATFORMS.get("gemini.google.com")),
                ("https://poe.com/", self.AI_PLATFORMS.get("poe.com")),
            ]
            
            for fallback_url, platform_config in fallback_platforms:
                if not platform_config:
                    continue
                    
                try:
                    platform_name = platform_config.get("name", "AI")
                    report(f"Trying {platform_name} as fallback source...")
                    
                    page.goto(fallback_url)
                    page.wait_for_load_state("networkidle", timeout=20000)
                    time.sleep(2)
                    
                    # Try to consult
                    ai_response = self._sync_consult_ai_platform(page, platform_config, query)
                    
                    if ai_response and len(ai_response) > 200:
                        combined_report += f"## AI Consultation: {platform_name}\n"
                        combined_report += f"**URL:** {fallback_url}\n"
                        combined_report += f"**Type:** 🤖 AI-Generated Fallback\n\n"
                        combined_report += f"{ai_response}\n\n---\n\n"
                        visited_count += 1
                        report(f"Got response from {platform_name}!")
                        break  # Got a good response, stop trying
                except Exception as e:
                    self.logger.warning(f"AI fallback to {platform_name} failed: {e}")
                    continue
        
        if visited_count == 0:
            # Take debug screenshot
            try:
                from pathlib import Path
                debug_dir = Path("agent/data/browser/debug")
                debug_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(debug_dir / "deep_research_fail.png"))
            except:
                pass
            return SkillResult(success=False, error=f"Failed to visit any sites for '{query}'")
        
        return SkillResult(
            success=True,
            data={"content": combined_report, "sites_visited": visited_count},
            message=f"Deep research completed. Visited {visited_count} sites."
        )

    def _sync_action_google_search(self, params: Dict, context: Dict) -> SkillResult:
        """Search Google and click the first result (legacy)."""
        query = params.get("query")
        if not query:
            return SkillResult(success=False, error="Query required")
            
        page = self._get_current_page()
        
        # Navigate to Google search
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        page.goto(url)
        page.wait_for_load_state("networkidle")
        
        # Wait extra time for dynamic content to render
        import time
        time.sleep(2)
        
        # Try to find and click the first search result using multiple methods
        try:
            # Method 1: Click on the first h3 which is typically the result title
            h3_elements = page.query_selector_all("h3")
            self.logger.info(f"Found {len(h3_elements)} h3 elements")
            
            for h3 in h3_elements:
                try:
                    # Check if this h3 has a parent link
                    parent_link = h3.evaluate("el => el.closest('a')?.href || ''")
                    if parent_link and 'google.com' not in parent_link and parent_link.startswith('http'):
                        self.logger.info(f"Found result link: {parent_link}")
                        page.goto(parent_link)
                        page.wait_for_load_state("domcontentloaded")
                        return SkillResult(
                            success=True, 
                            data={"url": page.url, "title": page.title()},
                            message=f"Searched '{query}' and opened: {page.title()}"
                        )
                except:
                    continue
            
            # Method 2: Get all links and find first external one
            all_links = page.evaluate("""
                () => {
                    const links = [];
                    document.querySelectorAll('a[href]').forEach(a => {
                        if (a.href && a.href.startsWith('http') && 
                            !a.href.includes('google.com') && 
                            !a.href.includes('gstatic.com') &&
                            !a.href.includes('youtube.com/watch') &&
                            a.offsetParent !== null) {  // visible links only
                            links.push(a.href);
                        }
                    });
                    return links;
                }
            """)
            
            self.logger.info(f"Found {len(all_links)} external links")
            
            if all_links:
                result_url = all_links[0]
                self.logger.info(f"Navigating to: {result_url}")
                page.goto(result_url)
                page.wait_for_load_state("domcontentloaded")
                return SkillResult(
                    success=True, 
                    data={"url": page.url, "title": page.title()},
                    message=f"Searched '{query}' and opened: {page.title()}"
                )
            
            # Method 3: Just click the first h3 directly
            if h3_elements:
                self.logger.info("Clicking first h3 directly")
                h3_elements[0].click()
                page.wait_for_load_state("domcontentloaded")
                return SkillResult(
                    success=True, 
                    data={"url": page.url, "title": page.title()},
                    message=f"Clicked first result: {page.title()}"
                )
            
            return SkillResult(
                success=False, 
                error=f"Could not find any clickable search results for '{query}'"
            )
            
        except Exception as e:
            self.logger.error(f"Google search error: {e}")
            return SkillResult(
                success=False, 
                error=f"Failed to process search results: {str(e)}"
            )
    
    def _sync_action_download(self, params: Dict, context: Dict) -> SkillResult:
        """Download a file."""
        selector = params.get("selector")
        url = params.get("url")
        save_path = params.get("path", "agent/data/browser/downloads/")
        
        page = self._get_current_page()
        Path(save_path).mkdir(parents=True, exist_ok=True)
        
        with page.expect_download() as download_info:
            if selector:
                page.click(selector)
            elif url:
                page.goto(url)
        
        download = download_info.value
        final_path = Path(save_path) / download.suggested_filename
        download.save_as(final_path)
        
        return SkillResult(
            success=True,
            data={"path": str(final_path), "filename": download.suggested_filename},
            message=f"Downloaded: {download.suggested_filename}"
        )
    
    def _sync_action_wait(self, params: Dict, context: Dict) -> SkillResult:
        """Wait for element or condition."""
        selector = params.get("selector")
        timeout = params.get("timeout", 30000)
        state = params.get("state", "visible")  # visible, hidden, attached, detached
        
        page = self._get_current_page()
        
        if selector:
            page.wait_for_selector(selector, state=state, timeout=timeout)
        else:
            page.wait_for_load_state("networkidle", timeout=timeout)
        
        return SkillResult(success=True, message=f"Wait completed for: {selector or 'page load'}")
    
    def _sync_action_scroll(self, params: Dict, context: Dict) -> SkillResult:
        """Scroll the page."""
        import time
        direction = params.get("direction", "down")
        amount = params.get("amount", 500)
        infinite = params.get("infinite", False)
        
        page = self._get_current_page()
        
        if infinite:
            # Infinite scroll - keep scrolling until no new content
            prev_height = 0
            while True:
                current_height = page.evaluate("document.body.scrollHeight")
                if current_height == prev_height:
                    break
                prev_height = current_height
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
        else:
            scroll_amount = amount if direction == "down" else -amount
            page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        
        return SkillResult(success=True, message=f"Scrolled {direction}")
    
    def _sync_action_run_script(self, params: Dict, context: Dict) -> SkillResult:
        """Execute JavaScript on page."""
        script = params.get("script", "")
        
        page = self._get_current_page()
        result = page.evaluate(script)
        
        return SkillResult(
            success=True,
            data={"result": result},
            message="Script executed"
        )
    
    # ==================== SESSION MANAGEMENT ====================
    
    def _sync_create_session(self, name: str) -> BrowserSession:
        """Create a new browser session with its own context."""
        profile_path = self.PROFILE_DIR / name
        profile_path.mkdir(parents=True, exist_ok=True)
        
        state_file = profile_path / "state.json"
        
        # Create context with persistent storage
        context = self._browser.new_context(
            storage_state=str(state_file) if state_file.exists() else None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        page = context.new_page()
        
        session = BrowserSession(
            name=name,
            profile_path=profile_path,
            context=context,
            page=page
        )
        
        self._sessions[name] = session
        self._current_session = name
        
        return session
    
    def _sync_save_session_state(self, session: BrowserSession) -> None:
        """Save session cookies and storage."""
        try:
            state_path = session.profile_path / "state.json"
            session.context.storage_state(path=str(state_path))
            self.logger.info(f"Saved session state: {session.name}")
        except Exception as e:
            self.logger.error(f"Failed to save session state: {e}")
    
    def _sync_action_new_session(self, params: Dict, context: Dict) -> SkillResult:
        """Create a new named session."""
        name = params.get("name", f"session_{len(self._sessions)}")
        self._sync_create_session(name)
        return SkillResult(success=True, message=f"Created session: {name}")
    
    def _sync_action_switch_session(self, params: Dict, context: Dict) -> SkillResult:
        """Switch to a different session."""
        name = params.get("name")
        if name not in self._sessions:
            return SkillResult(success=False, error=f"Session not found: {name}")
        
        self._current_session = name
        return SkillResult(success=True, message=f"Switched to session: {name}")
    
    def _sync_action_close_session(self, params: Dict, context: Dict) -> SkillResult:
        """Close a session."""
        name = params.get("name", self._current_session)
        if name not in self._sessions:
            return SkillResult(success=False, error=f"Session not found: {name}")
        
        session = self._sessions[name]
        self._sync_save_session_state(session)
        session.context.close()
        del self._sessions[name]
        
        # Switch to another session if available
        if self._current_session == name:
            self._current_session = next(iter(self._sessions), None)
        
        return SkillResult(success=True, message=f"Closed session: {name}")
    
    # ==================== HEALTH & DRY-RUN ====================
    
    def health(self) -> SkillHealth:
        """Check browser health."""
        if not self._initialized:
            # Not yet initialized, but that's OK - lazy init
            return SkillHealth.READY
        
        if not self._browser:
            return SkillHealth.UNAVAILABLE
        
        if not self._current_session:
            return SkillHealth.DEGRADED
        
        return SkillHealth.READY
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """Preview browser action without executing."""
        previews = {
            "navigate": f"Would navigate to: {params.get('url', 'unknown')}",
            "click": f"Would click: {params.get('selector') or params.get('text', 'unknown')}",
            "fill": f"Would fill field '{params.get('selector') or params.get('label')}' with value",
            "scrape": f"Would scrape content from: {params.get('selector', 'body')}",
            "login": f"Would attempt login at: {params.get('url', 'current page')}",
            "download": f"Would download to: {params.get('path', 'downloads/')}",
        }
        
        return previews.get(action, f"Would execute: {action} with {params}")
