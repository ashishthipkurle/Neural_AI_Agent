"""
INDRA OS — General Agent Worker

Wraps the existing ChatBrain as a BaseAgent for conversational tasks.
Handles questions, opinions, advice, explanations, greetings, and web search.
This is the fallback agent for anything that isn't a specialist task.
"""

import asyncio
import json
import logging
from typing import Optional

from agents.base_agent import BaseAgent
from agents.task import Task, TaskResult

logger = logging.getLogger("Agent.General")

# Keywords for confidence scoring
_STRONG_SIGNALS = [
    "what is", "who is", "explain", "tell me about", "how does",
    "why", "what do you think", "opinion", "advice", "help me understand",
    "summarize", "translate", "define", "meaning of",
    "hello", "hi", "hey", "good morning", "good evening",
    "how are you", "thanks", "thank you",
]

_MEDIUM_SIGNALS = [
    "what", "how", "when", "where", "can you",
    "do you know", "is it", "should i",
]


class GeneralWorker(BaseAgent):
    """
    General-purpose conversational agent.
    Handles chat, Q&A, opinions, explanations, and small talk.
    """

    def __init__(self, llm_func=None, speak_func=None, search_func=None):
        super().__init__(
            name="general",
            description="General conversation, Q&A, opinions, advice, and explanations",
            capabilities=[
                "answer_question",
                "explain_topic",
                "give_advice",
                "translate",
                "summarize",
                "web_search",
                "small_talk",
                "greeting",
            ],
        )
        self._llm = llm_func          # async callable(prompt) -> str
        self._speak = speak_func       # callable(text) for TTS
        self._search = search_func     # optional web search

    async def can_handle(self, task_description: str) -> float:
        """General agent can handle most things at moderate confidence."""
        lower = task_description.lower().strip()

        # Strong signals — this is clearly a conversation
        if any(lower.startswith(s) or s in lower for s in _STRONG_SIGNALS):
            return 0.85

        # Medium signals
        if any(lower.startswith(s) for s in _MEDIUM_SIGNALS):
            return 0.6

        # General agent is the fallback — always willing but at low confidence
        return 0.3

    async def execute(self, task: Task) -> TaskResult:
        """Handle a conversational task."""
        text = task.description

        await self.publish_progress(0.2, "Thinking...", 0, 2)

        if not self._llm:
            return TaskResult(
                task_id=task.id,
                success=False,
                output="No LLM available",
                error="LLM function not configured",
            )

        try:
            # Check if web search would help
            needs_search = self._needs_web_search(text)
            search_context = ""

            if needs_search and self._search:
                await self.publish_progress(0.3, "Searching the web...", 0, 3)
                try:
                    search_context = await self._search(text)
                except Exception as e:
                    logger.warning(f"Web search failed: {e}")

            # Build prompt
            prompt = text
            if search_context:
                prompt = (
                    f"Context from web search:\n{search_context}\n\n"
                    f"User question: {text}\n\n"
                    f"Answer based on the search results above:"
                )

            await self.publish_progress(0.5, "Generating response...", 1, 2)

            # Get LLM response
            response = await self._llm(prompt)

            # Speak the response if TTS available
            if self._speak and response:
                self._speak(response)

            await self.publish_progress(1.0, "Done", 2, 2)

            return TaskResult(
                task_id=task.id,
                success=True,
                output=response,
                steps_taken=[
                    "Received question",
                    f"{'Searched web, then g' if search_context else 'G'}enerated response",
                    "Delivered via TTS",
                ],
            )

        except Exception as e:
            logger.error(f"General agent error: {e}", exc_info=True)
            return TaskResult(
                task_id=task.id,
                success=False,
                output="I had trouble processing that, sir.",
                error=str(e),
            )

    def _needs_web_search(self, text: str) -> bool:
        """Heuristic: does this question need real-time web data?"""
        lower = text.lower()
        search_signals = [
            "latest", "current", "today", "news", "price",
            "weather", "score", "result", "update", "recent",
            "2024", "2025", "2026",
        ]
        return any(s in lower for s in search_signals)
