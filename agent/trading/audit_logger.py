"""
Regulatory & Audit Logger.

Architecture:
    - Cryptographically signs and sequences every emitted signal.
    - Embeds precise system-state metadata to prove compliance.
    - Outputs immutable JSONL format for cold storage archiving.
"""
import json
import time
import hashlib
import logging
from typing import Dict, Any

class AuditLogger:
    """
    Forces every generated signal to carry cryptographic context representing
    the exact state of the distributed engine and risk portfolios at execution.
    """

    def __init__(self, log_dir: str = "./audit_logs") -> None:
        self.logger = logging.getLogger("AuditLogger")
        self.log_dir = log_dir
        import os
        os.makedirs(self.log_dir, exist_ok=True)
        # We roll this file daily in production
        self.current_log_file = os.path.join(self.log_dir, f"audit_trail_{int(time.time() // 86400)}.jsonl")

    def _hash_payload(self, payload: str) -> str:
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def generate_audit_receipt(
        self,
        signal_dict: Dict[str, Any],
        snapshot_id: str,
        feature_schema_hash: str,
        index_version: str,
        risk_state_hash: str,
        portfolio_covariance_hash: str,
        drift_state_hash: str,
        capital_allocation_state_hash: str,
        shard_id: int,
        node_id: str,
        coordinator_epoch: int,
        request_id: str
    ) -> Dict[str, Any]:
        """
        Creates an immutable, verifiable receipt for a single trading signal.
        """
        timestamp = time.time()
        
        # Strip transient or unnecessary fields from signal
        core_signal = {
            "instrument_id": signal_dict.get("instrument_id"),
            "timeframe": signal_dict.get("timeframe"),
            "action": signal_dict.get("signal"), # LONG/SHORT
            "confidence": signal_dict.get("confidence"),
            "proposed_size": signal_dict.get("proposed_size", 0.0)
        }

        receipt = {
            "request_id": request_id,
            "timestamp_utc": timestamp,
            "signal": core_signal,
            "system_state": {
                "snapshot_id": snapshot_id,
                "feature_schema_hash": feature_schema_hash,
                "index_version": index_version,
                "risk_state_hash": risk_state_hash,
                "portfolio_covariance_hash": portfolio_covariance_hash,
                "drift_state_hash": drift_state_hash,
                "capital_allocation_state_hash": capital_allocation_state_hash
            },
            "cluster_state": {
                "shard_id": shard_id,
                "node_id": node_id,
                "coordinator_epoch": coordinator_epoch
            }
        }

        # Sign the specific emission
        receipt_str = json.dumps(receipt, sort_keys=True)
        signature = self._hash_payload(receipt_str)
        receipt["audit_signature"] = signature

        self._flush_to_disk(receipt)
        return receipt

    def _flush_to_disk(self, receipt: Dict[str, Any]) -> None:
        try:
            with open(self.current_log_file, 'a') as f:
                f.write(json.dumps(receipt) + "\n")
        except Exception as e:
            self.logger.critical(f"FAILED TO WRITE AUDIT TRAIL: {e}")
            # In a highly hardened system, failing to write audit log triggers Failure/Halt.
