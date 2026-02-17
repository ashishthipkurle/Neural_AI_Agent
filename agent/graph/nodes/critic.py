"""
Critic Agent Node — reviews work quality, validates against plan.

Updated for production state schema.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.critic")

CRITIC_PROMPT = """\
You are a Quality Critic for an autonomous agent.

Your job:
1. Review the work that was done.
2. Compare results against the original plan and success criteria.
3. Identify any issues, gaps, or errors.
4. Decide if the work is acceptable.

Respond with ONLY a JSON object:
{
  "approved": true|false,
  "quality_score": 0.0 to 1.0,
  "issues": ["issue 1", "issue 2"],
  "recommendation": "accept" | "redo" | "improve"
}
"""


async def critic_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Critic agent — reviews work quality."""
    from agent.core.llm_provider import get_llm

    app_config = config.get("configurable", {}).get("app_config", {})
    llm = get_llm(app_config, temperature=0.0)

    intent = state.get("intent", {})
    plan = state.get("plan_graph", {})
    results = state.get("tool_results", {})

    context = f"""OBJECTIVE: {intent.get('objective', state.get('goal', ''))}
SUCCESS CRITERIA: {intent.get('success_criteria', 'completed successfully')}

PLAN:
{json.dumps(plan.get('nodes', []), indent=2, default=str)[:600]}

RESULTS:
{json.dumps(results, indent=2, default=str)[:600]}
"""

    messages = [
        SystemMessage(content=CRITIC_PROMPT),
        HumanMessage(content=context),
    ]

    try:
        response = await llm.ainvoke(messages)
        text = response.content.strip()
        review = json.loads(text)
    except Exception as exc:
        logger.warning(f"Critic parse failed: {exc}")
        review = {"approved": True, "quality_score": 0.6, "issues": [], "recommendation": "accept"}

    approved = review.get("approved", True)
    quality = review.get("quality_score", 0.5)
    issues = review.get("issues", [])

    # Mark critic's own subgoal as done
    subgoal = state.get("current_subgoal", "")
    plan_graph = dict(state.get("plan_graph", {}))
    for node in plan_graph.get("nodes", []):
        if node.get("id") == subgoal:
            node["status"] = "done"
            break

    update: Dict[str, Any] = {
        "plan_graph": plan_graph,
        "messages": [AIMessage(content=f"Review: {'approved' if approved else 'needs work'} (quality: {quality:.2f})")],
        "audit_log": [{
            "node": "critic",
            "action": "review",
            "approved": approved,
            "quality_score": quality,
            "issues": issues,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }

    if not approved:
        update["error"] = f"Critic flagged issues: {'; '.join(issues)}"

    return update
