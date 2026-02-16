from typing import Any, Dict

from agent.core.conformance_checker import ConformanceChecker


def build_conformance_report(config_path: str = "agent/config/settings.yaml") -> Dict[str, Any]:
    checker = ConformanceChecker(".")
    return checker.report()
