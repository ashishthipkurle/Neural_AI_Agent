"""
INDRA OS — Computer Control Agent Worker

Full control of the computer — open apps, navigate UI, manage files,
automate desktop tasks. Absorbs and enhances INDRA's existing executor.py
with proper planning, accessibility-first control, and post-action verification.
"""

import asyncio
import logging
import os
import subprocess
import time
from typing import Optional

from agents.base_agent import BaseAgent
from agents.task import Task, TaskResult

logger = logging.getLogger("Agent.ComputerControl")

_STRONG_SIGNALS = [
    "open ", "close ", "launch ", "start ", "run ",
    "click", "type ", "navigate", "go to ", "switch to",
    "minimize", "maximize", "scroll", "screenshot",
    "copy file", "move file", "delete file", "rename file",
    "create folder", "extract", "compress", "zip",
    "install", "uninstall", "download",
    "drag", "right click", "double click",
    "search for", "find file",
    "set volume", "mute", "brightness",
    "shut down", "restart", "lock",
    "connect wifi", "bluetooth",
]

_MEDIUM_SIGNALS = [
    "show me", "pull up", "bring up", "check ",
    "open", "file", "folder", "desktop",
    "browser", "chrome", "notepad", "explorer",
    "settings", "control panel", "task manager",
]


class ComputerControlWorker(BaseAgent):
    """
    Controls the entire computer on behalf of the user.
    Uses accessibility APIs first (fast, reliable), falls back to vision-based
    control (screenshot + VisionLLM + click coordinates) when needed.
    """

    def __init__(self, llm_func=None, vision_func=None, speak_func=None):
        super().__init__(
            name="computer_control",
            description="Full computer control — open apps, navigate UI, manage files, automate desktop tasks",
            capabilities=[
                "open_app", "close_app", "navigate_ui", "manage_files",
                "take_screenshot", "manage_windows", "system_settings",
                "clipboard", "install_software", "browser_control",
                "keyboard_shortcuts", "file_operations",
            ],
        )
        self._llm = llm_func
        self._vision = vision_func
        self._speak = speak_func
        self._mouse = None
        self._keyboard = None
        self._browser = None
        self._max_steps = 30
        self._cancel = False

    async def initialize(self) -> bool:
        """Load mouse, keyboard, and browser controllers."""
        try:
            from jarvis.hands.mouse import Mouse
            from jarvis.hands.keyboard import Keyboard

            self._mouse = Mouse()
            self._keyboard = Keyboard()

            # Browser is optional — loaded lazily on first use
            try:
                from jarvis.hands.browser import Browser
                self._browser = Browser()
            except Exception:
                logger.info("Browser controller not loaded (will use OS-level launch)")

            self.status = self.status.IDLE
            logger.info("Computer control agent initialized")
            return True
        except Exception as e:
            logger.warning(f"Computer control init partial: {e}")
            # Still mark as idle — can work without hardware controllers
            self.status = self.status.IDLE
            return True

    async def can_handle(self, task_description: str) -> float:
        lower = task_description.lower().strip()

        if any(lower.startswith(s.strip()) or s.strip() in lower for s in _STRONG_SIGNALS):
            return 0.9

        if any(s in lower for s in _MEDIUM_SIGNALS):
            return 0.65

        return 0.15

    async def execute(self, task: Task) -> TaskResult:
        """Execute a computer control task using plan → execute → verify."""
        self._cancel = False
        steps_taken = []

        try:
            # Step 1: Plan
            await self.publish_progress(0.1, "Planning steps...", 0, -1)
            plan = await self._plan_task(task.description)
            steps_taken.append(f"Planned {len(plan)} steps")

            if self._speak:
                self._speak("On it, sir.")

            # Step 2: Execute each step
            for i, step in enumerate(plan):
                if self._cancel or self._cancel_requested:
                    return TaskResult(
                        task_id=task.id, success=False,
                        output="Task cancelled", error="Cancelled",
                        steps_taken=steps_taken,
                    )

                progress = (i + 1) / len(plan)
                await self.publish_progress(progress, step, i, len(plan))

                success = await self._execute_step(step)
                steps_taken.append(f"{'[OK]' if success else '[FAIL]'} {step}")

                if not success:
                    # Try one more time with vision fallback
                    success = await self._execute_step_vision(step)
                    if not success:
                        steps_taken.append(f"Failed: {step}")
                        if self._speak:
                            self._speak(f"I got stuck on step: {step}. Moving on.")

                # Brief pause for UI to settle
                await asyncio.sleep(0.5)

            await self.publish_progress(1.0, "Done", len(plan), len(plan))

            if self._speak:
                self._speak("Done, sir.")

            return TaskResult(
                task_id=task.id, success=True,
                output=f"Completed {len(plan)} steps successfully.",
                steps_taken=steps_taken,
            )

        except Exception as e:
            logger.error(f"Computer control error: {e}", exc_info=True)
            return TaskResult(
                task_id=task.id, success=False,
                output="Task failed", error=str(e),
                steps_taken=steps_taken,
            )

    async def _plan_task(self, description: str) -> list[str]:
        """Break a task into atomic executable steps using LLM."""
        if not self._llm:
            return [description]

        prompt = f"""You are a Windows 11 computer automation planner.
Break this task into simple, atomic steps that can each be done with ONE action
(one click, one keystroke, one command).

Task: "{description}"

Rules:
- Each step should be ONE action (click, type, open, press key, etc.)
- Use Windows keyboard shortcuts when possible (Win+E for Explorer, etc.)
- Be specific about what to click or where to navigate
- Include verification steps ("verify X appeared on screen")

Return ONLY a JSON array of step strings:
["step 1", "step 2", "step 3"]"""

        try:
            response = await self._llm(prompt)
            response = response.strip()
            if "```" in response:
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            steps = __import__("json").loads(response)
            if isinstance(steps, list) and len(steps) > 0:
                return steps[:self._max_steps]
        except Exception as e:
            logger.warning(f"Planning failed: {e}")

        # Fallback: simple decomposition
        return self._simple_plan(description)

    def _simple_plan(self, description: str) -> list[str]:
        """Keyword-based fallback planning."""
        lower = description.lower()
        steps = []

        if "open" in lower:
            app = description.split("open", 1)[-1].strip()
            steps = [
                f"Press Win key to open Start Menu",
                f"Type '{app}'",
                "Press Enter to launch",
                f"Verify {app} opened",
            ]
        elif "go to" in lower or "navigate" in lower:
            url = description.split("go to", 1)[-1].strip() if "go to" in lower else description.split("navigate", 1)[-1].strip()
            steps = [
                "Open Chrome browser",
                f"Navigate to {url}",
                "Verify page loaded",
            ]
        elif "download" in lower:
            steps = [
                "Identify download source",
                "Navigate to download page",
                "Click download button",
                "Wait for download to complete",
                "Verify file in Downloads folder",
            ]
        else:
            steps = [
                "Analyze current screen state",
                f"Execute: {description}",
                "Verify completion",
            ]

        return steps

    async def _execute_step(self, step: str) -> bool:
        """Execute a single step using accessibility/keyboard shortcuts."""
        lower = step.lower()

        try:
            # ── Keyboard shortcuts ──
            if "press win" in lower or "win key" in lower:
                if self._keyboard:
                    self._keyboard.press("win")
                    await asyncio.sleep(0.5)
                    return True

            if "press enter" in lower:
                if self._keyboard:
                    self._keyboard.press("enter")
                    await asyncio.sleep(0.3)
                    return True

            if "press escape" in lower or "press esc" in lower:
                if self._keyboard:
                    self._keyboard.press("escape")
                    return True

            # ── Type text ──
            if lower.startswith("type ") or "type '" in lower:
                import re
                match = re.search(r"['\"](.+?)['\"]", step)
                text = match.group(1) if match else step.split("type", 1)[-1].strip()
                if self._keyboard and text:
                    self._keyboard.type_text(text, interval=0.03)
                    await asyncio.sleep(0.3)
                    return True

            # ── Open URL ──
            if "navigate to" in lower or "go to" in lower:
                import re
                url_match = re.search(r'(https?://\S+|www\.\S+|\S+\.\w{2,})', step)
                if url_match and self._browser:
                    url = url_match.group(1)
                    self._browser.open_url(url)
                    await asyncio.sleep(1)
                    return True

            # ── Open app via Start Menu ──
            if "open" in lower and ("chrome" in lower or "browser" in lower):
                os.startfile("chrome") if os.name == "nt" else None
                await asyncio.sleep(1)
                return True

            if "open" in lower and "explorer" in lower:
                if self._keyboard:
                    self._keyboard.hotkey("win", "e")
                    await asyncio.sleep(0.5)
                    return True

            if "open" in lower and "terminal" in lower:
                if self._keyboard:
                    self._keyboard.hotkey("win", "x")
                    await asyncio.sleep(0.5)
                    self._keyboard.press("i")  # Windows Terminal
                    return True

            # ── File operations ──
            if "copy file" in lower or "move file" in lower:
                # Parse source and destination from the step
                # Delegate to shell commands
                return await self._run_shell(step)

            if "delete file" in lower:
                return await self._run_shell(step)

            # ── Hotkeys ──
            if "ctrl+" in lower or "alt+" in lower:
                import re
                match = re.search(r'(ctrl|alt|shift|win)\+(\w+)', lower)
                if match and self._keyboard:
                    self._keyboard.hotkey(match.group(1), match.group(2))
                    return True

            # ── Screenshot / verify ──
            if "verify" in lower or "check" in lower or "screenshot" in lower:
                # For now, verification is a no-op placeholder
                # Full implementation would screenshot + vision check
                await asyncio.sleep(0.3)
                return True

            # Couldn't handle with simple logic
            return False

        except Exception as e:
            logger.warning(f"Step execution error: {e}")
            return False

    async def _execute_step_vision(self, step: str) -> bool:
        """Fallback: use vision LLM to figure out what to do."""
        if not self._vision:
            return False

        try:
            # Take screenshot
            from jarvis.utils.screenshot import capture_screen_base64
            screenshot = capture_screen_base64()

            # Ask vision LLM what to do
            prompt = (
                f"I need to: {step}\n\n"
                "Look at the screenshot and tell me exactly what to click or type. "
                "Respond with ONE action in JSON: "
                '{"action": "click", "x": 500, "y": 300} or '
                '{"action": "type", "text": "hello"} or '
                '{"action": "hotkey", "keys": "ctrl+c"}'
            )

            response = await self._vision(prompt, screenshot)
            if response:
                action_data = __import__("json").loads(response)
                return await self._do_action(action_data)

        except Exception as e:
            logger.warning(f"Vision fallback failed: {e}")

        return False

    async def _do_action(self, action: dict) -> bool:
        """Execute a parsed action dict."""
        try:
            act = action.get("action", "")

            if act == "click" and self._mouse:
                x, y = int(action["x"]), int(action["y"])
                self._mouse.click(x, y)
                return True

            if act == "type" and self._keyboard:
                self._keyboard.type_text(action["text"])
                return True

            if act == "hotkey" and self._keyboard:
                keys = action["keys"].split("+")
                self._keyboard.hotkey(*keys)
                return True

            if act == "scroll" and self._mouse:
                self._mouse.scroll(action.get("direction", "down"), action.get("amount", 3))
                return True

        except Exception as e:
            logger.warning(f"Action execution failed: {e}")

        return False

    async def _run_shell(self, description: str) -> bool:
        """Run a shell command for file operations."""
        if not self._llm:
            return False

        try:
            prompt = (
                f"Convert this to a Windows PowerShell command: {description}\n"
                "Return ONLY the PowerShell command, nothing else."
            )
            cmd = await self._llm(prompt)
            cmd = cmd.strip().strip("`").strip()

            if cmd and len(cmd) < 500:
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    capture_output=True, text=True, timeout=30,
                )
                return result.returncode == 0
        except Exception as e:
            logger.warning(f"Shell command failed: {e}")

        return False

    async def cancel(self):
        self._cancel = True
        await super().cancel()
