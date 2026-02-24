import logging
from typing import Dict, Any

class PortfolioManager:
    """
    Tracks overall portfolio state, leverage, and net exposures.
    Read-only tracking system used by RiskManager and Dashboards.
    """
    
    def __init__(self, initial_equity: float = 100000.0) -> None:
        self.logger = logging.getLogger("PortfolioManager")
        self.equity = initial_equity
        self.positions: Dict[str, Dict[str, Any]] = {}
        
    def update_position(self, asset: str, quantity: float, avg_price: float, current_price: float) -> None:
        """Upsert a position."""
        self.positions[asset] = {
            "quantity": quantity,
            "avg_price": avg_price,
            "current_price": current_price,
            "value": quantity * current_price,
            "unrealized_pnl": (current_price - avg_price) * quantity
        }
        
    def get_total_exposure(self) -> float:
        """Gross exposure (Long + Short)."""
        return sum(abs(pos.get("value", 0.0)) for pos in self.positions.values())
        
    def get_net_exposure(self) -> float:
        """Net exposure (Long - Short)."""
        return sum(pos.get("value", 0.0) for pos in self.positions.values())
        
    def get_leverage(self) -> float:
        """Gross Leverage ratio."""
        if self.equity <= 0:
            self.logger.warning("Equity is zero or negative. Leverage undefined.")
            return 0.0
        return self.get_total_exposure() / self.equity
        
    def get_state_summary(self) -> Dict[str, Any]:
        unrealized = sum(pos.get("unrealized_pnl", 0.0) for pos in self.positions.values())
        return {
            "equity": self.equity + unrealized,
            "cash": self.equity, # Simplified
            "gross_exposure": self.get_total_exposure(),
            "net_exposure": self.get_net_exposure(),
            "leverage": self.get_leverage(),
            "open_positions_count": len(self.positions)
        }
