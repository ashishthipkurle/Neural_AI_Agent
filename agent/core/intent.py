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

        # NUCLEAR OPTION: Screen Analysis ("what's on my screen", "describe my screen")
        screen_keywords = ["what's on my screen", "whats on my screen", "describe my screen", 
                          "what do you see", "what is on screen", "read my screen", 
                          "analyze my screen", "look at my screen", "what is on my screen"]
        if any(k in u_lower for k in screen_keywords):
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

        # NUCLEAR OPTION: Telegram Commands
        if "telegram" in u_lower:
            # Skip if complex command (research/search) so LLM can handle the chain
            # e.g. "Do deep research on cars and send to telegram" should NOT be trapped here
            if any(k in u_lower for k in ["research", "analysis", "find", "deep", "scan", "monitor"]):
                 pass # Fall through to LLM for complex handling
            
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
        - launch_app(app_name, extra_args): Launch an application.
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

        if not intents:
             return [Intent(action="unknown", reasoning="Fallback parser could not understand.")]
             
        return intents

