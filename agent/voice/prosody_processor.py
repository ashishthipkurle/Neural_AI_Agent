"""
Prosody Processor - Advanced text preprocessing for human-like speech.

This module transforms raw text into a format optimized for neural TTS,
adding natural pauses, emphasis, and emotional timing.
"""

import re
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger("ProsodyProcessor")

@dataclass
class ProsodyChunk:
    """A chunk of text to be spoken with specific prosody."""
    text: str
    pause_after: float = 0.0  # seconds of silence after this chunk
    speed: float = 1.0        # local speed modifier

class ProsodyProcessor:
    """
    Transforms text for naturally paced speech.
    
    Features:
    - Smart text cleaning
    - Emotion-aware pause injection
    - Phrase chunking
    - Ellipsis handling for timing
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ProsodyProcessor")

    def process(self, text: str, emotion_settings: Optional['EmotionSettings'] = None) -> str:
        """
        Process text into enhanced text with prosody markers.
        
        Args:
            text: Raw input text.
            emotion_settings: Emotion modulation settings.
        
        Returns:
            Enhanced text string with added pauses (..., —).
        """
        if not text:
            return ""

        clean_text = self._clean_text(text)
        
        # 1. Expand sizing for better flow
        # Ensure space around major punctuation
        clean_text = re.sub(r'([.,!?;:])', r'\1 ', clean_text)
        
        # 2. Inject Pauses logic
        processed_text = clean_text
        
        # Add ellipses for conscious pauses if emotion allows
        # For concerned/calm/thinking/apologetic, we add more breathing room.
        if emotion_settings and emotion_settings.pauses:
            # Replace commas with ellipsis for longer pause feeling
            # But don't overdo it - only for long phrases
            processed_text = processed_text.replace(", ", "... ")
            
            # Add explicit pause markers for the TTS engine to interpret if needed
            # For now, we rely on the text representation "..." or "—"
            processed_text = processed_text.replace("—", " — ")

        # 3. Collapse multiple spaces
        processed_text = re.sub(r'\s+', ' ', processed_text).strip()
        
        # 4. Final Polish
        # Ensure ellipsis has space
        processed_text = processed_text.replace("...", "... ")
        
        return processed_text.strip()

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove markdown chars that shouldn't be spoken
        text = text.replace("*", "") 
        text = text.replace("#", "")
        text = text.replace("`", "")
        text = text.replace("_", "")
        text = text.replace("[", "").replace("]", "")
        
        # Remove URLs (simplified)
        text = re.sub(r'http\S+', 'link', text)
        
        # Normalize whitespace
        text = " ".join(text.split())
        return text

    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into synthesis chunks.
        Needed because some TTS engines have character limits or need
        better pacing control.
        """
        # Split by sentence endings
        chunks = re.split(r'(?<=[.!?])\s+', text)
        return [c.strip() for c in chunks if c.strip()]

