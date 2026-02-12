"""
Unit tests for the Destructive Action Handler.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from agent.security.destructive_action_handler import (
    DestructiveActionHandler, DestructiveActionRequest, DestructiveActionPhase
)

@pytest.fixture
def mock_deps():
    gate = MagicMock()
    gate.request_consent = AsyncMock()
    gate.create_request = MagicMock()
    
    return {
        "consent_gate": gate,
        "rollback_manager": MagicMock(),
        "audit_logger": MagicMock()
    }

@pytest.fixture
def handler(mock_deps):
    return DestructiveActionHandler(**mock_deps)

def test_risk_classification(handler):
    """Test risk classification logic."""
    assert handler._classify_risk("format_disk", {}) == "CRITICAL"
    assert handler._classify_risk("delete_file", {}) == "HIGH"
    assert handler._classify_risk("write_file", {}) == "MEDIUM"
    assert handler._classify_risk("read_file", {}) == "LOW"

def test_full_destructive_flow_success(handler, mock_deps):
    """Test successful execution of the 7-phase flow."""
    async def _test():
        # Setup
        executor = AsyncMock(return_value="Success")
        mock_deps["consent_gate"].create_request.return_value = MagicMock(id="req_1")
        
        # Mock consent result
        consent_res = MagicMock()
        consent_res.approved = True
        consent_res.confirmation_method = "dual"
        mock_deps["consent_gate"].request_consent.return_value = consent_res
        
        # Mock rollback/snapshot
        mock_deps["rollback_manager"].record_file_write.return_value = MagicMock(id="snap_1")
        
        # Execute
        request = await handler.handle(
            action="delete_file",
            parameters={"path": "test.txt"},
            executor=executor,
            user_id="tester"
        )
        
        # Verify Phases
        print(f"DEBUG: success flow phases={request.phases_completed}")
        assert DestructiveActionPhase.MARK.value in request.phases_completed
        assert DestructiveActionPhase.DRY_RUN.value in request.phases_completed
        assert DestructiveActionPhase.CONFIRMATION.value in request.phases_completed
        assert DestructiveActionPhase.SNAPSHOT.value in request.phases_completed
        assert DestructiveActionPhase.EXECUTE.value in request.phases_completed
        assert DestructiveActionPhase.VERIFY.value in request.phases_completed
        assert DestructiveActionPhase.AUDIT.value in request.phases_completed
        
        assert request.execution_result["success"] is True
        assert request.audit_entry_id is not None
        
        # Check calls
        handler.audit_logger.log.assert_called_once()
        executor.assert_called_once()
    
    asyncio.run(_test())

def test_destructive_flow_denied(handler, mock_deps):
    """Test flow aborts on consent denial."""
    async def _test():
        # Setup
        executor = AsyncMock()
        
        # Mock consent denial
        consent_res = MagicMock(approved=False, denial_reason="User said no")
        mock_deps["consent_gate"].request_consent.return_value = consent_res
        
        # Execute
        request = await handler.handle(
            action="delete_file",
            parameters={"path": "test.txt"},
            executor=executor
        )
        
        # Verify Abort
        print(f"DEBUG: denied flow aborted={request.aborted}, phases={request.phases_completed}")
        assert request.aborted is True
        assert DestructiveActionPhase.CONFIRMATION.value in request.phases_completed
        # Should NOT have executed or audited
        assert DestructiveActionPhase.EXECUTE.value not in request.phases_completed
        assert DestructiveActionPhase.AUDIT.value not in request.phases_completed
        
        executor.assert_not_called()
    
    asyncio.run(_test())

def test_rollback_on_failure(handler, mock_deps):
    """Test rollback is triggered if execution fails."""
    async def _test():
        # Setup
        executor = AsyncMock(side_effect=Exception("Disk error"))
        
        # Needs consent to proceed to execution
        consent_res = MagicMock()
        consent_res.approved = True
        consent_res.confirmation_method = "voice"
        mock_deps["consent_gate"].request_consent.return_value = consent_res
        
        mock_deps["rollback_manager"].record_file_write.return_value = MagicMock(id="snap_1")
        
        # Execute with OS patch
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()): 
                request = await handler.handle(
                    action="overwrite_file",
                    parameters={"path": "important.txt"},
                    executor=executor
                )
        
        # Verify Failure handling
        print(f"DEBUG: rollback flow aborted={request.aborted}, reason={request.abort_reason}")
        print(f"DEBUG: rollback_manager calls: {mock_deps['rollback_manager'].rollback_last.call_args_list}")
        
        assert request.aborted is True
        assert "Execution failed" in request.abort_reason
        
        # Ensure rollback called
        mock_deps["rollback_manager"].rollback_last.assert_called_once()
    
    asyncio.run(_test())
