"""
Voice Skill - Speech input/output capabilities.

Wraps existing TTS and STT functionality as a skill for:
- Speaking responses
- Listening for input
- Voice notifications
- Progress updates
"""

import logging
from typing import Dict, Any, Optional

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth


class VoiceSkill(BaseSkill):
    """
    Voice interaction skill.
    
    Actions:
    - speak: Convert text to speech
    - listen: Listen for voice input
    - notify: Speak a notification
    - confirm: Ask for confirmation
    - progress: Speak progress update
    """
    
    def __init__(self):
        super().__init__()
        self._tts = None
        self._stt = None
    
    @property
    def name(self) -> str:
        return "voice"
    
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="voice",
            version="1.0.0",
            description="Speech input/output for human interaction",
            actions=["speak", "listen", "notify", "confirm", "progress"],
            requires=["edge-tts"],
            permissions=["audio"]
        )
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """Initialize TTS and STT engines."""
        try:
            from agent.voice.tts import TextToSpeech
            self._tts = TextToSpeech()
            self.logger.info("Voice skill: TTS loaded.")
        except Exception as e:
            self.logger.error(f"Failed to load TTS: {e}")
        
        try:
            from agent.voice.stt import SpeechRecognizer
            self._stt = SpeechRecognizer()
            self.logger.info("Voice skill: STT loaded.")
        except Exception as e:
            self.logger.warning(f"STT not available: {e}")
        
        super().on_load()
    
    def on_unload(self) -> None:
        """Cleanup voice resources."""
        super().on_unload()
    
    # ==================== INTENT MATCHING ====================
    
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill can handle the intent."""
        intent_lower = intent.lower()
        
        if any(x in intent_lower for x in ["say", "speak", "tell me", "read aloud"]):
            return 0.85
        
        if any(x in intent_lower for x in ["listen", "hear", "voice input"]):
            return 0.8
        
        return 0.0
    
    # ==================== EXECUTION ====================
    
    def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Execute a voice action."""
        
        handlers = {
            "speak": self._action_speak,
            "listen": self._action_listen,
            "notify": self._action_notify,
            "confirm": self._action_confirm,
            "progress": self._action_progress,
        }
        
        handler = handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")
        
        try:
            return handler(params, context or {})
        except Exception as e:
            self.logger.error(f"Voice action '{action}' failed: {e}")
            return SkillResult(success=False, error=str(e))
    
    # ==================== ACTIONS ====================
    
    def _action_speak(self, params: Dict, context: Dict) -> SkillResult:
        """Speak text."""
        text = params.get("text", "")
        
        if not text:
            return SkillResult(success=False, error="Text required")
        
        if not self._tts:
            return SkillResult(success=False, error="TTS not available")
        
        self._tts.speak(text)
        
        return SkillResult(
            success=True,
            message=f"Spoke: {text[:50]}..."
        )
    
    def _action_listen(self, params: Dict, context: Dict) -> SkillResult:
        """Listen for voice input."""
        timeout = params.get("timeout", 10)
        
        if not self._stt:
            return SkillResult(success=False, error="STT not available")
        
        try:
            # This would block and listen
            text = self._stt.listen(timeout=timeout)
            return SkillResult(
                success=True,
                data={"text": text},
                message=f"Heard: {text}"
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _action_notify(self, params: Dict, context: Dict) -> SkillResult:
        """Speak a notification with appropriate tone."""
        message = params.get("message", "")
        urgency = params.get("urgency", "normal")  # low, normal, high
        
        if not self._tts:
            return SkillResult(success=False, error="TTS not available")
        
        # Could adjust voice/speed based on urgency in future
        self._tts.speak(message)
        
        return SkillResult(success=True, message="Notification spoken")
    
    def _action_confirm(self, params: Dict, context: Dict) -> SkillResult:
        """Ask for confirmation."""
        question = params.get("question", "Are you sure?")
        
        if not self._tts or not self._stt:
            return SkillResult(success=False, error="TTS/STT not available")
        
        # Speak the question
        self._tts.speak(question)
        
        # Listen for response
        try:
            response = self._stt.listen(timeout=10)
            confirmed = any(x in response.lower() for x in ["yes", "yeah", "yep", "confirm", "sure"])
            
            return SkillResult(
                success=True,
                data={"confirmed": confirmed, "response": response},
                message=f"User said: {response}"
            )
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _action_progress(self, params: Dict, context: Dict) -> SkillResult:
        """Speak a progress update."""
        message = params.get("message", "Working on it...")
        
        if not self._tts:
            # Silently succeed if TTS not available
            return SkillResult(success=True, message="(Progress update silent - TTS unavailable)")
        
        self._tts.speak(message)
        
        return SkillResult(success=True, message="Progress spoken")
    
    # ==================== HEALTH ====================
    
    def health(self) -> SkillHealth:
        """Check voice skill health."""
        if not self._loaded:
            return SkillHealth.UNAVAILABLE
        if not self._tts:
            return SkillHealth.UNAVAILABLE
        if not self._stt:
            return SkillHealth.DEGRADED  # Can speak but not listen
        return SkillHealth.READY
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """Preview voice action."""
        if action == "speak":
            return f"Would say: {params.get('text', '')[:50]}..."
        if action == "listen":
            return f"Would listen for {params.get('timeout', 10)} seconds"
        return f"Would execute voice.{action}"
