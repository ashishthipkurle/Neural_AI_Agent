"""
Planner Node — Scans the project and creates an implementation plan.

READ-ONLY: This node only reads files, searches patterns, and generates a plan.
It does NOT write, edit, or execute any code.
"""

from __future__ import annotations

import logging
import os
import platform
from datetime import datetime, timezone
from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.nodes.planner")

MAX_SCAN_ROUNDS = 15

PLANNER_SYSTEM_PROMPT = """You are a senior software architect. Your job is to analyze a codebase and create a detailed implementation plan.

RULES:
- You are in READ-ONLY mode. You can ONLY read, search, and analyze files.
- You CANNOT create, write, edit, or delete any files.
- You CANNOT run commands that modify the system.
- You CAN use: bash (read-only commands like ls, find, cat, head, git status), glob, grep, read, ls
- You CANNOT use: write, edit, multi_edit, bash (with write/modify commands)

YOUR PROCESS:
1. First, understand what the user wants to accomplish
2. Scan the project structure (use ls and glob to map the codebase)
3. Read the key files that will need to be modified
4. Identify patterns, frameworks, and conventions used
5. Create a step-by-step implementation plan

YOUR PLAN MUST INCLUDE:
- **Summary**: What the task accomplishes (1-2 sentences)
- **Files to Modify**: List each file with what changes are needed
- **Files to Create**: Any new files needed (with purpose)
- **Files to Delete**: Any files to remove (if applicable)
- **Steps**: Numbered implementation steps in order of execution
- **Verification**: How to verify the changes work

FORMAT YOUR PLAN as clear markdown. Be specific — include file paths, function names, and what exactly changes.

When you are done scanning and have your plan ready, call the exit_plan_mode tool with your complete plan.

<env>
Working directory: {cwd}
Platform: {platform}
Date: {date}
</env>

{directory_tree}
"""


def _build_directory_tree(root: str, max_depth: int = 3, max_entries: int = 80) -> str:
    """Build a compact directory tree string for context."""
    lines = []
    count = 0
    skip_dirs = {
        '.git', 'node_modules', '__pycache__', '.next', '.venv', 'venv',
        'dist', 'build', '.cache', '.mypy_cache', '.pytest_cache',
        'egg-info', '.egg-info', '.tox', 'coverage', '.coverage',
    }

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith('.')]

        depth = dirpath.replace(root, '').count(os.sep)
        if depth >= max_depth:
            dirnames.clear()
            continue

        indent = '  ' * depth
        dir_name = os.path.basename(dirpath) or root
        lines.append(f"{indent}{dir_name}/")
        count += 1

        sub_indent = '  ' * (depth + 1)
        for f in sorted(filenames)[:20]:
            if count >= max_entries:
                lines.append(f"{sub_indent}... (truncated)")
                return '\n'.join(lines)
            lines.append(f"{sub_indent}{f}")
            count += 1

    return '\n'.join(lines)


async def planner_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Scan the project and create an implementation plan."""
    from agent.core.llm_provider import get_llm_with_tools
    from agent.graph.tools import glob, grep, ls, read, bash, exit_plan_mode

    logger.info("Planner node: scanning project and creating plan...")

    goal = state.get("goal", "")
    configurable = config.get("configurable", {})
    app_config = configurable.get("app_config", {})

    # Read-only tools for scanning
    read_only_tools = [glob, grep, ls, read, bash, exit_plan_mode]

    try:
        llm_with_tools = get_llm_with_tools(app_config, read_only_tools)
    except Exception:
        from agent.core.llm_provider import get_llm
        llm_raw = get_llm(app_config)
        llm_with_tools = llm_raw.bind_tools(read_only_tools)

    tool_map = {t.name: t for t in read_only_tools}

    cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dir_tree = _build_directory_tree(cwd, max_depth=2, max_entries=60)

    sys_prompt = PLANNER_SYSTEM_PROMPT.format(
        cwd=cwd,
        platform=platform.system(),
        date=datetime.now().strftime("%Y-%m-%d"),
        directory_tree=f"<directory_tree>\n{dir_tree}\n</directory_tree>" if dir_tree else "",
    )

    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content=f"TASK: {goal}\n\nScan the project and create a detailed implementation plan for this task. Use glob, grep, read, and ls to understand the codebase first, then call exit_plan_mode with your plan."),
    ]

    plan_text = None

    try:
        for round_num in range(MAX_SCAN_ROUNDS):
            response = llm_with_tools.invoke(messages)
            text = getattr(response, "content", "") or ""
            tc_list = getattr(response, "tool_calls", []) or []

            messages.append(response)

            if not tc_list:
                # No tools called — check if it contains a plan
                if len(text) > 100:
                    plan_text = text
                break

            for tc in tc_list:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                tool_id = tc.get("id", f"plan_{round_num}")

                # Block write operations in planning mode
                if tool_name in ("write", "edit", "multi_edit"):
                    result_str = "ERROR: Write operations are not allowed in planning mode. Use read-only tools."
                    messages.append(ToolMessage(content=result_str, tool_call_id=tool_id))
                    continue

                # Block destructive bash commands
                if tool_name == "bash":
                    cmd = tool_args.get("command", "")
                    cmd_lower = cmd.lower().strip()
                    destructive_prefixes = ["rm ", "del ", "mkdir ", "echo ", "mv ", "cp ", "npm install", "pip install", "git add", "git commit", "git push"]
                    if any(cmd_lower.startswith(p) for p in destructive_prefixes):
                        result_str = f"ERROR: '{cmd}' is destructive. Planning mode is read-only. Use ls, cat, find, git status, git log instead."
                        messages.append(ToolMessage(content=result_str, tool_call_id=tool_id))
                        continue
                    # Enforce timeout for bash in planning
                    tool_args["timeout"] = min(tool_args.get("timeout", 15000), 15000)

                # Check for exit_plan_mode — this means we have the plan
                if tool_name == "exit_plan_mode":
                    plan_text = tool_args.get("plan", text)
                    result_str = "[PLAN SUBMITTED]"
                    messages.append(ToolMessage(content=result_str, tool_call_id=tool_id))
                    logger.info(f"Planner: plan submitted ({len(plan_text)} chars)")
                    break

                # Execute read-only tool
                try:
                    tool_fn = tool_map.get(tool_name)
                    if tool_fn:
                        # Inject state for tools that need it
                        if tool_name in ("edit", "multi_edit", "write", "exit_plan_mode"):
                            tool_args["state"] = state
                        result = tool_fn.invoke(tool_args)
                        result_str = str(result)[:8000]
                    else:
                        result_str = f"Unknown tool: {tool_name}"
                except Exception as e:
                    result_str = f"Tool error: {e}"

                messages.append(ToolMessage(content=result_str, tool_call_id=tool_id))

            if plan_text:
                break

            logger.info(f"Planner round {round_num + 1}: executed {len(tc_list)} tool(s)")

    except Exception as e:
        logger.error(f"Planner failed: {e}")
        plan_text = f"Planning failed: {e}. The coder will proceed without a plan."

    if not plan_text:
        plan_text = "The planner could not generate a plan. The coder will analyze and implement the task directly."

    logger.info(f"Planner completed. Plan length: {len(plan_text)} chars")

    return {
        "plan_text": plan_text,
        "phase": "awaiting_approval",
        "messages": [AIMessage(content=f"📋 **Implementation Plan**\n\n{plan_text}")],
        "audit_log": [{
            "node": "planner",
            "action": "plan_created",
            "plan_length": len(plan_text),
            "scan_rounds": min(round_num + 1, MAX_SCAN_ROUNDS) if 'round_num' in dir() else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
