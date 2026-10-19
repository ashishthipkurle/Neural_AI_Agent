"""
INDRA OS — Coding Agent Worker

A Claude-Code-style coding agent that can write files, run commands,
iterate on errors, and build entire projects. Uses an LLM-driven
Plan → Code → Test → Fix → Verify loop.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from agents.base_agent import BaseAgent
from agents.task import Task, TaskResult

logger = logging.getLogger("Agent.Coding")

_STRONG_SIGNALS = [
    "write code", "create a script", "build a", "code a",
    "fix this code", "debug", "python script", "javascript",
    "create a website", "create a project", "write a function",
    "refactor", "html", "css", "react", "node", "flask",
    "django", "api", "database", "sql", "write a program",
    "make a bot", "create an app", "fix the bug",
]

_MEDIUM_SIGNALS = [
    "code", "program", "script", "function", "class",
    "compile", "run", "test", "deploy", "git",
    "import", "install package", "npm", "pip",
]

MAX_FIX_ITERATIONS = 5
WORKSPACE_DIR = Path("d:/All Projects/My AI Agent/workspace")


class CodingWorker(BaseAgent):
    """
    Coding agent with iterative code-write-test-fix loop.
    Inspired by Claude Code / Agentic coding tools.
    """

    def __init__(self, llm_func=None, speak_func=None):
        super().__init__(
            name="coding",
            description="Write code, fix bugs, create projects, run tests, and build applications",
            capabilities=[
                "write_code", "fix_bug", "create_project", "run_tests",
                "explain_code", "refactor", "create_file", "edit_file",
                "run_command", "git_operations",
            ],
        )
        self._llm = llm_func
        self._speak = speak_func

    async def can_handle(self, task_description: str) -> float:
        lower = task_description.lower().strip()
        if any(s in lower for s in _STRONG_SIGNALS):
            return 0.92
        if any(s in lower for s in _MEDIUM_SIGNALS):
            return 0.65
        return 0.1

    async def execute(self, task: Task) -> TaskResult:
        """Execute a coding task with the iterative loop."""
        steps_taken = []
        artifacts = []

        try:
            if self._speak:
                self._speak("On it, sir. Let me work on the code.")

            # Step 1: Analyze the request and plan
            await self.publish_progress(0.1, "Analyzing request...", 0, 4)
            plan = await self._plan(task.description)
            steps_taken.append(f"Plan: {json.dumps(plan, indent=2)[:200]}")

            # Step 2: Read existing files if referenced
            await self.publish_progress(0.2, "Reading context...", 1, 4)
            context = await self._gather_context(task.description, plan)

            # Step 3: Generate code
            await self.publish_progress(0.4, "Writing code...", 2, 4)
            code_result = await self._generate_code(task.description, plan, context)

            if not code_result:
                return TaskResult(
                    task_id=task.id, success=False,
                    output="Failed to generate code",
                    error="LLM returned empty response",
                    steps_taken=steps_taken,
                )

            # Step 4: Write files
            files_written = await self._write_files(code_result)
            artifacts.extend(files_written)
            steps_taken.append(f"Wrote {len(files_written)} files: {files_written}")

            # Step 5: Run & iterate if there's a runnable component
            if plan.get("run_command"):
                await self.publish_progress(0.6, "Testing code...", 3, 4)
                run_success, run_output = await self._run_and_fix(
                    plan["run_command"], code_result, task.description
                )
                steps_taken.append(
                    f"Run result: {'success' if run_success else 'failed'}"
                )
                if not run_success:
                    steps_taken.append(f"Last output: {run_output[:200]}")

            await self.publish_progress(1.0, "Done", 4, 4)

            if self._speak:
                self._speak(
                    f"Done, sir. I've written {len(files_written)} files."
                )

            return TaskResult(
                task_id=task.id, success=True,
                output=f"Created {len(files_written)} files: {', '.join(f.split('/')[-1] for f in files_written)}",
                artifacts=artifacts,
                steps_taken=steps_taken,
            )

        except Exception as e:
            logger.error(f"Coding agent error: {e}", exc_info=True)
            return TaskResult(
                task_id=task.id, success=False,
                output="Coding task failed",
                error=str(e),
                steps_taken=steps_taken,
            )

    async def _plan(self, description: str) -> dict:
        """Use LLM to plan the coding task."""
        if not self._llm:
            return {"files": [{"path": "output.py", "purpose": "main"}], "language": "python"}

        prompt = f"""You are a senior software engineer. Plan this coding task:

Task: "{description}"

Respond with ONLY valid JSON:
{{
    "files": [
        {{"path": "relative/path/filename.ext", "purpose": "what this file does"}}
    ],
    "language": "python",
    "project_dir": "project_name",
    "run_command": "python main.py",
    "dependencies": ["package1", "package2"],
    "description": "brief summary of what we're building"
}}

JSON:"""

        try:
            response = await self._llm(prompt)
            response = response.strip()
            if "```" in response:
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
                response = response.split("```")[0]
            return json.loads(response)
        except Exception as e:
            logger.warning(f"Planning failed: {e}")
            return {"files": [{"path": "output.py", "purpose": "main"}], "language": "python"}

    async def _gather_context(self, description: str, plan: dict) -> str:
        """Read existing files mentioned in the task for context."""
        context_parts = []

        # Check if task references existing files
        for file_info in plan.get("files", []):
            path = file_info.get("path", "")
            full_path = WORKSPACE_DIR / plan.get("project_dir", "") / path
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding="utf-8", errors="ignore")
                    if len(content) < 5000:
                        context_parts.append(
                            f"=== Existing file: {path} ===\n{content}\n"
                        )
                except Exception:
                    pass

        return "\n".join(context_parts) if context_parts else ""

    async def _generate_code(self, description: str, plan: dict, context: str) -> Optional[dict]:
        """Generate code using LLM."""
        if not self._llm:
            return None

        files_spec = json.dumps(plan.get("files", []), indent=2)
        context_block = f"\n\nExisting code context:\n{context}" if context else ""

        prompt = f"""You are an expert programmer. Write the code for this task.

Task: "{description}"
Language: {plan.get('language', 'python')}
Files to create: {files_spec}
{context_block}

Return your response as a JSON object with file contents:
{{
    "files": {{
        "path/to/file1.py": "file content here...",
        "path/to/file2.py": "file content here..."
    }}
}}

Write complete, production-quality code. No placeholders or TODOs.
JSON response:"""

        try:
            response = await self._llm(prompt)
            response = response.strip()
            if "```" in response:
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
                response = response.split("```")[0]
            return json.loads(response)
        except Exception as e:
            logger.warning(f"Code generation failed: {e}")
            return None

    async def _write_files(self, code_result: dict) -> list[str]:
        """Write generated code to disk."""
        files_written = []
        files = code_result.get("files", {})

        for rel_path, content in files.items():
            full_path = WORKSPACE_DIR / rel_path
            try:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")
                files_written.append(str(full_path))
                logger.info(f"Wrote: {full_path}")
            except Exception as e:
                logger.error(f"Failed to write {full_path}: {e}")

        return files_written

    async def _run_and_fix(self, run_command: str, code_result: dict, description: str) -> tuple[bool, str]:
        """
        Run the code, and if it fails, feed the error back to the LLM
        to fix it. Iterate up to MAX_FIX_ITERATIONS times.
        """
        last_output = ""

        for iteration in range(MAX_FIX_ITERATIONS):
            logger.info(f"Run attempt {iteration + 1}/{MAX_FIX_ITERATIONS}")

            try:
                result = subprocess.run(
                    run_command, shell=True,
                    capture_output=True, text=True,
                    timeout=30, cwd=str(WORKSPACE_DIR),
                )
                last_output = result.stdout + result.stderr

                if result.returncode == 0:
                    logger.info("Code ran successfully")
                    return True, last_output

                # Error — try to fix
                logger.info(f"Run failed (exit {result.returncode}), attempting fix...")

                if not self._llm or iteration >= MAX_FIX_ITERATIONS - 1:
                    break

                await self.publish_progress(
                    0.6 + (iteration * 0.08),
                    f"Fixing error (attempt {iteration + 1})...",
                    3, 4
                )

                fix_prompt = f"""The code I wrote has an error. Fix it.

Original task: "{description}"
Error output:
{last_output[:2000]}

Current code:
{json.dumps(code_result.get('files', {}), indent=2)[:3000]}

Return the FIXED code as JSON:
{{"files": {{"path/to/file.py": "fixed content..."}}}}

JSON:"""

                fix_response = await self._llm(fix_prompt)
                fix_response = fix_response.strip()
                if "```" in fix_response:
                    fix_response = fix_response.split("```")[1]
                    if fix_response.startswith("json"):
                        fix_response = fix_response[4:]
                    fix_response = fix_response.split("```")[0]

                fixed = json.loads(fix_response)
                code_result["files"].update(fixed.get("files", {}))
                await self._write_files(fixed)

            except subprocess.TimeoutExpired:
                last_output = "Command timed out after 30 seconds"
                break
            except Exception as e:
                last_output = str(e)
                break

        return False, last_output
