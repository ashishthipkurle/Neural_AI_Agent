
import unittest
import sys
from unittest.mock import MagicMock

# Mock Twilio
sys.modules['twilio'] = MagicMock()
sys.modules['twilio.rest'] = MagicMock()
sys.modules['twilio.twiml.voice_response'] = MagicMock()

from agent.skills.voice_call.skill import AdvancedVoiceCallSkill
from agent.memory.personal_memory import PersonalMemoryManager

class TestAdvancedVoiceCallSkill(unittest.TestCase):
    def setUp(self):
        # Mock Memory
        self.mock_memory = MagicMock()
        self.mock_memory.get_user_context.return_value = "User is TestUser"
        self.mock_memory.get_relationship.return_value = {"phone_number": "+1234567890"}
        
        self.config = {
            'voice_calls': {
                'twilio': {
                    'account_sid': 'AC_TEST',
                    'auth_token': 'AUTH_TEST',
                    'from_number': '+0987654321'
                }
            }
        }
        
        # Setup Client mock
        import twilio.rest
        
        self.skill = AdvancedVoiceCallSkill(self.config, self.mock_memory)
        # Force inject mock client
        self.mock_client_instance = MagicMock()
        self.mock_calls = MagicMock()
        self.mock_calls.create.return_value.sid = "CA12345"
        self.mock_client_instance.calls = self.mock_calls
        self.skill.client = self.mock_client_instance

    def test_make_call_command(self):
        # Test basic execution
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            self.skill.execute("make_call", {"phone_number": "+1112223333", "purpose": "Testing"})
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.data['call_sid'], "CA12345")
        
        # Verify Twilio create called with correct args
        self.mock_calls.create.assert_called_once()
        args, kwargs = self.mock_calls.create.call_args
        self.assertEqual(kwargs['to'], "+1112223333")
        self.assertEqual(kwargs['from_'], "+0987654321")

    def test_disclosure_generation(self):
        ctx = "User is Alex"
        resp = self.skill.generate_response("Hello", [], ctx, "Test purpose")
        self.assertIn("calling on behalf of", resp) # Check disclosure logic
        
    def test_lookup_phone_by_name(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Call by name "John"
        result = loop.run_until_complete(
            self.skill.execute("make_call", {"contact_name": "John", "purpose": "Hi"})
        )
        # Should look up from mock_memory and find +1234567890
        # Then call Twilio
        
        self.assertTrue(result.success)
        # Verify to number was the one from memory
        args, kwargs = self.mock_calls.create.call_args
        self.assertEqual(kwargs['to'], "+1234567890")

if __name__ == '__main__':
    unittest.main()
