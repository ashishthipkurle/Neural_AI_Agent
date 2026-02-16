from __future__ import annotations

from typing import Any, Dict

from agent.core.audit_logger import AuditLogger
from agent.core.consent_manager import ConsentManager, ConsentPolicy
from agent.core.execution_pipeline import ExecutionPipeline
from agent.core.intent_parser import IntentParser
from agent.core.mission_engine import MissionEngine
from agent.core.models import WorkerType
from agent.core.plan_validator import PlanValidator
from agent.core.reflection_engine import ReflectionEngine
from agent.core.retry_manager import RetryManager
from agent.core.risk_engine import RiskEngine
from agent.core.supervisor import Supervisor
from agent.core.task_checkpoint import TaskCheckpointStore
from agent.memory.vector_store import VectorStore
from agent.workers.browser_worker import BrowserWorker
from agent.workers.coding_worker import CodingWorker
from agent.workers.desktop_worker import DesktopWorker
from agent.workers.integration_worker import IntegrationWorker
from agent.workers.research_worker import ResearchWorker
from agent.workers.skill_worker import SkillExecutionWorker


class AutonomousRuntime:
    def __init__(self) -> None:
        checkpoint_store = TaskCheckpointStore("agent_data/missions.db")
        mission_engine = MissionEngine(checkpoint_store)
        plan_validator = PlanValidator()
        supervisor = Supervisor(plan_validator)
        consent_manager = ConsentManager(
            ConsentPolicy(
                profile_name="strict",
                require_for_medium=True,
                require_for_high=True,
                require_for_critical=True,
            )
        )

        workers = {
            WorkerType.SKILL: SkillExecutionWorker(),
            WorkerType.RESEARCH: ResearchWorker(),
            WorkerType.CODING: CodingWorker(),
            WorkerType.BROWSER: BrowserWorker(),
            WorkerType.DESKTOP: DesktopWorker(),
            WorkerType.INTEGRATION: IntegrationWorker(),
        }

        self._vector_store = VectorStore()

        def _memory_context_provider(goal: str) -> list[dict]:
            if self._vector_store is None:
                return []
            try:
                results = self._vector_store.search(goal, k=3)
                return results if isinstance(results, list) else []
            except Exception:
                return []

        self.pipeline = ExecutionPipeline(
            mission_engine=mission_engine,
            supervisor=supervisor,
            intent_parser=IntentParser(),
            risk_engine=RiskEngine(),
            consent_manager=consent_manager,
            retry_manager=RetryManager(),
            reflection_engine=ReflectionEngine(),
            audit_logger=AuditLogger("agent_data/audit.db"),
            workers=workers,
            plan_validator=plan_validator,
            memory_context_provider=_memory_context_provider,
        )
        self.mission_engine = mission_engine

    async def run_goal(self, goal: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        return await self.pipeline.run(goal, metadata)

    def list_running_missions(self) -> list[dict[str, Any]]:
        return self.mission_engine.running_missions()


RUNTIME = AutonomousRuntime()
