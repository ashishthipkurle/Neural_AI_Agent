import logging

class KillSwitch:
    """
    Emergency Portfolio Kill-Switch.
    When activated, blocks ALL new trades across the entire module.
    Mechanically requires explicit string assertion to reset.
    """
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("KillSwitch")
        self.is_active = False
        self.activation_reason = ""
        
    def activate(self, reason: str) -> None:
        """Trip the kill-switch."""
        self.is_active = True
        self.activation_reason = reason
        self.logger.critical(f"KILL-SWITCH ACTIVATED. REASON: {reason}")
        
    def manual_reset(self, acknowledgement: str) -> bool:
        """
        Reset the kill-switch. Requires exact string match to prevent accidental resets.
        """
        expected_ack = "I_ACKNOWLEDGE_RISK_AND_RESET"
        if acknowledgement == expected_ack:
            self.is_active = False
            self.activation_reason = ""
            self.logger.info("KILL-SWITCH MANUALLY RESET.")
            return True
            
        self.logger.error(f"Kill-switch reset failed. Invalid acknowledgement string. Expected '{expected_ack}'.")
        return False
        
    def check_status(self) -> str:
        """Returns the current state for signal assembly."""
        return "ACTIVE" if self.is_active else "INACTIVE"
