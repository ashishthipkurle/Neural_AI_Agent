from agent.core.models import PlanStep, RiskLevel, WorkerType
from agent.core.plan_validator import PlanValidator
from agent.core.supervisor import Supervisor


def test_supervisor_rejects_critical_review():
    supervisor = Supervisor(PlanValidator())
    steps = [
        PlanStep(
            step_id="s1",
            title="Do work",
            worker_type=WorkerType.SKILL,
            action="run_skill",
            params={},
            acceptance_criteria=["always_true"],
        )
    ]
    assert supervisor.review("m1", RiskLevel.CRITICAL, steps) is False
    assert supervisor.review("m1", RiskLevel.LOW, steps) is True
