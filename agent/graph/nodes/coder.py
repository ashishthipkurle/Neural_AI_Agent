"""
Coder Agent Node — Autonomous Claude Code Implementation.

Single intelligent agent. No subagent routing. No plan mode.
Handles everything: questions, code tasks, explanations, refactors.
Uses the compact/full Claude Code prompt + 16 tools + multi-turn loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables.config import RunnableConfig
from pydantic import ValidationError

from agent.graph.state import AgentState

logger = logging.getLogger("graph.nodes.coder")

MAX_TOOL_ROUNDS = 100

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
from agent.graph.nodes.coder_prompts import (
    CODER_PROMPT, CODER_PROMPT_COMPACT, COMPACT_PROMPT,
)


# ---------------------------------------------------------------------------
# Directory Tree (capped at 50 entries)
# ---------------------------------------------------------------------------
def _get_directory_tree(cwd: str, max_depth: int = 2, max_entries: int = 50) -> str:
    tree = []
    ignores = {".git", "node_modules", "__pycache__", "venv", ".venv", ".idea", ".vscode",
               "dist", "build", ".gradle", ".next", "coverage", ".cache"}
    skip_ext = {".pyc", ".class", ".o", ".so", ".dll", ".exe", ".png", ".jpg", ".jpeg",
                ".gif", ".ico", ".svg", ".mp4", ".mp3", ".woff", ".ttf", ".eot"}
    count = 0

    for root, dirs, files in os.walk(cwd):
        dirs[:] = sorted([d for d in dirs if d not in ignores and not d.startswith('.')])
        level = root.replace(cwd, "").strip(os.sep).count(os.sep)
        if root == cwd:
            level = 0
        else:
            level += 1
        if level > max_depth:
            continue

        indent = "  " * level
        folder = os.path.basename(root) or os.path.basename(cwd)
        tree.append(f"{indent}{folder}/")
        count += 1
        if count >= max_entries:
            tree.append("  ...[truncated]")
            break

        subindent = "  " * (level + 1)
        for f in sorted(files):
            if not f.startswith('.') and Path(f).suffix.lower() not in skip_ext:
                tree.append(f"{subindent}{f}")
                count += 1
                if count >= max_entries:
                    break
        if count >= max_entries:
            tree.append(f"{subindent}...[truncated]")
            break

    return "\n".join(tree)


# ---------------------------------------------------------------------------
# Git & CLAUDE.md helpers
# ---------------------------------------------------------------------------
def _get_git_info(cwd: str) -> dict:
    info = {
        "is_git_repo": False, "current_branch": "N/A", "main_branch": "main",
        "git_status": "N/A", "recent_commits": "N/A"
    }
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                       cwd=cwd, capture_output=True, check=True, timeout=5)
        info["is_git_repo"] = True
        info["current_branch"] = subprocess.run(
            ["git", "branch", "--show-current"], cwd=cwd, capture_output=True, text=True, timeout=5
        ).stdout.strip() or "detached"
        info["git_status"] = subprocess.run(
            ["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, timeout=5
        ).stdout.strip()[:500] or "(clean)"
        info["recent_commits"] = subprocess.run(
            ["git", "log", "--oneline", "-5"], cwd=cwd, capture_output=True, text=True, timeout=5
        ).stdout.strip()[:500] or "(no commits)"
    except:
        pass
    return info


def _read_claude_md(cwd: str) -> str:
    for name in ["CLAUDE.md", ".claude/CLAUDE.md"]:
        path = os.path.join(cwd, name)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()[:3000]
            except:
                pass
    return ""


# ---------------------------------------------------------------------------
# LLM invoke with retry
# ---------------------------------------------------------------------------
async def _llm_invoke_safe(llm, messages, retries=3):
    for attempt in range(retries):
        try:
            return await llm.ainvoke(messages)
        except Exception as e:
            if attempt == retries - 1:
                raise
            logger.warning(f"LLM invoke failed (attempt {attempt+1}): {e}")
            await asyncio.sleep(2 ** attempt)


# ---------------------------------------------------------------------------
# Tool Call Parser (handles markdown JSON, XML tags, bare JSON)
# ---------------------------------------------------------------------------
def _parse_json_tool_calls(text: str) -> List[Dict]:
    calls = []

    # Pattern 1: ```json ... ``` blocks
    for block in re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL):
        try:
            parsed = json.loads(block)
            if "name" in parsed:
                args = parsed.get("arguments", parsed.get("args", parsed.get("parameters", {})))
                if isinstance(args, str):
                    try: args = json.loads(args)
                    except: args = {}
                calls.append({"name": parsed["name"], "args": args, "id": parsed.get("id", f"parsed_{parsed['name']}")})
        except: pass

    # Pattern 2: <tool_call> XML tags
    for block in re.findall(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', text, re.DOTALL):
        try:
            parsed = json.loads(block)
            if "name" in parsed:
                args = parsed.get("arguments", parsed.get("args", parsed.get("parameters", {})))
                if isinstance(args, str):
                    try: args = json.loads(args)
                    except: args = {}
                calls.append({"name": parsed["name"], "args": args, "id": parsed.get("id", f"parsed_{parsed['name']}")})
        except: pass

    # Pattern 3: Brute-force balanced bracket extraction
    if not calls:
        idx = 0
        while idx < len(text):
            start = text.find('{', idx)
            if start == -1:
                break
            braces = 0
            end = -1
            in_string = False
            escape = False
            for i in range(start, len(text)):
                char = text[i]
                if escape:
                    escape = False
                    continue
                if char == '\\':
                    escape = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if char == '{':
                        braces += 1
                    elif char == '}':
                        braces -= 1
                        if braces == 0:
                            end = i + 1
                            break
            if end != -1:
                block = text[start:end]
                try:
                    parsed = json.loads(block)
                    if isinstance(parsed, dict) and "name" in parsed:
                        args = parsed.get("arguments", parsed.get("args", parsed.get("parameters", {})))
                        if isinstance(args, str):
                            try: args = json.loads(args)
                            except: args = {}
                        calls.append({"name": parsed["name"], "args": args, "id": parsed.get("id", f"parsed_{parsed['name']}")})
                except:
                    pass
                idx = start + 1
            else:
                idx = start + 1

    return calls


# ---------------------------------------------------------------------------
# Bash prefix extractor (fast regex, no LLM)
# ---------------------------------------------------------------------------
def _extract_bash_prefix(command: str) -> str:
    cmd = command.strip()
    injection_patterns = [r'\$\(', r'`.*`', r'\|\|', r'&&', r';', r'\n', r'\|']
    for pattern in injection_patterns:
        if re.search(pattern, cmd):
            if pattern in (r'\$\(', r'`.*`'):
                return "command_injection_detected"
    parts = cmd.split()
    if not parts:
        return "none"
    base = parts[0]
    if base == "git" and len(parts) > 1:
        sub = parts[1]
        return f"git" if sub.startswith("-") else f"git {sub}"
    if base in ("npm", "npx", "yarn", "pnpm") and len(parts) > 1:
        sub = parts[1]
        if sub == "run" and len(parts) > 2:
            return f"{base} run {parts[2]}"
        return f"{base} {sub}"
    if base == "pip" and len(parts) > 1:
        return f"pip {parts[1]}"
    if base == "python" and len(parts) > 1 and parts[1] == "-m" and len(parts) > 2:
        return f"python -m {parts[2]}"
    return base


# ===========================================================================
# CONTEXT COMPACTION (Gap 3)
# ===========================================================================
async def _compact_context(llm, messages: list, round_num: int) -> list:
    """Compress conversation history to preserve context window.

    Keeps: SystemPrompt + compact summary + last 5 messages.
    Uses COMPACT_PROMPT to generate a thorough summary.
    """
    if len(messages) < 10:
        return messages  # Not worth compacting

    # Separate system messages and content
    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    non_system = [m for m in messages if not isinstance(m, SystemMessage)]

    if not non_system:
        return messages

    # Keep last 5 messages as-is (recent context)
    keep_recent = non_system[-5:] if len(non_system) > 5 else non_system
    to_summarize = non_system[:-5] if len(non_system) > 5 else []

    if not to_summarize:
        return messages

    # Build summary request
    summary_text = "\n".join(
        f"[{type(m).__name__}]: {getattr(m, 'content', '')[:300]}"
        for m in to_summarize
    )

    try:
        summary_request = [
            SystemMessage(content=COMPACT_PROMPT),
            HumanMessage(content=f"Summarize this conversation (rounds 1-{round_num}):\n\n{summary_text[:8000]}"),
        ]
        summary_response = await _llm_invoke_safe(llm, summary_request, retries=1)
        compact_text = summary_response.content.strip() if summary_response.content else ""

        if len(compact_text) < 50:
            # Summary too short, keep original
            return messages

        # Rebuild: system + summary + recent messages
        compacted = list(system_msgs)
        compacted.append(HumanMessage(content=f"[CONTEXT SUMMARY — rounds 1-{round_num}]\n\n{compact_text}"))
        compacted.extend(keep_recent)

        logger.info(f"Context compacted: {len(messages)} → {len(compacted)} messages")
        return compacted

    except Exception as e:
        logger.warning(f"Context compaction failed: {e}")
        return messages  # Return original on failure


# ===========================================================================
# MAIN CODER NODE
# ===========================================================================
async def coder_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Autonomous coder agent — handles everything.

    No subagent dispatch. No plan mode. The LLM decides what to do.
    """
    from agent.core.llm_provider import get_llm_with_tools
    from agent.graph.tools import CODER_TOOLS

    app_config = config.get("configurable", {}).get("app_config", {})
    cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    try:
        llm = get_llm_with_tools(app_config, CODER_TOOLS)
    except Exception:
        from agent.core.llm_provider import get_llm
        llm = get_llm(app_config)

    # Build system prompt
    git_info = _get_git_info(cwd)
    claude_md = _read_claude_md(cwd)
    model_name = app_config.get("llm", {}).get("model_name", "local-model")
    directory_tree = _get_directory_tree(cwd)

    is_cloud = "cloud" in model_name.lower() or any(k in model_name.lower() for k in ["gpt", "claude", "gemini"])

    if is_cloud:
        sys_prompt = CODER_PROMPT.format(
            cwd=cwd,
            is_git_repo=git_info["is_git_repo"],
            platform=sys.platform if hasattr(sys, 'platform') else platform.system(),
            os_version=platform.version(),
            date=datetime.now().strftime('%Y/%m/%d'),
            model_name=model_name,
            model_id=model_name,
            current_branch=git_info["current_branch"],
            main_branch=git_info["main_branch"],
            git_status=git_info["git_status"],
            recent_commits=git_info["recent_commits"],
            claude_md=claude_md,
            directory_tree=directory_tree
        )
    else:
        sys_prompt = CODER_PROMPT_COMPACT.format(
            cwd=cwd,
            is_git_repo=git_info["is_git_repo"],
            platform=sys.platform if hasattr(sys, 'platform') else platform.system(),
            date=datetime.now().strftime('%Y/%m/%d'),
            current_branch=git_info["current_branch"],
            git_status=git_info["git_status"],
            claude_md=claude_md,
            directory_tree=directory_tree
        )
        logger.info(f"Using COMPACT prompt for local model '{model_name}'")

    # Get the task and history
    task_desc = state.get("goal", "")
    plan_text = state.get("plan_text")
    existing_messages = state.get("messages", [])

    # Initialize messages with system prompt if not already present
    if not any(isinstance(m, SystemMessage) for m in existing_messages):
        messages = [SystemMessage(content=sys_prompt)]
        if task_desc:
            # If we have an approved plan, inject it as the primary directive
            if plan_text:
                messages.append(HumanMessage(content=(
                    f"TASK: {task_desc}\n\n"
                    f"APPROVED IMPLEMENTATION PLAN — Follow this plan step by step:\n"
                    f"<plan>\n{plan_text}\n</plan>\n\n"
                    f"Execute each step in order. Use the tools to read files first, "
                    f"then make the changes specified in the plan. Verify your changes work."
                )))
            else:
                messages.append(HumanMessage(content=f"TASK: {task_desc}"))
    else:
        messages = list(existing_messages)
        # Ensure latest task is in context if it was updated
        if task_desc and not any(task_desc in getattr(m, 'content', '') for m in reversed(messages)):
             messages.append(HumanMessage(content=f"NEW TASK/UPDATE: {task_desc}"))

    tool_results = dict(state.get("tool_results", {}))
    final_text = ""
    is_finished = False

    # Track starting message count to avoid returning duplicates
    initial_msg_count = len(messages)
    stall_count = 0
    MAX_STALLS = 3
    consecutive_errors = 0
    COMPACTION_INTERVAL = 8  # Compact context every N rounds
    MAX_MESSAGES_BEFORE_COMPACT = 40  # Or when messages exceed this count

    # Get broadcast function for streaming progress
    broadcast_fn = config.get("configurable", {}).get("broadcast_fn")

    def _broadcast(msg: str):
        if broadcast_fn:
            try:
                broadcast_fn("step", "system", msg, None)
            except Exception:
                pass

    # ── Multi-turn Agentic Loop ──
    try:
        for round_num in range(MAX_TOOL_ROUNDS):
            # ── Gap 3: Context Compaction ──
            non_system_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
            if (round_num > 0 and round_num % COMPACTION_INTERVAL == 0) or len(non_system_msgs) > MAX_MESSAGES_BEFORE_COMPACT:
                messages = await _compact_context(llm, messages, round_num)
                logger.info(f"Context compacted at round {round_num}. Messages: {len(messages)}")
                _broadcast(f"📦 Context compacted (round {round_num})")

            response = await _llm_invoke_safe(llm, messages)
            text = response.content.strip() if response.content else ""

            tc_list = getattr(response, "tool_calls", None) or []
            if not tc_list and text:
                tc_list = _parse_json_tool_calls(text)
                if tc_list and hasattr(response, "tool_calls"):
                    # Inject so LangChain serialization knows it issued tools
                    response.tool_calls = tc_list

            messages.append(response)

            if not tc_list:
                # Stalling detection: if no tools AND it looks like it's just describing what it *wants* to do
                stalling_patterns = ["I will", "Let me", "I'll try", "Next, I", "I am going to"]
                if any(p.lower() in text.lower() for p in stalling_patterns) and len(text.split()) < 50:
                    stall_count += 1
                    if stall_count > MAX_STALLS:
                        logger.warning("Coder exceeded max stalling nudges. Breaking loop.")
                        final_text = text or "Agent is stalling without using tools. Please provide more specific instructions or check tool availability."
                        is_finished = True
                        break
                    
                    nudge_msg = (
                        "SYSTEM: You are describing what you intend to do, but you haven't issued any tool calls. "
                        "You MUST use a tool (bash, write_file, read_file, grep_search, etc.) to proceed. "
                        "If you are stuck, perform a search or read a file. Do not just talk."
                    )
                    messages.append(HumanMessage(content=nudge_msg))
                    logger.info(f"Coder stalling detected ({stall_count}/{MAX_STALLS}). Nudging with tool requirement.")
                    continue

                if "```" in text:
                    warning_msg = "SYSTEM: You returned a raw code block instead of using a tool. Please use the `write_file` or `bash` tool to save your changes to disk. Do not reply with conversational text."
                    messages.append(HumanMessage(content=warning_msg))
                    logger.warning("Coder attempted to output raw code block without tools. Injecting warning.")
                    continue
                final_text = text
                is_finished = True
                break

            # ── Gap 4: Streaming Progress ──
            tool_names = [tc.get('name', '?') for tc in tc_list]
            if len(tc_list) > 1:
                _broadcast(f"🔧 Running {len(tc_list)} tools in parallel: {', '.join(tool_names)}")
            else:
                _broadcast(f"🔧 {tool_names[0]}...")

            # Parallel tool execution
            async def run_tool(tc_item: dict) -> ToolMessage:
                name = tc_item.get("name", "")
                args = tc_item.get("args", {})
                tc_id = tc_item.get("id", f"call_{round_num}_{name}")

                tool_func = None
                for t in CODER_TOOLS:
                    if getattr(t, "name", getattr(t, "__name__", str(t))) == name:
                        tool_func = t
                        break

                if not tool_func:
                    result_str = f"Error: Tool '{name}' not found."
                else:
                    try:
                        # State-aware tools
                        if name == "todo_read":
                            # We don't mutate args here just in case, though it's safer to always copy
                            pass
                        elif name == "todo_write":
                            state["todo_list"] = args.get("todos", [])

                        if name == "bash":
                            cmd = args.get("command", "")
                            prefix = _extract_bash_prefix(cmd)
                            if prefix == "command_injection_detected":
                                result_str = "Error: Command contains potential injection. Please use simple commands."
                            else:
                                allowed = state.get("allowed_bash_prefixes", [])
                                if prefix not in allowed and prefix != "none":
                                    logger.info(f"[Bash] Auto-approving prefix '{prefix}'")
                                    if "allowed_bash_prefixes" not in state:
                                        state["allowed_bash_prefixes"] = []
                                    state["allowed_bash_prefixes"].append(prefix)

                                # Enforce 30s timeout for bash
                                if "timeout" not in args:
                                    args["timeout"] = 30000
                                res = await tool_func.ainvoke(args) if hasattr(tool_func, "ainvoke") else tool_func(**args)
                                result_str = str(res)

                                if len(result_str) > 15000:
                                    result_str = result_str[:12000] + "\n\n...[Output truncated at 12000 chars. Use grep/read for specific content.]"
                        elif name in ("write", "edit", "multi_edit", "notebook_edit", "todo_read"):
                            # Direct invocation to pass InjectedState (ainvoke strips it)
                            call_args = dict(args)
                            call_args["state"] = state
                            res = tool_func.func(**call_args) if hasattr(tool_func, "func") else tool_func(**call_args)
                            result_str = str(res)
                        else:
                            if hasattr(tool_func, "ainvoke"):
                                res = await tool_func.ainvoke(args)
                            else:
                                res = tool_func(**args)
                            result_str = str(res)

                    except Exception as exc:
                        result_str = f"Tool Error: {exc}"

                tool_results[f"coder_{name}_r{round_num}"] = result_str
                return ToolMessage(content=result_str, tool_call_id=tc_id)

            tool_msgs = await asyncio.gather(*(run_tool(tc_item) for tc_item in tc_list))

            # ── Gap 5: Error Recovery ──
            error_count_this_round = sum(1 for tm in tool_msgs if "Error" in tm.content[:50])
            if error_count_this_round > 0:
                consecutive_errors += error_count_this_round
            else:
                consecutive_errors = 0  # Reset on success

            for tm in tool_msgs:
                messages.append(tm)

            # If too many consecutive errors, inject recovery prompt
            if consecutive_errors >= 3:
                recovery_msg = (
                    "SYSTEM: Multiple tool calls have failed. Stop and reconsider your approach. "
                    "Read the error messages carefully. Try a different strategy — perhaps read the file "
                    "again, check the correct path, or use a simpler command. "
                    "Do NOT repeat the same failing command."
                )
                messages.append(HumanMessage(content=recovery_msg))
                _broadcast("⚠️ Errors detected — agent is reconsidering approach...")
                consecutive_errors = 0  # Reset after recovery prompt

            logger.info(f"Coder round {round_num + 1}: executed {len(tc_list)} tool(s)")
        else:
            final_text = text or "Max tool rounds reached"
            logger.warning(f"Coder hit max tool rounds ({MAX_TOOL_ROUNDS})")

    except Exception as e:
        final_text = f"Coder error: {e}"
        logger.error(f"Coder failed: {e}")

    # Only return NEW messages to avoid duplication in state
    new_messages = messages[initial_msg_count:]
    if final_text and not new_messages: # fallback if loop broke immediately
        new_messages = [AIMessage(content=final_text)]
        
    return {
        "tool_results": tool_results,
        "messages": new_messages,
        "is_finished": is_finished,
        "audit_log": [{
            "node": "coder",
            "action": "execute",
            "tool_rounds": min(round_num + 1, MAX_TOOL_ROUNDS) if 'round_num' in dir() else 0,
            "is_finished": is_finished,
            "stall_count": stall_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
