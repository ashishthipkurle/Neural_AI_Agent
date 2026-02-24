import logging

class CapitalPreservation:
    """
    State machine for portfolio preservation modes.
    Modes: NORMAL -> DEFENSIVE -> CRITICAL -> HALTED
    Triggered by peak-to-trough drawdowns.
    """
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("CapitalPreservation")
        self.mode = "NORMAL"
        
    def evaluate_mode(self, current_drawdown: float) -> str:
        """
        Determine operational mode based on current drawdown.
        
        Args:
            current_drawdown (float): Positive percentage representing drawdown from peak (e.g., 0.10 for 10%)
            
        Returns:
            str: The active preservation mode.
        """
        previous_mode = self.mode
        
        if current_drawdown >= 0.20:
            self.mode = "HALTED"
        elif current_drawdown >= 0.12:
            self.mode = "CRITICAL"
        elif current_drawdown >= 0.06:
            self.mode = "DEFENSIVE"
        else:
            self.mode = "NORMAL"
            
        if self.mode != previous_mode:
            self.logger.warning(f"Capital preservation mode transition: {previous_mode} -> {self.mode} (DD: {current_drawdown:.2%})")
            
        return self.mode
        
    def get_position_sizing_multiplier(self) -> float:
        """Returns a multiplier to forcefully shrink position sizes based on mode."""
        if self.mode == "NORMAL":
            return 1.0
        elif self.mode == "DEFENSIVE":
            return 0.5
        elif self.mode == "CRITICAL":
            return 0.25
        return 0.0 # HALTED
