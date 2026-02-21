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

MAX_TOOL_ROUNDS = 12
LLM_RETRY_ATTEMPTS = 2

CODER_PROMPT = """\
You are a Code Agent. Your ONLY job is to WRITE and EXECUTE code.

>>> CRITICAL: WRITE THE CODE DIRECTLY. <<<
Do NOT search for existing implementations. Do NOT read source files to learn APIs.
The task description tells you WHAT to create. Create it NOW using coding_tool or file_ops_tool(write_file).
Every round you spend on list_dir, search, or read_file instead of writing code is WASTED.
Your FIRST tool call should be coding_tool(write_code) or file_ops_tool(write_file).

Available tools and their correct usage:
─────────────────────────────────────────
coding_tool(action, code, language, path)
  Actions: write_code, edit_code, execute_code, run_command
  - write_code: writes code to a file. Requires path= and code= params.
  - execute_code: runs code. Pass code= with source code. For Python, it gets written to a temp file and executed with python.
  - run_command: runs a shell command. Pass code= with the command string.

file_ops_tool(action, path, content)
  Actions: read_file, write_file, list_dir, create_dir, delete_path, search, exists
  - write_file: content MUST be a string. For JSON, format as string: content='{{"key":"value"}}'

memory_tool(action, content, query)
  Actions: store, search, recall

vision_tool(action, question, path, text)
  Actions: screenshot, analyze, ocr, detect_elements, find_text

WORKSPACE: {workspace}
Current workspace contents:
{workspace_listing}

CRITICAL RULES:
1. WRITE FIRST — Your first action must be coding_tool(write_code) or file_ops_tool(write_file). Do NOT start with list_dir, search, or read_file.
2. BUILD FULL PATHS — use {workspace}/subfolder/filename as the path.
3. DO NOT SEARCH for existing code. The task tells you what to write. Write it from scratch.
4. DO NOT READ source files (stm.py, ltm.py, knowledge_graph.py etc.) to learn API signatures. The tool APIs are documented above.
5. For execute_code with Python, pass code= containing the Python source.
6. For write_file, content MUST be a string.
7. When done, respond with a plain-text summary (no tool calls).
8. When a task mentions "from step_N", proceed with your best knowledge — do NOT search for step_N files.
9. Keep responses SHORT. Output ONE tool call at a time.
10. STM is IN-MEMORY only. Generate timestamps with datetime.now() in coding_tool.
11. To update LTM use ltm_tool. To update KG use kg_tool.
12. To RUN or DEPLOY a Python script, use coding_tool(action="execute_code", code="<paste or inline the full script source>"). Do NOT just read_file the script and stop — read_file only returns text, it does NOT execute anything.
13. When told to "launch", "run", or "execute" tasks from previous steps, use file_ops_tool(read_file) to get the EXISTING script content, then pass that content to coding_tool(action="execute_code", code=<script content>). Do NOT write a new simulation or placeholder script. Run the ACTUAL code that was already created.
14. After writing a script file, ALWAYS execute it in the SAME turn using coding_tool(action="execute_code"). Do NOT mark the task as done until execution succeeds. Writing a file is NOT the same as running it.
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
    from agent.graph.tools import coding_tool, file_ops_tool, memory_tool, vision_tool, ltm_tool, kg_tool

    app_config = config.get("configurable", {}).get("app_config", {})
    tools = [coding_tool, file_ops_tool, memory_tool, vision_tool, ltm_tool, kg_tool]

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
                non_productive_rounds = 0  # Reset when agent actually writes/executes

            for tc in tc_list:
                name = tc.get("name", "")
                args = tc.get("args", {})
                tc_id = tc.get("id", f"call_{round_num}_{name}")

                # HARD BLOCK: After 4 non-productive (read-only) rounds, block ALL read-only actions
                if non_productive_rounds >= 4 and name == "file_ops_tool" and args.get("action") in READ_ONLY_ACTIONS:
                    result_str = (
                        "BLOCKED: You have spent " + str(non_productive_rounds) + " rounds on read-only operations "
                        "(list_dir/search/read_file) without writing ANY code. "
                        "STOP exploring. WRITE the code NOW using coding_tool(action='write_code') "
                        "or coding_tool(action='execute_code'). The task tells you what to create — create it."
                    )
                    logger.warning(f"Blocked non-productive round {non_productive_rounds}: {name}({args.get('action', '?')})")
                else:
                    result_str = await _execute_single_tool(name, args, tool_map)

                tool_results[f"coder_{name}_r{round_num}"] = result_str
                messages.append(ToolMessage(content=result_str, tool_call_id=tc_id))

            # After 4+ non-productive rounds, inject a strong redirect
            if non_productive_rounds >= 4:
                messages.append(HumanMessage(
                    content="STOP all read-only operations (list_dir, search, read_file). "
                            "You have wasted " + str(non_productive_rounds) + " rounds without writing code. "
                            "WRITE the code NOW. Use coding_tool(action='write_code', path='...', code='...') "
                            "to create the file the task asks for. Do NOT call any more read-only tools."
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
