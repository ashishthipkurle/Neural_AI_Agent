"""
LLM Pre-Trade Reviewer — Advisory Sanity Check via Local Ollama.

Sends a 1-paragraph trade summary to Ollama for a sanity check.
Advisory only: can reduce confidence by max 10%, can never BLOCK.
Graceful degradation: if Ollama is down, skip silently.

No veto power — this is a nudge, not a gate.
"""
import logging
import time
from typing import Dict, Any, Optional


class LLMPreTradeReviewer:
    """
    Sends a 1-paragraph trade summary to Ollama for a sanity check.
    Advisory only: can reduce confidence by max 10%, can never BLOCK.
    Graceful degradation: if Ollama is down, skip silently.
    """

    MAX_CONFIDENCE_REDUCTION = 0.10  # Can only nudge, not veto
    TIMEOUT_SECONDS = 10             # Don't wait forever
    DEFAULT_MODEL = "llama3.1:8b"
    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, model: str = None, base_url: str = None) -> None:
        self.logger = logging.getLogger("LLMPreTradeReviewer")
        self.model = model or self.DEFAULT_MODEL
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self._available = None  # Lazy check

    def review(self, signal: Dict[str, Any], ta_reports: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send trade summary to Ollama for advisory review.

        Returns:
            {
                "adjustment": -0.05,    # confidence reduction (0 to -0.10)
                "review_text": "...",    # LLM's 2-sentence review
                "skipped": False,        # True if Ollama was unavailable
            }
        """
        try:
            prompt = self._build_prompt(signal, ta_reports)
            response_text = self._call_ollama(prompt)

            if not response_text:
                return {"adjustment": 0.0, "review_text": "", "skipped": True}

            # Parse response for red flags
            adjustment = self._parse_adjustment(response_text)

            self.logger.info(
                f"LLM review for {signal.get('symbol', '?')}: "
                f"adj={adjustment:+.2f} | {response_text[:80]}..."
            )

            return {
                "adjustment": adjustment,
                "review_text": response_text.strip(),
                "skipped": False,
            }

        except Exception as e:
            self.logger.debug(f"LLM review skipped: {e}")
            return {"adjustment": 0.0, "review_text": "", "skipped": True}

    def _build_prompt(self, signal: Dict[str, Any], ta_reports: Dict[str, Any] = None) -> str:
        """Build the review prompt."""
        ta_direction = "N/A"
        if ta_reports:
            ta_direction = ta_reports.get("direction", "N/A")

        return (
            f"You are a risk-aware trading reviewer. "
            f"Signal: {signal.get('direction', '?')} {signal.get('symbol', '?')} "
            f"@ {signal.get('entry_price', 0):.2f}\n"
            f"Strategy: {signal.get('strategy_name', '?')}, "
            f"Regime: {signal.get('regime', '?')}\n"
            f"Confidence: {signal.get('confidence', 0):.2f}\n"
            f"TradingAgents says: {ta_direction}\n\n"
            f"In 2 sentences: Is this a reasonable trade? Any red flags? "
            f"End with CAUTION or OK."
        )

    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Call local Ollama API with timeout."""
        try:
            import requests
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 100},
                },
                timeout=self.TIMEOUT_SECONDS,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")
            else:
                self.logger.debug(f"Ollama returned status {response.status_code}")
                return None

        except ImportError:
            self.logger.debug("requests library not available")
            return None
        except Exception as e:
            self.logger.debug(f"Ollama call failed: {e}")
            return None

    def _parse_adjustment(self, response_text: str) -> float:
        """
        Parse the LLM response to determine confidence adjustment.
        Returns 0.0 (no change) to -0.10 (max reduction).
        """
        text_lower = response_text.lower()

        # Look for explicit caution signals
        caution_words = ["caution", "risky", "concerned", "warning", "careful",
                         "uncertain", "questionable", "avoid", "red flag"]
        caution_count = sum(1 for w in caution_words if w in text_lower)

        if caution_count >= 3:
            return -self.MAX_CONFIDENCE_REDUCTION  # -0.10
        elif caution_count >= 2:
            return -0.07
        elif caution_count >= 1:
            return -0.03
        else:
            return 0.0  # No adjustment — trade looks fine
