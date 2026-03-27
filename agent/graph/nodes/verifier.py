"""
Verifier Node — Post-change verification.

Runs compile/lint/test checks after the coder finishes editing files.
If errors are found, routes back to coder for 1 retry attempt.
If clean, proceeds to completion.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from agent.graph.state import AgentState

logger = logging.getLogger("graph.nodes.verifier")

# Max time for any single verification command
VERIFY_TIMEOUT = 30


def _detect_project_types(cwd: str, modified_files: List[str] = None) -> Set[str]:
    """Detect project types from file extensions and config files."""
    types = set()

    # Check config files
    config_checks = {
        "package.json": "node",
        "tsconfig.json": "typescript",
        "pyproject.toml": "python",
        "setup.py": "python",
        "requirements.txt": "python",
        "Cargo.toml": "rust",
        "go.mod": "go",
    }

    for config_file, proj_type in config_checks.items():
        if os.path.isfile(os.path.join(cwd, config_file)):
            types.add(proj_type)

    # Check from modified files
    if modified_files:
        ext_map = {
            ".py": "python",
            ".js": "node",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
        }
        for f in modified_files:
            ext = os.path.splitext(f)[1].lower()
            if ext in ext_map:
                types.add(ext_map[ext])

    return types or {"python"}  # Default to python


def _get_modified_files(state: AgentState) -> List[str]:
    """Extract list of files that were modified by the coder."""
    modified = []
    originals = state.get("original_file_contents", {})
    if originals:
        modified.extend(originals.keys())

    # Also check tool results for write/edit operations
    tool_results = state.get("tool_results", {})
    for key, val in tool_results.items():
        if any(op in key for op in ("write", "edit", "multi_edit")):
            # Try to extract file path from the result
            if isinstance(val, str) and ("/" in val or "\\" in val):
                # Rough heuristic — extract path-like strings
                for word in val.split():
                    if ("/" in word or "\\" in word) and "." in word:
                        cleaned = word.strip("'\"(),")
                        if os.path.isfile(cleaned):
                            modified.append(cleaned)

    return list(set(modified))


async def _run_check(cmd: str, cwd: str) -> Dict[str, Any]:
    """Run a single verification command with timeout."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=VERIFY_TIMEOUT,
        )
        return {
            "command": cmd,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[:3000],
            "stderr": stderr.decode("utf-8", errors="replace")[:3000],
            "success": proc.returncode == 0,
        }
    except asyncio.TimeoutError:
        return {
            "command": cmd,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {VERIFY_TIMEOUT}s",
            "success": False,
        }
    except Exception as e:
        return {
            "command": cmd,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False,
        }


async def verifier_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Verify that code changes are valid by running compile/lint/test checks."""

    cwd = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    modified_files = _get_modified_files(state)
    project_types = _detect_project_types(cwd, modified_files)

    # Broadcast progress
    broadcast_fn = config.get("configurable", {}).get("broadcast_fn")
    if broadcast_fn:
        try:
            broadcast_fn("step", "system", "🔍 Verifying changes...", None)
        except Exception:
            pass

    checks = []

    # ── Python checks ──
    if "python" in project_types:
        py_files = [f for f in modified_files if f.endswith(".py")]
        for pyf in py_files[:10]:  # Limit to 10 files
            if os.path.isfile(pyf):
                checks.append(f'python -m py_compile "{pyf}"')

    # ── TypeScript checks ──
    if "typescript" in project_types:
        tsconfig = os.path.join(cwd, "tsconfig.json")
        if os.path.isfile(tsconfig):
            checks.append("npx tsc --noEmit --pretty 2>&1 | head -50")

    # ── Node.js checks ──
    if "node" in project_types and "typescript" not in project_types:
        pkg = os.path.join(cwd, "package.json")
        if os.path.isfile(pkg):
            # Check if there's a lint script
            try:
                import json
                with open(pkg) as f:
                    pkg_data = json.load(f)
                scripts = pkg_data.get("scripts", {})
                if "lint" in scripts:
                    checks.append("npm run lint 2>&1 | head -30")
            except Exception:
                pass

    # ── Rust checks ──
    if "rust" in project_types:
        checks.append("cargo check 2>&1 | head -30")

    # ── Go checks ──
    if "go" in project_types:
        checks.append("go build ./... 2>&1 | head -30")

    if not checks:
        logger.info("No verification checks applicable. Passing through.")
        return {
            "phase": "complete",
            "is_finished": True,
            "audit_log": [{
                "node": "verifier",
                "action": "skip",
                "reason": "no_applicable_checks",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    # Run all checks in parallel
    logger.info(f"Running {len(checks)} verification check(s)...")
    results = await asyncio.gather(*[_run_check(cmd, cwd) for cmd in checks])

    # Analyze results
    failures = [r for r in results if not r["success"]]
    successes = [r for r in results if r["success"]]

    logger.info(f"Verification: {len(successes)} passed, {len(failures)} failed")

    if broadcast_fn:
        try:
            if failures:
                broadcast_fn("step", "system", f"⚠️ {len(failures)} check(s) failed — retrying fix...", None)
            else:
                broadcast_fn("step", "system", f"✅ All {len(successes)} check(s) passed", None)
        except Exception:
            pass

    if failures:
        # Build error summary for the coder to fix
        error_summary = "VERIFICATION FAILED — fix these errors:\n\n"
        for f in failures:
            error_summary += f"Command: {f['command']}\n"
            if f["stderr"]:
                error_summary += f"Error:\n{f['stderr'][:1000]}\n"
            if f["stdout"]:
                error_summary += f"Output:\n{f['stdout'][:500]}\n"
            error_summary += "\n---\n"

        # Check if this is already a retry (prevent infinite loops)
        verification_retries = sum(
            1 for entry in state.get("audit_log", [])
            if entry.get("node") == "verifier" and entry.get("action") == "failed"
        )

        if verification_retries >= 1:
            # Already retried once — accept and finish
            logger.warning("Verification failed after retry. Accepting with warnings.")
            return {
                "phase": "complete",
                "is_finished": True,
                "messages": [AIMessage(content=f"⚠️ Changes applied but verification found issues:\n\n{error_summary}")],
                "audit_log": [{
                    "node": "verifier",
                    "action": "failed_final",
                    "failures": len(failures),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            }

        # First failure — route back to coder for fix
        return {
            "phase": "verification_failed",
            "is_finished": False,
            "messages": [AIMessage(content=f"🔧 **Verification found errors.** Fixing automatically...\n\n{error_summary}")],
            "error": error_summary[:500],
            "audit_log": [{
                "node": "verifier",
                "action": "failed",
                "failures": len(failures),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }],
        }

    # All passed!
    return {
        "phase": "complete",
        "is_finished": True,
        "messages": [AIMessage(content=f"✅ All {len(successes)} verification check(s) passed.")],
        "audit_log": [{
            "node": "verifier",
            "action": "passed",
            "checks_run": len(results),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }
