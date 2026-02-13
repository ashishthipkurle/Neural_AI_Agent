from pathlib import Path
from typing import Dict, Any, List

try:
    import yaml
except ImportError:
    yaml = None


def _exists(path: str) -> bool:
    return Path(path).exists()


def _status(has_required: bool, has_optional: bool = False) -> str:
    if has_required and has_optional:
        return "implemented"
    if has_required:
        return "partial"
    return "missing"


def build_conformance_report(config_path: str = "agent/config/settings.yaml") -> Dict[str, Any]:
    """Build a lightweight architecture coverage report.

    Status values:
    - implemented: core + hardening signals found
    - partial: core found but hardening/integration incomplete
    - missing: core not found
    """
    checks: List[Dict[str, Any]] = []

    checks.append({
        "area": "skills_framework",
        "status": _status(
            _exists("agent/skills/base_skill.py") and _exists("agent/skills/skill_router.py"),
            _exists("agent/skills/skill_loader.py")
        ),
        "required": ["agent/skills/base_skill.py", "agent/skills/skill_router.py"],
        "optional": ["agent/skills/skill_loader.py"]
    })

    checks.append({
        "area": "mission_planning",
        "status": _status(
            _exists("agent/skills/mission/skill.py") and _exists("agent/skills/planning/skill.py"),
            _exists("agent/skills/browser/skill.py")
        ),
        "required": ["agent/skills/mission/skill.py", "agent/skills/planning/skill.py"],
        "optional": ["agent/skills/browser/skill.py"]
    })

    checks.append({
        "area": "safety_orchestration",
        "status": _status(
            _exists("agent/core/orchestrator/consent_gate.py") and _exists("agent/core/orchestrator/state_machine.py"),
            _exists("agent/core/orchestrator/rollback.py") and _exists("agent/security/audit_log.py")
        ),
        "required": ["agent/core/orchestrator/consent_gate.py", "agent/core/orchestrator/state_machine.py"],
        "optional": ["agent/core/orchestrator/rollback.py", "agent/security/audit_log.py"]
    })

    checks.append({
        "area": "task_lifecycle",
        "status": _status(
            _exists("agent/core/task_manager.py") or _exists("agent/tasks/manager.py"),
            _exists("agent/tasks/executor.py") and _exists("agent/tasks/scheduler.py")
        ),
        "required": ["agent/core/task_manager.py"],
        "optional": ["agent/tasks/executor.py", "agent/tasks/scheduler.py"]
    })

    checks.append({
        "area": "memory_rag",
        "status": _status(
            _exists("agent/memory/vector_store.py") and _exists("agent/memory/personal_memory.py"),
            _exists("agent/memory/history_manager.py")
        ),
        "required": ["agent/memory/vector_store.py", "agent/memory/personal_memory.py"],
        "optional": ["agent/memory/history_manager.py"]
    })

    checks.append({
        "area": "voice_vision",
        "status": _status(
            _exists("agent/voice") and _exists("agent/vision"),
            _exists("agent/skills/voice/skill.py") and _exists("agent/skills/vision/skill.py")
        ),
        "required": ["agent/voice", "agent/vision"],
        "optional": ["agent/skills/voice/skill.py", "agent/skills/vision/skill.py"]
    })

    checks.append({
        "area": "integrations_workflows",
        "status": _status(
            _exists("agent/skills/integrations/skill.py") and _exists("agent/skills/workflows/skill.py"),
            _exists("agent/skills/telegram/skill.py")
        ),
        "required": ["agent/skills/integrations/skill.py", "agent/skills/workflows/skill.py"],
        "optional": ["agent/skills/telegram/skill.py"]
    })

    checks.append({
        "area": "multi_agent",
        "status": _status(
            _exists("agent/core/multi_agent.py"),
            _exists("agent/core/learning_orchestrator.py")
        ),
        "required": ["agent/core/multi_agent.py"],
        "optional": ["agent/core/learning_orchestrator.py"]
    })

    config = {}
    config_loaded = False
    auto_approval = True
    try:
        settings_text = Path(config_path).read_text(encoding="utf-8")
        if yaml is not None:
            config = yaml.safe_load(settings_text) or {}
            auto_approval = bool(config.get("security", {}).get("auto_approval", True))
            config_loaded = True
        else:
            normalized = settings_text.replace(" ", "").lower()
            if "auto_approval:false" in normalized:
                auto_approval = False
            config_loaded = True
    except Exception:
        config_loaded = False
    strict_policy = not auto_approval

    checks.append({
        "area": "strict_consent_default",
        "status": "implemented" if strict_policy and config_loaded else "partial",
        "required": ["agent/config/settings.yaml (security.auto_approval=false)"],
        "optional": []
    })

    counts = {
        "implemented": sum(1 for c in checks if c["status"] == "implemented"),
        "partial": sum(1 for c in checks if c["status"] == "partial"),
        "missing": sum(1 for c in checks if c["status"] == "missing")
    }

    overall = "implemented"
    if counts["missing"] > 0:
        overall = "partial"
    elif counts["partial"] > 0:
        overall = "partial"

    return {
        "overall": overall,
        "counts": counts,
        "checks": checks
    }
