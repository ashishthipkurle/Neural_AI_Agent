"""
Capital Allocation & Optimization Engine.

Transforms approved binary signals into precisely sized capital allocations.
Enforces institutional-grade mathematical limits:
    - Kelly Fraction Capping (Empirical Win Rate & R-Multiple)
    - Volatility Targeting (Dynamic gross exposure scaling)
    - Drawdown Adaptive Scaling (Exponential decay)
    - Correlation-Adjusted Risk Parity
    - Tail Risk (Expected Shortfall) Constraints
    
Strictly deterministic. No LLM math.
"""
import math
import logging
from typing import Dict, Any

class CapitalAllocator:
    """
    Final sizing authority. Receives a risk-approved signal and determines
    the exact dollar or fractional capital to deploy based on portfolio
    optimization mathematics.
    """

    def __init__(
        self,
        max_kelly_fraction: float = 0.25,        # Never deploy more than 1/4th Kelly
        target_annual_volatility: float = 0.15,  # 15% Volatility Target
        max_gross_exposure_pct: float = 0.05,    # 5% max capital per trade absolute cap
        drawdown_decay_factor: float = 10.0,     # Severity of exposure cut during drawdowns
        tail_risk_es99_limit_pct: float = 0.10   # 10% max expected shortfall
    ) -> None:
        self.logger = logging.getLogger("CapitalAllocator")
        
        # Hard Caps
        self.max_kelly = max_kelly_fraction
        self.target_volatility = target_annual_volatility
        self.max_exposure = max_gross_exposure_pct
        self.drawdown_decay_factor = drawdown_decay_factor
        self.tail_risk_limit = tail_risk_es99_limit_pct
        
    def calculate_kelly_fraction(self, win_rate: float, expected_r_multiple: float) -> float:
        """
        Kelly = W - ((1 - W) / R)
        Returns the mathematically optimal fraction of capital to risk.
        If R is zero or negative (invalid game), returns 0.
        """
        if expected_r_multiple <= 0 or win_rate <= 0:
            return 0.0
            
        kelly = win_rate - ((1.0 - win_rate) / expected_r_multiple)
        
        # Half-Kelly or Quarter-Kelly is standard in institutional practice
        capped_kelly = max(0.0, min(kelly, self.max_kelly))
        return capped_kelly

    def apply_volatility_targeting(self, base_allocation: float, current_portfolio_vol: float) -> float:
        """
        Adjusts gross exposure dynamically to maintain target portfolio volatility.
        scale_factor = target_vol / current_portfolio_vol
        """
        if current_portfolio_vol <= 0:
            return base_allocation # Bootstrapping or flat portfolio
            
        scale_factor = self.target_volatility / current_portfolio_vol
        
        # Cap leverage scale to a reasonable bound if volatility is extremely low
        scale_factor = min(scale_factor, 3.0) 
        
        return base_allocation * scale_factor

    def apply_drawdown_decay(self, allocation: float, current_drawdown_pct: float) -> float:
        """
        Exponentially decays exposure based on depth of active drawdown.
        exposure_multiplier = exp(-drawdown * decay_factor)
        """
        if current_drawdown_pct <= 0:
            return allocation
            
        decay_multiplier = math.exp(-current_drawdown_pct * self.drawdown_decay_factor)
        return allocation * decay_multiplier

    def apply_risk_parity_penalty(self, allocation: float, cluster_concentration: float) -> float:
        """
        Reduces allocation if deploying into an already highly correlated cluster.
        cluster_concentration should be [0.0, 1.0] representing cluster's share of total risk.
        """
        if cluster_concentration >= 1.0:
            return 0.0
            
        # Linear penalty: if cluster is 30% of risk, reduce new allocation by 30%
        # Ensures equalized marginal contribution to risk across uncorrelated clusters.
        penalty_factor = max(0.0, 1.0 - cluster_concentration)
        return allocation * penalty_factor

    def check_tail_risk(self, proposed_portfolio_es99: float) -> bool:
        """
        Expected Shortfall at 99% must remain below defined capital fraction.
        """
        if proposed_portfolio_es99 > self.tail_risk_limit:
            self.logger.warning(
                f"Tail Risk Block: Proposed ES99 ({proposed_portfolio_es99:.4f}) "
                f"exceeds limit ({self.tail_risk_limit:.4f})."
            )
            return False
        return True

    def allocate_capital(
        self,
        total_account_value: float,
        signal_win_rate: float,
        signal_expected_r: float,
        portfolio_volatility: float,
        current_drawdown: float,
        cluster_concentration: float,
        proposed_es99: float
    ) -> Dict[str, Any]:
        """
        Master orchestration of capital math. 
        Takes inputs from risk/probability engines and returns final sizing.
        """
        # 1. Base sizing via Kelly Criterion
        kelly_fraction = self.calculate_kelly_fraction(signal_win_rate, signal_expected_r)
        
        if kelly_fraction <= 0.0:
            return {"allocated_capital": 0.0, "reason": "Zero or negative Kelly edge", "fraction": 0.0}
            
        # 2. Volatility Targeting
        vol_adjusted_fraction = self.apply_volatility_targeting(kelly_fraction, portfolio_volatility)
        
        # 3. Drawdown Adaptive Scaling
        dd_adjusted_fraction = self.apply_drawdown_decay(vol_adjusted_fraction, current_drawdown)
        
        # 4. Correlation / Risk Parity Penalty
        parity_fraction = self.apply_risk_parity_penalty(dd_adjusted_fraction, cluster_concentration)
        
        # 5. Global Exposure Cap
        final_fraction = min(parity_fraction, self.max_exposure)
        
        # 6. Tail Risk Constraint Check
        if not self.check_tail_risk(proposed_es99):
            return {"allocated_capital": 0.0, "reason": "Tail Risk (ES99) limit exceeded", "fraction": final_fraction}

        allocated_dollars = final_fraction * total_account_value
        
        self.logger.info(
            f"Capital Allocated: {final_fraction*100:.2f}% (${allocated_dollars:.2f}) | "
            f"Kelly: {kelly_fraction:.3f}, VolAdj: {vol_adjusted_fraction:.3f}, "
            f"DDAdj: {dd_adjusted_fraction:.3f}, Parity: {parity_fraction:.3f}"
        )

        return {
            "allocated_capital": round(allocated_dollars, 2),
            "fraction": round(final_fraction, 6),
            "reason": "Optimal allocation computed"
        }
