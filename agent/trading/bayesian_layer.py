import logging

class BayesianLayer:
    """
    Bayesian confidence updating for strategy signals.
    Adjusts the probability of a signal being correct based on historical success 
    rates and real-time evidence.
    """
    
    def __init__(self, prior: float = 0.5) -> None:
        self.logger = logging.getLogger("BayesianLayer")
        if not (0.0 <= prior <= 1.0):
            raise ValueError("Prior must be between 0.0 and 1.0")
        self.prior = prior
        self.posterior = prior
        
    def update_confidence(self, likelihood: float, evidence_strength: float) -> float:
        """
        Apply Bayes' Theorem: P(Model Correct | Evidence)
        
        Args:
            likelihood: P(Evidence | Model is Correct)
            evidence_strength: P(Evidence) 
            
        Returns:
            float: Updated posterior probability (0.0 to 1.0)
        """
        if evidence_strength <= 0.0:
            return self.posterior
            
        # P(A|B) = [P(B|A) * P(A)] / P(B)
        numerator = likelihood * self.posterior
        denominator = evidence_strength
        
        new_posterior = numerator / denominator
        
        # Bound the probability strictly between 0 and 1
        self.posterior = max(min(new_posterior, 1.0), 0.0) 
        
        self.logger.debug(f"Bayesian update: prior={self.prior:.2f} -> posterior={self.posterior:.2f}")
        
        # Shift prior for next iteration
        self.prior = self.posterior
        
        return self.posterior
        
    def reset(self, initial_prior: float = 0.5) -> None:
        self.prior = initial_prior
        self.posterior = initial_prior
