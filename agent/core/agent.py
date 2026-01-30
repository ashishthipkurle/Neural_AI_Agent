
import yaml
import logging
import time
from agent.core.intent import IntentParser
from agent.core.router import ToolRouter
from agent.ui.server import GUIServer, UIMessageType

class Agent:
    """
    Main orchestrator for the AI Agent.
    """
    def __init__(self, config_path: str = "agent/config/settings.yaml"):
        # Load config first
        self.config = self._load_config(config_path)
        self._setup_logging()
        
        # Initialize components
        self.ui_server = GUIServer()
        self.ui_server.start()
        
        self.router = ToolRouter() 
        self.intent_parser = IntentParser(self.config)
        self.voice = None
        
        # Link Vision Events to GUI
        self.router.vision_tools.set_event_callback(self.ui_server.send_update)

    def _load_config(self, path: str) -> dict:
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not load config from {path}: {e}")
            return {}

    def _setup_logging(self):
        level = self.config.get('agent', {}).get('log_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("Agent")

    def tick(self):
        """
        Runs background tasks. Should be called frequently.
        """
        self.router.scheduler.run_pending()

    def enable_voice(self):
        """
        Initializes the Voice Interface (Voice 2.0).
        """
        try:
            from agent.core.voice import VoiceInterface
            self.voice = VoiceInterface(self.config)
            self.logger.info("Voice Mode Enabled")
            # self.voice.speak("System Online. Listening.") 
            # Commented out to avoid auto-speak on init if undesired
        except Exception as e:
            self.logger.error(f"Failed to enable voice: {e}")

    def run_voice_loop(self):
        """
        Voice 2.0 Main Loop.
        Uses Blocking Wake Word -> Active Mode.
        """
        if not hasattr(self, 'voice') or not self.voice:
            self.enable_voice()
            
        if not self.voice:
            print("Voice interface could not be initialized.")
            return

        print("--- Voice Mode Active (Offline) ---")
        self.voice.speak("System online. Waiting for wake word.", emotion="happy")

        while True:
            try:
                # 1. Wait for Wake Word (Blocking)
                print("Waiting for wake word...")
                wake_word = self.voice.wait_for_wake_word()
                
                if not wake_word:
                    print("Wake word engine unavailable. Exiting voice mode.")
                    self.voice.speak("Voice system unavailable.", emotion="sad")
                    break
                    
                print(f"Wake word detected: {wake_word}")
                self.voice.speak("Yes?", emotion="neutral")
                
                # 2. Enter Active Conversation Loop
                active_mode = True
                consecutive_silence = 0
                
                while active_mode:
                    # Listen for command
                    print("Listening for command...")
                    self.ui_server.send_update(UIMessageType.STATUS, "listening")
                    user_input = self.voice.listen(timeout=8)
                    
                    if not user_input:
                        consecutive_silence += 1
                        if consecutive_silence >= 2:
                            active_mode = False
                        continue
                    
                    # Reset silence counter if we heard something
                    consecutive_silence = 0
                    
                    self.ui_server.send_update(UIMessageType.TRANSCRIPT, {"type": "user", "text": user_input})
                    self.ui_server.send_update(UIMessageType.STATUS, "processing")
                    
                    # If user said "exit" or similar, break
                    if user_input.lower() in ["exit", "stop", "goodbye", "sleep"]:
                        self.voice.speak("Going to sleep.", emotion="calm")
                        active_mode = False
                        self.ui_server.send_update(UIMessageType.STATUS, "idle")
                        continue
                    
                    # Process input
                    print(f"User: {user_input}")
                    responses = self._process_input_and_return_responses(user_input)
                    
                    # Speak responses
                    self.ui_server.send_update(UIMessageType.STATUS, "speaking")
                    for response in responses:
                        self.ui_server.send_update(UIMessageType.TRANSCRIPT, {"type": "agent", "text": response})
                        # Todo: infer emotion from response content?? For now neutral/happy
                        self.voice.speak(response)
                        
                    self.ui_server.send_update(UIMessageType.STATUS, "idle")

            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"Voice Loop Error: {e}")
                time.sleep(1)

    def _process_input_and_return_responses(self, user_input: str) -> list:
        """
        Processes input and returns a list of response strings for TTS.
        """
        self.logger.info(f"Received input: {user_input}")
        responses = []
        
        # 1. Parse Intent (Returns a LIST of intents)
        intents = self.intent_parser.parse(user_input)
        
        if not intents:
            msg = "I'm not sure what you want me to do."
            print(msg)
            return [msg]

        for intent in intents:
            self.logger.info(f"Parsed intent: {intent}")
            
            if intent.action == "unknown":
                msg = "I didn't understand that command."
                print(msg)
                responses.append(msg)
                continue

            # 2. Check Permissions / Command Authority
            from agent.security.permissions import requires_confirmation
            
            # Check if intent action warrants confirmation
            if requires_confirmation(intent.action):
                warning_msg = f"The action '{intent.action}' requires confirmation. Should I proceed?"
                print(f"[AUTHORITY] {warning_msg}")
                
                # Check if voice enabled, if so speak and listen
                if hasattr(self, 'voice') and self.voice:
                    self.voice.speak(warning_msg, emotion="serious")
                    confirmation = self.voice.listen(timeout=5)
                    if not confirmation or "yes" not in confirmation.lower():
                        msg = "Action cancelled by user."
                        self.logger.info(msg)
                        self.voice.speak(msg, emotion="neutral")
                        responses.append(msg)
                        continue
                else:
                    # Text mode confirmation
                    response = input("Confirm (yes/no): ")
                    if "yes" not in response.lower():
                        print("Action cancelled.")
                        responses.append("Action cancelled.")
                        continue

            # 3. Route to Tool
            try:
                result = self.router.route(intent)
                
                # 4. Handle Result
                if result:
                    print(result)
                    # If it's a chat response, speak it directly.
                    if intent.action in ["chat", "chat_tool", "search_online", "search_memory"]:
                        # result is "Agent: [Message]"
                        clean_res = str(result).replace("Agent:", "").strip()
                        responses.append(clean_res)
                    else:
                        # For actions, just confirm strictly
                        if "Launched" in str(result):
                            responses.append(str(result))
                        elif "Calculated" in str(result) or "Result" in str(result):
                             responses.append(str(result))
                        else:
                            responses.append("Done.")
            except Exception as e:
                self.logger.error(f"Error executing tool {intent.action}: {e}")
                msg = f"I couldn't complete that action. {str(e)}"
                print(msg)
                responses.append(msg)
                                
        return responses

    def run(self, user_input: str) -> str:
        """
        Main execution loop for a single turn (Text Mode).
        """
        # Run scheduled jobs before processing input
        self.tick()
        self._process_input_and_return_responses(user_input)
        return ""
