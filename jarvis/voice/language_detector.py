"""
INDRA Language Detector — Detects if input is English, Hindi, or Marathi.
Used to route TTS to the correct engine (Kokoro for English, gTTS for Hindi/Marathi).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import get_logger

logger = get_logger("LangDetect")

try:
    from langdetect import detect
    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False
    logger.warning("langdetect not installed — defaulting all text to English")

LANGUAGE_MAP = {
    "en": "english",
    "hi": "hindi",
    "mr": "marathi",
}


def detect_language(text: str) -> str:
    """
    Detect the language of a text string.
    
    Returns: 'english', 'hindi', 'marathi', or 'english' as fallback.
    
    Design decision: Short strings (< 10 chars) default to English because
    langdetect is unreliable on very short inputs. This prevents false
    Hindi/Marathi detection on single English words.
    """
    if not HAS_LANGDETECT:
        return "english"

    if not text or len(text.strip()) < 10:
        return "english"

    try:
        code = detect(text)
        detected = LANGUAGE_MAP.get(code, "english")
        logger.debug(f"Detected '{code}' → {detected} for: {text[:40]}...")
        return detected
    except Exception as e:
        logger.debug(f"Language detection failed ({e}), defaulting to English")
        return "english"
