"""
Voice Conversation State Manager

Manages per-call conversation state for interactive AI voice calls.
Each call gets a conversation context with purpose, history, and turn tracking.
The LLM generates contextual responses based on the full conversation history.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger("VoiceConversation")

MAX_TURNS = 6  # Max conversation turns before graceful end


@dataclass
class CallConversation:
    """State for a single active phone conversation."""
    call_sid: str
    purpose: str
    contact_name: str
    caller_name: str
    turns: List[Dict[str, str]] = field(default_factory=list)  # [{role: "ai"/"human", text: "..."}]
    created_at: float = field(default_factory=time.time)
    ended: bool = False

    @property
    def turn_count(self) -> int:
        return len([t for t in self.turns if t["role"] == "human"])

    def add_ai_turn(self, text: str):
        self.turns.append({"role": "ai", "text": text})

    def add_human_turn(self, text: str):
        self.turns.append({"role": "human", "text": text})

    def should_end(self) -> bool:
        """Check if conversation should end naturally."""
        return self.turn_count >= MAX_TURNS or self.ended

    def build_history_text(self) -> str:
        """Format conversation history for LLM context."""
        lines = []
        for turn in self.turns:
            speaker = "AI Assistant" if turn["role"] == "ai" else self.contact_name
            lines.append(f"{speaker}: {turn['text']}")
        return "\n".join(lines)


class VoiceConversationManager:
    """
    Manages all active voice call conversations.
    
    Provides LLM prompts for generating contextual responses
    and tracks state across multiple concurrent calls.
    """

    def __init__(self):
        self.conversations: Dict[str, CallConversation] = {}
        self.logger = logging.getLogger("VoiceConversation")

    def create_conversation(self, call_sid: str, purpose: str, 
                          contact_name: str, caller_name: str) -> CallConversation:
        """Register a new call conversation."""
        conv = CallConversation(
            call_sid=call_sid,
            purpose=purpose,
            contact_name=contact_name,
            caller_name=caller_name
        )
        self.conversations[call_sid] = conv
        self.logger.info(f"Created conversation for call {call_sid}: purpose='{purpose}'")
        return conv

    def get_conversation(self, call_sid: str) -> Optional[CallConversation]:
        return self.conversations.get(call_sid)

    def end_conversation(self, call_sid: str):
        conv = self.conversations.get(call_sid)
        if conv:
            conv.ended = True
            self.logger.info(f"Ended conversation {call_sid} after {conv.turn_count} turns")

    def cleanup_old(self, max_age_seconds: int = 600):
        """Remove conversations older than max_age."""
        now = time.time()
        expired = [sid for sid, c in self.conversations.items() 
                   if now - c.created_at > max_age_seconds]
        for sid in expired:
            del self.conversations[sid]

    def generate_greeting_prompt(self, conv: CallConversation) -> str:
        """Build the opening greeting for the call."""
        greeting = f"Hello! This is an AI assistant calling on behalf of {conv.caller_name}."
        
        # Convert the purpose into a natural first question
        purpose = conv.purpose.strip()
        lower = purpose.lower()
        
        if lower.startswith("ask "):
            question_part = purpose[4:].strip()
            # Rephrase pronouns: he/she -> you
            question_part = question_part.replace(" he is", " you are").replace(" she is", " you are")
            question_part = question_part.replace(" he ", " you ").replace(" she ", " you ")
            question_part = question_part.replace(" his ", " your ").replace(" her ", " your ")
            greeting += f" {conv.caller_name} wanted to know, {question_part}?"
        elif lower.startswith("tell "):
            message_part = purpose[5:].strip()
            message_part = message_part.replace(" he ", " they ").replace(" she ", " they ")
            greeting += f" {conv.caller_name} wanted to tell you: {message_part}."
        else:
            greeting += f" {purpose}."
        
        return greeting

    def build_llm_prompt(self, conv: CallConversation, latest_speech: str) -> tuple:
        """
        Build system prompt and user message for generating the next AI response.
        
        Returns (system_prompt, user_message)
        """
        system_prompt = f"""You are an AI assistant making a phone call on behalf of {conv.caller_name}.
You are talking to {conv.contact_name} on the phone.

PURPOSE OF THIS CALL: {conv.purpose}

RULES:
- Be natural, conversational, and friendly
- Keep responses SHORT (1-2 sentences max) — this is a phone call, not an essay
- Ask follow-up questions relevant to the purpose
- If the person seems busy or wants to end the call, wrap up politely
- Do NOT repeat the same question
- Do NOT introduce yourself again
- Respond directly to what they said
- If the purpose has been fulfilled (you got the information), start wrapping up
- After getting the answer, say something like "Great, I'll let {conv.caller_name} know. Thanks! Goodbye."

CONVERSATION SO FAR:
{conv.build_history_text()}

This is turn {conv.turn_count + 1} of the conversation."""

        user_message = f"{conv.contact_name} just said: \"{latest_speech}\"\n\nGenerate your next spoken response (1-2 sentences only):"

        return system_prompt, user_message

    def build_farewell(self, conv: CallConversation) -> str:
        """Generate a farewell message when max turns reached."""
        return f"Thank you so much for your time! I'll pass everything along to {conv.caller_name}. Have a wonderful day! Goodbye."


# Global singleton instance
conversation_manager = VoiceConversationManager()
