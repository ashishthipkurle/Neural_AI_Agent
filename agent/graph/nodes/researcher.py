"""
Researcher Agent Node — uses LLM tool calling for web research + memory search.

Uses a multi-turn tool-calling loop with:
- Error resilience: retries on transient LLM failures
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.researcher")

MAX_TOOL_ROUNDS = 6
LLM_RETRY_ATTEMPTS = 2

RESEARCHER_PROMPT = """\
You are a Research Agent. Search for information and synthesize findings.

Available tools:
- research_tool: search the web (query: str)
- browser_tool: navigate to a URL (url: str, action: str)
- memory_tool: search personal memory (action: store | search | recall, query: str, content: str)

RULES:
1. ACT DIRECTLY. Call the most relevant tool first.
2. When done, respond with a plain-text summary (no tool calls).
3. When a task mentions "from step_N" or "using step_N output", that refers to context from a previous agent — do NOT search for files named 'step_1'. Proceed with your best knowledge.
4. If memory_tool returns nothing useful, summarize what you know and FINISH. Do NOT call research_tool for internal architecture — it will search the web, which is wrong for internal system knowledge.
5. Keep responses SHORT.
"""


def _get_tool_map():
    """Get the full tool map for researcher."""
    from agent.graph import tools as t
    return {
        "research_tool": t.research_tool,
        "browser_tool": t.browser_tool,
        "memory_tool": t.memory_tool,
    }


def _parse_json_tool_calls(text: str) -> list:
    """Extract JSON tool call objects from plain text response (fallback)."""
    calls = []
    for m in re.finditer(r'\{(?:[^{}]|\{[^{}]*\})*\}', text):
        try:
            obj = json.loads(m.group())
            if "tool" in obj:
                calls.append({"name": obj["tool"], "args": obj.get("params", {}), "id": f"text_{len(calls)}"})
        except json.JSONDecodeError:
            continue
    return calls


async def _execute_single_tool(name: str, args: dict, tool_map: dict) -> str:
    """Execute one tool call with a 90s timeout."""
    fn = tool_map.get(name)
    if not fn:
        return f"Error: unknown tool '{name}'"
    try:
        result = await asyncio.wait_for(fn.ainvoke(args), timeout=90)
        logger.info(f"✓ Researcher tool {name}: {str(result)[:120]}")
        return str(result)
    except asyncio.TimeoutError:
        logger.warning(f"✗ Researcher tool {name} timed out after 90s")
        return f"Error: {name} timed out after 90s"
    except Exception as e:
        logger.warning(f"✗ Researcher tool {name} failed: {e}")
        return f"Error: {e}"


async def _llm_invoke_safe(llm, messages):
    """Invoke LLM with retry on transient errors and hard 120s timeout."""
    for attempt in range(LLM_RETRY_ATTEMPTS + 1):
        try:
            return await asyncio.wait_for(llm.ainvoke(messages), timeout=120)
        except asyncio.TimeoutError:
            logger.warning(f"LLM call timed out (attempt {attempt + 1}) after 120s")
            if attempt >= LLM_RETRY_ATTEMPTS:
                raise
        except Exception as e:
            if attempt < LLM_RETRY_ATTEMPTS:
                logger.warning(f"LLM call failed (attempt {attempt + 1}), retrying: {e}")
                await asyncio.sleep(1)
            else:
                logger.error(f"LLM call failed after {LLM_RETRY_ATTEMPTS + 1} attempts: {e}")
                raise


async def researcher_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Research agent — gathers information via multi-turn tool loop."""
    from agent.core.llm_provider import get_llm_with_tools
    from agent.graph.tools import research_tool, browser_tool, memory_tool

    app_config = config.get("configurable", {}).get("app_config", {})
    tools = [research_tool, browser_tool, memory_tool]

    try:
        llm = get_llm_with_tools(app_config, tools)
    except Exception:
        from agent.core.llm_provider import get_llm
        llm = get_llm(app_config)

    subgoal = state.get("current_subgoal", "")
    plan = state.get("plan_graph", {})
    task_desc = ""
    for node in plan.get("nodes", []):
        if node.get("id") == subgoal:
            task_desc = node.get("task", "")
            break

    if not task_desc:
        task_desc = state.get("goal", "")

    memory_ctx = state.get("world_state", {}).get("memory_context", "")
    user_content = f"RESEARCH TASK: {task_desc}"
    if memory_ctx:
        user_content += f"\n\nCONTEXT:\n{memory_ctx[:500]}"

    messages = [
        SystemMessage(content=RESEARCHER_PROMPT),
        HumanMessage(content=user_content),
    ]

    tool_map = _get_tool_map()
    tool_results = dict(state.get("tool_results", {}))
    final_text = ""
    round_num = 0

    # ── Multi-turn tool-calling loop ──────────────────────────────
    try:
        for round_num in range(MAX_TOOL_ROUNDS):
            response = await _llm_invoke_safe(llm, messages)
            text = response.content.strip() if response.content else ""

            tc_list = getattr(response, "tool_calls", None) or []
            if not tc_list and text:
                tc_list = _parse_json_tool_calls(text)

            if not tc_list:
                final_text = text
                break

            messages.append(response)
            for tc in tc_list:
                name = tc.get("name", "")
                args = tc.get("args", {})
                tc_id = tc.get("id", f"call_{round_num}_{name}")

                result_str = await _execute_single_tool(name, args, tool_map)
                tool_results[f"research_{name}_r{round_num}"] = result_str
                messages.append(ToolMessage(content=result_str, tool_call_id=tc_id))

            logger.info(f"Researcher round {round_num + 1}: executed {len(tc_list)} tool(s)")
        else:
            final_text = text or "Max tool rounds reached"
            logger.warning(f"Researcher hit max tool rounds ({MAX_TOOL_ROUNDS})")
    except Exception as e:
        final_text = f"Researcher error: {e}"
        logger.error(f"Researcher failed: {e}")

    # Mark subgoal as done
    plan_graph = dict(state.get("plan_graph", {}))
    nodes = list(plan_graph.get("nodes", []))
    matched = False
    for i, node in enumerate(nodes):
        node_id = node.get("id", "")
        if node_id == subgoal or (not matched and node.get("task", "") == task_desc and node.get("status") not in ("done", "skipped")):
            nodes[i] = {**node, "status": "done"}
            matched = True
            logger.info(f"✓ Researcher: marked subgoal '{node_id}' as done")
            break
    if not matched:
        logger.warning(f"⚠ Researcher: could not match subgoal '{subgoal}' to any plan node")
    plan_graph["nodes"] = nodes

    return {
        "tool_results": tool_results,
        "plan_graph": plan_graph,
        "messages": [AIMessage(content=final_text)],
        "audit_log": [{
            "node": "researcher",
            "action": "research",
            "subgoal": subgoal,
            "tool_rounds": min(round_num + 1, MAX_TOOL_ROUNDS),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
