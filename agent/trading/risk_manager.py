import logging
from typing import Dict, Any

class RiskManager:
    """
    Position-level and portfolio-level risk gating limits.
    Acts as a secondary firewall before signals are presented to the user.
    """
    
    def __init__(self, max_portfolio_risk: float = 0.05, max_position_risk: float = 0.01) -> None:
        self.logger = logging.getLogger("RiskManager")
        # Global absolute risk boundaries (e.g., maximum 5% overall portfolio risk)
        self.max_portfolio_risk = max_portfolio_risk
        # Local position risk (e.g., maximum 1% risk per trade)
        self.max_position_risk = max_position_risk
        
    def check_position_limits(self, dollar_risk: float, portfolio_value: float) -> bool:
        """
        Verify that a single trade's risk does not exceed maximum bounds.
        """
        if portfolio_value <= 0:
            return False
            
        risk_pct = dollar_risk / portfolio_value
        if risk_pct > self.max_position_risk:
            self.logger.warning(f"Position risk ({risk_pct:.2%}) exceeds limit ({self.max_position_risk:.2%})")
            return False
            
        return True
        
    def check_portfolio_limits(self, current_total_risk: float, new_trade_risk: float, portfolio_value: float) -> bool:
        """
        Verify that adding a new trade won't push overall portfolio risk beyond limits.
        """
        if portfolio_value <= 0:
            return False
            
        projected_risk = (current_total_risk + new_trade_risk) / portfolio_value
        if projected_risk > self.max_portfolio_risk:
            self.logger.warning(f"Projected portfolio risk ({projected_risk:.2%}) exceeds limit ({self.max_portfolio_risk:.2%})")
            return False
            
        return True
