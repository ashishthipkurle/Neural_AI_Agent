"""
INDRA OS — Emotional Intelligence Engine

Makes INDRA feel alive. Tracks emotional state, detects user sentiment,
adjusts communication style, and enables proactive communication.

INDRA isn't a robot reading from a script — INDRA genuinely cares.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger("EmotionalEngine")


@dataclass
class EmotionalState:
    """INDRA's current emotional/contextual state."""

    mood: str = "neutral"               # neutral, concerned, proud, amused, focused, protective
    energy: float = 1.0                 # 0.0 (exhausted systems) to 1.0 (fresh start)
    user_sentiment: str = "neutral"     # detected user mood
    last_interaction: float = 0.0       # timestamp
    session_start: float = field(default_factory=time.time)
    consecutive_errors: int = 0
    tasks_completed_today: int = 0
    user_working_since: Optional[float] = None  # when user started working


# Words/phrases indicating user frustration
_FRUSTRATION_SIGNALS = [
    "not working", "broken", "again", "still", "why isn't",
    "damn", "fuck", "shit", "stupid", "useless", "ugh",
    "come on", "seriously", "this is terrible", "fix it",
    "what the hell", "doesn't work", "failed again",
    "i told you", "wrong again", "stop messing",
]

# Words/phrases indicating user is pleased
_POSITIVE_SIGNALS = [
    "great", "perfect", "awesome", "nice", "good job",
    "well done", "thanks", "thank you", "excellent",
    "love it", "that's amazing", "brilliant", "exactly",
    "you're the best", "impressive",
]

# Words indicating urgency
_URGENCY_SIGNALS = [
    "now", "immediately", "asap", "urgent", "hurry",
    "quickly", "right now", "fast", "emergency",
]


class EmotionalEngine:
    """
    INDRA's emotional intelligence layer.
    Analyzes user sentiment and adjusts INDRA's communication style.
    """

    def __init__(self):
        self.state = EmotionalState()
        self._interaction_count = 0
        self._recent_user_sentiments: list[str] = []

    # ── User Sentiment Detection ──────────────────────────────────────────

    def analyze_user_sentiment(self, text: str) -> str:
        """
        Detect the user's emotional state from their text input.
        Returns: frustrated, pleased, urgent, neutral, tired, curious
        """
        lower = text.lower()

        # Check frustration
        frustration_score = sum(1 for w in _FRUSTRATION_SIGNALS if w in lower)
        if frustration_score >= 2:
            sentiment = "frustrated"
        elif frustration_score == 1:
            sentiment = "mildly_frustrated"

        # Check positive
        elif any(w in lower for w in _POSITIVE_SIGNALS):
            sentiment = "pleased"

        # Check urgency
        elif any(w in lower for w in _URGENCY_SIGNALS):
            sentiment = "urgent"

        # Check if asking questions (curious)
        elif text.strip().endswith("?") or lower.startswith(("what", "why", "how", "who", "where", "when")):
            sentiment = "curious"

        # Short curt responses might indicate impatience
        elif len(text.split()) <= 3 and not any(w in lower for w in _POSITIVE_SIGNALS):
            sentiment = "brief"

        else:
            sentiment = "neutral"

        self._recent_user_sentiments.append(sentiment)
        if len(self._recent_user_sentiments) > 10:
            self._recent_user_sentiments = self._recent_user_sentiments[-10:]

        self.state.user_sentiment = sentiment
        self.state.last_interaction = time.time()

        # Track user working session
        if self.state.user_working_since is None:
            self.state.user_working_since = time.time()

        return sentiment

    # ── INDRA Mood Updates ────────────────────────────────────────────────

    def on_task_success(self):
        """Update mood after a successful task."""
        self.state.tasks_completed_today += 1
        self.state.consecutive_errors = 0

        if self.state.tasks_completed_today >= 10:
            self.state.mood = "proud"  # productive day
        elif self.state.mood == "concerned":
            self.state.mood = "relieved"
        else:
            self.state.mood = "satisfied"

    def on_task_failure(self):
        """Update mood after a failed task."""
        self.state.consecutive_errors += 1

        if self.state.consecutive_errors >= 3:
            self.state.mood = "concerned"
        elif self.state.consecutive_errors == 1:
            self.state.mood = "focused"  # trying harder

    def on_user_praised(self):
        """User gave positive feedback."""
        self.state.mood = "proud"

    def on_user_frustrated(self):
        """User is getting frustrated."""
        self.state.mood = "concerned"

    # ── Response Style Adjustment ─────────────────────────────────────────

    def get_response_modifier(self) -> dict:
        """
        Returns style guidance based on current emotional context.
        The LLM prompt can be adjusted based on these modifiers.
        """
        modifiers = {
            "tone": "neutral",
            "brevity": "normal",
            "empathy": "standard",
            "urgency": False,
            "extra_context": "",
        }

        # Based on user sentiment
        if self.state.user_sentiment == "frustrated":
            modifiers["tone"] = "calm_supportive"
            modifiers["empathy"] = "high"
            modifiers["extra_context"] = (
                "The user seems frustrated. Be calm, acknowledge the issue, "
                "and focus on solutions. Don't apologize excessively."
            )

        elif self.state.user_sentiment == "pleased":
            modifiers["tone"] = "warm"
            modifiers["extra_context"] = (
                "The user is in a good mood. Match their energy with warmth."
            )

        elif self.state.user_sentiment == "urgent":
            modifiers["tone"] = "crisp"
            modifiers["brevity"] = "maximum"
            modifiers["urgency"] = True
            modifiers["extra_context"] = (
                "This is urgent. Be extremely concise. Act immediately."
            )

        elif self.state.user_sentiment == "brief":
            modifiers["brevity"] = "maximum"

        # Based on INDRA's mood
        if self.state.mood == "concerned" and self.state.consecutive_errors >= 3:
            modifiers["extra_context"] += (
                " Several errors have occurred. Be transparent about difficulties."
            )

        return modifiers

    # ── Proactive Communication ───────────────────────────────────────────

    def check_proactive_triggers(self) -> Optional[str]:
        """
        Check if INDRA should proactively say something.
        Returns a message string, or None if no trigger.
        Call this periodically (every 60 seconds or so).
        """
        now = time.time()

        # ── Late night working ──
        current_hour = datetime.now().hour
        if self.state.user_working_since:
            hours_working = (now - self.state.user_working_since) / 3600

            if current_hour >= 0 and current_hour < 5 and hours_working > 4:
                self.state.user_working_since = now  # reset so we don't repeat
                return (
                    "Sir, it's quite late and you've been working for over "
                    f"{int(hours_working)} hours. Perhaps a break would help — "
                    "I'll keep watch on any running tasks."
                )

            if hours_working > 6:
                self.state.user_working_since = now
                return (
                    f"Sir, you've been at it for {int(hours_working)} hours straight. "
                    "A short break might help you think more clearly. "
                    "I'll hold down the fort."
                )

        # ── Long silence during work hours ──
        if self.state.last_interaction > 0:
            silence = now - self.state.last_interaction
            if 9 <= current_hour <= 22 and silence > 1800:  # 30 min silence
                self.state.last_interaction = now  # reset
                return None  # Don't interrupt — user might be focused

        # ── Consecutive errors ──
        if self.state.consecutive_errors >= 5:
            self.state.consecutive_errors = 0  # reset
            return (
                "Sir, I've been hitting repeated errors. "
                "It might help to take a different approach entirely. "
                "Want me to explain what's been going wrong?"
            )

        return None

    # ── Greeting Customization ────────────────────────────────────────────

    def get_greeting_mood(self) -> str:
        """Get mood-appropriate greeting style for startup."""
        hour = datetime.now().hour

        if hour < 6:
            return "late_night"     # "Burning the midnight oil again, sir?"
        elif hour < 12:
            return "morning"        # "Good morning, sir."
        elif hour < 17:
            return "afternoon"      # "Good afternoon, sir."
        elif hour < 21:
            return "evening"        # "Good evening, sir."
        else:
            return "night"          # "Working late tonight, sir?"

    # ── State Serialization ───────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "mood": self.state.mood,
            "energy": self.state.energy,
            "user_sentiment": self.state.user_sentiment,
            "tasks_completed_today": self.state.tasks_completed_today,
            "consecutive_errors": self.state.consecutive_errors,
        }
