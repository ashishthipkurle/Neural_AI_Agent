"""
Clowbot-Class Frozen Execution Pipeline.

8-stage pipeline with each stage as a distinct, testable component:

    Input
    → IntentParser
    → Policy / Consent Gate
    → Planner (Supervisor)
    → Orchestrator
    → Skill Execution
    → Verification
    → Audit Logger
    → UI / Voice Output

NO STAGE MAY BE MERGED, SKIPPED, OR BYPASSED.

This module is ADDITIVE — it does not replace NeuralAgent.process_input().
It wraps existing components into explicit pipeline stages.
"""

import logging
import hashlib
import time
import uuid
import json
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime


logger = logging.getLogger("Pipeline")


class PipelineStage(Enum):
    """The 8 mandatory pipeline stages."""
    INPUT = "input"
    INTENT_PARSER = "intent_parser"
    POLICY_CONSENT_GATE = "policy_consent_gate"
    PLANNER_SUPERVISOR = "planner_supervisor"
    ORCHESTRATOR = "orchestrator"
    SKILL_EXECUTION = "skill_execution"
    VERIFICATION = "verification"
    AUDIT_LOGGER = "audit_logger"
    UI_VOICE_OUTPUT = "ui_voice_output"


@dataclass
class PipelineContext:
    """Context passed through all pipeline stages."""
    # Identifiers
    pipeline_id: str = ""
    user_id: str = "local_user"
    session_id: str = ""
    
    # Input
    raw_input: str = ""
    source: str = "local"
    image_data: Optional[str] = None
    
    # Intent parsing output
    intents: List[Dict[str, Any]] = field(default_factory=list)
    intent_hash: str = ""
    
    # Consent
    consent_level: int = 0
    consent_token: Optional[str] = None
    consent_approved: bool = True
    
    # Planning
    plan: List[Dict[str, Any]] = field(default_factory=list)
    plan_confidence: float = 0.0
    
    # Execution
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Verification
    verified: bool = False
    verification_notes: List[str] = field(default_factory=list)
    
    # Assumptions & confidence
    assumptions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    uncertainty: List[str] = field(default_factory=list)
    
    # Output
    response: str = ""
    result_hash: str = ""
    
    # Timing
    stage_timings: Dict[str, float] = field(default_factory=dict)
    total_duration: float = 0.0
    
    # Error tracking
    errors: List[str] = field(default_factory=list)
    current_stage: str = ""
    
    # Logs
    logs: List[str] = field(default_factory=list)


class PipelineStageBase:
    """Base class for all pipeline stages."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Pipeline.{name}")
    
    async def __call__(self, ctx: PipelineContext) -> PipelineContext:
        """Execute this pipeline stage."""
        ctx.current_stage = self.name
        ctx.logs.append(f"[{self.name}] Stage entered")
        start = time.time()
        
        try:
            ctx = await self.process(ctx)
            ctx.logs.append(f"[{self.name}] Stage completed")
        except Exception as e:
            ctx.errors.append(f"[{self.name}] {e}")
            ctx.logs.append(f"[{self.name}] Stage FAILED: {e}")
            self.logger.error(f"Stage {self.name} failed: {e}")
        
        ctx.stage_timings[self.name] = time.time() - start
        return ctx
    
    async def process(self, ctx: PipelineContext) -> PipelineContext:
        """Override in subclass."""
        raise NotImplementedError


# ==================== STAGE 1: INPUT ====================

class InputStage(PipelineStageBase):
    """Stage 1: Input normalization and fingerprinting."""
    
    def __init__(self):
        super().__init__(PipelineStage.INPUT.value)
    
    async def process(self, ctx: PipelineContext) -> PipelineContext:
        ctx.pipeline_id = str(uuid.uuid4())
        ctx.session_id = ctx.session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate intent hash for audit trail
        ctx.intent_hash = hashlib.sha256(
            ctx.raw_input.encode('utf-8')
        ).hexdigest()[:16]
        
        ctx.logs.append(f"Input fingerprinted: hash={ctx.intent_hash}")
        return ctx


# ==================== STAGE 2: INTENT PARSER ====================

class IntentParserStage(PipelineStageBase):
    """Stage 2: Parse raw input into structured intents."""
    
    def __init__(self, intent_parser=None):
        super().__init__(PipelineStage.INTENT_PARSER.value)
        self._parser = intent_parser
    
    async def process(self, ctx: PipelineContext) -> PipelineContext:
        if not self._parser:
            ctx.assumptions.append("No IntentParser available, passing raw input")
            ctx.intents = [{"action": "chat", "parameters": {"message": ctx.raw_input}, "confidence": 0.5}]
            return ctx
        
        parsed = self._parser.parse(ctx.raw_input)
        ctx.intents = [
            {
                "action": intent.action,
                "tool_name": intent.tool_name,
                "parameters": intent.parameters,
                "confidence": intent.confidence,
                "reasoning": intent.reasoning
            }
            for intent in parsed
        ]
        
        # Aggregate confidence
        if ctx.intents:
            ctx.confidence = sum(i.get("confidence", 0) for i in ctx.intents) / len(ctx.intents)
        
        ctx.logs.append(f"Parsed {len(ctx.intents)} intents, avg confidence={ctx.confidence:.2f}")
        return ctx


# ==================== STAGE 3: POLICY / CONSENT GATE ====================

class PolicyConsentGateStage(PipelineStageBase):
    """Stage 3: Check consent requirements for all planned actions."""
    
    def __init__(self, consent_gate=None, safety_framework=None):
        super().__init__(PipelineStage.POLICY_CONSENT_GATE.value)
        self._consent_gate = consent_gate
        self._safety_framework = safety_framework
    
    async def process(self, ctx: PipelineContext) -> PipelineContext:
        if not self._consent_gate:
            ctx.consent_approved = True
            ctx.consent_level = 0
            ctx.assumptions.append("No ConsentGate configured, auto-approving")
            return ctx
        
        # Check each intent against consent gate
        max_consent_level = 0
        for intent in ctx.intents:
            action = intent.get("action", "")
            level = self._consent_gate.determine_consent_level(action)
            max_consent_level = max(max_consent_level, level.value)
        
        ctx.consent_level = max_consent_level
        
        if max_consent_level == 0:
            ctx.consent_approved = True
            ctx.consent_token = f"auto_{ctx.pipeline_id[:8]}"
        else:
            # For non-zero consent, create a consent request
            request = self._consent_gate.create_request(
                action=ctx.intents[0].get("action", "unknown") if ctx.intents else "unknown",
                parameters=ctx.intents[0].get("parameters", {}) if ctx.intents else {}
            )
            result = await self._consent_gate.request_consent(request)
            ctx.consent_approved = result.approved
            ctx.consent_token = request.id
            
            if not result.approved:
                ctx.logs.append(f"Consent DENIED for level {max_consent_level}")
                ctx.response = "Action requires consent which was not granted."
                return ctx
        
        ctx.logs.append(f"Consent level={max_consent_level}, approved={ctx.consent_approved}")
        return ctx


# ==================== STAGE 4: PLANNER (SUPERVISOR) ====================

class PlannerSupervisorStage(PipelineStageBase):
    """Stage 4: Plan the execution sequence from intents."""
    
    def __init__(self):
        super().__init__(PipelineStage.PLANNER_SUPERVISOR.value)
    
    async def process(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.consent_approved:
            ctx.logs.append("Skipping planning — consent not approved")
            return ctx
        
        # Convert intents to plan steps
        ctx.plan = []
        for i, intent in enumerate(ctx.intents):
            step = {
                "step_id": i,
                "action": intent.get("action", ""),
                "tool_name": intent.get("tool_name", ""),
                "parameters": intent.get("parameters", {}),
                "confidence": intent.get("confidence", 0.0),
                "assumptions": [intent.get("reasoning", "No reasoning provided")],
                "status": "pending"
            }
            ctx.plan.append(step)
        
        ctx.plan_confidence = ctx.confidence
        ctx.logs.append(f"Plan created with {len(ctx.plan)} steps, confidence={ctx.plan_confidence:.2f}")
        return ctx


# ==================== STAGE 5: ORCHESTRATOR ====================

class OrchestratorStage(PipelineStageBase):
    """Stage 5: Coordinate execution of the plan through skill/tool router."""
    
    def __init__(self, executor: Optional[Callable] = None):
        super().__init__(PipelineStage.ORCHESTRATOR.value)
        self._executor = executor
    
    async def process(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.consent_approved:
            return ctx
        
        ctx.logs.append("Orchestrator coordinating plan execution")
        # The actual execution happens in SkillExecutionStage
        # Orchestrator just validates and orders the plan
        
        for step in ctx.plan:
            step["status"] = "ready"
        
        return ctx


# ==================== STAGE 6: SKILL EXECUTION ====================

class SkillExecutionStage(PipelineStageBase):
    """Stage 6: Execute each planned step through the skill/tool system."""
    
    def __init__(self, skill_router=None, command_router=None, tool_router=None):
        super().__init__(PipelineStage.SKILL_EXECUTION.value)
        self._skill_router = skill_router
        self._command_router = command_router
        self._tool_router = tool_router
    
    async def process(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.consent_approved:
            return ctx
        
        for step in ctx.plan:
            # Prioritize tool_name (concrete implementation) over action (intent)
            # This fixes cases where action='chat' but tool='chat_tool'
            action = step.get("tool_name") or step.get("action", "")
            params = step.get("parameters", {})
            
            start = time.time()
            try:
                result = await self._execute_step(action, params, ctx)
                step["status"] = "completed"
                step["result"] = result
                step["duration"] = time.time() - start
                
                ctx.execution_results.append({
                    "step_id": step["step_id"],
                    "action": action,
                    "success": result.get("success", True),
                    "result": result,
                    "duration": step["duration"],
                    "confidence": step.get("confidence", 0.0)
                })
                
            except Exception as e:
                step["status"] = "failed"
                step["error"] = str(e)
                step["duration"] = time.time() - start
                ctx.errors.append(f"Step {step['step_id']} ({action}): {e}")
                
                ctx.execution_results.append({
                    "step_id": step["step_id"],
                    "action": action,
                    "success": False,
                    "error": str(e),
                    "duration": step["duration"],
                    "confidence": 0.0
                })
        
        ctx.logs.append(f"Executed {len(ctx.execution_results)} steps")
        return ctx
    
    async def _execute_step(self, action: str, params: dict, ctx: PipelineContext) -> dict:
        """Execute a single step through available routers."""
        # Normalize action aliases
        ACTION_ALIASES = {
            "chat": "chat_tool",
            "navigate": "browser_navigate",
            "browse": "browser_navigate",
            "go_to": "browser_navigate",
        }
        action = ACTION_ALIASES.get(action, action)
        
        # Try skill router first
        if self._skill_router:
            skill = self._skill_router.skill_loader.get_skill_for_intent(action)
            if skill:
                result = await self._skill_router.route_intent(action, params)
                return {
                    "success": result.success,
                    "message": result.result.message if result.result else "",
                    "data": result.result.data if result.result else None,
                    "skill": result.skill_name
                }
        
        # Try command router
        if self._command_router:
            handler = self._command_router.get_handler(action) if hasattr(self._command_router, 'get_handler') else None
            if handler:
                result = await self._command_router.route(action, params)
                return {
                    "success": result.success,
                    "message": str(result.result) if result.success else result.error,
                    "data": result.result
                }
        
        # Try tool router
        if self._tool_router:
            handler = self._tool_router.tools.get(action)
            if handler:
                import asyncio
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(**params)
                else:
                    result = handler(**params)
                return {"success": True, "message": str(result), "data": result}
        
        return {"success": False, "message": f"No handler found for action: {action}"}


# ==================== STAGE 7: VERIFICATION ====================

class VerificationStage(PipelineStageBase):
    """Stage 7: Verify execution results for correctness."""
    
    def __init__(self):
        super().__init__(PipelineStage.VERIFICATION.value)
    
    async def process(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.execution_results:
            ctx.verified = True
            ctx.verification_notes.append("No results to verify")
            return ctx
        
        all_success = True
        for result in ctx.execution_results:
            if not result.get("success", False):
                all_success = False
                ctx.verification_notes.append(
                    f"Step {result['step_id']} ({result['action']}) FAILED: "
                    f"{result.get('error', 'unknown error')}"
                )
            else:
                ctx.verification_notes.append(
                    f"Step {result['step_id']} ({result['action']}) verified OK"
                )
        
        ctx.verified = all_success
        
        # Generate result hash for audit trail
        import json
        result_str = json.dumps(
            [r.get("result", {}) for r in ctx.execution_results],
            default=str, sort_keys=True
        )
        ctx.result_hash = hashlib.sha256(result_str.encode()).hexdigest()[:16]
        
        ctx.logs.append(
            f"Verification: {'PASSED' if all_success else 'FAILED'}, "
            f"result_hash={ctx.result_hash}"
        )
        return ctx


# ==================== STAGE 8: AUDIT LOGGER ====================

class AuditLoggerStage(PipelineStageBase):
    """Stage 8a: Write immutable audit record."""
    
    def __init__(self, audit_logger=None):
        super().__init__(PipelineStage.AUDIT_LOGGER.value)
        self._audit_logger = audit_logger
    
    async def process(self, ctx: PipelineContext) -> PipelineContext:
        if not self._audit_logger:
            ctx.assumptions.append("No AuditLogger configured, skipping audit")
            return ctx
        
        # Build the audit record with the frozen schema fields
        for result in ctx.execution_results:
            self._audit_logger.log(
                event_type="pipeline_execution",
                action=result.get("action", ""),
                description=f"Pipeline {ctx.pipeline_id} step {result.get('step_id', '?')}",
                parameters=result.get("result", {}),
                result=str(result.get("result", {}).get("message", "")),
                error=result.get("error"),
                user_initiated=True,
                source_module="pipeline",
                # Extended fields (if audit logger supports them)
                **self._build_extended_fields(ctx, result)
            )
        
        ctx.logs.append(f"Audit logged {len(ctx.execution_results)} entries")
        return ctx
    
    def _build_extended_fields(self, ctx: PipelineContext, result: dict) -> dict:
        """Build extended audit fields, returning empty dict if not supported."""
        # These will be consumed by the extended AuditLogger
        # If the logger doesn't support them, they'll be filtered by **kwargs
        return {}


# ==================== STAGE 8b: UI / VOICE OUTPUT ====================

class UIVoiceOutputStage(PipelineStageBase):
    """Stage 8b: Broadcast results to UI and voice systems."""
    
    def __init__(self, sync_broadcast=None, voice_manager=None):
        super().__init__(PipelineStage.UI_VOICE_OUTPUT.value)
        self._sync_broadcast = sync_broadcast
        self._voice_manager = voice_manager

    def _humanize_response(self, response: str) -> str:
        text = (response or "").strip()
        if not text:
            return "Done."

        if text.startswith("[") or text.startswith("{"):
            try:
                payload = json.loads(text)
            except Exception:
                return text

            if isinstance(payload, list) and payload:
                first = payload[0] if isinstance(payload[0], dict) else None
                if first and first.get("source") == "DowntimeVerifier":
                    attempts = first.get("verification_attempts")
                    down_count = first.get("down_observed_count")
                    link = first.get("link") or first.get("url") or "the target website"
                    consistent = first.get("is_consistently_down")
                    if consistent:
                        return f"Verified {link} is down across {down_count}/{attempts} checks."
                    return f"Verified {link} was down in {down_count}/{attempts} checks, so it is not consistently down."

                if first and first.get("source") == "Wikipedia":
                    title = first.get("title", "result")
                    snippet = (first.get("snippet") or "").strip().replace("\n", " ")
                    if len(snippet) > 320:
                        snippet = snippet[:320].rstrip() + "..."
                    return f"Top result from {title}: {snippet}" if snippet else f"Found a result from {title}."

        return text

    def _voice_friendly_text(self, response: str) -> str:
        text = self._humanize_response(response)
        if len(text) > 450:
            return text[:450].rstrip() + "..."
        return text
    
    async def process(self, ctx: PipelineContext) -> PipelineContext:
        # Compile response from execution results
        if not ctx.response:
            messages = []
            for result in ctx.execution_results:
                msg = result.get("result", {}).get("message", "")
                if msg:
                    messages.append(msg)
            ctx.response = " ".join(messages) if messages else "Done."

        ctx.response = self._humanize_response(ctx.response)
        
        # Broadcast to UI
        if self._sync_broadcast and ctx.source == "local":
            self._sync_broadcast("assistant", "assistant", ctx.response, ctx.pipeline_id)

        # Signal completion to UI ASAP (prevents long TTS from blocking "Processing..." clear)
        if self._sync_broadcast and ctx.source == "local":
            self._sync_broadcast("status", "system", "Done", ctx.pipeline_id)
        
        # Speak
        if self._voice_manager and ctx.source == "local":
            try:
                await self._voice_manager.speak(self._voice_friendly_text(ctx.response), suppress_sync=True)
            except Exception as e:
                ctx.logs.append(f"Voice output failed: {e}")
        
        ctx.logs.append("Output delivered")
        return ctx


# ==================== PIPELINE EXECUTOR ====================

class ClowbotPipeline:
    """
    The Clowbot-class 8-stage execution pipeline.
    
    All stages execute in strict order. No stage may be skipped.
    Each stage is independently testable.
    """
    
    def __init__(
        self,
        intent_parser=None,
        consent_gate=None,
        safety_framework=None,
        skill_router=None,
        command_router=None,
        tool_router=None,
        audit_logger=None,
        sync_broadcast=None,
        voice_manager=None
    ):
        self.logger = logging.getLogger("ClowbotPipeline")
        
        # Build the 8-stage pipeline
        self.stages: List[PipelineStageBase] = [
            InputStage(),
            IntentParserStage(intent_parser),
            PolicyConsentGateStage(consent_gate, safety_framework),
            PlannerSupervisorStage(),
            OrchestratorStage(),
            SkillExecutionStage(skill_router, command_router, tool_router),
            VerificationStage(),
            AuditLoggerStage(audit_logger),
            UIVoiceOutputStage(sync_broadcast, voice_manager),
        ]
        
        self.logger.info(f"ClowbotPipeline initialized with {len(self.stages)} stages")
    
    async def execute(
        self,
        user_input: str,
        source: str = "local",
        image_data: Optional[str] = None,
        user_id: str = "local_user"
    ) -> PipelineContext:
        """
        Execute the full 8-stage pipeline.
        
        Args:
            user_input: Raw user input text.
            source: Input source ("local", "telegram", "api").
            image_data: Optional image data.
            user_id: User identifier.
        
        Returns:
            PipelineContext with all results, logs, and audit data.
        """
        ctx = PipelineContext(
            raw_input=user_input,
            source=source,
            image_data=image_data,
            user_id=user_id
        )
        
        pipeline_start = time.time()
        self.logger.info(f"Pipeline started for: '{user_input[:50]}...'")
        
        for stage in self.stages:
            ctx = await stage(ctx)
            
            # If consent was denied, stop after consent gate
            if stage.name == PipelineStage.POLICY_CONSENT_GATE.value and not ctx.consent_approved:
                self.logger.warning("Pipeline halted: consent denied")
                break
        
        ctx.total_duration = time.time() - pipeline_start
        self.logger.info(
            f"Pipeline completed in {ctx.total_duration:.3f}s, "
            f"verified={ctx.verified}, errors={len(ctx.errors)}"
        )
        
        return ctx
    
    def get_stage_names(self) -> List[str]:
        """Return list of all pipeline stage names."""
        return [stage.name for stage in self.stages]
