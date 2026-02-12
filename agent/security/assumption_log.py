"""
Assumption Log — Persistent confidence and assumption tracking.

Every action, plan step, and skill execution MUST:
- Include a confidence score (0.0-1.0)
- Log assumptions made
- Record uncertainty where applicable

Persisted in JSONL format.
"""

import logging
import json
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("AssumptionLog")


@dataclass
class AssumptionEntry:
    """Single assumption log entry."""
    id: str
    timestamp: str
    session_id: str
    source_module: str
    action: str
    skill_name: str
    confidence: float
    assumptions: List[str]
    uncertainty: List[str]
    input_summary: str
    decision_rationale: str
    outcome_success: Optional[bool] = None
    outcome_notes: Optional[str] = None


class AssumptionLogger:
    """Persistent assumption and confidence logger (JSONL)."""

    def __init__(self, log_dir: str = "logs/assumptions", session_id: Optional[str] = None):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self._counter = 0
        self._lock = threading.RLock()

    def _gen_id(self) -> str:
        with self._lock:
            self._counter += 1
            return f"assume_{self.session_id}_{self._counter}"

    def _log_file(self) -> Path:
        return self.log_dir / f"assumptions_{datetime.now():%Y-%m-%d}.jsonl"

    def log(self, source_module: str, action: str, confidence: float,
            assumptions: List[str], uncertainty: Optional[List[str]] = None,
            skill_name: str = "", input_summary: str = "",
            decision_rationale: str = "") -> str:
        entry = AssumptionEntry(
            id=self._gen_id(), timestamp=datetime.now().isoformat(),
            session_id=self.session_id, source_module=source_module,
            action=action, skill_name=skill_name,
            confidence=max(0.0, min(1.0, confidence)),
            assumptions=assumptions, uncertainty=uncertainty or [],
            input_summary=input_summary[:200],
            decision_rationale=decision_rationale
        )
        self._write(entry)
        return entry.id

    def log_outcome(self, entry_id: str, success: bool, notes: str = "") -> None:
        followup = {"type": "outcome", "original_id": entry_id,
                     "timestamp": datetime.now().isoformat(),
                     "success": success, "notes": notes}
        with self._lock:
            try:
                with open(self._log_file(), 'a', encoding='utf-8') as f:
                    f.write(json.dumps(followup) + "\n")
            except Exception as e:
                logger.error(f"Failed to log outcome: {e}")

    def _write(self, entry: AssumptionEntry) -> None:
        with self._lock:
            try:
                with open(self._log_file(), 'a', encoding='utf-8') as f:
                    f.write(json.dumps(asdict(entry)) + "\n")
            except Exception as e:
                logger.error(f"Failed to write assumption: {e}")

    def get_entries(self, date: Optional[str] = None, source_module: Optional[str] = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        target = date or datetime.now().strftime("%Y-%m-%d")
        lf = self.log_dir / f"assumptions_{target}.jsonl"
        if not lf.exists():
            return []
        entries = []
        try:
            with open(lf, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        e = json.loads(line.strip())
                        if e.get("type") == "outcome":
                            continue
                        if source_module and e.get("source_module") != source_module:
                            continue
                        entries.append(e)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Read error: {e}")
        return entries[-limit:]

    def get_statistics(self, date: Optional[str] = None) -> Dict[str, Any]:
        entries = self.get_entries(date=date, limit=10000)
        if not entries:
            return {"total": 0, "avg_confidence": 0.0, "low_confidence": 0}
        confs = [e.get("confidence", 0) for e in entries]
        return {
            "total": len(entries),
            "avg_confidence": round(sum(confs) / len(confs), 3),
            "low_confidence": sum(1 for c in confs if c < 0.5),
        }
