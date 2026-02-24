import logging
from typing import Dict, Any

class ComplianceLayer:
    """
    Enforces strict compliance rules before any trade or signal is authorized.
    Acts as a gating mechanism connecting standard risk metrics with regulatory status.
    """
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("ComplianceLayer")
        
    def check_compliance(self, signal: Dict[str, Any]) -> bool:
        """
        Evaluate a fully-assembled signal against hard compliance constraints.
        
        Args:
            signal: Full signal dict adhering to Section 12 structure.
            
        Returns:
            bool: True if compliant, False if blocked.
        """
        # Rule 1: Kill Switch Check
        if signal.get("kill_switch_state") != "INACTIVE":
            self.logger.error("Compliance Blocked: Kill-switch is ACTIVE.")
            return False
            
        # Rule 2: Regulatory Classifier Check
        if signal.get("regulatory_risk_classification") in ["RESTRICTED", "PROHIBITED"]:
            self.logger.error("Compliance Blocked: Asset/Trade is Restricted.")
            return False
            
        # Rule 3: Capital Preservation Check
        if signal.get("capital_mode") == "HALTED":
            self.logger.error("Compliance Blocked: Capital mode is HALTED due to drawdowns.")
            return False
            
        self.logger.debug("Compliance checks passed.")
        return True
