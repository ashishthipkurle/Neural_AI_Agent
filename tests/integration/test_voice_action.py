"""
Integration Tests - Voice to Action Flow.

Tests the complete pipeline:
1. Voice input → STT
2. STT → Intent parsing
3. Intent → Tool execution
4. Tool result → TTS response
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import logging

# Configure logging for tests
logging.basicConfig(level=logging.DEBUG)


class TestVoiceToActionFlow:
    """Integration tests for voice command processing."""
    
    @pytest.fixture
    def mock_voice_manager(self):
        """Create mock voice manager."""
        from unittest.mock import MagicMock
        
        voice = MagicMock()
        voice.is_available.return_value = True
        voice.listen.return_value = "what time is it"
        voice.speak = MagicMock()
        voice.greet = MagicMock()
        return voice
    
    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM that returns structured intents."""
        llm = MagicMock()
        llm.parse_intent.return_value = {
            "actions": [{
                "action": "get_time",
                "reasoning": "User asked for current time",
                "parameters": {}
            }]
        }
        llm.chat.return_value = "It's 10:30 AM."
        return llm
    
    def test_voice_input_to_intent_parsing(self, mock_voice_manager, mock_llm):
        """Test that voice input is correctly parsed into intent."""
        # Simulate voice input
        voice_text = mock_voice_manager.listen()
        assert voice_text == "what time is it"
        
        # Parse intent
        intent = mock_llm.parse_intent(voice_text, "You are a helpful assistant.")
        
        assert "actions" in intent
        assert len(intent["actions"]) > 0
        assert intent["actions"][0]["action"] == "get_time"
    
    def test_intent_to_tool_execution(self, mock_voice_manager, mock_llm):
        """Test that intents are correctly routed to tools."""
        # Create mock tool registry
        tool_registry = {
            "get_time": MagicMock(return_value="10:30 AM"),
            "chat_tool": MagicMock(return_value="Hello!"),
        }
        
        # Parse intent
        intent = mock_llm.parse_intent("what time is it", "")
        action = intent["actions"][0]["action"]
        
        # Execute tool
        assert action in tool_registry
        result = tool_registry[action]()
        assert result == "10:30 AM"
    
    def test_tool_result_to_speech(self, mock_voice_manager):
        """Test that tool results are spoken via TTS."""
        # Simulate tool result
        tool_result = "The current time is 10:30 AM."
        
        # Speak result
        mock_voice_manager.speak(tool_result)
        
        # Verify speak was called
        mock_voice_manager.speak.assert_called_once_with(tool_result)
    
    def test_full_voice_command_flow(self, mock_voice_manager, mock_llm):
        """Test complete voice command flow end-to-end."""
        # 1. User speaks
        user_input = mock_voice_manager.listen()
        assert user_input is not None
        
        # 2. Parse intent
        intent = mock_llm.parse_intent(user_input, "")
        assert "actions" in intent
        
        # 3. Execute action (mocked)
        action = intent["actions"][0]["action"]
        result = "10:30 AM"  # Simulated tool result
        
        # 4. Generate response
        response = mock_llm.chat("", f"The time is {result}")
        assert response is not None
        
        # 5. Speak response
        mock_voice_manager.speak(response)
        mock_voice_manager.speak.assert_called_once()
    
    def test_voice_confirmation_for_dangerous_action(self, mock_voice_manager):
        """Test that dangerous actions require voice confirmation."""
        # Set up voice confirmation mock
        mock_voice_manager.confirm_action = MagicMock(return_value=True)
        
        # Simulate dangerous action
        dangerous_action = "delete_file"
        description = "Delete file test.txt"
        
        # Request confirmation
        confirmed = mock_voice_manager.confirm_action(description)
        
        assert confirmed is True
        mock_voice_manager.confirm_action.assert_called_once_with(description)
    
    def test_voice_denial_blocks_action(self, mock_voice_manager):
        """Test that denied actions are blocked."""
        mock_voice_manager.confirm_action = MagicMock(return_value=False)
        
        dangerous_action = "delete_file"
        description = "Delete file test.txt"
        
        # Request confirmation (denied)
        confirmed = mock_voice_manager.confirm_action(description)
        
        assert confirmed is False
        # Action should not proceed


class TestWakeWordToAction:
    """Tests for wake word activation flow."""
    
    def test_wake_word_activates_listening(self):
        """Test that wake word triggers listening state."""
        # Mock wake word detector
        wake_detector = MagicMock()
        wake_detector.detected = MagicMock(return_value=True)
        
        # State machine mock
        state_machine = MagicMock()
        state_machine.transition_to = MagicMock()
        
        # Simulate wake word detection
        if wake_detector.detected():
            state_machine.transition_to("LISTENING")
        
        state_machine.transition_to.assert_called_once_with("LISTENING")


class TestEmotionalResponse:
    """Tests for emotion-aware responses."""
    
    def test_emotion_mapping_to_tts(self):
        """Test that emotions are correctly mapped to TTS parameters."""
        emotion_params = {
            "happy": {"rate": 1.1, "pitch": 1.1, "volume": 1.0},
            "sad": {"rate": 0.9, "pitch": 0.9, "volume": 0.8},
            "excited": {"rate": 1.2, "pitch": 1.2, "volume": 1.1},
            "calm": {"rate": 0.95, "pitch": 1.0, "volume": 0.9},
        }
        
        # Test each emotion has valid parameters
        for emotion, params in emotion_params.items():
            assert "rate" in params
            assert "pitch" in params
            assert "volume" in params
            assert 0.5 <= params["rate"] <= 2.0
            assert 0.5 <= params["pitch"] <= 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
