import logging
from typing import Dict, Any
from agent.trading.analysis_logger import AnalysisLogger

class AuditTrail:
    """
    Append-only, hash-chained immutable audit ledger interface.
    Wraps AnalysisLogger to provide a simplified API for compliance tracking.
    """
    
    def __init__(self, db_path: str = "agent_data/trading_audit.db") -> None:
        self.logger = logging.getLogger("AuditTrail")
        self._logger = AnalysisLogger(db_path=db_path)
        
    def record(self, payload: Dict[str, Any], event_type: str = "SYSTEM_AUDIT", actor: str = "SYSTEM") -> str:
        """
        Records an event immutably and returns its unique compliance record ID.
        """
        record_id = self._logger.log(
            event_type=event_type,
            actor=actor,
            payload=payload
        )
        self.logger.debug(f"Audit record created: {record_id}")
        return record_id
        
    def verify_chain(self) -> bool:
        """
        Cryptographically verifies the entire audit log database.
        """
        is_valid = self._logger.verify_chain()
        if not is_valid:
            self.logger.critical("AUDIT CHAIN INTEGRITY COMPROMISED!")
        return is_valid
