
import logging
from typing import Dict, Any, List, Optional
from agent.memory.personal_memory import PersonalMemoryManager

class SafetyFramework:
    """
    Module 12: Safety & Consent Framework
    Enforces permissions, risk analysis, and approval flows.
    """

    def __init__(self, config: Dict[str, Any], personal_memory: PersonalMemoryManager):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.memory = personal_memory
        
        # Load limits from config or defaults
        self.spending_limits = self.config.get('safety', {}).get('spending_limits', {
            'daily_usd': 50.0,
            'monthly_usd': 500.0
        })
        self.blocked_paths = self.config.get('safety', {}).get('blocked_paths', [])
        
        self._emergency_stop_active = False
        
        # Spending tracking (should be persistent, but in-memory for MVP step)
        # In full impl, this would query PersonalMemory or a ledger
        self._daily_spend = 0.0

    def classify_risk(self, action: Dict[str, Any]) -> str:
        """
        Input: {type, target, scope, cost_estimate}
        Returns: risk_level (LOW, MEDIUM, HIGH, CRITICAL)
        """
        action_type = action.get('type', '').lower()
        target = action.get('target', '')
        cost = action.get('cost_estimate', 0.0)
        
        # Rule: Emergency Stop Check
        if self._emergency_stop_active:
            return "CRITICAL"

        # Rule: Spending
        if cost > 0:
            return "CRITICAL" # Spending always needs approval per spec logic imply

        # Rule: System Commands
        if action_type in ['execute_command', 'shell']:
            return "HIGH"

        # Rule: File Operations
        if action_type in ['write_file', 'delete_file']:
            # Check blocked paths
            if any(path in target for path in self.blocked_paths):
                return "CRITICAL"
            return "HIGH" # Standard file write is high risk
            
        # Rule: Network
        if action_type in ['http_request', 'download']:
            return "MEDIUM"
            
        # Rule: Phone Calls
        if action_type == 'voice_call':
            return "CRITICAL"

        return "LOW"

    def requires_approval(self, action: Dict[str, Any]) -> bool:
        """Return True if risk >= config.approval_threshold"""
        risk = self.classify_risk(action)
        
        # Configurable threshold, default to HIGH
        thresholds = self.config.get('autonomous_mode', {}).get('require_approval_for', ['CRITICAL', 'HIGH'])
        
        return risk.upper() in [t.upper() for t in thresholds]

    async def get_approval(self, action: Dict[str, Any], 
                           telegram_skill: Any) -> bool:
        """
        Send detailed approval request via Telegram.
        """
        if not telegram_skill:
            self.logger.warning("No Telegram skill for approval. Defaulting to False.")
            return False
            
        description = action.get('description', 'Unknown Action')
        risk = self.classify_risk(action)
        
        # Logic to send request -> wait for callback
        # This is async and depends on Telegram implementation.
        # For foundation phase, we'll placeholder this.
        self.logger.info(f"Requesting approval for {description} (Risk: {risk})")
        
        # In real implementation:
        # return await telegram_skill.request_approval(description, risk)
        return False

    def check_spending_limit(self, estimated_cost: float) -> bool:
        """
        Check against daily/monthly limits.
        """
        if estimated_cost + self._daily_spend > self.spending_limits['daily_usd']:
            return False
        return True

    def emergency_stop(self) -> None:
        """
        1. Pause all running tasks
        2. Set global emergency flag
        """
        self.logger.warning("EMERGENCY STOP TRIGGERED")
        self._emergency_stop_active = True
        
        # Notify user via logs/telegram (if available)

    def is_emergency_stop_active(self) -> bool:
        """Check emergency status"""
        return self._emergency_stop_active
