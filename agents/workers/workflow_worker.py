"""
INDRA OS — Workflow Automater Agent Worker

Creates, manages, and executes automated workflows like n8n/Zapier but locally.
Converts natural language descriptions into executable workflow definitions
with scheduling, triggers, and multi-step pipelines.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agents.base_agent import BaseAgent
from agents.task import Task, TaskResult

logger = logging.getLogger("Agent.Workflow")

WORKFLOWS_DIR = Path("d:/All Projects/My AI Agent/data/workflows")
WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)

_STRONG_SIGNALS = [
    "automate", "workflow", "schedule", "every morning",
    "every day", "every hour", "recurring", "trigger",
    "automatically", "cron", "when i get", "set up a",
    "run daily", "run weekly", "batch",
    "pipeline", "chain", "sequence",
]

_MEDIUM_SIGNALS = [
    "repeat", "routine", "periodic", "regular",
    "backup", "sync", "monitor", "alert when",
    "notify me", "check every",
]


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    action: str              # open_url, run_command, send_email, etc.
    params: dict = field(default_factory=dict)
    description: str = ""
    on_error: str = "continue"  # continue, abort, retry


@dataclass
class Workflow:
    """A complete automated workflow."""
    id: str
    name: str
    description: str
    trigger: str             # manual, cron:*/5 * * * *, on_file_change:/path
    steps: list[WorkflowStep] = field(default_factory=list)
    variables: dict = field(default_factory=dict)
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_run: Optional[str] = None
    run_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger": self.trigger,
            "steps": [{"action": s.action, "params": s.params, "description": s.description} for s in self.steps],
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "run_count": self.run_count,
        }


class WorkflowWorker(BaseAgent):
    """
    Workflow automation agent. Creates and runs multi-step workflows
    from natural language descriptions.
    """

    def __init__(self, llm_func=None, speak_func=None, message_bus=None):
        super().__init__(
            name="workflow",
            description="Create and run automated workflows — schedules, pipelines, triggers",
            capabilities=[
                "create_workflow", "run_workflow", "schedule_workflow",
                "list_workflows", "edit_workflow", "delete_workflow",
            ],
        )
        self._llm = llm_func
        self._speak = speak_func
        self._bus = message_bus
        self._workflows: dict[str, Workflow] = {}
        self._scheduled_tasks: dict[str, asyncio.Task] = {}

    async def initialize(self) -> bool:
        """Load saved workflows from disk."""
        try:
            for f in WORKFLOWS_DIR.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    wf = self._dict_to_workflow(data)
                    self._workflows[wf.id] = wf
                except Exception as e:
                    logger.warning(f"Failed to load workflow {f}: {e}")

            logger.info(f"Loaded {len(self._workflows)} workflows")
            self.status = self.status.IDLE
            return True
        except Exception as e:
            logger.error(f"Workflow init error: {e}")
            self.status = self.status.IDLE
            return True

    async def can_handle(self, task_description: str) -> float:
        lower = task_description.lower().strip()
        if any(s in lower for s in _STRONG_SIGNALS):
            return 0.9
        if any(s in lower for s in _MEDIUM_SIGNALS):
            return 0.6
        return 0.05

    async def execute(self, task: Task) -> TaskResult:
        """Handle a workflow task."""
        steps_taken = []

        try:
            intent = self._classify(task.description)
            steps_taken.append(f"Intent: {intent}")

            if intent == "create":
                return await self._create_workflow(task, steps_taken)
            elif intent == "run":
                return await self._run_workflow_by_name(task, steps_taken)
            elif intent == "list":
                return await self._list_workflows(task, steps_taken)
            elif intent == "delete":
                return await self._delete_workflow(task, steps_taken)
            else:
                return await self._create_workflow(task, steps_taken)

        except Exception as e:
            logger.error(f"Workflow agent error: {e}", exc_info=True)
            return TaskResult(
                task_id=task.id, success=False,
                output="Workflow task failed",
                error=str(e), steps_taken=steps_taken,
            )

    def _classify(self, text: str) -> str:
        lower = text.lower()
        if any(w in lower for w in ["list", "show", "what workflows"]):
            return "list"
        if any(w in lower for w in ["delete", "remove"]):
            return "delete"
        if any(w in lower for w in ["run", "execute", "start"]) and any(w in lower for w in ["workflow", "automation"]):
            return "run"
        return "create"

    async def _create_workflow(self, task: Task, steps: list) -> TaskResult:
        """Create a workflow from natural language."""
        if not self._llm:
            return TaskResult(
                task_id=task.id, success=False,
                output="Need LLM to design workflow",
                error="No LLM", steps_taken=steps,
            )

        await self.publish_progress(0.2, "Designing workflow...", 0, 3)

        prompt = f"""Design an automation workflow for this request:
"{task.description}"

Return as JSON:
{{
    "name": "short_name",
    "description": "what it does",
    "trigger": "manual" or "cron:0 9 * * *" (cron expression),
    "steps": [
        {{
            "action": "run_command|open_url|write_file|notify|wait|delegate_to_agent",
            "params": {{"command": "...", "url": "...", "path": "...", "text": "...", "seconds": 5, "agent": "...", "task": "..."}},
            "description": "what this step does"
        }}
    ]
}}

Available actions:
- run_command: execute a shell command (params: command)
- open_url: open a URL in browser (params: url)
- write_file: write content to file (params: path, content)
- read_file: read a file (params: path)
- notify: send notification to user via TTS (params: text)
- wait: pause for seconds (params: seconds)
- delegate_to_agent: ask another INDRA agent to do something (params: agent, task)

JSON:"""

        try:
            response = await self._llm(prompt)
            response = response.strip()
            if "```" in response:
                response = response.split("```")[1].replace("json", "").split("```")[0]
            wf_data = json.loads(response)

            # Create workflow object
            import uuid
            wf = Workflow(
                id=uuid.uuid4().hex[:8],
                name=wf_data.get("name", "unnamed"),
                description=wf_data.get("description", task.description),
                trigger=wf_data.get("trigger", "manual"),
                steps=[
                    WorkflowStep(
                        action=s.get("action", "notify"),
                        params=s.get("params", {}),
                        description=s.get("description", ""),
                    )
                    for s in wf_data.get("steps", [])
                ],
            )

            # Save
            self._workflows[wf.id] = wf
            self._save_workflow(wf)
            steps.append(f"Created workflow: {wf.name} ({len(wf.steps)} steps)")

            await self.publish_progress(0.6, "Workflow created", 1, 3)

            # Run it immediately if trigger is manual
            if wf.trigger == "manual":
                await self.publish_progress(0.7, "Running workflow...", 2, 3)
                run_result = await self._execute_workflow(wf)
                steps.extend(run_result)

            if self._speak:
                self._speak(
                    f"Workflow '{wf.name}' created with {len(wf.steps)} steps, sir. "
                    f"Trigger: {wf.trigger}."
                )

            await self.publish_progress(1.0, "Done", 3, 3)
            return TaskResult(
                task_id=task.id, success=True,
                output=f"Workflow '{wf.name}' created: {wf.description}",
                steps_taken=steps,
            )

        except Exception as e:
            return TaskResult(
                task_id=task.id, success=False,
                output="Failed to create workflow",
                error=str(e), steps_taken=steps,
            )

    async def _execute_workflow(self, wf: Workflow) -> list[str]:
        """Execute all steps of a workflow."""
        results = []
        wf.last_run = datetime.utcnow().isoformat()
        wf.run_count += 1

        for i, step in enumerate(wf.steps):
            try:
                result = await self._execute_step(step)
                results.append(f"[OK] Step {i+1}: {step.description} -> {result[:100]}")
            except Exception as e:
                results.append(f"[FAIL] Step {i+1}: {step.description} -> ERROR: {e}")
                if step.on_error == "abort":
                    break

        self._save_workflow(wf)
        return results

    async def _execute_step(self, step: WorkflowStep) -> str:
        """Execute a single workflow step."""
        action = step.action
        params = step.params

        if action == "run_command":
            result = subprocess.run(
                params.get("command", "echo hello"),
                shell=True, capture_output=True, text=True, timeout=60,
            )
            return result.stdout[:500] or result.stderr[:500]

        elif action == "open_url":
            os.startfile(params.get("url", "https://google.com"))
            return "Opened URL"

        elif action == "write_file":
            path = Path(params.get("path", "output.txt"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(params.get("content", ""), encoding="utf-8")
            return f"Wrote to {path}"

        elif action == "read_file":
            path = Path(params.get("path", ""))
            if path.exists():
                return path.read_text(encoding="utf-8", errors="ignore")[:1000]
            return "File not found"

        elif action == "notify":
            text = params.get("text", "Workflow step completed")
            if self._speak:
                self._speak(text)
            return f"Notified: {text}"

        elif action == "wait":
            secs = int(params.get("seconds", 5))
            await asyncio.sleep(secs)
            return f"Waited {secs}s"

        elif action == "delegate_to_agent":
            # This would use the message bus to delegate
            return f"Delegated to {params.get('agent', '?')}: {params.get('task', '?')}"

        else:
            return f"Unknown action: {action}"

    async def _list_workflows(self, task: Task, steps: list) -> TaskResult:
        if not self._workflows:
            msg = "No workflows created yet, sir."
            if self._speak:
                self._speak(msg)
            return TaskResult(task_id=task.id, success=True, output=msg, steps_taken=steps)

        lines = [f"You have {len(self._workflows)} workflows:\n"]
        for wf in self._workflows.values():
            status = "enabled" if wf.enabled else "disabled"
            lines.append(
                f"  - {wf.name} ({status}) -- {wf.description} "
                f"[trigger: {wf.trigger}, runs: {wf.run_count}]"
            )
        output = "\n".join(lines)
        if self._speak:
            self._speak(f"You have {len(self._workflows)} workflows, sir.")
        return TaskResult(task_id=task.id, success=True, output=output, steps_taken=steps)

    async def _run_workflow_by_name(self, task: Task, steps: list) -> TaskResult:
        # Find workflow by name match
        name_lower = task.description.lower()
        for wf in self._workflows.values():
            if wf.name.lower() in name_lower:
                results = await self._execute_workflow(wf)
                steps.extend(results)
                return TaskResult(
                    task_id=task.id, success=True,
                    output=f"Workflow '{wf.name}' executed ({wf.run_count} total runs)",
                    steps_taken=steps,
                )
        return TaskResult(
            task_id=task.id, success=False,
            output="Workflow not found", error="No matching workflow",
            steps_taken=steps,
        )

    async def _delete_workflow(self, task: Task, steps: list) -> TaskResult:
        name_lower = task.description.lower()
        for wf_id, wf in list(self._workflows.items()):
            if wf.name.lower() in name_lower:
                del self._workflows[wf_id]
                (WORKFLOWS_DIR / f"{wf_id}.json").unlink(missing_ok=True)
                return TaskResult(
                    task_id=task.id, success=True,
                    output=f"Deleted workflow '{wf.name}'",
                    steps_taken=steps,
                )
        return TaskResult(
            task_id=task.id, success=False,
            output="Workflow not found", steps_taken=steps,
        )

    def _save_workflow(self, wf: Workflow):
        path = WORKFLOWS_DIR / f"{wf.id}.json"
        path.write_text(json.dumps(wf.to_dict(), indent=2), encoding="utf-8")

    def _dict_to_workflow(self, data: dict) -> Workflow:
        return Workflow(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            trigger=data.get("trigger", "manual"),
            steps=[
                WorkflowStep(
                    action=s.get("action", "notify"),
                    params=s.get("params", {}),
                    description=s.get("description", ""),
                )
                for s in data.get("steps", [])
            ],
            enabled=data.get("enabled", True),
            created_at=data.get("created_at", ""),
            last_run=data.get("last_run"),
            run_count=data.get("run_count", 0),
        )
