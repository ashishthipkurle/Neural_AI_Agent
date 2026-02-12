
import unittest
import sys
from unittest.mock import MagicMock, AsyncMock

# Mock python-telegram-bot
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.error'] = MagicMock()

from agent.skills.telegram.skill import TelegramSkill

class TestTelegramSkill(unittest.TestCase):
    def setUp(self):
        self.config = {
            'telegram': {
                'bot_token': 'TEST_TOKEN',
                'chat_id': '123456'
            }
        }
        
        # Setup Bot mock
        import telegram
        self.mock_bot = MagicMock()
        self.mock_bot.send_message = AsyncMock() # Async method
        telegram.Bot.return_value = self.mock_bot
        
        self.skill = TelegramSkill(self.config)

    def test_send_message_action(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            self.skill.execute("send_message", {"text": "Hello"})
        )
        
        self.assertTrue(result.success)
        self.mock_bot.send_message.assert_called_once()
        args, kwargs = self.mock_bot.send_message.call_args
        self.assertEqual(kwargs['text'], "Hello")
        self.assertEqual(kwargs['chat_id'], "123456")

    def test_request_approval(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Should send message and return False (default)
        result = loop.run_until_complete(
            self.skill.execute("request_approval", {"description": "Delete OS", "risk_level": "CRITICAL"})
        )
        
        self.assertTrue(result.success)
        self.assertFalse(result.data['approved'])
        self.mock_bot.send_message.assert_called()

if __name__ == '__main__':
    unittest.main()
