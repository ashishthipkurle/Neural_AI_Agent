"""
INDRA Chat Brain — Fast conversational LLM via Ollama.
Runs in its own thread pool so it never blocks vision brain.
Streams responses and flushes complete sentences to speaker immediately.
"""

import threading
import time
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    CHAT_MODEL, OLLAMA_HOST, MAX_HISTORY_TURNS,
    MEMORY_RECALL_N, TARGET_LLM_MS
)
from brain.context_manager import ContextManager, load_system_prompt
from utils.logger import get_logger
from utils.time_utils import get_time_string

logger = get_logger("ChatBrain")

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False
    logger.error("ollama SDK not installed!")

# Sentence-ending punctuation for streaming flush
SENTENCE_ENDINGS = (".", "!", "?", "...", "।")  # Last one is Hindi purna viram


class ChatBrain:
    """
    Fast conversational LLM. Runs in its own thread pool, completely isolated
    from VisionBrain. Uses Ollama streaming for sentence-by-sentence TTS.
    """

    def __init__(self, speaker, context_manager: ContextManager, memory_store):
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="chat_brain")
        self.speaker = speaker
        self.ctx = context_manager
        self.memory = memory_store
        self.history = []  # list of {"role": str, "content": str}
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()

    def respond_async(self, user_input: str):
        """Submit response generation as non-blocking future."""
        self._cancel_event.clear()
        return self.executor.submit(self._respond, user_input)

    def _respond(self, user_input: str) -> str:
        """
        Generate a response. Streams from Ollama and flushes complete
        sentences to the speaker queue immediately.
        """
        if not HAS_OLLAMA:
            fallback = "My language model isn't available right now."
            self.speaker.enqueue(fallback)
            return fallback

        t_start = time.perf_counter()

        # 1. Recall relevant memories
        try:
            memory_snippets = self.memory.recall(user_input, n=MEMORY_RECALL_N)
        except Exception:
            memory_snippets = []

        # 2. Assemble context with token trimming
        system_prompt_raw = load_system_prompt()
        # Inject current time into system prompt
        system_prompt_raw = system_prompt_raw.replace(
            "{CURRENT_TIME}", get_time_string()
        )
        if memory_snippets:
            memory_block = self.ctx.build_memory_block(memory_snippets)
            system_prompt_raw = system_prompt_raw.replace(
                "{LOADED_MEMORY}", memory_block
            )
        else:
            system_prompt_raw = system_prompt_raw.replace(
                "{LOADED_MEMORY}", "No memories loaded yet."
            )

        system_prompt, trimmed_history = self.ctx.assemble_context(
            system_prompt=system_prompt_raw,
            memory_snippets=memory_snippets,
            conversation_history=self.history,
            user_message=user_input
        )

        # 3. Build messages list
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(trimmed_history)
        messages.append({"role": "user", "content": user_input})

        # 4. Stream response from Ollama
        sentence_buffer = ""
        full_response = ""
        first_token_time = None

        try:
            stream = ollama.chat(
                model=CHAT_MODEL,
                messages=messages,
                stream=True
            )

            for chunk in stream:
                if self._cancel_event.is_set():
                    logger.info("Chat cancelled by user")
                    break

                token = chunk.get("message", {}).get("content", "")
                if not token:
                    continue

                if first_token_time is None:
                    first_token_time = time.perf_counter()
                    ttft_ms = (first_token_time - t_start) * 1000
                    logger.info(f"Time to first token: {ttft_ms:.0f}ms")

                sentence_buffer += token
                full_response += token

                # Flush complete sentences to TTS immediately
                stripped = sentence_buffer.rstrip()
                if any(stripped.endswith(p) for p in SENTENCE_ENDINGS):
                    if sentence_buffer.strip():
                        self.speaker.enqueue(sentence_buffer.strip())
                    sentence_buffer = ""

            # Flush any remaining buffer
            if sentence_buffer.strip():
                self.speaker.enqueue(sentence_buffer.strip())

        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            error_msg = "I'm having trouble connecting to my language model."
            self.speaker.enqueue(error_msg, priority=True)
            return error_msg

        # 5. Update conversation history
        with self._lock:
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": full_response})
            # Roll history if too long
            max_entries = MAX_HISTORY_TURNS * 2
            if len(self.history) > max_entries:
                self.history = self.history[-max_entries:]

        # 6. Log latency
        elapsed_ms = (time.perf_counter() - t_start) * 1000
        logger.info(f"Response time: {elapsed_ms:.0f}ms (target: {TARGET_LLM_MS}ms)")
        if elapsed_ms > TARGET_LLM_MS * 2:
            logger.warning(f"Latency exceeded 2x target: {elapsed_ms:.0f}ms")

        return full_response

    def build_greeting(self, memory_context: list[str], project_briefing: str) -> str:
        """
        Generate a personalised startup greeting using the LLM.
        Falls back to a template if the LLM is unavailable.
        """
        from utils.time_utils import get_formatted_greeting

        base_greeting = get_formatted_greeting()

        if project_briefing:
            base_greeting += f" {project_briefing}"

        if memory_context:
            # Use last relevant memory for a personalised touch
            base_greeting += " How can I be of service?"
        else:
            base_greeting += " What can I do for you?"

        return base_greeting

    def cancel(self):
        """Cancel any in-flight LLM generation."""
        self._cancel_event.set()
        logger.info("Chat brain cancel requested")

    def clear_history(self):
        """Clear conversation history (e.g. on new session)."""
        with self._lock:
            self.history.clear()
        logger.info("Conversation history cleared")
