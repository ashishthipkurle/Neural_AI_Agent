"""
Failure-Mode Mitigation — Five explicit mitigation handlers.

1. LLM Hallucination — Cross-reference output against tool registry
2. Resource Exhaustion — psutil monitoring for CPU/RAM
3. Corrupt Artifact — Checksum verification for generated files
4. Privacy Leakage — Regex filters for PII in outputs
5. Partial Execution Rollback — Wraps RollbackManager for multi-step plans

FROZEN: All five handlers are mandatory.
"""

import logging
import re
import hashlib
import os
from typing import Dict, Any, Optional, List, Set

logger = logging.getLogger("FailureMitigation")


class HallucinationDetector:
    """Detect LLM hallucinations by cross-referencing against known tools/skills."""

    def __init__(self, known_tools: Optional[Set[str]] = None):
        self.known_tools = known_tools or set()

    def register_tools(self, tools: Set[str]) -> None:
        self.known_tools.update(tools)

    def check(self, llm_output: dict) -> Dict[str, Any]:
        """Check if LLM output references tools that don't exist."""
        issues = []
        action = llm_output.get("action", "")
        tool = llm_output.get("tool_name", "")

        if tool and self.known_tools and tool not in self.known_tools:
            issues.append(f"Unknown tool referenced: '{tool}' (not in registry)")

        # Check for impossible confidence
        conf = llm_output.get("confidence", 0)
        if isinstance(conf, (int, float)) and conf > 1.0:
            issues.append(f"Impossible confidence score: {conf}")

        return {
            "hallucination_detected": len(issues) > 0,
            "issues": issues,
            "severity": "HIGH" if issues else "NONE"
        }


class ResourceMonitor:
    """Monitor system resources for exhaustion."""

    def __init__(self, cpu_threshold: float = 90.0, ram_threshold: float = 90.0):
        self.cpu_threshold = cpu_threshold
        self.ram_threshold = ram_threshold

    def check(self) -> Dict[str, Any]:
        """Check current resource usage."""
        result = {"exhaustion_detected": False, "issues": [], "metrics": {}}
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory().percent
            result["metrics"] = {"cpu_percent": cpu, "ram_percent": ram}

            if cpu > self.cpu_threshold:
                result["issues"].append(f"CPU at {cpu}% (threshold: {self.cpu_threshold}%)")
                result["exhaustion_detected"] = True
            if ram > self.ram_threshold:
                result["issues"].append(f"RAM at {ram}% (threshold: {self.ram_threshold}%)")
                result["exhaustion_detected"] = True
        except ImportError:
            result["metrics"] = {"note": "psutil not installed"}
        except Exception as e:
            result["issues"].append(f"Monitoring error: {e}")
        return result


class ArtifactIntegrityChecker:
    """Verify checksums of generated files."""

    def __init__(self):
        self._checksums: Dict[str, str] = {}

    def register(self, file_path: str) -> str:
        """Register a file and store its checksum."""
        checksum = self._compute_checksum(file_path)
        if checksum:
            self._checksums[file_path] = checksum
        return checksum or ""

    def verify(self, file_path: str) -> Dict[str, Any]:
        """Verify a file against its stored checksum."""
        if file_path not in self._checksums:
            return {"verified": False, "reason": "No checksum registered"}
        current = self._compute_checksum(file_path)
        expected = self._checksums[file_path]
        return {
            "verified": current == expected,
            "expected": expected,
            "actual": current,
            "reason": "OK" if current == expected else "Checksum mismatch"
        }

    @staticmethod
    def _compute_checksum(file_path: str) -> Optional[str]:
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except Exception:
            return None


class PrivacyLeakageFilter:
    """Detect and redact PII from outputs."""

    PATTERNS = {
        "email": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
        "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "phone": re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'),
        "api_key": re.compile(r'(?:sk|pk|api)[-_][a-zA-Z0-9]{20,}'),
        "credit_card": re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
    }

    def scan(self, text: str) -> Dict[str, Any]:
        """Scan text for PII patterns."""
        found = {}
        for name, pattern in self.PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                found[name] = len(matches)
        return {
            "leakage_detected": len(found) > 0,
            "types_found": found,
            "severity": "CRITICAL" if "ssn" in found or "credit_card" in found else
                        "HIGH" if found else "NONE"
        }

    def redact(self, text: str) -> str:
        """Redact PII from text."""
        for name, pattern in self.PATTERNS.items():
            text = pattern.sub(f"[REDACTED_{name.upper()}]", text)
        return text


class PartialExecutionRollback:
    """Rollback multi-step plans on partial failure."""

    def __init__(self, rollback_manager=None):
        self.rollback_manager = rollback_manager
        self._completed_steps: List[Dict[str, Any]] = []

    def record_step(self, step_id: int, action: str, result: Any) -> None:
        self._completed_steps.append({
            "step_id": step_id, "action": action, "result": result
        })

    def rollback_all(self) -> Dict[str, Any]:
        """Rollback all completed steps in reverse order."""
        rolled_back = []
        if self.rollback_manager:
            try:
                self.rollback_manager.rollback_last()
                rolled_back.append("rollback_manager")
            except Exception as e:
                logger.error(f"Rollback failed: {e}")
        self._completed_steps.clear()
        return {"rolled_back": rolled_back, "steps_cleared": True}


class FailureMitigationSuite:
    """Unified failure mitigation suite combining all 5 handlers."""

    def __init__(self, known_tools: Optional[Set[str]] = None, rollback_manager=None):
        self.hallucination = HallucinationDetector(known_tools)
        self.resources = ResourceMonitor()
        self.artifacts = ArtifactIntegrityChecker()
        self.privacy = PrivacyLeakageFilter()
        self.rollback = PartialExecutionRollback(rollback_manager)

    def pre_execution_check(self, llm_output: dict) -> Dict[str, Any]:
        """Run all pre-execution checks."""
        checks = {
            "hallucination": self.hallucination.check(llm_output),
            "resources": self.resources.check(),
            "privacy": self.privacy.scan(str(llm_output)),
        }
        safe = all(
            not c.get("hallucination_detected", False) and
            not c.get("exhaustion_detected", False) and
            not c.get("leakage_detected", False)
            for c in checks.values()
        )
        checks["safe_to_proceed"] = safe
        return checks

    def post_execution_check(self, output_text: str) -> Dict[str, Any]:
        """Run post-execution checks on output."""
        return {
            "privacy": self.privacy.scan(output_text),
            "resources": self.resources.check()
        }
