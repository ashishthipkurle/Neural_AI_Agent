import logging

class RegulatoryClassifier:
    """
    Assigns strict compliance risk classifications to trades based on jurisdiction rules,
    asset types, and leverage limits.
    """
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("RegulatoryClassifier")
        
    def classify_trade(self, asset: str, instrument_type: str, leverage: float = 1.0) -> str:
        """
        Classifies the trade into a regulatory risk tier.
        
        Returns:
            str: "LOW_RISK", "MEDIUM_RISK", "HIGH_RISK", "RESTRICTED", or "PROHIBITED"
        """
        # Simulated logic for regulatory scoping
        asset_upper = asset.upper()
        
        if "MEME" in asset_upper or instrument_type == "UNREGULATED_DERIVATIVE":
            return "PROHIBITED"
            
        if leverage > 5.0:
            return "RESTRICTED"
            
        if instrument_type == "OPTIONS" or leverage > 2.0:
            return "HIGH_RISK"
            
        if "CRYPTO" in instrument_type:
            return "MEDIUM_RISK"
            
        return "LOW_RISK"
