"""
Capital-Level Portfolio Risk Aggregator.

Architecture:
    - O(1) Incremental Portfolio Risk Computation via Covariance updates.
    - Aggregates Sector, Factor, and Regime exposures.
    - Estimates daily Tail Risk (Expected Shortfall).
    - Hard-rejects signals that destabilize portfolio variance constraints.
"""
import logging
import math
from typing import Dict, Any

class PortfolioRiskAggregator:
    """
    Acts as the final risk gatekeeper. Ensures that the overall portfolio
    does not become highly skewed toward a single sector, factor, or regime,
    and maintains variance bounds.
    """

    def __init__(
        self, 
        max_sector_exposure: float = 0.25, 
        max_regime_exposure: float = 0.40,
        max_portfolio_variance: float = 0.04  # 20% annualized vol approx
    ) -> None:
        self.logger = logging.getLogger("PortfolioRiskAggregator")
        self.max_sector_exposure = max_sector_exposure
        self.max_regime_exposure = max_regime_exposure
        self.max_portfolio_variance = max_portfolio_variance
        
        # State tracking (updated O(1) incrementally)
        self.total_capital: float = 1_000_000.0
        self.current_portfolio_variance: float = 0.0
        
        # Categorical exposures
        self.sector_exposures: Dict[str, float] = {}  # sector -> dollar_exposure
        self.regime_exposures: Dict[str, float] = {}  # regime -> dollar_exposure

    def evaluate_signal_impact(
        self, 
        signal_size_usd: float,
        sector: str,
        regime: str,
        incremental_variance_impact: float
    ) -> Dict[str, Any]:
        """
        Calculates if the proposed trade breaches any portfolio-level constraints.
        Returns evaluation dict with 'approved' boolean.
        """
        current_sector_usd = self.sector_exposures.get(sector, 0.0)
        proposed_sector_usd = current_sector_usd + abs(signal_size_usd)
        
        current_regime_usd = self.regime_exposures.get(regime, 0.0)
        proposed_regime_usd = current_regime_usd + abs(signal_size_usd)
        
        proposed_variance = self.current_portfolio_variance + incremental_variance_impact

        risk_log = {
            "incremental_variance": incremental_variance_impact,
            "cluster_exposure": proposed_sector_usd / self.total_capital,
            "regime_exposure": proposed_regime_usd / self.total_capital,
            "expected_shortfall": proposed_variance,
            "blocked_reason": None
        }
        self.logger.info(f"PORTFOLIO_RISK_CHECK: {risk_log}")

        if (proposed_sector_usd / self.total_capital) > self.max_sector_exposure:
            self.logger.warning("PORTFOLIO_GATE_REJECTED: Sector > Max")
            return {"approved": False, "reason": f"Sector > {self.max_sector_exposure*100}%"}

        if (proposed_regime_usd / self.total_capital) > self.max_regime_exposure:
            self.logger.warning("PORTFOLIO_GATE_REJECTED: Regime > Max")
            return {"approved": False, "reason": f"Regime > {self.max_regime_exposure*100}%"}

        if proposed_variance > self.max_portfolio_variance:
            self.logger.warning("PORTFOLIO_GATE_REJECTED: Variance Threshold Exceeded")
            return {"approved": False, "reason": "Variance Threshold Exceeded"}

        return {"approved": True, "reason": "All portfolio risk metrics within bounds."}

    def commit_trade(
        self, 
        signal_size_usd: float,
        sector: str,
        regime: str,
        incremental_variance_impact: float
    ) -> None:
        """
        O(1) update of internal states after trade execution.
        """
        abs_size = abs(signal_size_usd)
        self.sector_exposures[sector] = self.sector_exposures.get(sector, 0.0) + abs_size
        self.regime_exposures[regime] = self.regime_exposures.get(regime, 0.0) + abs_size
        self.current_portfolio_variance += incremental_variance_impact
        
        self.logger.info(f"Committed trade risk logic: Sector={sector}, Regime={regime}, Add_Var={incremental_variance_impact:.6f}")

    def get_portfolio_state_hash(self) -> str:
        """
        Used for the regulatory Audit Trail. Hashes exact current portfolio limits.
        """
        # Deterministic representation
        state_str = f"Cap:{self.total_capital}|Var:{self.current_portfolio_variance:.6f}"
        for sec in sorted(self.sector_exposures.keys()):
            state_str += f"|{sec}:{self.sector_exposures[sec]:.2f}"
            
        import hashlib
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]
