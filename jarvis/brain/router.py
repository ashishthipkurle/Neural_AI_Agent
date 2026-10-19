"""
INDRA Request Router -- Classifies input as TYPE 1/2/3/4.
Routes correctly between chat_brain (conversation) and executor (action).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CHAT_MODEL
from utils.logger import get_logger

logger = get_logger("Router")

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False


class Router:
    """
    Classifies user intent into one of 4 types:
      TYPE 1 -- CONVERSATION (fast LLM)
      TYPE 2 -- HYBRID (verbal answer + fast action)
      TYPE 3 -- COMPUTER TASK (executor via vision LLM)
      TYPE 4 -- AMBIGUOUS (ask clarifying question)
    """

    def __init__(self, chat_brain, vision_brain):
        self.chat = chat_brain
        self.vision = vision_brain

    # -- Keywords for fast routing (no LLM needed) --
    ACTION_KEYWORDS = [
        "open", "close", "launch", "start", "run", "click", "type",
        "search", "download", "install", "uninstall", "delete",
        "copy", "paste", "move", "rename", "create", "save",
        "scroll", "minimize", "maximize", "switch", "navigate",
        "play", "pause", "stop", "mute", "unmute", "volume",
        "screenshot", "record", "shut down", "restart", "lock",
        "send", "message", "go to", "schedule", "set",
        "write", "post", "upload", "share",
    ]
    # Multi-command patterns: "in X do Y"
    MULTI_CMD_PATTERNS = [
        "in ", "on ", "go to ", "using ",
    ]
    GREETING_KEYWORDS = [
        "hello", "hi indra", "hey indra", "good morning", "good evening",
        "how are you", "what's up", "thank you", "thanks",
        "who are you", "what can you do",
        "what time", "what date", "what day",
    ]

    def classify(self, text: str) -> str:
        """
        Classify intent using keyword fast-path first, then LLM fallback.
        Returns: 'TYPE1', 'TYPE2', 'TYPE3', or 'TYPE4'
        """
        if not text:
            return "TYPE1"

        text_lower = text.lower().strip().rstrip(".")

        # -- Fast path: greeting check --
        for kw in self.GREETING_KEYWORDS:
            if text_lower == kw or text_lower.startswith(kw + " ") or text_lower.startswith(kw + ","):
                logger.debug(f"Fast-routed '{text[:30]}' as TYPE1 (keyword: {kw})")
                return "TYPE1"

        # -- Fast path: direct action keyword at start --
        for kw in self.ACTION_KEYWORDS:
            if text_lower.startswith(kw + " ") or text_lower.startswith(kw + "."):
                logger.debug(f"Fast-routed '{text[:30]}' as TYPE3 (keyword: {kw})")
                return "TYPE3"

        # -- Fast path: multi-command patterns like "in telegram send hi" --
        for pat in self.MULTI_CMD_PATTERNS:
            if text_lower.startswith(pat):
                # Check if any action keyword appears later in the sentence
                rest = text_lower[len(pat):]
                for kw in self.ACTION_KEYWORDS:
                    if kw in rest:
                        logger.debug(f"Fast-routed '{text[:30]}' as TYPE3 (multi-cmd: {pat}+{kw})")
                        return "TYPE3"

        # -- Slow path: LLM classification --
        if not HAS_OLLAMA:
            return "TYPE1"

        prompt = f"""Classify the user's intent into exactly one of these 4 categories. Return ONLY the string 'TYPE1', 'TYPE2', 'TYPE3', or 'TYPE4'. Nothing else.

TYPE 1: Conversation, answering questions, opinions, greetings, small talk. No screen/computer action needed.
TYPE 2: Hybrid. Needs a spoken answer AND a brief computer action (like opening a tab or checking a quick fact).
TYPE 3: Computer Task. Requires operating the computer (clicking, typing, scrolling, downloading, posting, coding, etc.).
TYPE 4: Ambiguous. It's unclear what they want or what platform they mean. Needs clarification.

User input: "{text}"

Classification:"""

        try:
            response = ollama.chat(
                model=CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0}  # Deterministic
            )
            
            raw = response.get("message", {}).get("content", "").strip().upper()
            
            # Extract just the type
            for t in ["TYPE1", "TYPE2", "TYPE3", "TYPE4"]:
                if t in raw:
                    logger.debug(f"Router classified '{text[:30]}...' as {t}")
                    return t
                    
            logger.warning(f"Router returned invalid classification: {raw}")
            return "TYPE1"  # Default fallback
            
        except Exception as e:
            logger.error(f"Router classification failed: {e}")
            # Even if LLM fails, try keyword match one more time
            for kw in self.ACTION_KEYWORDS:
                if kw in text_lower:
                    return "TYPE3"
            return "TYPE1"

    def get_clarification(self, text: str) -> str:
        """Generate ONE clarifying question for a TYPE 4 ambiguous input."""
        prompt = f"""The user said: "{text}"
This is ambiguous. Generate exactly ONE brief, direct clarifying question to ask them what they mean. 
Do not explain why you are asking. Just ask the question.
Example: "Did you mean the document on your desktop or the one in Google Drive?"
"""
        try:
            response = ollama.chat(
                model=CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.3}
            )
            return response.get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"Router clarification failed: {e}")
            return "I'm not quite sure what you mean. Could you clarify?"
