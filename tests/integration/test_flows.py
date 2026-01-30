"""
Integration Tests for Humanoid Local AI Agent.

Tests end-to-end flows across multiple modules.
"""
import pytest
import asyncio
import tempfile
import os

# Skip integration tests if dependencies are missing
pytestmark = pytest.mark.integration


class TestOrchestrationFlow:
    """Test complete orchestration flow."""
    
    def test_state_machine_transitions(self):
        """Test state machine handles full flow."""
        from agent.core.orchestrator import StateMachine, AgentState
        
        sm = StateMachine()
        
        # Full workflow: IDLE -> LISTENING -> THINKING -> ACTING -> IDLE
        assert sm.state == AgentState.IDLE
        
        # IDLE -> LISTENING (valid)
        sm.to_listening("Awaiting input")
        assert sm.state == AgentState.LISTENING
        
        # LISTENING -> THINKING (valid)
        sm.to_thinking("Processing user input")
        assert sm.state == AgentState.THINKING
        
        # THINKING -> ACTING (valid)
        sm.to_acting("Executing action")
        assert sm.state == AgentState.ACTING
        
        # ACTING -> IDLE (valid)
        sm.to_idle("Completed")
        assert sm.state == AgentState.IDLE
    
    def test_lock_unlock_flow(self):
        """Test lock/unlock workflow."""
        from agent.core.orchestrator import StateMachine, AgentState
        
        sm = StateMachine()
        
        # Lock
        sm.lock("Security test")
        assert sm.is_locked
        assert sm.state == AgentState.LOCKED
        
        # Cannot transition while locked
        assert not sm.to_thinking("Should fail")
        
        # Unlock
        sm.unlock("Auth successful")
        assert not sm.is_locked
        assert sm.state == AgentState.IDLE


class TestMemoryFlow:
    """Test memory system integration."""
    
    def test_short_term_memory_lifecycle(self):
        """Test short-term memory storage and retrieval."""
        from agent.memory.short_term import ShortTermMemory
        
        stm = ShortTermMemory()
        
        # Add various types
        stm.add_message("user", "Hello there")
        stm.add_message("assistant", "Hi! How can I help?")
        stm.add_action("search", "Found 10 results")
        
        # Retrieve
        recent = stm.get_recent(10)
        assert len(recent) == 3
        
        # Message history
        messages = stm.get_message_history(10)
        assert len(messages) == 2
        
        # Context string
        context = stm.get_context_string()
        assert "SHORT-TERM MEMORY" in context


class TestSecurityFlow:
    """Test security module integration."""
    
    def test_audit_logging_flow(self, tmp_path):
        """Test audit logging captures events."""
        from agent.security.audit_log import AuditLogger
        
        logger = AuditLogger(log_dir=str(tmp_path / "audit"))
        
        # Log various events
        logger.log_command("test_action", {"key": "value"})
        logger.log_consent("delete_file", approved=True, method="voice")
        logger.log_security("login_attempt", "User attempted login", severity="info")
        
        # Retrieve entries
        entries = logger.get_entries(limit=10)
        assert len(entries) == 3
    
    def test_pin_fallback_security(self, tmp_path):
        """Test PIN authentication with lockout."""
        from agent.security.face.pin_fallback import PINFallback
        
        pin = PINFallback(pin_file=str(tmp_path / "test.pin"))
        
        # Set PIN
        assert pin.set_pin("1234")
        assert pin.is_configured()
        
        # Correct PIN
        assert pin.verify("1234")
        
        # Wrong PIN exhausts attempts
        for _ in range(5):
            assert not pin.verify("0000")
        
        # Should be locked out
        assert pin.get_remaining_attempts() == 0


class TestVoiceFlow:
    """Test voice system integration."""
    
    def test_emotion_detection(self):
        """Test emotion detection from text."""
        from agent.voice.emotion_controller import EmotionController, Emotion
        
        ec = EmotionController()
        
        # Test various emotions (based on keyword matching)
        assert ec.detect_emotion("happy") == Emotion.HAPPY
        assert ec.detect_emotion("sorry") == Emotion.CONCERNED  # 'sorry' maps to concerned in current impl
        assert ec.detect_emotion("I can definitely do that") == Emotion.CONFIDENT
    
    def test_prosody_settings(self):
        """Test prosody settings for emotions."""
        from agent.voice.emotion_controller import EmotionController, Emotion
        
        ec = EmotionController()
        
        # Get settings for happy
        settings = ec.get_prosody_settings(Emotion.HAPPY)
        assert settings.speed_modifier > 1.0  # Faster
        
        # Get settings for calm
        settings = ec.get_prosody_settings(Emotion.CALM)
        assert settings.speed_modifier < 1.0  # Slower


class TestConsentFlow:
    """Test consent gate integration."""
    
    def test_consent_level_classification(self):
        """Test action classification for consent levels."""
        from agent.core.orchestrator import ConsentGate, ConsentLevel
        
        gate = ConsentGate()
        
        # Safe actions
        level = gate.determine_consent_level("read_file")
        assert level == ConsentLevel.NONE
        
        # Dangerous actions require consent
        level = gate.determine_consent_level("delete_file")
        assert level != ConsentLevel.NONE


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
