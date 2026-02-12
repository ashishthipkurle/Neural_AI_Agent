"""
Unit tests for the Clowbot-class 8-stage pipeline.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from agent.core.pipeline import (
    ClowbotPipeline, PipelineContext, PipelineStage,
    InputStage, IntentParserStage, PolicyConsentGateStage,
    PlannerSupervisorStage, OrchestratorStage, SkillExecutionStage,
    VerificationStage, AuditLoggerStage, UIVoiceOutputStage
)
from agent.core.orchestrator.consent_gate import ConsentLevel, ConsentResult, ConsentGate

@pytest.fixture
def mock_dependencies():
    gate = MagicMock()
    gate.request_consent = AsyncMock()
    gate.create_request = MagicMock()
    gate.determine_consent_level = MagicMock()
    
    return {
        "intent_parser": MagicMock(),
        "consent_gate": gate,
        "safety_framework": MagicMock(),
        "skill_router": AsyncMock(),
        "command_router": AsyncMock(),
        "tool_router": MagicMock(),
        "audit_logger": MagicMock(),
        "sync_broadcast": MagicMock(),
        "voice_manager": AsyncMock()
    }

@pytest.fixture
def pipeline(mock_dependencies):
    return ClowbotPipeline(**mock_dependencies)

def test_pipeline_initialization(pipeline):
    """Test that all 8 stages are initialized."""
    async def _test():
        assert len(pipeline.stages) == 9 # 8 stages + Input is stage 1
        stage_names = pipeline.get_stage_names()
        expected = [
            "input", "intent_parser", "policy_consent_gate", 
            "planner_supervisor", "orchestrator", "skill_execution", 
            "verification", "audit_logger", "ui_voice_output"
        ]
        assert stage_names == expected
    asyncio.run(_test())

def test_input_stage():
    """Test input stage fingerprinting."""
    async def _test():
        stage = InputStage()
        ctx = PipelineContext(raw_input="test input")
        ctx = await stage(ctx)
        
        assert ctx.pipeline_id is not None
        assert ctx.intent_hash is not None
        assert ctx.current_stage == "input"
    asyncio.run(_test())

def test_intent_parser_stage(mock_dependencies):
    """Test intent parsing."""
    async def _test():
        parser = mock_dependencies["intent_parser"]
        intent_mock = MagicMock()
        intent_mock.action = "test_action"
        intent_mock.parameters = {"p": 1}
        intent_mock.confidence = 0.9
        parser.parse.return_value = [intent_mock]
        
        stage = IntentParserStage(parser)
        ctx = PipelineContext(raw_input="test")
        ctx = await stage(ctx)
        
        assert len(ctx.intents) == 1
        assert ctx.intents[0]["action"] == "test_action"
        assert ctx.confidence == 0.9
    asyncio.run(_test())

def test_policy_consent_gate_approved(mock_dependencies):
    """Test consent gate approval."""
    async def _test():
        gate = mock_dependencies["consent_gate"]
        gate.determine_consent_level.return_value = ConsentLevel.SINGLE
        gate.create_request.return_value = MagicMock(id="req_123")
        gate.request_consent.return_value = ConsentResult(
            request_id="req_123", approved=True, confirmation_method="voice",
            timestamp="now"
        )
        
        stage = PolicyConsentGateStage(gate)
        ctx = PipelineContext(
            intents=[{"action": "delete_file", "parameters": {}}]
        )
        ctx = await stage(ctx)
        
        assert ctx.consent_approved is True
        assert ctx.consent_token == "req_123"
    asyncio.run(_test())

def test_policy_consent_gate_denied(mock_dependencies):
    """Test consent gate denial halts pipeline."""
    async def _test():
        gate = mock_dependencies["consent_gate"]
        gate.determine_consent_level.return_value = ConsentLevel.CRITICAL
        gate.create_request.return_value = MagicMock(id="req_456")
        gate.request_consent.return_value = ConsentResult(
            request_id="req_456", approved=False, confirmation_method="denied",
            timestamp="now"
        )
        
        stage = PolicyConsentGateStage(gate)
        ctx = PipelineContext(
            intents=[{"action": "format_disk", "parameters": {}}]
        )
        ctx = await stage(ctx)
        
        assert ctx.consent_approved is False
        assert "Action requires consent which was not granted" in ctx.response
    asyncio.run(_test())

def test_planner_stage():
    """Test planner conversion."""
    async def _test():
        stage = PlannerSupervisorStage()
        ctx = PipelineContext(
            intents=[{"action": "act1"}, {"action": "act2"}],
            consent_approved=True
        )
        ctx = await stage(ctx)
        
        assert len(ctx.plan) == 2
        assert ctx.plan[0]["action"] == "act1"
        assert ctx.plan[1]["action"] == "act2"
    asyncio.run(_test())

def test_skill_execution_stage(mock_dependencies):
    """Test skill execution routing."""
    async def _test():
        router = mock_dependencies["skill_router"]
        router.skill_loader.get_skill_for_intent.return_value = MagicMock(name="test_skill")
        
        # Mock result
        result_mock = MagicMock()
        result_mock.success = True
        result_mock.result.message = "Done"
        result_mock.result.data = {}
        result_mock.skill_name = "test_skill"
        router.route_intent.return_value = result_mock
        
        stage = SkillExecutionStage(skill_router=router)
        ctx = PipelineContext(
            plan=[{"step_id": 0, "action": "test_action", "parameters": {}}],
            consent_approved=True
        )
        ctx = await stage(ctx)
        
        assert len(ctx.execution_results) == 1
        assert ctx.execution_results[0]["success"] is True
        assert ctx.execution_results[0]["action"] == "test_action"
    asyncio.run(_test())

def test_verification_stage():
    """Test verification logic."""
    async def _test():
        stage = VerificationStage()
        
        # Success case
        ctx = PipelineContext(
            execution_results=[{"step_id": 0, "success": True, "result": "ok", "action": "test_action"}]
        )
        ctx = await stage(ctx)
        print(f"DEBUG: verified={ctx.verified}, execution_results={ctx.execution_results}")
        print(f"DEBUG: verification_notes={ctx.verification_notes}")
        assert ctx.verified is True
        assert ctx.result_hash is not None
        
        # Failure case
        ctx_fail = PipelineContext(
            execution_results=[{"step_id": 0, "success": False, "error": "oops"}]
        )
        ctx_fail = await stage(ctx_fail)
        assert ctx_fail.verified is False
    asyncio.run(_test())

def test_audit_logger_stage(mock_dependencies):
    """Test audit logging."""
    async def _test():
        logger_mock = mock_dependencies["audit_logger"]
        stage = AuditLoggerStage(logger_mock)
        
        ctx = PipelineContext(
            pipeline_id="pid_1",
            execution_results=[{"step_id": 0, "action": "cmd", "result": {"message": "ok"}}]
        )
        await stage(ctx)
        
        logger_mock.log.assert_called_once()
        args = logger_mock.log.call_args[1]
        assert args["event_type"] == "pipeline_execution"
        assert args["action"] == "cmd"
    asyncio.run(_test())

def test_full_pipeline_execution(pipeline, mock_dependencies):
    """Test end-to-end pipeline execution flow."""
    async def _test():
        # Setup mocks for happy path
        parser = mock_dependencies["intent_parser"]
        intent_mock = MagicMock()
        intent_mock.action = "hello"
        intent_mock.parameters = {}
        intent_mock.confidence = 1.0
        parser.parse.return_value = [intent_mock]
        
        gate = mock_dependencies["consent_gate"]
        gate.determine_consent_level.return_value = ConsentLevel.NONE
        
        router = mock_dependencies["skill_router"]
        res = MagicMock()
        res.success = True
        res.result.message = "Hello there"
        router.route_intent.return_value = res
        router.skill_loader.get_skill_for_intent.return_value = MagicMock()
        
        # Execute
        ctx = await pipeline.execute("hello bot")
        
        assert ctx.total_duration > 0
        assert ctx.verified is True
        assert len(ctx.execution_results) == 1
        assert "Hello there" in ctx.response
    asyncio.run(_test())
