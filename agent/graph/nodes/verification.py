"""
Self-Verification Engine — §10 of Production Autonomous Agent Spec.

Before declaring success:
1. Re-evaluate original objective
2. Compare final world_state with success_criteria
3. Confirm no hidden incomplete dependencies
4. Generate confidence score

If confidence < threshold → re-enter planning phase.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.verification")

VERIFICATION_PROMPT = """\
You are a Verification Engine for an autonomous agent.

Compare the original objective with the current results and determine
if the goal is truly complete.

Respond with ONLY a JSON object:
{
  "complete": true|false,
  "confidence": 0.0 to 1.0,
  "issues": ["issue 1", "issue 2"],
  "recommendation": "proceed" | "re_plan" | "retry_step" | "escalate"
}

RULES:
1. confidence < 0.6 → set recommendation to "re_plan"
2. confidence 0.6-0.8 → set recommendation to "retry_step"
3. confidence > 0.8 → set recommendation to "proceed"
4. If any critical issue, override to "escalate"

No markdown. No extra text. JSON only.
"""


async def verification_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Self-verification engine — §10."""
    from agent.core.llm_provider import get_llm

    app_config = config.get("configurable", {}).get("app_config", {})
    llm = get_llm(app_config, temperature=0.0)

    # Build verification context
    intent = state.get("intent", {})
    plan = state.get("plan_graph", {})
    results = state.get("tool_results", {})
    error = state.get("error")

    context = f"""ORIGINAL OBJECTIVE: {intent.get('objective', state.get('goal', ''))}
SUCCESS CRITERIA: {intent.get('success_criteria', 'task completed')}

PLAN STATUS:
{_plan_status(plan)}

TOOL RESULTS:
{json.dumps(results, default=str)[:800]}

LAST ERROR: {error or 'none'}
"""

    messages = [
        SystemMessage(content=VERIFICATION_PROMPT),
        HumanMessage(content=context),
    ]

    try:
        response = await llm.ainvoke(messages)
        text = response.content.strip()
        result = json.loads(text)
    except Exception as exc:
        logger.warning(f"Verification parse failed: {exc}")
        result = {
            "complete": False,
            "confidence": 0.3,
            "issues": [str(exc)],
            "recommendation": "retry_step",
        }

    confidence = result.get("confidence", 0.0)
    complete = result.get("complete", False)
    recommendation = result.get("recommendation", "proceed")
    issues = result.get("issues", [])

    logger.info(
        f"Verification: complete={complete}, confidence={confidence:.2f}, "
        f"recommendation={recommendation}"
    )

    update: Dict[str, Any] = {
        "verification_status": complete and confidence >= 0.7,
        "verification_confidence": confidence,
        "audit_log": [{
            "node": "verification",
            "action": "verify",
            "complete": complete,
            "confidence": confidence,
            "issues": issues,
            "recommendation": recommendation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }

    if not complete or confidence < 0.7:
        if recommendation == "re_plan":
            update["error"] = f"Verification failed (confidence={confidence:.2f}): needs re-planning"
        elif recommendation == "escalate":
            update["error"] = f"Verification escalated: {'; '.join(issues)}"
        else:
            update["error"] = f"Verification incomplete (confidence={confidence:.2f})"

    return update


def _plan_status(plan: Dict[str, Any]) -> str:
    """Format plan status for verification context."""
    nodes = plan.get("nodes", [])
    if not nodes:
        return "No plan exists"

    lines = []
    for n in nodes:
        lines.append(f"[{n.get('status', '?')}] {n.get('task', '?')}")
    return "\n".join(lines)
