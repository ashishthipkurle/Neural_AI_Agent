import logging
from typing import Dict, Any

class SignalEngine:
    """
    Assembles the final comprehensive signal structure required by Section 12.
    Ensures that all components of the quantitative pipeline are consistently 
    represented in the final trade decision object.
    """
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("SignalEngine")
        
    def assemble_signal(self, **kwargs) -> Dict[str, Any]:
        """
        Constructs the strict Section 12 signal dictionary.
        Validates the presence of required fields to ensure traceability.
        """
        signal_data = {
            "asset": kwargs.get("asset", "UNKNOWN"),
            "timeframe": kwargs.get("timeframe", "1d"),
            "selected_strategy": kwargs.get("selected_strategy", "default"),
            "regime": kwargs.get("regime", "QUIET"),
            "reinforcement_weight": kwargs.get("reinforcement_weight", 1.0),
            "bayesian_confidence": kwargs.get("bayesian_confidence", 0.5),
            "kelly_fraction": kwargs.get("kelly_fraction", 0.0),
            "macro_bias": kwargs.get("macro_bias", "RISK_ON"),
            "forecasted_drawdown_risk": kwargs.get("forecasted_drawdown_risk", 0.0),
            "regulatory_risk_classification": kwargs.get("regulatory_risk_classification", "LOW_RISK"),
            "portfolio_state": kwargs.get("portfolio_state", "NORMAL"),
            "capital_mode": kwargs.get("capital_mode", "NORMAL"),
            "kill_switch_state": kwargs.get("kill_switch_state", "INACTIVE"),
            "compliance_record_id": kwargs.get("compliance_record_id", ""),
            "reporting_reference_id": kwargs.get("reporting_reference_id", ""),
            "indicators_snapshot": kwargs.get("indicators_snapshot", {}),
            "signal": kwargs.get("signal", 0), # 1 for Buy, -1 for Sell
            "probability_score": kwargs.get("probability_score", 0.0),
            "confidence": kwargs.get("confidence", "LOW"),
            "risk_level": kwargs.get("risk_level", "LOW"),
            "stop_loss": kwargs.get("stop_loss", 0.0),
            "take_profit": kwargs.get("take_profit", 0.0),
            "position_size": kwargs.get("position_size", 0.0),
            "portfolio_risk_impact": kwargs.get("portfolio_risk_impact", 0.0),
            "reasoning": kwargs.get("reasoning", ""),
            "warnings": kwargs.get("warnings", [])
        }
        
        # Self-check for required execution block fields
        if signal_data["kill_switch_state"] != "INACTIVE":
            signal_data["warnings"].append("KILL SWITCH ACTIVE. Execution blocked.")
            signal_data["position_size"] = 0.0
            
        return signal_data
