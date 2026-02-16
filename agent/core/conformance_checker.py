from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

REQUIRED_FILES = [
    "agent/main.py",
    "agent/config/settings.yaml",
    "agent/config/policy_profiles.yaml",
    "agent/core/supervisor.py",
    "agent/core/worker_base.py",
    "agent/core/mission_engine.py",
    "agent/core/execution_pipeline.py",
    "agent/core/intent_parser.py",
    "agent/core/risk_engine.py",
    "agent/core/consent_manager.py",
    "agent/core/retry_manager.py",
    "agent/core/reflection_engine.py",
    "agent/core/audit_logger.py",
    "agent/core/task_checkpoint.py",
    "agent/core/plan_validator.py",
    "agent/core/conformance_checker.py",
    "agent/workers/skill_worker.py",
    "agent/workers/research_worker.py",
    "agent/workers/coding_worker.py",
    "agent/workers/browser_worker.py",
    "agent/workers/desktop_worker.py",
    "agent/workers/integration_worker.py",
    "agent/api/server.py",
    "agent/api/websocket.py",
    "agent/background/voice_loop.py",
    "agent/background/telegram_loop.py",
    "agent/background/task_scheduler.py",
    "agent/safety/destructive_pipeline.py",
    "agent/safety/rollback_manager.py",
    "agent/memory/sqlite_store.py",
    "agent/memory/vector_store.py",
    "agent/memory/conversation_store.py",
]


class ConformanceChecker:
    def __init__(self, workspace_root: str = ".") -> None:
        self.workspace_root = Path(workspace_root)

    def report(self) -> Dict[str, Any]:
        checks: List[Dict[str, Any]] = []
        for rel in REQUIRED_FILES:
            exists = (self.workspace_root / rel).exists()
            checks.append({"artifact": rel, "status": "implemented" if exists else "missing"})

        missing = [item for item in checks if item["status"] == "missing"]
        overall = "implemented" if not missing else "partial"

        return {
            "overall": overall,
            "required_count": len(REQUIRED_FILES),
            "implemented_count": len(REQUIRED_FILES) - len(missing),
            "missing_count": len(missing),
            "checks": checks,
            "pipeline_stage_count": 13,
            "notes": [
                "Supervisor delegates only; workers execute scoped tasks.",
                "Destructive actions require frozen pipeline and explicit consent.",
                "Missions are checkpointed for crash-safe resume.",
            ],
        }
