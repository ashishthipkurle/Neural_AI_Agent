
import unittest
from agent.core.safety_framework import SafetyFramework

class TestSafetyFramework(unittest.TestCase):
    def setUp(self):
        config = {
            'safety': {
                'spending_limits': {'daily_usd': 50},
                'blocked_paths': ['/etc']
            },
            'autonomous_mode': {
                'require_approval_for': ['HIGH', 'CRITICAL']
            }
        }
        self.safety = SafetyFramework(config, None) # Mock memory for now

    def test_risk_classification(self):
        # Low risk
        self.assertEqual(self.safety.classify_risk({'type': 'read_file'}), "LOW")
        
        # Medium risk
        self.assertEqual(self.safety.classify_risk({'type': 'http_request'}), "MEDIUM")
        
        # High risk
        self.assertEqual(self.safety.classify_risk({'type': 'execute_command'}), "HIGH")
        
        # Critical (Blocked Path)
        self.assertEqual(self.safety.classify_risk({'type': 'write_file', 'target': '/etc/hosts'}), "CRITICAL")
        
        # Critical (Spending)
        self.assertEqual(self.safety.classify_risk({'type': 'api_call', 'cost_estimate': 1.0}), "CRITICAL")

    def test_approval_logic(self):
        # High requires approval
        self.assertTrue(self.safety.requires_approval({'type': 'execute_command'}))
        
        # Low does not
        self.assertFalse(self.safety.requires_approval({'type': 'read_file'}))

    def test_emergency_stop(self):
        self.assertFalse(self.safety.is_emergency_stop_active())
        self.safety.emergency_stop()
        self.assertTrue(self.safety.is_emergency_stop_active())
        
        # Even low risk becomes critical in emergency
        self.assertEqual(self.safety.classify_risk({'type': 'read_file'}), "CRITICAL")

if __name__ == '__main__':
    unittest.main()
