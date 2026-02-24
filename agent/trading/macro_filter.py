import logging
from typing import Dict, Any

class MacroFilter:
    """
    Macro-economic overlay for filtering trade signals.
    Acts as a top-level gatekeeper based on broader economic conditions 
    (e.g., risk-free rates, volatility index, credit spreads).
    """
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("MacroFilter")
        
    def assess_macro_regime(self, risk_free_rate: float, vcs_index: float, credit_spread: float) -> str:
        """
        Determines RISK_ON or RISK_OFF based on macro variables.
        
        Args:
            risk_free_rate: e.g., US 10-Year Treasury Yield
            vcs_index: Volatility index (like VIX)
            credit_spread: e.g., High Yield minus Risk Free
            
        Returns:
            str: "RISK_ON" or "RISK_OFF"
        """
        # Thresholds would typically be dynamic or learned; hardcoded for isolation
        if vcs_index > 30.0 or credit_spread > 5.0:
            self.logger.info("Macro regime: RISK_OFF")
            return "RISK_OFF"
            
        self.logger.info("Macro regime: RISK_ON")
        return "RISK_ON"
        
    def adjust_signal(self, base_signal: dict, macro_regime: str) -> dict:
        """
        Adjusts signal confidence/strength based on the macro regime.
        """
        adjusted_signal = base_signal.copy()
        strength = adjusted_signal.get("strength", 0.0)
        
        if macro_regime == "RISK_OFF" and strength > 0:
            # Dampen long signals in risk-off environment
            adjusted_signal["strength"] = strength * 0.5
            adjusted_signal["warnings"] = adjusted_signal.get("warnings", []) + ["Signal dampened due to RISK_OFF macro regime."]
            
        elif macro_regime == "RISK_ON" and strength < 0:
            # Dampen short signals in risk-on environment
            adjusted_signal["strength"] = strength * 0.5
            adjusted_signal["warnings"] = adjusted_signal.get("warnings", []) + ["Short signal dampened due to RISK_ON macro regime."]
            
        return adjusted_signal
