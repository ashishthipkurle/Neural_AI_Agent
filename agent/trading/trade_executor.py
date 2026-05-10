import logging
from typing import Dict, Any
from agent.trading.audit_trail import AuditTrail


class TradeExecutor:
    """
    Dual-mode trade executor.
    - autonomous_mode=False: STRICTLY requires 'CONFIRM TRADE' string (original behavior).
    - autonomous_mode=True: Executes via broker_adapter without human confirmation.
    """

    def __init__(self, broker_adapter=None, autonomous_mode: bool = False) -> None:
        self.logger = logging.getLogger("TradeExecutor")
        self.audit = AuditTrail()
        self.broker = broker_adapter
        self.autonomous_mode = autonomous_mode

    def stage_trade(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepares a trade for human review. Returns the data to be displayed in the UI.
        """
        self.logger.info(f"Staging trade for explicit confirmation: {signal.get('asset')}")
        return {
            "status": "STAGED_AWAITING_CONFIRMATION",
            "prompt": "EXECUTION REQUIRES EXPLICIT CONFIRMATION. Reply 'CONFIRM TRADE'.",
            "signal_details": signal
        }

    def execute(self, signal: Dict[str, Any], manual_confirmation: str = "") -> Dict[str, Any]:
        """
        Executes the trade.
        - If autonomous_mode=True: skips confirmation, calls broker directly.
        - If autonomous_mode=False: requires exact 'CONFIRM TRADE' string.
        """
        if not self.autonomous_mode:
            # Original manual confirmation path
            if manual_confirmation != "CONFIRM TRADE":
                self.logger.warning(f"Trade rejected. Invalid confirmation: '{manual_confirmation}'")
                return {
                    "status": "REJECTED",
                    "reason": "Missing exact confirmation string 'CONFIRM TRADE'."
                }

        # Write to immutable audit ledger
        actor = "AUTONOMOUS_SYSTEM" if self.autonomous_mode else "AUTHORIZED_USER"
        event_type = "AUTONOMOUS_TRADE_EXECUTION" if self.autonomous_mode else "HUMAN_CONFIRMED_TRADE_EXECUTION"

        compliance_id = self.audit.record(
            payload=signal,
            event_type=event_type,
            actor=actor,
        )

        self.logger.info(f"Trade Executed. Compliance ID: {compliance_id}")

        # Execute via broker if available
        broker_order_id = ""
        if self.broker and self.broker.is_connected:
            symbol = signal.get("asset", signal.get("symbol", ""))
            direction = signal.get("direction", signal.get("action", "BUY"))
            qty = signal.get("quantity", signal.get("position_size", 1))
            side = "buy" if direction in ("LONG", "BUY") else "sell"

            order_result = self.broker.place_market_order(symbol, qty, side)
            broker_order_id = order_result.get("order_id", "")

            if order_result.get("error"):
                return {
                    "status": "BROKER_ERROR",
                    "compliance_record_id": compliance_id,
                    "error": order_result.get("message", "Unknown broker error"),
                }
        else:
            broker_order_id = f"SIM_{compliance_id[:12]}"

        return {
            "status": "EXECUTED",
            "compliance_record_id": compliance_id,
            "broker_order_id": broker_order_id,
            "mode": "AUTONOMOUS" if self.autonomous_mode else "MANUAL",
        }

