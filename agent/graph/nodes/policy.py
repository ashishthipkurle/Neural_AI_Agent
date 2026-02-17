"""
Policy Enforcement Node — §6/§12 of Production Autonomous Agent Spec.

All actions must be classified: SAFE, ELEVATED, DESTRUCTIVE.
DESTRUCTIVE requires confirmation, security token, snapshot, double verification.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.policy")

# Keywords that indicate destructive intent
DESTRUCTIVE_KEYWORDS = frozenset({
    "delete", "remove", "format", "erase", "uninstall", "drop", "truncate",
    "wipe", "destroy", "terminate", "kill", "shutdown", "reboot",
    "modify boot", "registry", "system32", "disk format",
})

ELEVATED_KEYWORDS = frozenset({
    "install", "download", "execute", "run", "send", "post", "publish",
    "transfer", "deploy", "upload", "commit", "push", "trade", "buy", "sell",
    "pay", "purchase", "order", "book", "schedule",
})

# Hard-blocked actions — NEVER allowed
BLOCKED_ACTIONS = frozenset({
    "format disk", "modify boot config", "delete system32",
    "escalate privileges", "disable antivirus", "disable firewall",
})


async def policy_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Evaluate goal against safety policy — §12.

    Classifies risk, blocks forbidden actions, flags approval needs.
    """
    goal = state.get("goal", "").lower()
    intent = state.get("intent", {})
    risk_from_intent = intent.get("risk_level", "low")

    # ── Hard blocks ──
    for blocked in BLOCKED_ACTIONS:
        if blocked in goal:
            logger.warning(f"BLOCKED: '{blocked}' detected in goal")
            return {
                "error": f"Action blocked by policy: '{blocked}' is never allowed",
                "needs_approval": False,
                "verification_status": False,
                "audit_log": [{
                    "node": "policy",
                    "action": "BLOCKED",
                    "reason": f"Forbidden action: {blocked}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            }

    # ── Risk classification ──
    risk_level = "low"

    for kw in DESTRUCTIVE_KEYWORDS:
        if kw in goal:
            risk_level = "critical"
            break

    if risk_level != "critical":
        for kw in ELEVATED_KEYWORDS:
            if kw in goal:
                risk_level = "high" if risk_from_intent in ("high", "critical") else "medium"
                break

    # Override with intent-level assessment if higher
    risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    if risk_order.get(risk_from_intent, 0) > risk_order.get(risk_level, 0):
        risk_level = risk_from_intent

    needs_approval = risk_level in ("high", "critical")

    # Update world state with risk
    world = dict(state.get("world_state", {}))
    world["risk_level"] = risk_level

    logger.info(f"Policy: risk={risk_level}, needs_approval={needs_approval}")

    return {
        "needs_approval": needs_approval,
        "world_state": world,
        "audit_log": [{
            "node": "policy",
            "action": "classify",
            "risk_level": risk_level,
            "needs_approval": needs_approval,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
