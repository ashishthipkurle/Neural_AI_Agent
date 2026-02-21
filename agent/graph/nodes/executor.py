"""
Executor Agent Node — performs real-world OS actions.

Uses a multi-turn tool-calling loop with:
- Error resilience: retries on transient LLM failures
- Workspace context: pre-loads directory structure so the LLM doesn't waste rounds exploring
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.executor")

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

MAX_TOOL_ROUNDS = 12
LLM_RETRY_ATTEMPTS = 2

EXECUTOR_PROMPT = """\
You are an Executor Agent. You perform REAL-WORLD ACTIONS using tools.

>>> CRITICAL: ACT IMMEDIATELY. DO NOT EXPLORE. <<<
You already know the workspace structure (shown below). Do NOT waste rounds on list_dir, search, or read_file.
Your FIRST tool call should be a PRODUCTIVE action: write_file, coding_tool(execute_code), ltm_tool, or kg_tool.
file_ops_tool(action, path, content)
  Actions: read_file, write_file, list_dir, create_dir, delete_path, search, exists
  - write_file: content MUST be a string. For JSON, format as string: content='{{"key":"value"}}'
  - search: finds files by name pattern. path=search_root, content=search_term
  - exists: checks if path exists and returns type/size

coding_tool(action, code, language, path)
  Actions: write_code, execute_code, run_command
  - execute_code: runs Python code. Pass code= with Python source.
  - NEVER read a Python script with file_ops_tool read_file expecting it to execute. Use coding_tool instead.

memory_tool(action, content, query)
  Actions: store, search, recall
  - store: saves content to personal memory with content= param
  - search: queries personal memory with query= param

ltm_tool(action, key, value, category, query)
  Actions: store, retrieve, search
  - store: saves to VERSIONED Long-Term Memory database. Requires key= and value=.
  - retrieve: gets current value for key=.
  - search: keyword search with query=.
  USE THIS to update Long-Term Memory, NOT memory_tool.

kg_tool(action, entity_id, entity_type, name, source, target, relation_type, query)
  Actions: add_entity, add_relation, get_entity, find_entities, stats
  - add_entity: creates an entity. Requires entity_id=, entity_type=, name=.
  - add_relation: links two entities. Requires source=, target=, relation_type=. BOTH entities must already exist.
  - stats: returns entity/relation counts.
  USE THIS to update the Knowledge Graph.

desktop_tool(action, app_name, text, key)
  Actions: launch_app, type_text, press_key, click, screenshot

vision_tool(action, question, path, text)
  Actions: screenshot, analyze, ocr, detect_elements, find_text, compare, read_popup

system_tool(action, app_name, expression)
  Actions: launch_app, calculate, system_info

voice_tool(action, text)
  Actions: speak, stop_speaking

telegram_tool(action, message, chat_id)
  Actions: send_message, check_messages

browser_tool(action, url, query)
  Actions: navigate, search, read_page

research_tool(query, depth)
  - Searches the web and returns a research summary.

WORKSPACE: {workspace}
Current workspace contents:
{workspace_listing}

CRITICAL RULES:
1. BUILD FULL PATHS — if the task mentions a subdirectory (e.g. "inside X"), use {workspace}/X/filename as the path.
2. ACT DIRECTLY — you already know the workspace structure above. Do NOT call list_dir or search unless absolutely necessary.
3. To EXECUTE Python code, use coding_tool(action="execute_code", code="...").
4. To update Long-Term Memory, use ltm_tool(action="store", key="...", value="...").
5. To update Knowledge Graph, use kg_tool(action="add_entity", ...) then kg_tool(action="add_relation", ...).
6. When done, respond with a plain-text summary (no tool calls).
7. When a task mentions "from step_N" or "using step_N output", that refers to context from a previous agent — do NOT search for files. Proceed with your best knowledge.
8. Keep responses SHORT. Output ONE tool call at a time.
9. Do NOT use file_ops_tool(action="search") to look for data you should CREATE. If a file does not exist, CREATE it with write_file. If you need to store structured data, use ltm_tool or kg_tool.
10. AUDIT LOGS are stored at {workspace}/agent_data/audit_logs/ as JSON files (one per session). Do NOT search for "audit.log" — it does not exist. Read files from agent_data/audit_logs/ directly.
11. LTM is stored in agent_data/ltm.db (use ltm_tool). KG is stored in agent_data/knowledge_graph.json (use kg_tool). Do NOT read these files directly — use the tools.
12. STM (Short-Term Memory) is an IN-MEMORY data structure — there are no STM files on disk. When a task mentions "STM timestamps" or "STM state", use coding_tool(action="execute_code") to generate the data (e.g. with datetime.now()) and write it directly. Do NOT search for STM files.
13. To RUN or DEPLOY a Python script, use coding_tool(action="execute_code", code="<paste or inline the full script source>"). Do NOT just read_file the script and stop — read_file only returns text, it does NOT execute anything.
14. When told to "launch", "run", or "execute" tasks from previous steps, use file_ops_tool(read_file) to get the EXISTING script content, then pass that content to coding_tool(action="execute_code", code=<script content>). Do NOT write a new simulation or placeholder script. Run the ACTUAL code that was already created.
"""


def _get_workspace_listing() -> str:
    """Get a compact listing of the workspace root."""
    try:
        entries = os.listdir(WORKSPACE_ROOT)
        dirs = [e + "/" for e in entries if os.path.isdir(os.path.join(WORKSPACE_ROOT, e)) and not e.startswith('.')]
        files = [e for e in entries if os.path.isfile(os.path.join(WORKSPACE_ROOT, e)) and not e.startswith('.')]
        return "\n".join(sorted(dirs) + sorted(files))
    except Exception:
        return "(could not list)"


def _get_tool_map():
    """Get the full tool map for executor."""
    from agent.graph import tools as t
    return {
        "desktop_tool": t.desktop_tool,
        "system_tool": t.system_tool,
        "voice_tool": t.voice_tool,
        "telegram_tool": t.telegram_tool,
        "vision_tool": t.vision_tool,
        "file_ops_tool": t.file_ops_tool,
        "memory_tool": t.memory_tool,
        "coding_tool": t.coding_tool,
        "browser_tool": t.browser_tool,
        "research_tool": t.research_tool,
        "ltm_tool": t.ltm_tool,
        "kg_tool": t.kg_tool,
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
        logger.info(f"✓ Executor tool {name}: {str(result)[:120]}")
        return str(result)
    except asyncio.TimeoutError:
        logger.warning(f"✗ Executor tool {name} timed out after 90s")
        return f"Error: {name} timed out after 90s"
    except Exception as e:
        logger.warning(f"✗ Executor tool {name} failed: {e}")
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


async def executor_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Executor agent — performs real-world actions with multi-turn tool loop."""
    from agent.core.llm_provider import get_llm_with_tools
    from agent.graph.tools import (
        desktop_tool, system_tool, voice_tool,
        telegram_tool, vision_tool, file_ops_tool,
        memory_tool, coding_tool, browser_tool, research_tool,
        ltm_tool, kg_tool,
    )

    app_config = config.get("configurable", {}).get("app_config", {})
    tools = [desktop_tool, system_tool, voice_tool, telegram_tool, vision_tool,
             file_ops_tool, memory_tool, coding_tool, browser_tool, research_tool,
             ltm_tool, kg_tool]

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

    # Pre-action screenshot for verification
    pre_screenshot = None
    try:
        from agent.vision.structured_vision import StructuredVisionSystem
        vision = StructuredVisionSystem()
        pre_screenshot = vision.capture_screenshot()
    except Exception:
        pass

    workspace_listing = _get_workspace_listing()
    messages = [
        SystemMessage(content=EXECUTOR_PROMPT.format(
            workspace=WORKSPACE_ROOT,
            workspace_listing=workspace_listing
        )),
        HumanMessage(content=f"EXECUTE: {task_desc}"),
    ]

    tool_map = _get_tool_map()
    tool_results = dict(state.get("tool_results", {}))
    final_text = ""
    round_num = 0
    non_productive_rounds = 0  # Unified counter for any read-only round

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

            # Unified non-productive round detector: any round where ALL calls are read-only
            READ_ONLY_ACTIONS = {"list_dir", "ls", "search", "read_file", "exists"}
            all_readonly = all(
                tc.get("name") == "file_ops_tool" and tc.get("args", {}).get("action") in READ_ONLY_ACTIONS
                for tc in tc_list
            )
            if all_readonly:
                non_productive_rounds += 1
            else:
                non_productive_rounds = 0  # Reset when agent actually acts

            for tc in tc_list:
                name = tc.get("name", "")
                args = tc.get("args", {})
                tc_id = tc.get("id", f"call_{round_num}_{name}")

                # HARD BLOCK: After 4 non-productive (read-only) rounds, block ALL read-only actions
                if non_productive_rounds >= 4 and name == "file_ops_tool" and args.get("action") in READ_ONLY_ACTIONS:
                    result_str = (
                        "BLOCKED: You have spent " + str(non_productive_rounds) + " rounds on read-only operations "
                        "(list_dir/search/read_file) without performing ANY real action. "
                        "STOP exploring. PERFORM the task NOW using coding_tool(execute_code), "
                        "file_ops_tool(write_file), ltm_tool, or kg_tool."
                    )
                    logger.warning(f"Blocked non-productive round {non_productive_rounds}: {name}({args.get('action', '?')})")
                else:
                    result_str = await _execute_single_tool(name, args, tool_map)

                tool_results[f"executor_{name}_r{round_num}"] = result_str
                messages.append(ToolMessage(content=result_str, tool_call_id=tc_id))

            # After 4+ non-productive rounds, inject a strong redirect
            if non_productive_rounds >= 4:
                messages.append(HumanMessage(
                    content="STOP all read-only operations. You have wasted " + str(non_productive_rounds) + " rounds. "
                            "ACT NOW: use coding_tool(execute_code), ltm_tool, kg_tool, or file_ops_tool(write_file)."
                ))

            logger.info(f"Executor round {round_num + 1}: executed {len(tc_list)} tool(s)")
        else:
            final_text = text or "Max tool rounds reached"
            logger.warning(f"Executor hit max tool rounds ({MAX_TOOL_ROUNDS})")
    except Exception as e:
        final_text = f"Executor error: {e}"
        logger.error(f"Executor failed: {e}")

    # Post-action verification via vision
    verification_result = None
    if pre_screenshot:
        try:
            vision = StructuredVisionSystem()
            post_screenshot = vision.capture_screenshot()
            verification_result = vision.verify_action(
                pre_screenshot, post_screenshot, expected_change=task_desc[:50]
            )
            tool_results["action_verification"] = verification_result
        except Exception:
            pass

    # Mark subgoal as done
    plan_graph = dict(state.get("plan_graph", {}))
    nodes = list(plan_graph.get("nodes", []))
    matched = False
    for i, node in enumerate(nodes):
        node_id = node.get("id", "")
        if node_id == subgoal or (not matched and node.get("task", "") == task_desc and node.get("status") not in ("done", "skipped")):
            nodes[i] = {**node, "status": "done"}
            matched = True
            logger.info(f"✓ Executor: marked subgoal '{node_id}' as done")
            break
    if not matched:
        logger.warning(f"⚠ Executor: could not match subgoal '{subgoal}' to any plan node")
    plan_graph["nodes"] = nodes

    return {
        "tool_results": tool_results,
        "plan_graph": plan_graph,
        "messages": [AIMessage(content=final_text)],
        "audit_log": [{
            "node": "executor",
            "action": "execute",
            "subgoal": subgoal,
            "tool_rounds": min(round_num + 1, MAX_TOOL_ROUNDS),
            "verified": verification_result.get("verified", False) if verification_result else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
