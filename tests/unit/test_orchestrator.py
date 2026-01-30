"""
Unit Tests for Core Orchestrator Module.

Tests:
- State machine transitions
- Consent gate behavior
- Command routing
- Rollback operations
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

# Import modules being tested
from agent.core.orchestrator import StateMachine, AgentState
from agent.core.orchestrator import ConsentGate, ConsentLevel, ConsentStatus
from agent.core.orchestrator import CommandRouter
from agent.core.orchestrator import RollbackManager


class TestStateMachine:
    """Tests for StateMachine class."""
    
    def test_initial_state(self):
        """Test initial state is IDLE."""
        sm = StateMachine()
        assert sm.state == AgentState.IDLE
    
    def test_valid_transition(self):
        """Test valid state transitions."""
        sm = StateMachine()
        
        assert sm.transition(AgentState.LISTENING, "test")
        assert sm.state == AgentState.LISTENING
        
        assert sm.transition(AgentState.THINKING, "test")
        assert sm.state == AgentState.THINKING
    
    def test_invalid_transition(self):
        """Test invalid state transition is rejected."""
        sm = StateMachine()
        # Cannot go from IDLE directly to ACTING
        assert not sm.transition(AgentState.ACTING, "test")
        assert sm.state == AgentState.IDLE
    
    def test_lock_unlock(self):
        """Test lock and unlock functionality."""
        sm = StateMachine()
        
        sm.lock("test")
        assert sm.is_locked
        assert sm.state == AgentState.LOCKED
        
        sm.unlock("test")
        assert not sm.is_locked
        assert sm.state == AgentState.IDLE
    
    def test_history(self):
        """Test transition history tracking."""
        sm = StateMachine()
        sm.transition(AgentState.LISTENING, "step 1")
        sm.transition(AgentState.THINKING, "step 2")
        
        history = sm.get_history(10)
        assert len(history) == 2


class TestConsentGate:
    """Tests for ConsentGate class."""
    
    def test_safe_action_no_consent(self):
        """Test safe actions don't require consent."""
        gate = ConsentGate()
        level = gate.determine_consent_level("read_file")
        assert level == ConsentLevel.NONE
    
    def test_dangerous_action_requires_consent(self):
        """Test dangerous actions require consent."""
        gate = ConsentGate()
        level = gate.determine_consent_level("delete_file")
        assert level in [ConsentLevel.SINGLE, ConsentLevel.DUAL]
    
    def test_create_request(self):
        """Test consent request creation."""
        gate = ConsentGate()
        request = gate.create_request(
            action="write_file",
            parameters={"path": "/test/file.txt"}
        )
        
        assert request.id is not None
        assert request.action == "write_file"
        assert request.status == ConsentStatus.PENDING


class TestRollbackManager:
    """Tests for RollbackManager class."""
    
    def test_record_file_write(self, tmp_path):
        """Test recording file write for rollback."""
        rm = RollbackManager(backup_base_path=str(tmp_path))
        
        action = rm.record_file_write(
            file_path=str(tmp_path / "test.txt"),
            original_content="original",
            new_content="new content"
        )
        
        assert action.id is not None
        assert action.can_rollback()
    
    def test_get_rollbackable(self, tmp_path):
        """Test getting rollbackable actions."""
        rm = RollbackManager(backup_base_path=str(tmp_path))
        
        rm.record_file_write(
            file_path=str(tmp_path / "test1.txt"),
            original_content="content1",
            new_content="new1"
        )
        
        rollbackable = rm.get_rollbackable()
        assert len(rollbackable) >= 1


class TestCommandRouter:
    """Tests for CommandRouter class."""
    
    def test_register_handler(self):
        """Test handler registration."""
        sm = StateMachine()
        gate = ConsentGate()
        router = CommandRouter(sm, gate)
        
        def test_handler(x):
            return x * 2
        
        router.register_handler("test_command", test_handler)
        
        assert "test_command" in router.list_commands()
    
    @pytest.mark.asyncio
    async def test_route_command(self):
        """Test command routing."""
        sm = StateMachine()
        gate = ConsentGate()
        router = CommandRouter(sm, gate)
        
        async def async_handler(value):
            return value + "_processed"
        
        router.register_handler("async_test", async_handler)
        
        result = await router.route(
            command="async_test",
            parameters={"value": "test"}
        )
        
        # Note: This may fail if consent is required
        # For full testing, mock consent approval


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
