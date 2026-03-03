from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import json
import logging
import re

@dataclass
class Intent:
    action: str
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    reasoning: str = ""

class IntentParser:
    """
    Parses natural language input into structured Intent objects.
    """
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.logger = logging.getLogger("IntentParser")
        self.llm = None
        
        # Initialize LLM if config exists
        llm_config = self.config.get('llm', {})
        api_key = llm_config.get('api_key')
        if api_key:
            from agent.core.llm_interface import LLMInterface
            self.llm = LLMInterface(
                api_key, 
                llm_config.get('model_name', 'gpt-4o'),
                llm_config.get('provider', 'openai')
            )
        
        self.learning_manager = None

    def inject_learning_manager(self, manager: Any):
        """Inject learning manager."""
        self.learning_manager = manager

    def _normalize_tokens(self, text: str) -> List[str]:
        tokens = re.findall(r"[a-zA-Z0-9_./-]+", text.lower())
        return [t.strip() for t in tokens if t.strip()]

    def _contains_any_stem(self, text: str, stems: List[str]) -> bool:
        tokens = self._normalize_tokens(text)
        for token in tokens:
            for stem in stems:
                if token.startswith(stem):
                    return True
        return False

    def _extract_semantic_hints(self, user_input: str) -> Dict[str, Any]:
        lower = user_input.lower()

        goal_stems = ["research", "investigat", "analy", "find", "compar", "study", "explor"]
        report_stems = ["report", "markdown", "document", "summary", "write", "save", "file", "create"]
        deliver_stems = ["send", "share", "deliver", "forward", "telegram"]

        is_research_goal = self._contains_any_stem(lower, goal_stems)
        has_report_request = self._contains_any_stem(lower, report_stems)
        has_delivery_request = self._contains_any_stem(lower, deliver_stems)

        md_match = re.search(r"([a-zA-Z0-9_./\\-]+\.md)\b", user_input, re.IGNORECASE)
        output_path = md_match.group(1).replace("\\\\", "/").replace("\\", "/") if md_match else None

        channel = "telegram" if "telegram" in lower else None

        return {
            "is_research_goal": is_research_goal,
            "has_report_request": has_report_request,
            "has_delivery_request": has_delivery_request,
            "output_path": output_path,
            "channel": channel,
        }

    def _should_route_to_mission(self, user_input: str) -> bool:
        hints = self._extract_semantic_hints(user_input)
        if hints["is_research_goal"] and (hints["has_report_request"] or hints["has_delivery_request"]):
            return True

        lower = user_input.lower()
        if any(k in lower for k in ["multi-step", "autonomous", "workflow", "end-to-end"]):
            return True

        return False

    def _extract_ordered_web_workflow(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract structured workflow: go to X, search Y, open first N results, summarize."""
        lower = user_input.lower()

        if not ("go to" in lower and "search" in lower and "open first" in lower and "summar" in lower):
            return None

        site_match = re.search(r"(?:go to|navigate to)\s+([a-zA-Z0-9./:-]+)", user_input, re.IGNORECASE)
        search_match = re.search(r"search\s+for\s+[\"']([^\"']+)[\"']", user_input, re.IGNORECASE)
        if not search_match:
            search_match = re.search(r"search\s+for\s+([^,.;]+)", user_input, re.IGNORECASE)
        open_match = re.search(r"open\s+first\s+(\d+)", user_input, re.IGNORECASE)

        target_site = site_match.group(1).strip() if site_match else "google.com"
        query = search_match.group(1).strip() if search_match else ""
        result_count = int(open_match.group(1)) if open_match else 3
        result_count = max(1, min(result_count, 10))

        if not query:
            return None

        return {
            "site": target_site,
            "query": query,
            "result_count": result_count,
        }

    def _extract_news_summary_workflow(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract shorthand workflow: search news -> summarize -> save file -> send telegram."""
        lower = user_input.lower()
        has_arrow = ("->" in lower) or ("→" in user_input)
        has_search = "search" in lower
        has_summary = "summar" in lower
        has_save = ("save" in lower) or ("file" in lower)
        has_telegram = "telegram" in lower

        if not (has_arrow and has_search and has_summary and has_save and has_telegram):
            return None

        query_match = re.search(r"search\s+(?:for\s+)?(.+?)(?:\s*(?:->|→)|,|$)", user_input, re.IGNORECASE)
        query = query_match.group(1).strip() if query_match else "latest news"

        if query.lower() in {"news", "the news", "latest", "latest news"}:
            query = "latest news"

        output_path = "generated/news_summary.md"
        md_match = re.search(r"([a-zA-Z0-9_./\\-]+\.md)\b", user_input, re.IGNORECASE)
        if md_match:
            output_path = md_match.group(1).replace('\\\\', '/').replace('\\', '/')

        return {
            "query": query,
            "output_path": output_path,
        }

    def _extract_startup_build_workflow(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Extract compound workflow: build landing page + research competitors + run + screenshot + telegram."""
        lower = user_input.lower()

        has_build = any(k in lower for k in ["build", "create react", "landing page", "react project"])
        has_research = any(k in lower for k in ["research competitors", "research", "competitor"])
        has_run = any(k in lower for k in ["run it", "run the project", "install dependencies"])
        has_screenshot = "screenshot" in lower
        has_telegram = "telegram" in lower

        if not (has_build and has_research and has_run and has_screenshot and has_telegram):
            return None

        startup_name = "startup"
        name_match = re.search(r"startup\s+called\s+([A-Za-z0-9\s&._-]+)", user_input, re.IGNORECASE)
        if name_match:
            startup_name = name_match.group(1).strip().rstrip(".,")
        else:
            landing_match = re.search(r"landing\s+page\s+for\s+([A-Za-z0-9\s&._-]+?)(?:,|\.|\band\b|$)", user_input, re.IGNORECASE)
            if landing_match:
                startup_name = landing_match.group(1).strip().rstrip(".,")

        safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", startup_name).strip("_").lower() or "startup"

        return {
            "startup_name": startup_name,
            "project_name": safe_name,
            "competitor_output_path": f"generated/{safe_name}_competitors.md",
            "screenshot_path": f"generated/{safe_name}_site.png",
        }

    def _extract_delete_target(self, user_input: str) -> Optional[str]:
        quoted = re.search(r"[\"']([^\"']+)[\"']", user_input)
        if quoted:
            return quoted.group(1).strip()

        keyword_match = re.search(
            r"(?:folder|directory|dir|file)\s+(?:named\s+)?([a-zA-Z0-9_./\\:-]+)",
            user_input,
            re.IGNORECASE,
        )
        if keyword_match:
            return keyword_match.group(1).strip()

        return None

    def _should_force_mission_for_chatgpt_report(self, user_input: str) -> bool:
        """Detect multi-step workflows that shouldn't be reduced to a telegram_send_message.

        Example: "go to chatgpt and chat ... then send the report on telegram".
        """
        lower = (user_input or "").lower()
        has_chatgpt = any(k in lower for k in ["chatgpt", "chat.openai.com", "openai.com", "gpt"])  # broad but safe
        has_navigation = any(k in lower for k in ["go to", "open", "navigate", "browse", "visit"])
        has_report = any(k in lower for k in ["report", "summary", "summar", "write up", "notes"])
        has_delivery = "telegram" in lower and any(k in lower for k in ["send", "share", "forward"])
        has_interaction = any(k in lower for k in ["chat with", "talk to", "discuss", "conversation"])

        # If it's explicitly a browser/chat interaction + report delivery, it's a mission.
        return (has_chatgpt and has_delivery and has_report and (has_navigation or has_interaction))

    def _get_learned_examples(self, user_input: str) -> str:
        """Fetch relevant learned examples/patterns."""
        if not self.learning_manager:
            return ""
        try:
            # Placeholder: In future, semantic search for similar past successful intents
            # patterns = self.learning_manager.pattern_recognizer.find_relevant_patterns(user_input)
            return ""
        except Exception:
            return ""


    def parse(self, user_input: str) -> List[Intent]:

        """
        Parses input using LLM if available, otherwise regex fallback.
        Returns a LIST of intents to execute in order.
        """
        self.logger.info(f"DEBUG: IntentParser.parse called with: '{user_input}'")
        print(f"DEBUG: IntentParser.parse called with: '{user_input}'")
        
        # NUCLEAR OPTION: Hard Switch for Surveillance to bypass ALL refusal logic
        u_lower = user_input.lower()
        if any(k in u_lower for k in ["cctv", "surveillance", "start scan", "activate camera", "monitor"]):
             if "start" in u_lower or "activate" in u_lower or "open" in u_lower or "monitor" in u_lower or "surveillance" in u_lower:
                  return [Intent(action="start_surveillance", tool_name="start_surveillance", parameters={"camera_index": 0})]
             elif "stop" in u_lower or "close" in u_lower:
                  return [Intent(action="stop_surveillance", tool_name="stop_surveillance", parameters={})]

        # NUCLEAR OPTION: Chart/Market Analysis
        chart_keywords = ["chart", "stock", "predict", "prediction", "up or down", "go up", "go down", 
                          "bullish", "bearish", "candle", "candlestick", "forex", "trading", "analysis",
                          "will it go", "price", "market"]
        if any(k in u_lower for k in chart_keywords):
            # Check if an image path was attached
            import re
            image_match = re.search(r'\[Image Path: (.+?)\]', user_input)
            if image_match:
                image_path = image_match.group(1)
                return [Intent(
                    action="analyze_chart", 
                    tool_name="analyze_chart", 
                    parameters={"path": image_path},
                    confidence=1.0,
                    reasoning="User provided chart image for analysis"
                )]

        # NUCLEAR OPTION: Compound startup build workflow
        startup_workflow = self._extract_startup_build_workflow(user_input)
        if startup_workflow:
            mission_goal = (
                f"Build a landing page for {startup_workflow['startup_name']}, research competitors, generate content, "
                f"create React project, install dependencies, run it, take screenshot, and send all artifacts via Telegram."
            )
            return [Intent(
                action="start_mission",
                tool_name="start_mission",
                parameters={
                    "goal": mission_goal,
                    "startup_build_workflow": startup_workflow,
                },
                confidence=1.0,
                reasoning="Detected complex startup workflow with explicit multi-step build/research/run/screenshot/telegram requirements; routing to mission controller."
            )]

        # NUCLEAR OPTION: Screen Analysis ("what's on my screen", "describe my screen")
        screen_keywords = ["what's on my screen", "whats on my screen", "describe my screen", 
                          "what do you see", "what is on screen", "read my screen", 
                          "analyze my screen", "look at my screen", "what is on my screen"]
        screenshot_keywords = [
            "take a screenshot", "capture screen", "capture my screen", "screenshot",
            "currently open", "which app is open", "what application is currently open"
        ]
        if any(k in u_lower for k in screen_keywords) or any(k in u_lower for k in screenshot_keywords):
            # This needs to capture screenshot then analyze with vision LLM
            return [
                Intent(
                    action="capture_screen",
                    tool_name="capture_screen", 
                    parameters={},
                    confidence=1.0,
                    reasoning="User wants screen analysis - capturing first"
                ),
                Intent(
                    action="describe_image",
                    tool_name="describe_image",
                    parameters={"use_last_capture": True},
                    confidence=1.0,
                    reasoning="Describe the captured screen"
                )
            ]

        # NUCLEAR OPTION: Ordered browser workflow command
        # Example: Go to google.com, search for "AI regulation India 2026", open first 3 results, summarize them.
        ordered_workflow = self._extract_ordered_web_workflow(user_input)
        if ordered_workflow:
            mission_goal = (
                f"Go to {ordered_workflow['site']}, search for '{ordered_workflow['query']}', "
                f"open first {ordered_workflow['result_count']} results, summarize them."
            )
            return [Intent(
                action="start_mission",
                tool_name="start_mission",
                parameters={
                    "goal": mission_goal,
                    "ordered_web_workflow": ordered_workflow,
                },
                confidence=1.0,
                reasoning="Detected ordered multi-step browser workflow with explicit execution order; routing to mission controller."
            )]

        # NUCLEAR OPTION: Shorthand workflow chain (search -> summarize -> save -> telegram)
        news_workflow = self._extract_news_summary_workflow(user_input)
        if news_workflow:
            mission_goal = (
                f"Search for {news_workflow['query']}, summarize findings, "
                f"save report to {news_workflow['output_path']}, and send it via Telegram."
            )
            return [Intent(
                action="start_mission",
                tool_name="start_mission",
                parameters={
                    "goal": mission_goal,
                    "news_summary_workflow": news_workflow,
                },
                confidence=1.0,
                reasoning="Detected shorthand news workflow with explicit execution chain; routing to mission controller."
            )]

        # NUCLEAR OPTION: Force Search for Real-Time Info
        # This prevents the LLM from using stale 2023 knowledge for 2026 questions.
        search_triggers = ["current", "latest", "president", "prime minister", "ceo", "weather", "news", "price", "stock", "score", "who is the"]
        if any(t in u_lower for t in search_triggers):
            if "who is the" in u_lower or any(x in u_lower for x in ["current", "latest", "news", "president", "prime minister"]):
                return [Intent(
                    action="search_online",
                    tool_name="search_online",
                    parameters={"query": user_input},  # <-- CRITICAL: Pass the full question
                    confidence=1.0,
                    reasoning="Real-time information keyword detected."
                )]

        # NUCLEAR OPTION: File/Folder delete
        delete_keywords = ["delete", "remove", "erase"]
        if any(k in u_lower for k in delete_keywords) and any(x in u_lower for x in ["folder", "directory", "dir", "file", "path"]):
            target_path = self._extract_delete_target(user_input)
            if target_path:
                return [Intent(
                    action="delete_path",
                    tool_name="delete_path",
                    parameters={"path": target_path, "recursive": True},
                    confidence=1.0,
                    reasoning="User requested deletion of a file/folder path."
                )]

        # NUCLEAR OPTION: Mission Mode
        if "start mission" in u_lower or "mission mode" in u_lower:
            # Extract goal from "start mission: <goal>" or "start mission <goal>" while preserving casing/content.
            goal = user_input
            goal = re.sub(r"(?i)^\s*start\s+mission\s*:?\s*", "", goal).strip()
            goal = re.sub(r"(?i)^\s*mission\s+mode\s*:?\s*", "", goal).strip()
            if not goal:
                goal = user_input  # Use full input if extraction failed
            return [Intent(
                action="start_mission",
                tool_name="start_mission",
                parameters={"goal": goal},
                confidence=1.0,
                reasoning="User wants to start an autonomous mission."
            )]

        # SEMANTIC ROUTING: Understand natural sentence intent beyond fixed syntax
        if self._should_route_to_mission(user_input):
            hints = self._extract_semantic_hints(user_input)
            return [Intent(
                action="start_mission",
                tool_name="start_mission",
                parameters={
                    "goal": user_input.strip(),
                    "semantic_hints": hints,
                },
                confidence=1.0,
                reasoning="Semantic interpretation detected a complex objective with research/report/delivery requirements; routing to mission controller."
            )]

        # NUCLEAR OPTION: Auto Mission for research-report workflows
        # Example: "Research top 5 AI startups..., create markdown report, save to generated/x.md, send via Telegram"
        has_research_goal = any(k in u_lower for k in ["research", "deep research", "find out", "analyze", "investigate"])
        has_report_goal = any(k in u_lower for k in ["report", "markdown", "save", "write", "file"])
        has_delivery_goal = any(k in u_lower for k in ["telegram", "send the file", "send file", "send it"])
        if has_research_goal and has_report_goal and has_delivery_goal:
            return [Intent(
                action="start_mission",
                tool_name="start_mission",
                parameters={"goal": user_input.strip()},
                confidence=1.0,
                reasoning="Detected research+report+delivery workflow; routing to mission controller to avoid coding/editor flow."
            )]

        # NUCLEAR OPTION: ChatGPT conversation + report to Telegram
        # Example: "go to chatgpt and chat ... then send the report on telegram"
        if self._should_force_mission_for_chatgpt_report(user_input):
            return [Intent(
                action="start_mission",
                tool_name="start_mission",
                parameters={"goal": user_input.strip()},
                confidence=1.0,
                reasoning="Detected multi-step ChatGPT interaction + report delivery; routing to mission controller."
            )]

        # NUCLEAR OPTION: Telegram Commands
        if "telegram" in u_lower:
            # Skip if complex command (research/search) so LLM can handle the chain
            # e.g. "Do deep research on cars and send to telegram" should NOT be trapped here
            if any(k in u_lower for k in ["research", "analysis", "find", "deep", "scan", "monitor"]):
                 pass # Fall through to LLM for complex handling
            # Skip if the user is describing a multi-step workflow (navigate/chat/report) and just wants delivery via Telegram.
            elif self._should_force_mission_for_chatgpt_report(user_input) or any(k in u_lower for k in ["go to", "navigate", "browse", "open", "chatgpt", "chat with", "summar", "report"]):
                pass
            
            # PRIORITY 1: Check for SEND first (user explicitly says "send X to Y")
            elif "send" in u_lower:
                # Smart Routing: Detect if user is messaging a CONTACT (GUI) or just sending (API)
                # Pattern: "send [message] to [contact] on telegram" -> GUI
                # Pattern: "send telegram message [text]" -> API (agent reporting)
                
                import re
                # Try to extract contact name using " to " pattern
                # e.g., "send hii to ashish on telegram" -> contact="ashish", message="hii"
                contact_match = re.search(r"send\s+(.+?)\s+to\s+(\w+)\s+(?:on|via|using|in)?\s*telegram", u_lower)
                
                if contact_match:
                    # User wants to message a specific person -> GUI Automation
                    message = contact_match.group(1).strip()
                    contact = contact_match.group(2).strip()
                    
                    return [Intent(
                        action="telegram_gui_send",
                        tool_name="desktop.telegram_gui_send",  # Route to DesktopSkill
                        parameters={"contact": contact, "message": message},
                        confidence=1.0,
                        reasoning=f"User wants to send '{message}' to contact '{contact}' via Telegram GUI."
                    )]
                
                # Fallback: No contact detected -> Use API (agent reporting mode)
                msg = u_lower.replace("telegram", "").replace("send", "").replace("message", "").replace("saying", "")
                for prep in [" on ", " to ", " via ", " using "]:
                    msg = msg.replace(prep, " ")
                msg = msg.strip()
                
                return [Intent(
                    action="telegram_send_message",
                    tool_name="telegram_send_message",
                    parameters={"message": msg or "Test message"},
                    confidence=1.0,
                    reasoning="User wants to send a telegram message (API mode)."
                )]
            
            # PRIORITY 2: Check messages (only if not sending)
            elif "check" in u_lower or "read" in u_lower or "messages" in u_lower:
                return [Intent(
                    action="telegram_check_messages",
                    tool_name="telegram_check_messages",
                    parameters={},
                    confidence=1.0,
                    reasoning="User wants to check telegram messages."
                )]


        # Override for "Search X on Y" (e.g. "search cars on chrome")
        # This prevents the LLM from hallucinating a search tool for browser launch intents
        # Override for "Search X on Y" (e.g. "search cars on chrome")
        # This prevents the LLM from hallucinating a search tool for browser launch intents
        if "search" in u_lower and (" on " in u_lower or " using " in u_lower):
             self.logger.info("DEBUG: Search Override Condition Met")
             print("DEBUG: Search Override Condition Met")
             
             # Use lower case for splitting to ensure matches
             parts_lower = u_lower.split(" on ") if " on " in u_lower else u_lower.split(" using ")
             
             if len(parts_lower) >= 2:
                 # Attempt to split "search cars" -> "cars"
                 query_part = parts_lower[0].replace("search", "").strip()
                 app_part = parts_lower[1].replace("browser", "").strip() # e.g. "chrome browser" -> "chrome"
                 
                 # Check if the target is a known browser
                 if any(b in app_part for b in ["chrome", "edge", "firefox", "brave", "opera"]):
                     url = f"https://www.google.com/search?q={query_part.replace(' ', '+')}"
                     return [Intent(
                        action="launch_app", 
                        tool_name="launch_app", 
                        parameters={"app_name": app_part, "extra_args": url},
                        confidence=1.0,
                        reasoning="User explicitly requested browser search."
                     )]

        if self.llm:
            return self._parse_with_llm(user_input)
        
        return self._parse_fallback(user_input)

    def _parse_with_llm(self, user_input: str) -> List[Intent]:
        learned_context = self._get_learned_examples(user_input)
        
        system_context = f"{learned_context}\n" + """
        
        AVAILABLE TOOLS:
        - chat_tool(message): General conversation.
        - launch_app(app_name, extra_args): Launch an application (200+ apps supported: notepad, chrome, vscode, photoshop, teams, slack, discord, etc.).
        - delete_path(path, recursive): Delete a file or directory path.
        - store_memory(text): Save a fact/event to long-term memory.
        - search_memory(query): specific recall.
        - search_online(query): Search the web via API (Google/DDG) for quick info.
        
        - make_call(phone_number, contact_name, purpose): Initiate a real phone call via Twilio.
        - end_call(call_sid): End an active call.
        
        - analyze_chart(image_path, timeframe, instrument): Analyze a financial chart image.
        - analyze_screen_chart(): Capture screen and analyze visible chart.
        
        - browser_navigate(url): Open a REAL browser (Playwright) to a URL.
        - browser_read(): Read the text content of the visible browser page.
        - browser_close(): Close the browser.
        
        - move_mouse(x, y): Move cursor to coordinates.
        - click_mouse(): Click left mouse button.
        - type_text(text): Type text on keyboard.
        - press_key(key): Press a specific key (enter, space, esc).
        
        - detect_faces(path): Find faces in an image.
        - recognize_faces(path): Identify people in an image.
        - register_face(name, path): Learn a new face.
        - describe_image(path): Describe a scene.
        - start_surveillance(camera_index): Start CCTV loop.
        - stop_surveillance(): Stop CCTV loop.
        - capture_screen(): Take a screenshot.
        - lock_agent(): Lock the device/agent securely.
        
        - start_mission(goal): Start an autonomous complex task (e.g. "Research cars", "Build a website", "Sustained web interaction", "Long-running tasks").
        - telegram_send_message(message): Send a text message via Telegram API (for reporting results).
        - telegram_check_messages(): Check for new messages.
        
        PC SYSTEM CONTROL TOOLS:
        - system_power(operation): Control power: shutdown, restart, hibernate, sleep, lock, logoff, cancel_shutdown, switch_user.
        - volume(direction, step, level, action): Control audio volume: up/down by step, set level 0-100, mute/unmute/toggle_mute/mute_mic/unmute_mic.
        - brightness(direction, step, level): Control screen brightness: up/down by step, or set 0-100.
        - display_control(mode, night_light, resolution, rotate): Display settings: dark/light mode, night light on/off, change resolution, rotate screen, mirror/extend displays.
        - window_management(operation, position): Window management: minimize_all, show_desktop, close_all, task_view, snap (left/right/top_left/top_right/bottom_left/bottom_right), always_on_top, tile_all, cascade.
        - virtual_desktop(operation, desktop_number): Virtual desktops: create, close, switch to desktop N.
        - open_settings(page): Open Windows Settings page: display, sound, notifications, privacy, windowsupdate, network, bluetooth, mousetouchpad, printers, appsfeatures, defaultapps, startupapps, powersleep, batterysaver.
        - network_control(operation): Network tools: show_ip, flush_dns, speed_test, check_connectivity, status, connect_vpn, disconnect_vpn, enable_wifi, disable_wifi, scan_wifi.
        - screenshot(mode): Take a screenshot: full, region, active_window, all_monitors.
        - screen_record(action): Screen recording: start, stop (via Xbox Game Bar).
        - file_navigate(location): Open a folder: documents, downloads, desktop, pictures, videos, music, home.
        - file_search(query, location): Search for files on the system.
        - disk_management(operation): Disk tools: disk_cleanup, defrag, chkdsk, usage.
        - accessibility(feature, enable): Accessibility: magnifier, narrator, on_screen_keyboard, color_filters, high_contrast.
        - wallpaper(action, image_path): Wallpaper control: change wallpaper, open settings.
        - clipboard_history(action): Clipboard: show history, clear.
        - bluetooth(operation): Bluetooth settings.
        
        RESPONSE FORMAT:
        Always output valid JSON.
        If multiple actions are needed, return a JSON array of actions.
        Each action should be a JSON object with "action" (tool name), "parameters" (dict), "confidence" (float), and "reasoning" (string).
        
        Example Single Action:
        { "action": "chat_tool", "parameters": { "message": "Hello there!" }, "confidence": 1.0, "reasoning": "User said hello." }
        
        Example Multiple Actions (Plan):
        1. User says: "Go to google.com and type 'Hello'"
           [
             { "action": "browser_navigate", "parameters": { "url": "google.com" }, "confidence": 1.0, "reasoning": "Navigate to Google." },
             { "action": "type_text", "parameters": { "text": "Hello" }, "confidence": 1.0, "reasoning": "Type text into search box." },
             { "action": "press_key", "parameters": { "key": "enter" }, "confidence": 1.0, "reasoning": "Submit search." }
           ]
        
        INSTRUCTIONS:
        1. IF USER ASKS A QUESTION:
           - Use 'chat_tool' for general conversation.
           - Use 'search_online' if the user asks for REAL-TIME info (news, weather, sports) or specific facts you don't know.
           - Use 'search_memory' for PERSONAL facts about the user.
        
        3. IF USER WANTS TO LAUNCH AN APP: Use 'launch_app'.
           - "Open Edge" -> { "action": "launch_app", "parameters": { "app_name": "edge" } }
           - "Open Notepad" -> { "action": "launch_app", "parameters": { "app_name": "notepad" } }
           - "Open Photoshop" -> { "action": "launch_app", "parameters": { "app_name": "photoshop" } }
           - "Open Docker" -> { "action": "launch_app", "parameters": { "app_name": "docker" } }
           - "Open 1Password" -> { "action": "launch_app", "parameters": { "app_name": "1password" } }
           - CRITICAL: Do NOT invent tools like 'open_edge' or 'open_app_tool'. Use ONLY 'launch_app'.
        
        4. IF USER WANTS TO BROWSE:
           - "Search Youtube" -> { "action": "browser_navigate", "parameters": { "url": "https://www.youtube.com" } }
           - "Go to google" -> { "action": "browser_navigate", "parameters": { "url": "google.com" } }
           - "Search cars on Chrome" -> { "action": "launch_app", "parameters": { "app_name": "chrome", "extra_args": "https://www.google.com/search?q=cars" } }
           - CRITICAL: Do NOT use 'google_search' or 'open_url'. Use 'browser_navigate'.
           
        4. IF USER WANTS VISION/CAMERA:
           - "Scan my face", "Who am I?", "Watch me" -> Use 'start_surveillance'.
           - "Take a screenshot", "What's on my screen?" -> Use 'capture_screen'.
           - "Describe this..." -> Use 'capture_screen' first if no file provided.
           - "Describe this image", "Read this" -> You MUST have a valid file path.
             - If user provides path: { "action": "describe_image", "parameters": { "path": "..." } }
             - If NO path provided: Use 'chat_tool' to ask "Which image file?"
             - DO NOT INVENT PATHS (e.g. /home/user/...).
             
        5. IF USER WANTS MARKET/CHART ANALYSIS:
           - "Analyze this chart" (with image) -> { "action": "analyze_chart", "parameters": { "image_path": "..." } }
        6. IF USER WANTS COMPLEX RESEARCH/MISSION:
           - "Research cars and send report to Telegram" ->
             { "action": "start_mission", "parameters": { "goal": "Research cars" }, "confidence": 1.0, "reasoning": "Mission will handle research and Telegram reporting." }
           - IMPORTANT: Do NOT add a separate telegram_send_message when using start_mission - Mission handles its own Telegram updates automatically.
           
        7. IF USER WANTS TO MAKE A CALL:
           - "Call my friend" -> { "action": "make_call", "parameters": { "contact_name": "friend" } }
           - "Call 555-0199" -> { "action": "make_call", "parameters": { "phone_number": "555-0199" } }
           - "Call John and ask about lunch" -> { "action": "make_call", "parameters": { "contact_name": "John", "purpose": "Ask about lunch" } }
        
        8. IF USER WANTS PC SYSTEM CONTROL (use these EXACT tool names):
           - "Shut down the computer" -> { "action": "system_power", "parameters": { "operation": "shutdown" } }
           - "Restart" -> { "action": "system_power", "parameters": { "operation": "restart" } }
           - "Lock the screen" -> { "action": "system_power", "parameters": { "operation": "lock" } }
           - "Increase volume" -> { "action": "volume", "parameters": { "direction": "up", "step": 10 } }
           - "Set volume to 50" -> { "action": "volume", "parameters": { "level": 50 } }
           - "Mute" -> { "action": "volume", "parameters": { "action": "mute" } }
           - "Increase brightness" -> { "action": "brightness", "parameters": { "direction": "up", "step": 10 } }
           - "Turn on dark mode" -> { "action": "display_control", "parameters": { "mode": "dark" } }
           - "Snap window to left" -> { "action": "window_management", "parameters": { "operation": "snap", "position": "left" } }
           - "Minimize all windows" -> { "action": "window_management", "parameters": { "operation": "minimize_all" } }
           - "Open display settings" -> { "action": "open_settings", "parameters": { "page": "display" } }
           - "Show my IP address" -> { "action": "network_control", "parameters": { "operation": "show_ip" } }
           - "Flush DNS" -> { "action": "network_control", "parameters": { "operation": "flush_dns" } }
           - "Go to Documents" -> { "action": "file_navigate", "parameters": { "location": "documents" } }
           - "Empty recycle bin" -> { "action": "disk_management", "parameters": { "operation": "empty_recycle_bin" } }
           - "Start screen recording" -> { "action": "screen_record", "parameters": { "action": "start" } }
           - "Create a new virtual desktop" -> { "action": "virtual_desktop", "parameters": { "operation": "create" } }
           - "Open magnifier" -> { "action": "accessibility", "parameters": { "feature": "magnifier" } }
           - "Change wallpaper" -> { "action": "wallpaper", "parameters": { "action": "change" } }
           - "Show clipboard history" -> { "action": "clipboard_history", "parameters": { "action": "show" } }
           - CRITICAL: Do NOT invent tools. Use ONLY the tools listed above.
        """
        
        try:
            result = self.llm.parse_intent(user_input, system_context)
            data = result # Fix: Assign result to data
            self.logger.info(f"LLM Raw Data: {data}")
            
            if result.get('error') == 'rate_limit':
                return [Intent(
                    action='chat', 
                    tool_name='chat_tool', 
                    parameters={'message': result.get('message', 'I am rate limited.')}, 
                    confidence=1.0, 
                    reasoning='API Quota Exceeded'
                )]
            
            # Retry once on JSON parse errors (transient LLM failures)
            if result.get('error') and 'error' in result and len(result) <= 2:
                self.logger.warning(f"LLM parse error, retrying once: {result.get('error')}")
                import time
                time.sleep(1)
                result = self.llm.parse_intent(user_input, system_context)
                data = result
                self.logger.info(f"LLM Retry Data: {data}")
                
                # If retry also failed, fall back to chat_tool
                if result.get('error') and 'error' in result and len(result) <= 2:
                    self.logger.warning(f"LLM retry also failed, falling back to chat_tool")
                    return [Intent(
                        action='chat',
                        tool_name='chat_tool',
                        parameters={'message': user_input},
                        confidence=0.5,
                        reasoning='LLM parse failed twice, using chat fallback'
                    )]
            
            # Check if it's a wrapper dict with 'actions' list
            if isinstance(data, dict) and "actions" in data and isinstance(data["actions"], list):
                data = data["actions"] # Unwrap it to a list

            # Check if the top-level JSON is a list of actions
            if isinstance(data, list):
                intents = []
                for item in data:
                    action_name = item.get("action") or item.get("tool")
                    
                    # Fix Hallucinations: Map invented search tools to chat_tool
                    # "search_online" is now a REAL tool, so we remove it from this list.
                    if action_name in ["search_tool", "perform_check", "google_search"]:
                        action_name = "chat_tool"
                        # Adapt params
                        params = item.get("parameters") or item.get("params") or {}
                        if "query" in params:
                            params["message"] = params.pop("query")
                        if "message" not in params:
                            # If no query/message, use original input as message
                            params["message"] = user_input
                        item["parameters"] = params

                    # 2. Fix Vision Hallucinations (e.g. "Scan my face" -> register_face empty)
                    params = item.get("parameters") or item.get("params") or {} # Get params early
                    if action_name in ["register_face", "recognize_faces", "detect_faces"] and "path" not in params:
                         # If no path provided, assume they mean LIVE surveillance
                         action_name = "start_surveillance"
                         item["parameters"] = {"camera_index": 0}

                    # Fix: Catch "Scan" keyword commonly missed
                    if any(k in user_input.lower() for k in ["scan", "camera", "cctv", "surveillance"]):
                        if action_name not in ["start_surveillance", "stop_surveillance", "detect_faces"]:
                             action_name = "start_surveillance"
                             item["parameters"] = {"camera_index": 0}

                    if action_name:
                        params = item.get("parameters") or item.get("params") or {}
                        
                        # 3. Robust Logic for Parameter Mapping (Fixes missing args)
                        if action_name == "launch_app":
                            if "app_name" not in params:
                                # Check for aliases
                                val = params.pop("name", None) or params.pop("app", None) or params.pop("application", None)
                                if val: params["app_name"] = val
                        
                        elif action_name == "search_memory":
                            if "query" not in params:
                                val = params.pop("text", None) or params.pop("content", None) or params.pop("message", None)
                                if val: params["query"] = val

                        elif action_name == "browser_navigate":
                            # Fix for "search youtube" -> mapped to browser_navigate but missing 'url'
                            if "url" not in params:
                                query = params.get("query") or params.get("search_term") or params.get("topic")
                                if query:
                                    if "youtube" in query.lower():
                                        params["url"] = "https://www.youtube.com/results?search_query=" + query.replace("youtube", "").strip()
                                    else:
                                        params["url"] = f"https://www.google.com/search?q={query}"
                                elif "app_name" in params and "youtube" in params["app_name"].lower():
                                     params["url"] = "https://www.youtube.com"
                                elif "site" in params:
                                     params["url"] = params["site"]

                        if not params:
                            # Try to extract from root keys if params dict is empty
                            known_keys = ["message", "text", "query", "app_name", "camera_index", "expression", "url", "key", "name", "app"]
                            for k, v in item.items():
                                if k not in ["action", "tool", "reasoning", "confidence"] and k in known_keys:
                                    if k in ["name", "app"]: 
                                        params["app_name"] = v
                                    else:
                                        params[k] = v
                                        
                        intents.append(Intent(
                            action=action_name,
                            tool_name=action_name,
                            parameters=params,
                            confidence=item.get("confidence", 1.0),
                            reasoning=item.get("reasoning", "")
                        ))
                if intents:
                    # Filter: Remove redundant telegram_send_message if start_mission is present
                    has_mission = any(i.action == "start_mission" for i in intents)
                    if has_mission:
                        # Remove telegram 'started/will send' messages - mission handles its own reporting
                        intents = [i for i in intents if not (
                            i.action == "telegram_send_message" and 
                            any(kw in (i.parameters.get("message", "") or "").lower() for kw in ["started", "will send", "research", "report"])
                        )]
                    return intents
                else:
                    return [Intent(action="chat", tool_name="chat_tool", parameters={"message": user_input}, confidence=0.5, reasoning="LLM returned an empty or invalid list of actions.")]
            
            # If it's a single action object
            tool_name = data.get("tool") or data.get("action")
            if not tool_name: # If no action/tool, it's an unknown intent
                return [Intent(action="chat", tool_name="chat_tool", parameters={"message": user_input}, confidence=0.5, reasoning="LLM returned no valid action or tool name.")]

            params = data.get("parameters") or data.get("params") or {}

            # Fix: Catch "Scan" keyword commonly missed (Single Object Path)
            if any(k in user_input.lower() for k in ["scan", "camera", "cctv", "surveillance"]):
                 if tool_name not in ["start_surveillance", "stop_surveillance", "detect_faces"]:
                      tool_name = "start_surveillance"
                      params["camera_index"] = 0
            
            # Fallback: if params empty, check if args are in root
            if not params:
                known_keys = ["message", "text", "query", "app_name", "camera_index", "expression", "url", "key"]
                for k, v in data.items():
                    if k not in ["action", "tool", "reasoning", "confidence"] and k in known_keys:
                        params[k] = v

            return [Intent(
                action=tool_name,
                tool_name=tool_name,
                parameters=params,
                confidence=data.get("confidence", 1.0),
                reasoning=data.get("reasoning", "")
            )]
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM Response as JSON: {e}\nRaw response: {data}")
            # Fallback to chat
            return [Intent(action="chat", tool_name="chat_tool", parameters={"message": "I'm having trouble processing that thought. Could you rephrase?"})]
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during LLM parsing: {e}")
            # Fallback
            return self._parse_fallback(user_input)

    def _parse_fallback(self, user_input: str) -> List[Intent]:
        """
        Mock parser fallback (Regex/Keyword based). Returns list.
        """
        u = user_input.lower()
        intents = []

        if any(x in u.split() for x in ["hello", "hi", "hey", "hii", "greetings"]):
            intents.append(Intent(action="chat", tool_name="chat_tool", parameters={"message": "Hello! I am your AI Assistant."}))
            # Don't return yet, might be "Hi, open chrome"

        # Handle complex "open X and search/go to Y" commands
        if ("launch" in u or "open" in u) and ("search" in u or "go to" in u or ".com" in u or ".org" in u):
            # Split on "and" to get app and action
            parts = u.replace("launch", "open").split(" and ")
            if len(parts) >= 2:
                # First part: app to open
                app_part = parts[0].replace("open", "").strip()
                # Second part: URL or search term
                action_part = " and ".join(parts[1:]).strip()
                
                # Determine the browser from app_part
                browser = "chrome" if "chrome" in app_part else "edge" if "edge" in app_part else None
                
                # Build the URL
                url = None
                search_part = action_part.replace("search", "").replace("go to", "").strip()
                
                # Check if it's already a URL-like string
                if any(x in search_part for x in [".com", ".org", ".net", ".io", "http"]):
                    url = search_part if search_part.startswith("http") else f"https://{search_part}"
                elif search_part:
                    # It's a search query
                    url = f"https://www.google.com/search?q={search_part.replace(' ', '+')}"
                
                if browser and url:
                    # Launch the specific browser with the URL
                    intents.append(Intent(
                        action="launch_app", 
                        tool_name="launch_app", 
                        parameters={"app_name": browser, "extra_args": url}
                    ))
                elif url:
                    # Just navigate to URL
                    intents.append(Intent(
                        action="browser_navigate", 
                        tool_name="browser_navigate", 
                        parameters={"url": url}
                    ))
                    
                if intents:
                    return intents



        # Simple app launch
        # Fix: Prevent "check telegram" from being parsed as "open telegram"
        if ("launch" in u or "open" in u) and "telegram" not in u:
             clean_u = u.replace("launch", "").replace("open", "").strip()
             # Remove common filler words
             for word in ["the", "my", "a", "an"]:
                 clean_u = clean_u.replace(f" {word} ", " ")
             clean_u = clean_u.strip()
             if clean_u:
                 intents.append(Intent(action="launch_app", tool_name="launch_app", parameters={"app_name": clean_u}))

        # Memory storage fallback
        if any(k in u for k in ["remember", "save", "note that", "memorize"]):
            # Extract what to remember (everything after the keyword)
            for keyword in ["remember", "save", "note that", "memorize"]:
                if keyword in u:
                    text = u.split(keyword, 1)[1].strip()
                    if text:
                        intents.append(Intent(
                            action="store_memory", 
                            tool_name="store_memory", 
                            parameters={"text": text}
                        ))
                    break

        # Vision / Surveillance Fallback
        if any(x in u for x in ["cctv", "surveillance", "scan", "camera"]):
            if "start" in u or "activate" in u or "open" in u or "monitor" in u or u in ["cctv", "start surveillance"]:
                intents.append(Intent(action="start_surveillance", tool_name="start_surveillance", parameters={"camera_index": 0}))
            elif "stop" in u or "close" in u or "end" in u:
                intents.append(Intent(action="stop_surveillance", tool_name="stop_surveillance", parameters={}))

        # Direct URL detection
        if any(x in u for x in [".com", ".org", ".net", ".io"]) and "browser_navigate" not in [i.action for i in intents]:
            import re
            url_match = re.search(r'(\S+\.(com|org|net|io)\S*)', u)
            if url_match:
                url = url_match.group(1)
                if not url.startswith("http"):
                    url = f"https://{url}"
                intents.append(Intent(action="browser_navigate", tool_name="browser_navigate", parameters={"url": url}))

        # ==================== PC SYSTEM COMMAND KEYWORD OVERRIDES ====================
        # These catch system commands when the LLM is unavailable

        # Power commands
        if any(k in u for k in ["shut down", "shutdown", "power off", "turn off the computer", "turn off the pc"]):
            return [Intent(action="system_power", tool_name="system_power", parameters={"operation": "shutdown"}, confidence=0.95)]
        if any(k in u for k in ["restart", "reboot"]):
            return [Intent(action="system_power", tool_name="system_power", parameters={"operation": "restart"}, confidence=0.95)]
        if u in ["hibernate"]:
            return [Intent(action="system_power", tool_name="system_power", parameters={"operation": "hibernate"}, confidence=0.95)]
        if any(k in u for k in ["put the computer to sleep", "put my computer to sleep"]) or u == "sleep":
            return [Intent(action="system_power", tool_name="system_power", parameters={"operation": "sleep"}, confidence=0.95)]
        if any(k in u for k in ["lock the screen", "lock the computer", "lock my computer", "lock screen"]):
            return [Intent(action="system_power", tool_name="system_power", parameters={"operation": "lock"}, confidence=0.95)]
        if any(k in u for k in ["log off", "sign out"]):
            return [Intent(action="system_power", tool_name="system_power", parameters={"operation": "logoff"}, confidence=0.95)]

        # Volume commands
        if any(k in u for k in ["increase volume", "volume up", "turn up the volume", "louder"]):
            return [Intent(action="volume", tool_name="volume", parameters={"direction": "up", "step": 10}, confidence=0.95)]
        if any(k in u for k in ["decrease volume", "volume down", "turn down the volume", "quieter", "softer"]):
            return [Intent(action="volume", tool_name="volume", parameters={"direction": "down", "step": 10}, confidence=0.95)]
        if u in ["mute", "mute audio", "mute sound"]:
            return [Intent(action="volume", tool_name="volume", parameters={"action": "mute"}, confidence=0.95)]
        if u in ["unmute", "unmute audio", "unmute sound"]:
            return [Intent(action="volume", tool_name="volume", parameters={"action": "unmute"}, confidence=0.95)]

        # Brightness commands
        if any(k in u for k in ["increase brightness", "brightness up", "brighter", "turn up the brightness"]):
            return [Intent(action="brightness", tool_name="brightness", parameters={"direction": "up", "step": 10}, confidence=0.95)]
        if any(k in u for k in ["decrease brightness", "brightness down", "dimmer", "turn down the brightness"]):
            return [Intent(action="brightness", tool_name="brightness", parameters={"direction": "down", "step": 10}, confidence=0.95)]

        # Display commands
        if any(k in u for k in ["dark mode", "enable dark mode", "turn on dark mode"]):
            return [Intent(action="display_control", tool_name="display_control", parameters={"mode": "dark"}, confidence=0.95)]
        if any(k in u for k in ["light mode", "disable dark mode", "turn off dark mode"]):
            return [Intent(action="display_control", tool_name="display_control", parameters={"mode": "light"}, confidence=0.95)]

        # Window management
        if any(k in u for k in ["minimize all", "show desktop", "hide all windows"]):
            return [Intent(action="window_management", tool_name="window_management", parameters={"operation": "minimize_all"}, confidence=0.95)]
        if any(k in u for k in ["task view", "show all open windows"]):
            return [Intent(action="window_management", tool_name="window_management", parameters={"operation": "task_view"}, confidence=0.95)]

        # Screenshot
        if any(k in u for k in ["take a screenshot", "take screenshot", "screenshot"]):
            return [Intent(action="screenshot", tool_name="screenshot", parameters={"mode": "full"}, confidence=0.95)]
        if "start screen recording" in u:
            return [Intent(action="screen_record", tool_name="screen_record", parameters={"action": "start"}, confidence=0.95)]
        if "stop screen recording" in u:
            return [Intent(action="screen_record", tool_name="screen_record", parameters={"action": "stop"}, confidence=0.95)]

        # Network
        if any(k in u for k in ["show my ip", "what's my ip", "what is my ip"]):
            return [Intent(action="network_control", tool_name="network_control", parameters={"operation": "show_ip"}, confidence=0.95)]
        if any(k in u for k in ["flush dns", "flush dns cache"]):
            return [Intent(action="network_control", tool_name="network_control", parameters={"operation": "flush_dns"}, confidence=0.95)]
        if any(k in u for k in ["speed test", "run speed test", "test bandwidth"]):
            return [Intent(action="network_control", tool_name="network_control", parameters={"operation": "speed_test"}, confidence=0.95)]

        # Settings
        if "check for updates" in u or "check for windows update" in u:
            return [Intent(action="open_settings", tool_name="open_settings", parameters={"page": "windowsupdate"}, confidence=0.95)]

        # File management
        if any(k in u for k in ["empty the recycle bin", "empty recycle bin"]):
            return [Intent(action="disk_management", tool_name="disk_management", parameters={"operation": "empty_recycle_bin"}, confidence=0.95)]
        if "disk cleanup" in u or "run disk cleanup" in u:
            return [Intent(action="disk_management", tool_name="disk_management", parameters={"operation": "disk_cleanup"}, confidence=0.95)]

        if not intents:
             return [Intent(action="unknown", reasoning="Fallback parser could not understand.")]
             
        return intents

