
import logging
import os
import time
import asyncio
from typing import List, Dict, Any, Optional
from agent.skills.base_skill import BaseSkill, SkillManifest, SkillResult, SkillHealth

# Try imports
try:
    from playwright.async_api import async_playwright, Page, BrowserContext
except ImportError:
    async_playwright = None
    Page = None
    BrowserContext = None

class AdvancedBrowserSkill(BaseSkill):
    """
    Module 7: Advanced Browser Agent
    Stealth browsing, session persistence, and CAPTCHA handling.
    
    Key design decisions:
    - Browser launches on startup but page is deferred until first use (no about:blank)
    - page.bring_to_front() is called before every navigation for visibility
    """

    def __init__(self, config: Dict[str, Any]):
        self._name = "browser"
        super().__init__()
        self.config = config
        self.headless = self.config.get('browser', {}).get('headless', False) # Default to Visible
        self.stealth_mode = self.config.get('browser', {}).get('stealth', True)
        
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._browser_pid = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name=self.name,
            version="1.0.0",
            description="Advanced web browsing with stealth capabilities.",
            actions=["browse", "navigate", "go_to", "click", "type", "press_key", "extract", "scrape", "google_search", "consult_ai", "browser_chat_loop"],
            requires=["playwright"],
            permissions=["network"]
        )

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        text = intent.lower() if isinstance(intent, str) else str(intent).lower()
        if "browse" in text or "go to" in text or "website" in text:
            return 0.9
        return 0.0

    async def on_start(self):
        """Initialize Playwright browser engine (but defer page creation until first use)."""
        if not async_playwright:
            self.logger.warning("Playwright not installed.")
            self._health = SkillHealth.UNAVAILABLE
            return
            
        try:
            import os
            if os.name == 'nt':
                import asyncio as _asyncio
                loop = _asyncio.get_running_loop()
                self.logger.info(f"Current event loop type: {type(loop).__name__}")
            
            self.playwright = await async_playwright().start()
            
            # Launch browser engine
            args = ["--start-maximized"]  # Start maximized for visibility
            if self.stealth_mode:
                args.extend(["--disable-blink-features=AutomationControlled"])
                
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=args
            )
            try:
                self._browser_pid = self.browser.process.pid if getattr(self.browser, "process", None) else None
            except Exception:
                self._browser_pid = None
            
            # Create context but DON'T create a page yet (avoids about:blank on startup)
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                no_viewport=True  # Use full window size (no fixed viewport)
            )
            
            # Additional stealth scripts
            if self.stealth_mode:
                await self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            self._health = SkillHealth.READY
            self.logger.info(f"Browser initialized (headless={self.headless}). Page deferred until first use.")
            super().on_load()
        except Exception as e:
            import traceback
            self.logger.error(f"Failed to start browser: {type(e).__name__}: {e}")
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")
            self._health = SkillHealth.DEGRADED

    async def _is_page_alive(self) -> bool:
        """Check if the current page/browser connection is still alive."""
        if not self.page:
            return False
        try:
            await self.page.title()  # lightweight probe
            return True
        except Exception:
            return False

    async def _recover_browser(self):
        """Tear down dead browser and re-launch from scratch."""
        self.logger.warning("Browser connection lost. Recovering...")
        # Close stale handles silently
        for obj_name in ("page", "context", "browser", "playwright"):
            obj = getattr(self, obj_name, None)
            if obj:
                try:
                    if hasattr(obj, 'close'):
                        await obj.close()
                    elif hasattr(obj, 'stop'):
                        await obj.stop()
                except Exception:
                    pass
            setattr(self, obj_name, None)
        # Re-init
        self._loaded = False
        await self.on_start()
        self.logger.info("Browser recovered successfully." if self.context else "Browser recovery FAILED.")

    async def _recycle_page(self):
        """Close current page and create a fresh one to release DOM memory."""
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass
            self.page = None
        if self.context:
            self.page = await self.context.new_page()
            self.logger.info("Browser page recycled (fresh page).")

    async def _ensure_page(self):
        """Create page on first use, or recover if the browser crashed."""
        # Check if existing page is alive
        if self.page:
            if await self._is_page_alive():
                return
            # Page exists but is dead — recycle or recover
            self.logger.warning("Page is stale (browser may have crashed).")
            self.page = None

        if self.context:
            try:
                self.page = await self.context.new_page()
                self.logger.info("Browser page created (first use).")
            except Exception:
                # Context is also dead — full recovery
                await self._recover_browser()
                if self.context:
                    self.page = await self.context.new_page()
        else:
            await self._recover_browser()
            if self.context:
                self.page = await self.context.new_page()

    def _bring_browser_to_foreground(self):
        """Raise Chromium window to foreground so user can see it."""
        if os.name != "nt" or self.headless:
            return
        target_pid = self._browser_pid
        if not target_pid:
            return
        try:
            import win32con
            import win32gui
            import win32process
        except Exception:
            return

        found_hwnd = None

        def _cb(hwnd, _):
            nonlocal found_hwnd
            if found_hwnd:
                return
            if not win32gui.IsWindowVisible(hwnd):
                return
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid == target_pid and win32gui.GetWindowText(hwnd):
                    found_hwnd = hwnd
            except Exception:
                pass

        try:
            win32gui.EnumWindows(_cb, None)
            if found_hwnd:
                win32gui.ShowWindow(found_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(found_hwnd)
        except Exception:
            pass

    @staticmethod
    def _is_browser_crash_error(error: Exception) -> bool:
        err_str = str(error).lower()
        crash_signatures = [
            "epipe",
            "broken pipe",
            "connection closed",
            "target page, context or browser has been closed",
            "browser has been closed",
            "target closed",
            "transport closed",
            "pipe closed",
        ]
        return any(sig in err_str for sig in crash_signatures)

    async def on_unload(self):
        """Cleanup."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        super().on_unload()

    async def execute(self, action: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        self.logger.info(f"Browser executing: {action} (Headless: {self.headless})")
        
        # Handle page recycle action (no page needed)
        if action == "recycle_page":
            await self._recycle_page()
            return SkillResult(success=True, message="Page recycled.")

        # Ensure browser is initialized
        if not self.context:
            if self.health() == SkillHealth.UNAVAILABLE:
                 return SkillResult(success=False, error="Browser not available.")
            if not self._loaded:
                 await self.on_start()
            if not self.context:
                 return SkillResult(success=False, error="Failed to initialize browser.")

        # Ensure page exists (lazy creation / crash recovery)
        try:
            await self._ensure_page()
        except Exception as e:
            if self._is_browser_crash_error(e):
                self.logger.error(f"Browser crash detected while preparing page: {e}")
                await self._recover_browser()
                return SkillResult(success=False, error="Browser crashed and was recovered. Retry the action.")
            self.logger.warning(f"Failed to prepare page for '{action}': {e}")
            return SkillResult(success=False, error=str(e))

        if not self.page:
            return SkillResult(success=False, error="Failed to create page.")

        try:
            if action in ("browse", "navigate", "go_to", "browser_navigate"):
                url = params.get('url')
                if not url: return SkillResult(success=False, error="No URL provided.")
                
                # Bring window to front so user can see the navigation
                await self.page.bring_to_front()
                self._bring_browser_to_foreground()
                
                await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
                title = await self.page.title()
                self.logger.info(f"Navigated to: {title} ({self.page.url})")
                return SkillResult(success=True, data={"title": title, "url": self.page.url})
                
            elif action == "click":
                selector = params.get('selector') or params.get('text')
                if not selector: return SkillResult(success=False, error="No selector.")
                # If it looks like plain text (no CSS selector chars), use text selector
                if selector and not any(c in selector for c in ['.', '#', '[', '>', '~', ':']):
                    selector = f"text={selector}"
                await self.page.click(selector, timeout=5000)
                return SkillResult(success=True, message="Clicked.")
                
            elif action == "type":
                selector = params.get('selector')
                text = params.get('text')
                if not selector or not text: return SkillResult(success=False, error="Missing params.")
                await self.page.fill(selector, text)
                return SkillResult(success=True, message="Typed text.")
                
            elif action == "press_key":
                key = params.get('key')
                if not key: return SkillResult(success=False, error="No key provided.")
                await self.page.keyboard.press(key)
                return SkillResult(success=True, message=f"Pressed key: {key}")
                
            elif action in ("extract", "scrape"):
                selector = params.get('selector', 'body')
                # For scrape, try multiple selectors
                if action == "scrape":
                    for sel in [selector, 'article', '.content', 'main', 'body']:
                        try:
                            content = await self.page.inner_text(sel)
                            if content and len(content.strip()) > 50:
                                return SkillResult(success=True, data={"content": content[:5000]})
                        except Exception:
                            continue
                content = await self.page.inner_text('body')
                return SkillResult(success=True, data={"content": content[:2000]})
            
            elif action == "google_search":
                query = params.get('query', '')
                if not query:
                    return SkillResult(success=False, error="No search query provided.")
                url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                await self.page.bring_to_front()
                self._bring_browser_to_foreground()
                await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
                title = await self.page.title()
                self.logger.info(f"Google search: {query} -> {title}")
                return SkillResult(success=True, data={"title": title, "url": self.page.url, "query": query})
            
            elif action == "consult_ai":
                # Navigate to an AI platform and type the query
                query = params.get('query', '')
                url = params.get('url', 'https://chatgpt.com')
                await self.page.bring_to_front()
                self._bring_browser_to_foreground()
                await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
                title = await self.page.title()
                self.logger.info(f"AI consult page loaded: {title}")
                return SkillResult(success=True, data={"title": title, "url": self.page.url, "query": query})

            elif action == "browser_chat_loop":
                # Sustained interaction loop
                duration_str = params.get('duration', '10m') # e.g. "10m", "5m"
                topic = params.get('topic', 'general')
                
                # Parse duration
                import re
                match = re.search(r"(\d+)", duration_str)
                minutes = int(match.group(1)) if match else 10
                requested_seconds = minutes * 60
                mission_started_at = time.time()
                hard_stop_time = mission_started_at + requested_seconds
                
                self.logger.info(f"Starting chat loop for {minutes} minutes on topic: {topic}")
                
                conversation_log = []
                last_response = ""
                seen_responses = set()
                total_messages_sent = 0
                total_responses_read = 0
                first_exchange_at = None
                last_exchange_at = None
                last_unsent_attempt_at = 0.0
                unsent_resend_cooldown = 12.0
                blocked_modal_hits = 0
                consecutive_send_failures = 0
                max_consecutive_send_failures = 8

                def _timestamp() -> str:
                    return time.strftime("%Y-%m-%d %H:%M:%S")

                async def _dismiss_blocking_overlays() -> bool:
                    nonlocal blocked_modal_hits
                    overlay_selectors = [
                        "#modal-no-auth-rate-limit",
                        "[data-testid='modal-no-auth-rate-limit']",
                        "div[data-state='open'] #modal-no-auth-rate-limit",
                    ]
                    visible_overlay = False

                    for selector in overlay_selectors:
                        loc = self.page.locator(selector)
                        try:
                            if await loc.count() > 0 and await loc.first.is_visible(timeout=500):
                                visible_overlay = True
                                break
                        except Exception:
                            continue

                    if not visible_overlay:
                        return False

                    blocked_modal_hits += 1
                    self.logger.warning("Detected ChatGPT auth/rate-limit modal. Attempting dismissal...")

                    close_candidates = [
                        self.page.locator("#modal-no-auth-rate-limit button[aria-label='Close']"),
                        self.page.locator("#modal-no-auth-rate-limit button:has-text('Close')"),
                        self.page.locator("#modal-no-auth-rate-limit button:has-text('Continue')"),
                        self.page.locator("#modal-no-auth-rate-limit button:has-text('Got it')"),
                        self.page.locator("button[aria-label='Close']"),
                    ]
                    for candidate in close_candidates:
                        try:
                            if await candidate.count() > 0 and await candidate.first.is_visible(timeout=400):
                                await candidate.first.click(timeout=1500)
                                await asyncio.sleep(0.5)
                                break
                        except Exception:
                            continue

                    try:
                        await self.page.keyboard.press("Escape")
                        await asyncio.sleep(0.2)
                    except Exception:
                        pass

                    return True

                async def _find_input_box():
                    selectors = [
                        "div#prompt-textarea[contenteditable='true']",
                        "#prompt-textarea[contenteditable='true']",
                        "div[contenteditable='true'][role='textbox']",
                        "textarea#prompt-textarea:visible",
                        "textarea[data-id='root']:visible",
                        "textarea:visible",
                    ]
                    for selector in selectors:
                        loc = self.page.locator(selector)
                        if await loc.count() == 0:
                            continue
                        candidate = loc.first
                        try:
                            if await candidate.is_visible(timeout=1000):
                                return candidate
                        except Exception:
                            continue
                    return None

                async def _read_input_text(input_box):
                    tag = await input_box.evaluate("el => el.tagName.toLowerCase()")
                    if tag in ["textarea", "input"]:
                        return await input_box.input_value()
                    return (await input_box.inner_text()) or ""

                async def _send_message(message: str) -> bool:
                    await _dismiss_blocking_overlays()
                    input_box = await _find_input_box()
                    if not input_box:
                        self.logger.warning("Could not find a visible chat input box.")
                        return False

                    clicked = False
                    for _ in range(2):
                        try:
                            await input_box.click(timeout=3000)
                            clicked = True
                            break
                        except Exception:
                            await _dismiss_blocking_overlays()
                            await asyncio.sleep(0.3)
                    if not clicked:
                        self.logger.warning("Unable to focus chat input because UI is blocked.")
                        return False

                    await asyncio.sleep(0.1)

                    existing_text = (await _read_input_text(input_box)).strip()
                    if existing_text:
                        await self.page.keyboard.press("Control+A")
                        await self.page.keyboard.press("Backspace")
                        await asyncio.sleep(0.1)

                    tag = await input_box.evaluate("el => el.tagName.toLowerCase()")
                    if tag in ["textarea", "input"]:
                        await input_box.fill(message, timeout=8000)
                    else:
                        await input_box.type(message, delay=10, timeout=10000)

                    send_btn = self.page.locator("button[data-testid='send-button']:not([disabled])").or_(
                        self.page.locator("button[aria-label='Send prompt']:not([disabled])")
                    ).first

                    sent = False
                    try:
                        if await send_btn.count() > 0 and await send_btn.is_visible(timeout=800):
                            await send_btn.click(timeout=2000)
                            sent = True
                    except Exception:
                        pass

                    if not sent:
                        try:
                            await self.page.keyboard.press("Enter")
                        except Exception:
                            return False

                    await asyncio.sleep(1.0)
                    post_text = (await _read_input_text(input_box)).strip()
                    if post_text and post_text == message.strip():
                        await _dismiss_blocking_overlays()
                        retry_btn = self.page.locator("button[data-testid='send-button']:not([disabled])").or_(
                            self.page.locator("button[aria-label='Send prompt']:not([disabled])")
                        ).first
                        try:
                            if await retry_btn.count() > 0 and await retry_btn.is_visible(timeout=800):
                                await retry_btn.click(timeout=2000)
                                await asyncio.sleep(0.8)
                        except Exception:
                            pass

                        post_text = (await _read_input_text(input_box)).strip()
                        if post_text and post_text == message.strip():
                            return False

                    return True

                def _build_follow_up(latest_response: str, topic_seed: str) -> str:
                    cleaned = " ".join(latest_response.split())
                    cue = cleaned[:70] if cleaned else topic_seed[:70]
                    return (
                        f"Go one level deeper on: {cue}. Keep it concise, with one intuitive example and one short check question."
                    )[:180]
                
                while time.time() < hard_stop_time:
                    try:
                        await _dismiss_blocking_overlays()

                        # 0. Handle Cookie Banners / Popups (Inside loop to catch late loaders)
                        try:
                            cookie_selector_strategies = [
                                self.page.get_by_role("button", name="Accept all"),
                                self.page.get_by_role("button", name="Accept"),
                                self.page.locator("button:has-text('Accept all')"),
                                self.page.locator("button:has-text('Accept')"),
                                self.page.locator("#onetrust-accept-btn-handler"),
                                self.page.get_by_text("Accept all", exact=True),
                                self.page.get_by_text("Reject non-essential")
                            ]
                            
                            for btn in cookie_selector_strategies:
                                if await btn.count() > 0 and await btn.first.is_visible():
                                    self.logger.info(f"Dismissing cookie banner...")
                                    await btn.first.click(timeout=2000)
                                    await asyncio.sleep(2)
                                    break
                        except:
                            pass

                        # 0.5 Ensure previous text is sent if anything is still in the composer
                        try:
                            input_box = await _find_input_box()
                            if input_box:
                                val = (await _read_input_text(input_box)).strip()
                                now_ts = time.time()
                                if len(val) > 5 and (now_ts - last_unsent_attempt_at) >= unsent_resend_cooldown:
                                    self.logger.info(f"Found unsent text ({len(val)} chars). Sending...")
                                    last_unsent_attempt_at = now_ts
                                    if await _send_message(val):
                                        total_messages_sent += 1
                                        conversation_log.append({"role": "user", "text": val, "ts": _timestamp()})
                                        if not first_exchange_at:
                                            first_exchange_at = now_ts
                                        last_exchange_at = now_ts
                                    else:
                                        consecutive_send_failures += 1
                        except Exception:
                            pass

                        # 1. Read latest response
                        try:
                            assistant_msgs = self.page.locator("[data-message-author-role='assistant'] .markdown")
                            count = await assistant_msgs.count()
                            if count > 0:
                                current_response = await assistant_msgs.nth(count - 1).inner_text()
                            else:
                                assistant_blocks = self.page.locator("[data-message-author-role='assistant']")
                                block_count = await assistant_blocks.count()
                                current_response = await assistant_blocks.nth(block_count - 1).inner_text() if block_count > 0 else ""
                                
                            # Fallback if specific selectors fail but body is readable
                            if not current_response:
                                content = await self.page.inner_text("body")
                                lines = [l.strip() for l in content.split('\n') if len(l.strip()) > 30]
                                lines = [l for l in lines if "ChatGPT can make mistakes" not in l and "cookie" not in l.lower()]
                                current_response = lines[-1] if lines else ""
                        except:
                            current_response = ""

                        normalized = " ".join(current_response.split())
                        lower_norm = normalized.lower()
                        skip_phrases = [
                            "got an idea?",
                            "chatgpt can make mistakes",
                            "by messaging chatgpt",
                            "is generating a response",
                        ]
                        if any(phrase in lower_norm for phrase in skip_phrases):
                            await asyncio.sleep(4)
                            continue

                        if (not normalized) or len(normalized) < 20 or normalized == last_response or normalized in seen_responses:
                            await asyncio.sleep(5)
                            continue
                            
                        last_response = normalized
                        seen_responses.add(normalized)
                        total_responses_read += 1
                        conversation_log.append({"role": "assistant", "text": normalized, "ts": _timestamp()})
                        now_ts = time.time()
                        if not first_exchange_at:
                            first_exchange_at = now_ts
                        last_exchange_at = now_ts
                        self.logger.info(f"Read AI response: {normalized[:80]}...")
                        
                        # 2. Reply
                        reply = _build_follow_up(normalized, topic)
                        self.logger.info(f"Typing reply...")

                        sent_ok = await _send_message(reply)
                        if not sent_ok:
                            consecutive_send_failures += 1
                            self.logger.warning("Skipping this loop cycle because reply could not be sent.")
                            if consecutive_send_failures >= max_consecutive_send_failures:
                                self.logger.warning("Too many consecutive send failures. Continuing until time limit with backoff.")
                                consecutive_send_failures = 0
                                await asyncio.sleep(8)
                                continue
                            await asyncio.sleep(4)
                            continue

                        consecutive_send_failures = 0
                        total_messages_sent += 1
                        conversation_log.append({"role": "user", "text": reply, "ts": _timestamp()})
                        now_ts = time.time()
                        if not first_exchange_at:
                            first_exchange_at = now_ts
                        last_exchange_at = now_ts

                        if first_exchange_at and last_exchange_at:
                            active_span = last_exchange_at - first_exchange_at
                            if active_span >= requested_seconds:
                                self.logger.info("Active conversation target reached.")
                                break
                        
                    except Exception as e:
                        self.logger.error(f"Error in chat loop: {e}")
                        await asyncio.sleep(5)

                mission_ended_at = time.time()
                active_span = 0
                if first_exchange_at and last_exchange_at and last_exchange_at >= first_exchange_at:
                    active_span = int(last_exchange_at - first_exchange_at)
                elapsed_total = int(mission_ended_at - mission_started_at)

                lines = []
                lines.append("# Browser Chat Mission Report")
                lines.append("")
                lines.append(f"Generated: {_timestamp()}")
                lines.append(f"Topic: {topic}")
                lines.append(f"Requested duration: {minutes} minutes")
                lines.append(f"Total runtime: {elapsed_total} sec")
                lines.append(f"Active conversation span: {active_span} sec")
                lines.append(f"User messages sent: {total_messages_sent}")
                lines.append(f"Assistant responses captured: {total_responses_read}")
                lines.append(f"Blocking modal detections: {blocked_modal_hits}")
                lines.append("")
                lines.append("## Transcript")
                lines.append("")

                for turn in conversation_log:
                    role = turn.get("role", "unknown").upper()
                    ts = turn.get("ts", "")
                    text = turn.get("text", "")
                    lines.append(f"### {role} ({ts})")
                    lines.append("")
                    lines.append(text)
                    lines.append("")

                transcript_content = "\n".join(lines).strip()

                from pathlib import Path
                mission_dir = Path("agent/data/missions")
                mission_dir.mkdir(parents=True, exist_ok=True)
                filename = f"browser_chat_report_{int(time.time())}.md"
                report_path = mission_dir / filename
                with open(report_path, "w", encoding="utf-8") as report_file:
                    report_file.write(transcript_content)

                active_ratio = (active_span / requested_seconds) if requested_seconds > 0 else 1.0
                completion_status = "complete" if active_ratio >= 0.95 else "partial"

                return SkillResult(
                    success=True,
                    message=f"Chat loop finished ({completion_status}) after {minutes} minutes.",
                    data={
                        "content": transcript_content,
                        "report_path": str(report_path),
                        "completion_status": completion_status,
                        "active_span_seconds": active_span,
                        "requested_seconds": requested_seconds,
                        "total_messages_sent": total_messages_sent,
                        "total_responses_read": total_responses_read,
                    },
                )
        
        except Exception as e:
            # Detect fatal Playwright/browser crashes (EPIPE, connection closed, etc.)
            if self._is_browser_crash_error(e):
                self.logger.error(f"Browser crash detected during '{action}': {e}")
                await self._recover_browser()
                return SkillResult(success=False, error=f"Browser crashed and was recovered. Retry the action.")
            self.logger.warning(f"Browser action '{action}' failed: {e}")
            return SkillResult(success=False, error=str(e))
            
        return SkillResult(success=False, error=f"Unknown action: {action}")
