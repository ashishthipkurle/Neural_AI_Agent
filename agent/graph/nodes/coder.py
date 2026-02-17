"""
Coder Agent Node — code operations via LLM tool calling.

Uses a multi-turn tool-calling loop with:
- Error resilience: retries on transient LLM failures
- Workspace context: pre-loads directory structure
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

logger = logging.getLogger("graph.coder")

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

MAX_TOOL_ROUNDS = 8
LLM_RETRY_ATTEMPTS = 2

CODER_PROMPT = """\
You are a Code Agent. You write, edit, and execute code using tools.

Available tools and their correct usage:
─────────────────────────────────────────
coding_tool(action, code, language, path)
  Actions: write_code, edit_code, execute_code, run_command
  - write_code: writes code to a file. Requires path= and code= params.
  - execute_code: runs code. Pass code= with source code. For Python, it gets written to a temp file and executed with python.
  - run_command: runs a shell command. Pass code= with the command string.
  - IMPORTANT: To run Python, use execute_code with code=. Do NOT use file_ops_tool read_file to "run" a script.

file_ops_tool(action, path, content)
  Actions: read_file, write_file, list_dir, create_dir, delete_path, search, exists
  - write_file: content MUST be a string. For JSON, format as string: content='{{"key":"value"}}'
  - search: finds files by name pattern. path=search_root, content=search_term

memory_tool(action, content, query)
  Actions: store, search, recall
  - store: saves content to long-term memory
  - search: queries memory

vision_tool(action, question, path, text)
  Actions: screenshot, analyze, ocr, detect_elements, find_text
  - analyze: uses LLM vision to describe what's on screen

WORKSPACE: {workspace}
Current workspace contents:
{workspace_listing}

CRITICAL RULES:
1. BUILD FULL PATHS — if the task mentions a subdirectory (e.g. "inside X"), use {workspace}/X/filename as the path. NEVER write files to the workspace root when a subdirectory is specified.
2. ACT DIRECTLY — you already know the workspace structure above. Do NOT call list_dir unless checking a subfolder you just created.
3. For execute_code with Python, pass code= containing the Python source. It will be written to a temp file and run.
4. For write_file, content MUST be a string. For JSON files, pass the JSON as a string.
5. When done, respond with a plain-text summary (no tool calls).
6. When a task mentions "from step_N" or "using step_N output", that refers to context from a previous agent — do NOT search for files named 'step_1' or 'step_N'. Instead, proceed with your best knowledge and CREATE the required content directly.
7. Keep responses SHORT. Output ONE tool call at a time.
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
    """Get the full tool map for coder."""
    from agent.graph import tools as t
    return {
        "coding_tool": t.coding_tool,
        "file_ops_tool": t.file_ops_tool,
        "memory_tool": t.memory_tool,
        "vision_tool": t.vision_tool,
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
        logger.info(f"✓ Coder tool {name}: {str(result)[:120]}")
        return str(result)
    except asyncio.TimeoutError:
        logger.warning(f"✗ Coder tool {name} timed out after 90s")
        return f"Error: {name} timed out after 90s"
    except Exception as e:
        logger.warning(f"✗ Coder tool {name} failed: {e}")
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


async def coder_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Coder agent — writes, edits, executes code with multi-turn tool loop."""
    from agent.core.llm_provider import get_llm_with_tools
    from agent.graph.tools import coding_tool, file_ops_tool, memory_tool, vision_tool

    app_config = config.get("configurable", {}).get("app_config", {})
    tools = [coding_tool, file_ops_tool, memory_tool, vision_tool]

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

    workspace_listing = _get_workspace_listing()
    messages = [
        SystemMessage(content=CODER_PROMPT.format(
            workspace=WORKSPACE_ROOT,
            workspace_listing=workspace_listing
        )),
        HumanMessage(content=f"CODING TASK: {task_desc}"),
    ]

    tool_map = _get_tool_map()
    tool_results = dict(state.get("tool_results", {}))
    final_text = ""
    round_num = 0
    consecutive_listdir_rounds = 0

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

            # Check if ALL calls this round are list_dir
            all_list_dir = all(
                tc.get("name") == "file_ops_tool" and tc.get("args", {}).get("action") in ("list_dir", "ls")
                for tc in tc_list
            )
            if all_list_dir:
                consecutive_listdir_rounds += 1
            else:
                consecutive_listdir_rounds = 0

            for tc in tc_list:
                name = tc.get("name", "")
                args = tc.get("args", {})
                tc_id = tc.get("id", f"call_{round_num}_{name}")

                # HARD BLOCK: After 2 consecutive list_dir-only rounds, block further list_dir
                if consecutive_listdir_rounds >= 2 and name == "file_ops_tool" and args.get("action") in ("list_dir", "ls"):
                    result_str = (
                        "BLOCKED: You have already listed directories multiple times. "
                        "The workspace is at: " + WORKSPACE_ROOT + ". "
                        "Stop exploring and perform the actual task NOW."
                    )
                    logger.warning(f"Blocked repeated list_dir call to: {args.get('path', '?')}")
                else:
                    result_str = await _execute_single_tool(name, args, tool_map)

                tool_results[f"coder_{name}_r{round_num}"] = result_str
                messages.append(ToolMessage(content=result_str, tool_call_id=tc_id))

            # After blocking, also inject a redirect message
            if consecutive_listdir_rounds >= 2:
                messages.append(HumanMessage(
                    content="STOP listing directories. You already know the workspace structure. "
                            "Perform the actual task NOW using write_file, edit_code, or other actions."
                ))

            logger.info(f"Coder round {round_num + 1}: executed {len(tc_list)} tool(s)")
        else:
            final_text = text or "Max tool rounds reached"
            logger.warning(f"Coder hit max tool rounds ({MAX_TOOL_ROUNDS})")
    except Exception as e:
        final_text = f"Coder error: {e}"
        logger.error(f"Coder failed: {e}")

    # Mark subgoal as done
    plan_graph = dict(state.get("plan_graph", {}))
    nodes = list(plan_graph.get("nodes", []))
    matched = False
    for i, node in enumerate(nodes):
        node_id = node.get("id", "")
        if node_id == subgoal or (not matched and node.get("task", "") == task_desc and node.get("status") not in ("done", "skipped")):
            nodes[i] = {**node, "status": "done"}
            matched = True
            logger.info(f"✓ Coder: marked subgoal '{node_id}' as done")
            break
    if not matched:
        logger.warning(f"⚠ Coder: could not match subgoal '{subgoal}' to any plan node")
    plan_graph["nodes"] = nodes

    return {
        "tool_results": tool_results,
        "plan_graph": plan_graph,
        "messages": [AIMessage(content=final_text)],
        "audit_log": [{
            "node": "coder",
            "action": "code",
            "subgoal": subgoal,
            "tool_rounds": min(round_num + 1, MAX_TOOL_ROUNDS),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
