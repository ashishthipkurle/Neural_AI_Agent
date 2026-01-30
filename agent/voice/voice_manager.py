"""
Voice Manager - Unified voice system coordinator.

This module integrates wake word, STT, TTS, and emotion control
into a cohesive voice interaction system.
"""
import logging
import asyncio
import uuid
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from .emotion_controller import EmotionController, Emotion


class VoiceState(Enum):
    """Voice system states."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@dataclass
class VoiceConfig:
    """Voice system configuration."""
    wake_words: list
    greeting_message: str
    confirm_before_action: bool
    voice_speed: float
    enable_emotion: bool


class VoiceManager:
    """
    Unified voice interaction manager.
    
    Features:
    - Wake word activation
    - Voice confirmation for actions
    - Emotion-aware speech
    - Humanoid-level conversation
    
    Behavior rules:
    - Greet user on activation
    - Speak naturally and briefly
    - NEVER speak during destructive actions without confirmation
    """
    
    DEFAULT_GREETING = "Hey there! How can I help?"
    
    def __init__(
        self,
        wake_word_engine=None,
        stt_engine=None,
        tts_engine=None,
        config: VoiceConfig = None
    ):
        """
        Initialize voice manager.
        """
        self.logger = logging.getLogger("VoiceManager")
        
        self.config = config or VoiceConfig(
            wake_words=[
                "hey neural", "neural", "new role", "new rule", "neutral", 
                "near all", "hii bro", "hey bro", "hi bro",
                "hey newton", "hey annual", "hey new right", "he knew that", "henry",
                "hey noodle", "he noodle"
            ],
            greeting_message=self.DEFAULT_GREETING,
            confirm_before_action=True,
            voice_speed=1.0,
            enable_emotion=True
        )
        
        # Instantiate engines if None
        if wake_word_engine is None:
            try:
                from .wake_word import WakeWordEngine
                wake_word_engine = WakeWordEngine(
                    wake_words=self.config.wake_words
                )
            except Exception as e:
                self.logger.error(f"Failed to load WakeWordEngine: {e}")
                
        if stt_engine is None:
            try:
                from .stt import SpeechToText
                stt_engine = SpeechToText()
            except Exception as e:
                self.logger.error(f"Failed to load SpeechToText: {e}")
                
        if tts_engine is None:
            try:
                from .tts import TextToSpeech
                tts_engine = TextToSpeech()
            except Exception as e:
                self.logger.error(f"Failed to load TextToSpeech: {e}")

        self.wake_word = wake_word_engine
        self.stt = stt_engine
        self.tts = tts_engine
        self.emotion = EmotionController()
        
        self._state = VoiceState.IDLE
        self._on_wake_callback: Optional[Callable] = None
        self._on_input_callback: Optional[Callable] = None
        
        # New synchronization hooks
        self.on_stt: Optional[Callable[[str], None]] = None
        self.on_partial: Optional[Callable[[str], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        
        self._running = False
        self.is_busy = False
        self.is_muted = False  # User can mute via UI
        
        self.logger.info("VoiceManager initialized.")
    
    def set_busy(self, busy: bool):
        """Set voice system busy state."""
        self.is_busy = busy
        if busy:
            self.logger.info("Voice system locked (BUSY).")
            self._state = VoiceState.PROCESSING
        else:
            self.logger.info("Voice system unlocked (IDLE).")
            self._state = VoiceState.IDLE
    
    def set_muted(self, muted: bool):
        """Mute/unmute voice capture from UI."""
        self.is_muted = muted
        if muted:
            self.logger.info("Voice system MUTED by user.")
            if self.on_status:
                self.on_status("Microphone muted")
        else:
            self.logger.info("Voice system UNMUTED by user.")
            if self.on_status:
                self.on_status("Microphone active")

    @property
    def state(self) -> VoiceState:
        """Get current voice state."""
        return self._state
    
    async def greet(self) -> None:
        """Speak greeting message."""
        import random
        greetings = [
            "Hey there! How can I help?",
            "Hi, I'm listening.",
            "Hey, what's up?",
            "Ready for command.",
            "Greetings. What do you need?",
            "Yes? I'm here.",
            "Neural online. Go ahead."
        ]
        chosen = random.choice(greetings)
        await self.speak(chosen, emotion=Emotion.HAPPY)
    
    async def speak(
        self, 
        text: str, 
        emotion: Emotion = None, 
        wait: bool = True,
        suppress_sync: bool = False
    ) -> None:
        """
        Speak text with optional emotion.
        """
        if not self.tts:
            self.logger.warning("TTS not available.")
            return
        
        # Broadcast to UI if sync hook available
        if not suppress_sync and self.on_status:
            # We use 'assistant' type for speech to mirror in chat
            self.on_status(text, role="assistant")
            
            # Yield to event loop to let the message flush
            await asyncio.sleep(0.05)

        self._state = VoiceState.SPEAKING
        
        try:
            # Detect emotion if not provided
            if emotion is None and self.config.enable_emotion:
                emotion = self.emotion.detect_emotion(text)
            
            # Speak
            self.logger.debug(f"Speaking: {text[:50]}... (emotion={emotion})")
            
            if hasattr(self.tts, 'speak'):
                emotion_str = emotion.value if emotion else "neutral"
                
                # Run blocking TTS in executor
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    None, 
                    lambda: self.tts.speak(text, emotion=emotion_str, wait=wait)
                )
            
        except Exception as e:
            self.logger.error(f"TTS error: {e}")
        finally:
            # Revert to processing if busy, else idle
            if self.is_busy:
                self._state = VoiceState.PROCESSING
            else:
                self._state = VoiceState.IDLE
    
    async def listen(self, timeout: float = 10.0) -> Optional[str]:
        """
        Listen for voice input.
        
        Args:
            timeout: Maximum listening time.
        
        Returns:
            Recognized text or None.
        """
        if not self.stt:
            self.logger.warning("STT not available.")
            return None
        
        self._state = VoiceState.LISTENING
        
        try:
            self.logger.debug(f"Listening (timeout={timeout}s)...")
            if self.on_status:
                self.on_status("Listening...")
            
            # Run blocking listen in executor to allow status update to flush
            if hasattr(self.stt, 'listen'):
                loop = asyncio.get_running_loop()
                text = await loop.run_in_executor(
                    None, 
                    lambda: self.stt.listen(timeout=timeout, on_partial=self.on_partial)
                )
                
                if text:
                    # Check if muted during listen
                    if self.is_muted:
                        self.logger.info("Discarding input because microphone was muted.")
                        if self.on_status:
                             self.on_status("Microphone muted")
                        return None
                        
                    self.logger.info(f"Heard: {text}")
                    if self.on_stt:
                        self.on_stt(text)
                    return text
            
            return None
            
        except Exception as e:
            self.logger.error(f"STT error: {e}")
            return None
        finally:
            if self.is_busy:
                self._state = VoiceState.PROCESSING
            else:
                self._state = VoiceState.IDLE
    
    async def confirm_action(self, action_description: str) -> bool:
        """
        Request voice confirmation for action.
        
        Args:
            action_description: Description of pending action.
        
        Returns:
            True if confirmed, False if denied.
        """
        if not self.config.confirm_before_action:
            return True
        
        # Speak confirmation request
        prompt = f"I'm about to {action_description}. Should I proceed?"
        await self.speak(prompt, emotion=Emotion.CONCERNED)
        
        # Listen for response
        response = await self.listen(timeout=10.0)
        
        if response:
            response_lower = response.lower()
            
            # Check for affirmative
            affirmative = {"yes", "yeah", "yep", "sure", "go ahead", "proceed", "do it"}
            if any(aff in response_lower for aff in affirmative):
                await self.speak("Alright, proceeding.", emotion=Emotion.CONFIDENT)
                return True
            
            # Check for negative
            negative = {"no", "nope", "stop", "cancel", "don't", "wait"}
            if any(neg in response_lower for neg in negative):
                await self.speak("Okay, I'll cancel that.", emotion=Emotion.CALM)
                return False
        
        # Timeout or unclear response
        await self.speak("I didn't get a clear response. Cancelling for safety.", emotion=Emotion.APOLOGETIC)
        return False
    
    async def start_voice_loop(
        self,
        on_wake: Callable[[], Awaitable[None]] = None,
        on_input: Callable[[str], Awaitable[None]] = None
    ) -> None:
        """
        Start the voice interaction loop.
        
        Args:
            on_wake: Callback when wake word detected.
            on_input: Callback when voice input received.
        """
        self._on_wake_callback = on_wake
        self._on_input_callback = on_input
        self._running = True
        
        self.logger.info("Starting voice loop...")
        
        while self._running:
            try:
                # 0. Check BUSY LOCK
                if self.is_busy:
                    await asyncio.sleep(0.5)
                    continue

                # 0b. Check MUTED state
                if self.is_muted:
                    await asyncio.sleep(0.5)
                    continue

                # 1. Wait for wake word
                if self.wake_word and hasattr(self.wake_word, 'wait_for_wake_word'):
                    self.logger.debug("Waiting for wake word...")
                    
                    # Broadcast listening state to UI (only if not muted)
                    # Note: We don't use 'Listening...' here because this is passive wake word listening
                    # But user wants to know agent is active? Maybe 'Ready' or nothing.
                    # 'Listening...' usually implies active command listening.
                    pass
                    
                    # Run the blocking wake word detection in a thread
                    # Pass a lambda that returns current mute state so engine can check it dynamically
                    loop = asyncio.get_event_loop()
                    text = await loop.run_in_executor(
                        None, 
                        lambda: self.wake_word.wait_for_wake_word(
                            on_partial=self.on_partial,
                            is_muted_callback=lambda: self.is_muted,
                            should_pause_callback=lambda: self.is_busy or self._state == VoiceState.SPEAKING or self._state == VoiceState.LISTENING
                        )
                    )
                    
                    if text and self._running:
                        # 2. Detected!
                        self.logger.info(f"Wake word detected: {text}")
                        
                        # 3. Acknowledge and notify
                        if self._on_wake_callback:
                            await self._on_wake_callback()
                        else:
                            await self.acknowledge()
                        
                        # 4. Listen for command
                        # Briefly wait for user to start speaking if they didn't include command in wake sentence
                        command = await self.listen(timeout=8.0)
                        if command and self._on_input_callback:
                            await self._on_input_callback(command)
                else:
                    # If no wake word engine, just sleep to prevent hogging CPU
                    await asyncio.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Voice loop error: {e}")
                await asyncio.sleep(2)
    
    def stop_voice_loop(self) -> None:
        """Stop the voice interaction loop."""
        self._running = False
        self.logger.info("Voice loop stopped.")
    
    async def acknowledge(self, variation: int = 0) -> None:
        """Speak acknowledgment."""
        acknowledgments = [
            "Got it.",
            "Understood.",
            "On it.",
            "Alright.",
            "Sure thing."
        ]
        acknowledgment = acknowledgments[variation % len(acknowledgments)]
        if self.on_status:
            self.on_status(acknowledgment, "system")
        await self.speak(acknowledgment, suppress_sync=True)
    
    async def report_success(self, action: str = "done") -> None:
        """Report successful action completion."""
        message = f"Done. {action}"
        if self.on_status:
            self.on_status(message, "system")
        await self.speak(message, emotion=Emotion.HAPPY, suppress_sync=True)
    
    async def report_error(self, error: str) -> None:
        """Report an error."""
        message = f"I ran into an issue. {error}"
        if self.on_status:
            self.on_status(message, "system")
        await self.speak(
            message,
            emotion=Emotion.APOLOGETIC,
            suppress_sync=True
        )
    
    def is_available(self) -> bool:
        """Check if voice system is available."""
        return self.stt is not None or self.tts is not None
