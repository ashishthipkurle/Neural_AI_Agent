"""
Emotion Controller - Emotion-aware voice modulation.

This module provides emotional context for TTS output,
adjusting prosody based on conversation context and action types.
"""
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class Emotion(Enum):
    """Supported emotional states."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    CONCERNED = "concerned"
    EXCITED = "excited"
    CALM = "calm"
    APOLOGETIC = "apologetic"
    CONFIDENT = "confident"


@dataclass
class EmotionSettings:
    """TTS modulation settings for an emotion."""
    speed_modifier: float  # 1.0 = normal, >1 = faster, <1 = slower
    pitch_modifier: float  # 1.0 = normal, >1 = higher, <1 = lower
    volume_modifier: float  # 1.0 = normal
    pauses: bool  # Add natural pauses


# Emotion to TTS settings mapping

# Emotion to TTS settings mapping
# Speed: 1.0=normal, >1=faster, <1=slower
EMOTION_PROFILES: Dict[Emotion, EmotionSettings] = {
    Emotion.NEUTRAL: EmotionSettings(1.0, 1.0, 1.0, True),
    Emotion.HAPPY: EmotionSettings(1.1, 1.1, 1.0, False),     # +10% speed
    Emotion.EXCITED: EmotionSettings(1.2, 1.15, 1.1, False),  # +20% speed
    Emotion.CALM: EmotionSettings(0.85, 0.95, 0.9, True),     # -15% speed
    Emotion.APOLOGETIC: EmotionSettings(0.8, 0.9, 0.9, True), # -20% speed
    Emotion.CONFIDENT: EmotionSettings(1.0, 1.05, 1.05, False),
    Emotion.CONCERNED: EmotionSettings(0.9, 0.95, 0.95, True),
}


class EmotionController:
    """
    Controls emotional context for voice output.
    
    Features:
    - Context-based emotion detection
    - Action-based emotion mapping
    - Prosody settings generation
    - Conversation mood tracking
    """
    
    # Keywords that suggest emotions
    EMOTION_KEYWORDS = {
        Emotion.HAPPY: {"great", "awesome", "wonderful", "happy", "success", "done"},
        Emotion.CONCERNED: {"error", "fail", "problem", "issue", "sorry", "unfortunately"},
        Emotion.EXCITED: {"new", "discover", "found", "interesting", "wow"},
        Emotion.CALM: {"okay", "sure", "alright", "understood"},
        Emotion.APOLOGETIC: {"sorry", "apologize", "mistake", "wrong"},
        Emotion.CONFIDENT: {"will", "can", "definitely", "absolutely"},
    }
    
    # Action types to emotions
    ACTION_EMOTIONS = {
        "greet": Emotion.HAPPY,
        "error": Emotion.APOLOGETIC,
        "confirm_destructive": Emotion.CONCERNED,
        "success": Emotion.HAPPY,
        "explain": Emotion.CALM,
        "alert": Emotion.CONCERNED,
        "complete": Emotion.CONFIDENT,
    }
    
    def __init__(self):
        """Initialize emotion controller."""
        self.logger = logging.getLogger("EmotionController")
        self._current_emotion = Emotion.NEUTRAL
        self._conversation_mood = 0.5  # 0 = negative, 1 = positive
        self.logger.info("EmotionController initialized.")
    
    @property
    def current_emotion(self) -> Emotion:
        """Get current emotional state."""
        return self._current_emotion
    
    def detect_emotion(self, text: str) -> Emotion:
        """
        Detect emotion from text content.
        
        Args:
            text: Text to analyze.
        
        Returns:
            Detected Emotion.
        """
        text_lower = text.lower()
        text_words = set(text_lower.split())
        
        # Check each emotion's keywords
        best_emotion = Emotion.NEUTRAL
        best_score = 0
        
        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            score = len(text_words & keywords)
            if score > best_score:
                best_score = score
                best_emotion = emotion
        
        # Update conversation mood
        if best_emotion in {Emotion.HAPPY, Emotion.EXCITED, Emotion.CONFIDENT}:
            self._conversation_mood = min(1.0, self._conversation_mood + 0.1)
        elif best_emotion in {Emotion.CONCERNED, Emotion.APOLOGETIC}:
            self._conversation_mood = max(0.0, self._conversation_mood - 0.1)
        
        self._current_emotion = best_emotion
        return best_emotion
    
    def get_emotion_for_action(self, action_type: str) -> Emotion:
        """Get appropriate emotion for an action type."""
        return self.ACTION_EMOTIONS.get(action_type, Emotion.NEUTRAL)
    
    def get_prosody_settings(self, emotion: Emotion = None) -> EmotionSettings:
        """
        Get TTS prosody settings for emotion.
        
        Args:
            emotion: Emotion to get settings for.
        
        Returns:
            EmotionSettings for TTS modulation.
        """
        emotion = emotion or self._current_emotion
        return EMOTION_PROFILES.get(emotion, EMOTION_PROFILES[Emotion.NEUTRAL])
    
    def format_for_tts(self, text: str, emotion: Emotion = None) -> str:
        """
        Format text for TTS with emotional markers.
        
        Some TTS engines support SSML or similar markup.
        This provides a generic approach.
        
        Args:
            text: Text to format.
            emotion: Emotion context.
        
        Returns:
            Formatted text (may include pauses, emphasis).
        """
        settings = self.get_prosody_settings(emotion)
        
        # Add pauses for concerned/calm emotions
        if settings.pauses:
            # Add slight pauses after sentences
            text = text.replace(". ", "... ")
            text = text.replace("? ", "...? ")
        
        return text
    
    def suggest_response_tone(self, context: str) -> str:
        """
        Suggest appropriate tone for response.
        
        Args:
            context: Current context/situation.
        
        Returns:
            Tone suggestion string.
        """
        emotion = self.detect_emotion(context)
        
        suggestions = {
            Emotion.NEUTRAL: "Maintain a helpful, professional tone.",
            Emotion.HAPPY: "Express enthusiasm and positivity.",
            Emotion.CONCERNED: "Show understanding and care.",
            Emotion.EXCITED: "Share in the excitement.",
            Emotion.CALM: "Be reassuring and measured.",
            Emotion.APOLOGETIC: "Be sincere and solution-focused.",
            Emotion.CONFIDENT: "Project assurance and capability.",
        }
        
        return suggestions.get(emotion, suggestions[Emotion.NEUTRAL])
    
    def get_mood_summary(self) -> str:
        """Get summary of conversation mood."""
        if self._conversation_mood > 0.7:
            return "positive"
        elif self._conversation_mood < 0.3:
            return "concerned"
        else:
            return "neutral"
    
    def reset_mood(self) -> None:
        """Reset conversation mood to neutral."""
        self._conversation_mood = 0.5
        self._current_emotion = Emotion.NEUTRAL
