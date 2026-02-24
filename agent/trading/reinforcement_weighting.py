import logging
import math
from typing import Dict, List

class ReinforcementWeighting:
    """
    Reinforcement learning-based strategy weighting using an Exponentially Weighted 
    Multi-Armed Bandit approach (Softmax action selection).
    Allows the agent to dynamically shift capital to outperforming strategies.
    """
    
    def __init__(self, strategies: List[str], decay_factor: float = 0.99) -> None:
        self.logger = logging.getLogger("ReinforcementWeighting")
        self.strategies = strategies
        self.decay_factor = decay_factor
        
        # Initialize Uniform weights
        n = len(strategies)
        self.weights = {s: 1.0 / n for s in strategies} if n > 0 else {}
        # Track exponential moving average of rewards
        self.scores = {s: 0.0 for s in strategies}
        
    def update_weights(self, strategy_returns: Dict[str, float]) -> Dict[str, float]:
        """
        Update strategy scores based on recent returns, apply exponential decay, 
        and recalculate weights using Softmax.
        
        Args:
            strategy_returns (Dict[str, float]): Recent returns for each strategy.
            
        Returns:
            Dict[str, float]: Updated target weights summing to 1.0.
        """
        if not self.strategies:
            return {}
            
        total_exp = 0.0
        exps = {}
        
        for s in self.strategies:
            # Apply decay and add new reward
            ret = strategy_returns.get(s, 0.0)
            self.scores[s] = (self.scores[s] * self.decay_factor) + ret
            
            # Softmax calculation (bounded for numerical stability)
            bounded_score = max(min(self.scores[s], 10.0), -10.0)
            e = math.exp(bounded_score)
            exps[s] = e
            total_exp += e
            
        # Normalize weights
        for s in self.strategies:
            if total_exp > 0:
                self.weights[s] = exps[s] / total_exp
            else:
                self.weights[s] = 1.0 / len(self.strategies)
                
        self.logger.debug(f"Updated weights: {self.weights}")
        return self.weights
