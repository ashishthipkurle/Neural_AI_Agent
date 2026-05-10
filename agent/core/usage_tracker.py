from dataclasses import dataclass, field
from typing import List, Dict, Optional
import logging

logger = logging.getLogger("core.usage_tracker")

@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    
    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_creation_tokens + self.cache_read_tokens
    
    def estimate_cost_usd(self, model: str = None) -> float:
        """Estimate cost based on Claw parity pricing."""
        if not model:
            return 0.0
            
        model_lower = model.lower()
        if "opus" in model_lower:
            input_price = 15.0 / 1_000_000
            output_price = 75.0 / 1_000_000
        elif "sonnet" in model_lower:
            input_price = 3.0 / 1_000_000
            output_price = 15.0 / 1_000_000
        elif "haiku" in model_lower:
            input_price = 0.25 / 1_000_000
            output_price = 1.25 / 1_000_000
        else:
            return 0.0 # Default unknown
            
        cost = (self.input_tokens + self.cache_creation_tokens) * input_price
        cost += self.output_tokens * output_price
        # Cache read is typically 10% of input cost
        cost += self.cache_read_tokens * (input_price * 0.1)
        
        return cost

    def add(self, other: 'TokenUsage'):
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_creation_tokens += other.cache_creation_tokens
        self.cache_read_tokens += other.cache_read_tokens

class UsageTracker:
    """Per-session token usage tracking — Claw-parity §usage.rs"""
    
    def __init__(self):
        self._history: List[TokenUsage] = []
        self._cumulative = TokenUsage()
    
    def record(self, usage: TokenUsage) -> None:
        self._history.append(usage)
        self._cumulative.add(usage)
        
    def cumulative(self) -> TokenUsage:
        return self._cumulative
        
    def current_turn(self) -> TokenUsage:
        return self._history[-1] if self._history else TokenUsage()
        
    def summary_lines(self, label: str, model: str = None) -> List[str]:
        usage = self.cumulative()
        cost = usage.estimate_cost_usd(model)
        
        lines = [
            f"--- {label} Usage Summary ---",
            f"Input Tokens:  {usage.input_tokens:,}",
            f"Output Tokens: {usage.output_tokens:,}"
        ]
        
        if usage.cache_creation_tokens > 0 or usage.cache_read_tokens > 0:
            lines.extend([
                f"Cache Write:   {usage.cache_creation_tokens:,}",
                f"Cache Read:    {usage.cache_read_tokens:,}"
            ])
            
        lines.append(f"Total Tokens:  {usage.total:,}")
        if cost > 0:
            lines.append(f"Est. Cost:     ${cost:.4f}")
            
        return lines
