"""
Intent Decomposition Node — §2 of Production Autonomous Agent Spec.

Converts raw user text into structured intent:
  {objective, constraints, assumptions, required_resources, risk_level, success_criteria}

No tool may execute from raw text. All must pass through this node first.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.intent")

INTENT_PROMPT = """\
You are an Intent Decomposition Engine.

Given user input, extract a structured intent object.

RULES:
1. Extract the REAL objective — not the literal text.
2. Identify implicit constraints (time, budget, quality, location).
3. List assumptions you're making.
4. List tools/resources needed.
5. Assess risk_level: "low", "medium", "high", "critical".
6. Define measurable success_criteria.

Respond with ONLY a JSON object:
{
  "objective": "clear real-world goal",
  "constraints": {"time": "...", "budget": "...", "quality": "...", "other": "..."},
  "assumptions": ["assumption 1", "assumption 2"],
  "required_resources": ["tool_name_1", "tool_name_2"],
  "risk_level": "low|medium|high|critical",
  "success_criteria": "how to verify this is done"
}

No markdown. No extra text.
"""


async def intent_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Decompose raw goal into structured intent — §2."""
    from agent.core.llm_provider import get_llm

    # Skip if intent already decomposed
    if state.get("intent", {}).get("objective"):
        return {}

    app_config = config.get("configurable", {}).get("app_config", {})
    llm = get_llm(app_config, temperature=0.1)

    goal = state.get("goal", "")
    memory_ctx = state.get("world_state", {}).get("memory_context", "")

    user_content = f"USER INPUT: {goal}"
    if memory_ctx:
        user_content += f"\n\nCONTEXT FROM MEMORY:\n{memory_ctx}"

    messages = [
        SystemMessage(content=INTENT_PROMPT),
        HumanMessage(content=user_content),
    ]

    logger.info("⏳ Intent: Sending decomposition to LLM...")
    try:
        response = await llm.ainvoke(messages)
        text = response.content.strip()
        logger.info(f"✓ Intent: LLM response received ({len(text)} chars)")

        intent = json.loads(text)
        if not isinstance(intent, dict):
            intent = {"objective": goal, "constraints": {}, "assumptions": [],
                      "required_resources": [], "risk_level": "medium",
                      "success_criteria": "task completed successfully"}
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning(f"Intent parsing failed: {exc}")
        intent = {
            "objective": goal,
            "constraints": {},
            "assumptions": [],
            "required_resources": [],
            "risk_level": "medium",
            "success_criteria": "task completed successfully",
        }

    logger.info(f"Intent decomposed: {intent.get('objective', '')[:80]}")

    return {
        "intent": intent,
        "audit_log": [{
            "node": "intent",
            "action": "decompose",
            "result": intent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
