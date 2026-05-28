"""
INDRA Context Manager — Token counting, history trimming, context assembly.
Ensures LLM calls never exceed the context window. Identity and memory are never trimmed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MAX_CONTEXT_TOKENS, MAX_HISTORY_TURNS, SYSTEM_PROMPT_PATH
from utils.logger import get_logger

logger = get_logger("Context")

# Use tiktoken for accurate token counting
try:
    import tiktoken
    _encoder = tiktoken.get_encoding("cl100k_base")
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    logger.warning("tiktoken not installed — using approximate token counting (words/0.75)")


def _count_tokens(text: str) -> int:
    """Count tokens in a string. Uses tiktoken if available, else approximation."""
    if HAS_TIKTOKEN:
        return len(_encoder.encode(text))
    # Rough approximation: ~0.75 words per token for English
    return int(len(text.split()) / 0.75)


def load_system_prompt() -> str:
    """Load the INDRA system prompt from disk."""
    path = Path(SYSTEM_PROMPT_PATH)
    if not path.exists():
        # Try relative to jarvis/ directory
        path = Path(__file__).parent.parent / "system_prompt.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    logger.error("system_prompt.txt not found!")
    return "You are INDRA, a helpful AI assistant for Ashish."


class ContextManager:
    """
    Assembles the full context sent to Ollama on every call.
    Ensures it never exceeds the model's context window.
    
    Priority order (NEVER trimmed):
      1. system_prompt (identity + rules)
      2. memory_snippets (Ashish's facts)
      3. user_message (current input)
    
    Trimmable (cut oldest first):
      4. conversation_history
    """

    def __init__(self):
        self._system_prompt_cache = None

    def count_tokens(self, text: str) -> int:
        """Public token counter."""
        return _count_tokens(text)

    def get_system_prompt(self) -> str:
        """Get the system prompt, cached after first load."""
        if self._system_prompt_cache is None:
            self._system_prompt_cache = load_system_prompt()
        return self._system_prompt_cache

    def build_memory_block(self, snippets: list[str]) -> str:
        """
        Format memory snippets into a clean block for system prompt injection.
        Format: "MEMORY:\n- snippet1\n- snippet2\n..."
        """
        if not snippets:
            return ""
        lines = "\n".join(f"- {s.strip()}" for s in snippets if s.strip())
        return f"\nMEMORY:\n{lines}\n"

    def assemble_context(
        self,
        system_prompt: str,
        memory_snippets: list[str],
        conversation_history: list[dict],
        user_message: str
    ) -> tuple[str, list[dict]]:
        """
        Assembles final context. Returns (system_prompt_with_memory, trimmed_history).
        
        Process:
          - Calculate tokens used by non-trimmable parts
          - Remaining budget = MAX_CONTEXT_TOKENS - non_trimmable_tokens
          - Add history turns newest-first until budget exceeded
          - Drop remaining old turns silently (no error)
          - Log a warning if more than 5 turns were dropped
        """
        # Build the full system prompt with injected memory
        memory_block = self.build_memory_block(memory_snippets)
        full_system = system_prompt + memory_block

        # Calculate non-trimmable token usage
        system_tokens = _count_tokens(full_system)
        user_tokens = _count_tokens(user_message)
        fixed_tokens = system_tokens + user_tokens + 50  # 50 token safety margin

        # Remaining budget for conversation history
        history_budget = MAX_CONTEXT_TOKENS - fixed_tokens

        if history_budget <= 0:
            logger.warning(
                f"System prompt + memory + user message already at {fixed_tokens} tokens. "
                f"No room for history (limit: {MAX_CONTEXT_TOKENS})."
            )
            return full_system, []

        # Add history turns newest-first until budget exceeded
        trimmed_history = []
        tokens_used = 0
        dropped_count = 0

        # Process history from newest to oldest
        for turn in reversed(conversation_history):
            turn_tokens = _count_tokens(turn.get("content", ""))
            if tokens_used + turn_tokens <= history_budget:
                trimmed_history.insert(0, turn)  # Prepend to maintain order
                tokens_used += turn_tokens
            else:
                dropped_count += 1

        if dropped_count > 0:
            level = "warning" if dropped_count > 5 else "debug"
            getattr(logger, level)(
                f"Context trimming: kept {len(trimmed_history)} turns, "
                f"dropped {dropped_count} oldest turns "
                f"({tokens_used}/{history_budget} token budget used)"
            )

        total_tokens = fixed_tokens + tokens_used
        logger.debug(
            f"Context assembled: {total_tokens} tokens "
            f"(system={system_tokens}, memory={_count_tokens(memory_block)}, "
            f"history={tokens_used}, user={user_tokens})"
        )

        return full_system, trimmed_history
