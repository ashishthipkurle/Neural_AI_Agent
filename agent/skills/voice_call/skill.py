
import logging
import json
import os
import time
from typing import List, Dict, Any, Optional
from agent.skills.base_skill import BaseSkill, SkillManifest, SkillResult
from agent.memory.personal_memory import PersonalMemoryManager

# Try imports
try:
    from twilio.rest import Client
    from twilio.twiml.voice_response import VoiceResponse, Connect
except ImportError:
    Client = None
    VoiceResponse = None

class AdvancedVoiceCallSkill(BaseSkill):
    """
    Module 9: Advanced Voice Call Skill
    Full-duplex conversational voice calls via Twilio/Deepgram/ElevenLabs.
    """

    def __init__(self, config: Dict[str, Any], personal_memory: PersonalMemoryManager):
        self._name = "voice_call"
        super().__init__()
        self.config = config
        self.memory = personal_memory
        
        # Config
        self.twilio_config = self.config.get('voice_calls', {}).get('twilio', {})
        self.deepgram_key = self.config.get('voice_calls', {}).get('deepgram_api_key')
        self.elevenlabs_key = self.config.get('voice_calls', {}).get('elevenlabs_api_key')
        
        # State
        self.active_calls = {} # call_sid -> {status, transcript, ...}
        self.client = None
        
        # Initialize Twilio Client
        if Client and self.twilio_config.get('account_sid'):
            try:
                self.client = Client(
                    self.twilio_config['account_sid'],
                    self.twilio_config['auth_token']
                )
            except Exception as e:
                self.logger.error(f"Failed to init Twilio client: {e}")

    @property
    def name(self) -> str:
        return self._name

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name=self.name,
            version="1.0.0",
            description="Advanced conversational voice calling.",
            actions=["make_call", "end_call"],
            requires=["twilio", "deepgram-sdk", "elevenlabs"],
            permissions=["network", "microphone"]
        )

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Match: 'call', 'phone', 'dial', 'make_call'"""
        text = intent.lower() if isinstance(intent, str) else str(intent).lower()
        keywords = ['call', 'phone', 'dial', 'make a call']
        if any(k in text for k in keywords):
            return 0.9
        return 0.0

    async def execute(self, action: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        if action == "make_call":
            phone_number = params.get('phone_number')
            contact_name = params.get('contact_name')
            purpose = params.get('purpose')
            
            if not phone_number:
                 # Try to look up by name in memory
                 if contact_name:
                     rel = self.memory.get_relationship(contact_name)
                     if rel and rel.get('phone_number'):
                         phone_number = rel.get('phone_number')
            
            if not phone_number:
                return SkillResult(success=False, error="No phone number provided or found.")

            result = self.make_intelligent_call(phone_number, contact_name, purpose)
            
            if result and not result.startswith("ERROR:"):
                call_sid = result
                msg = f"Call initiated to {contact_name or phone_number}."
                if purpose:
                    msg += f" Purpose: {purpose}"
                return SkillResult(success=True, message=msg, data={"call_sid": call_sid, "status": "initiated"})
            else:
                error_msg = result if result else "Failed to initiate call."
                return SkillResult(success=False, message=error_msg, error=error_msg)
                
        elif action == "end_call":
             call_sid = params.get('call_sid')
             self.end_call_gracefully(call_sid)
             return SkillResult(success=True, message="Call ended.")
             
        return SkillResult(success=False, error=f"Unknown action: {action}")

    def make_intelligent_call(self, phone_number: str, 
                              contact_name: str = None,
                              purpose: str = None,
                              user_context_override: str = None) -> Optional[str]:
        """
        Make an interactive voice call using ngrok tunnel + Twilio webhooks.
        The call will have a real conversation with the recipient.
        """
        if not self.client:
            self.logger.error("Twilio client not initialized.")
            return "ERROR: Twilio client not initialized."

        # Get the user's name (who is placing the call)
        caller_name = "your friend"
        try:
            with self.memory._get_connection() as conn:
                cursor = conn.execute("SELECT name FROM user_profile LIMIT 1")
                row = cursor.fetchone()
                if row and row[0]:
                    caller_name = row[0]
        except Exception:
            pass
        
        try:
            # Start ngrok tunnel if not already running
            public_url = self._get_ngrok_url()
            if not public_url:
                return "ERROR: Could not establish ngrok tunnel. Make sure ngrok is configured."
            
            self.logger.info(f"ngrok public URL: {public_url}")
            
            # Build webhook URL with conversation params
            import urllib.parse
            params = urllib.parse.urlencode({
                "purpose": purpose or "check in",
                "contact_name": contact_name or "friend",
                "caller_name": caller_name
            })
            answer_url = f"{public_url}/voice/answer?{params}"
            
            self.logger.info(f"Webhook URL: {answer_url}")
            
            # Initiate the call with webhook URL
            call = self.client.calls.create(
                to=phone_number,
                from_=self.twilio_config.get('from_number'),
                url=answer_url,
                status_callback=f"{public_url}/voice/status",
                status_callback_event=["initiated", "ringing", "answered", "completed"]
            )
            
            # Register in active calls
            self.active_calls[call.sid] = {
                "status": "initiated",
                "contact_name": contact_name,
                "purpose": purpose,
                "caller_name": caller_name,
                "transcript": []
            }
            
            self.logger.info(f"Interactive call initiated to {phone_number} ({contact_name}). SID: {call.sid}")
            return call.sid
            
        except Exception as e:
            self.logger.error(f"Twilio call failed: {e}")
            error_str = str(e)
            if "unverified" in error_str.lower():
                return "ERROR: Cannot call this number. On Twilio trial accounts, you must first verify the number at console.twilio.com."
            return f"ERROR: Call failed - {error_str}"

    def _get_ngrok_url(self) -> Optional[str]:
        """Get or create an ngrok tunnel to the local API server."""
        # Check if we already have a cached tunnel URL
        if hasattr(self, '_ngrok_url') and self._ngrok_url:
            try:
                # Verify it's still active
                from pyngrok import ngrok
                tunnels = ngrok.get_tunnels()
                for t in tunnels:
                    if t.public_url == self._ngrok_url:
                        return self._ngrok_url
            except Exception:
                pass
        
        try:
            from pyngrok import ngrok
            
            # Close any existing tunnels first
            try:
                for t in ngrok.get_tunnels():
                    ngrok.disconnect(t.public_url)
            except Exception:
                pass
            
            # Create new tunnel to port 8000 (our FastAPI server)
            tunnel = ngrok.connect(8000, "http")
            self._ngrok_url = tunnel.public_url
            
            # Ensure HTTPS
            if self._ngrok_url.startswith("http://"):
                self._ngrok_url = self._ngrok_url.replace("http://", "https://")
            
            self.logger.info(f"ngrok tunnel established: {self._ngrok_url}")
            return self._ngrok_url
            
        except Exception as e:
            self.logger.error(f"Failed to start ngrok tunnel: {e}")
            return None

    def _handle_call_stream(self, call_sid: str, contact_name: str, 
                            purpose: str, user_context: str):
        """
        WebSocket handler for real-time conversation.
        NOTE: This method is typically called by the API Server's WebSocket route, 
        passing the stream data to this skill.
        """
        # Placeholder for full duplex logic which requires WS connection handling.
        pass

    def generate_response(self, contact_message: str,
                          conversation_history: List[dict],
                          user_context: str,
                          purpose: str,
                          contact_info: dict = None) -> str:
        """
        Build and execute LLM prompt.
        """
        # CRITICAL: Ensure disclosure in first message if history is empty
        is_first_message = len(conversation_history) == 0
        disclosure = ""
        if is_first_message:
             user_name = "User" # Extract from user_context parsing needed
             disclosure = f"Hi, this is an AI assistant calling on behalf of {user_name}. "
        
        system_prompt = f"""
        SYSTEM: You are an AI assistant calling on behalf of a user.
        {disclosure}
        
        CONTEXT:
        {user_context}
        
        PURPOSE:
        {purpose}
        
        INSTRUCTIONS:
        - Be natural, conversational.
        - Use short sentences.
        """
        
        # Call LLM (mock or real)
        # return llm.generate(system_prompt, contact_message)
        return f"{disclosure}I'm calling about {purpose}."

    def detect_conversation_end(self, transcript: List[str]) -> bool:
        """Detect ending signals."""
        if not transcript:
            return False
        last = transcript[-1].lower()
        end_phrases = ["bye", "goodbye", "talk later", "that's all", "have a good day"]
        return any(p in last for p in end_phrases)

    def handle_interruption(self, call_sid: str):
        """Stop TTS, clear buffer."""
        self.logger.info(f"Interruption detection on {call_sid}")

    def end_call_gracefully(self, call_sid: str, summary: str = None) -> None:
        """Hang up and save summary."""
        if not self.client:
            return
            
        try:
            self.client.calls(call_sid).update(status='completed')
            self.logger.info(f"Call {call_sid} ended.")
            
            # Save memory
            call_info = self.active_calls.get(call_sid)
            if call_info and call_info.get('contact_name'):
                self.memory.update_relationship_from_call(
                    call_info['contact_name'],
                    summary or "Call completed.",
                    {}
                )
            
            self.active_calls.pop(call_sid, None)
            
        except Exception as e:
            self.logger.error(f"Failed to end call: {e}")

    def get_call_summary(self, call_sid: str) -> Dict[str, Any]:
        return self.active_calls.get(call_sid, {})
