"""
Mission Control Skill - Autonomous objective execution with remote reporting.
Wrapper around PlanningSkill that adds resilience and Telegram updates.
"""

import logging
import time
import re
from typing import Dict, Any, Optional, List

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth

class MissionControlSkill(BaseSkill):
    """
    Manages long-running "Missions".
    
    Actions:
    - start_mission: Begin an autonomous mission.
    """

    def __init__(self, agent=None):
        super().__init__()
        self._skill_router = None # Injected
        self._telegram_skill = None # Injected or resolved via router
        self._agent = agent
        self._runtime_reporter = None

    @property
    def name(self) -> str:
        return "mission"

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="mission",
            version="1.0.0",
            description="Autonomous mission controller. Handles complex, long-running tasks, sustained web interactions, and multi-step workflows with remote reporting.",
            actions=["start_mission"],
            requires=[],
            permissions=["skills", "network"]
        )

    def set_skill_router(self, router):
        self._skill_router = router
        self.logger.info(f"MissionSkill received router: {type(router).__name__}")

    def set_runtime_reporter(self, reporter):
        """Inject runtime reporter callback for live UI/WebSocket updates."""
        self._runtime_reporter = reporter

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        intent_lower = intent.lower()
        if any(x in intent_lower for x in ["start mission", "mission mode", "autonomously", "build all night"]):
            return 0.9
        return 0.0

    async def execute(self, action: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        # Handle raw intent strings (from SkillRouter)
        action_lower = action.lower()
        if "start mission" in action_lower or "mission mode" in action_lower:
            # Extract goal from raw intent
            goal = action_lower.replace("start mission:", "").replace("start mission", "").replace("mission mode:", "").replace("mission mode", "").strip()
            if goal:
                params = {"goal": goal}
            action = "start_mission"
        
        if action == "start_mission":
            return await self._start_mission(params)
        return SkillResult(success=False, error=f"Unknown action: {action}")

    async def _start_mission(self, params: Dict) -> SkillResult:
        goal = params.get("goal")
        if not goal:
            return SkillResult(success=False, error="Mission requires a goal.")

        def _emit_done() -> None:
            """Best-effort signal to clear UI processing indicators."""
            reporter = self._runtime_reporter
            if reporter is None and self._agent is not None:
                reporter = getattr(self._agent, "sync_broadcast", None)
            if not reporter:
                return
            try:
                reporter("status", "system", "Done")
            except TypeError:
                # Back-compat with any reporter that doesn't accept status events.
                try:
                    reporter("action", "system", "[Mission] Done")
                except Exception:
                    return
            except Exception:
                return

        constraints = self._extract_goal_constraints(goal)

        await self._report(f"Mission: {goal}")

        # 1. Decompose Goal (using PlanningSkill)
        plan_result = await self._call_skill("planning", "plan", {"goal": goal})
        if not plan_result.success:
            await self._report(f"Planning failed: {plan_result.error}")
            _emit_done()
            return SkillResult(success=False, error=plan_result.error)

        plan = plan_result.data.get("plan") if plan_result.data else {}
        steps = plan.get("steps", []) if plan else []
        steps = self._apply_constraints_to_steps(steps, constraints)
        
        await self._report(f"Plan: {len(steps)} steps.", silent=True)

        # 2. Execute Steps Loop (NEVER-STOP-UNTIL-DONE with AUTO-RETRY)
        previous_result = None
        MAX_RETRIES = 5
        MAX_REROUTES = 2
        reroute_count = 0
        
        step_index = 0
        while step_index < len(steps):
            step = steps[step_index]
            step_id = step.get("id", step_index + 1)
            desc = step.get("description", "")
            skill = step.get("skill", "")
            action = step.get("action", "")
            step_params = step.get("params", {})
            
            await self._report(f"Step {step_id}: {desc}", silent=True)
            
            # ---- PRE-STEP: Before screenshot, restore dev server in browser ----
            if skill == "vision" and action == "screenshot":
                dev_url = getattr(self, "_mission_dev_url", None)
                if dev_url:
                    self.logger.info(f"Restoring dev server {dev_url} in browser before screenshot...")
                    try:
                        nav_r = await self._call_skill("browser", "navigate", {"url": dev_url})
                        if nav_r.success:
                            import asyncio as _aio2
                            await _aio2.sleep(3)  # let page render
                            self.logger.info("Browser showing dev site for screenshot.")
                    except Exception as _e:
                        self.logger.warning(f"Could not restore dev URL before screenshot: {_e}")

            # Pass previous result to next step via context
            step_context = {"previous_result": previous_result}
            
            # Execute with AUTO-RETRY
            step_result = None
            last_error = None
            is_browser_chat_loop = (skill == "browser" and action == "browser_chat_loop")
            step_max_retries = 1 if is_browser_chat_loop else MAX_RETRIES
            
            for attempt in range(1, step_max_retries + 1):
                if attempt == 1 and skill == "coding" and action == "scaffold_react_website":
                    await self._report("coding skill scaffold in progress", silent=True)
                step_result = await self._call_skill(skill, action, step_params, step_context)
                
                if step_result.success:
                    break
                else:
                    last_error = step_result.error
                    if attempt < step_max_retries:
                        self.logger.warning(f"Step {step_id} failed (attempt {attempt}): {last_error}. Retrying...")
                        import asyncio
                        await asyncio.sleep(1 + attempt)  # Increasing backoff
            
            if step_result and step_result.success:
                previous_result = step_result.data

                # ---- AUTO-OPEN: after coding builds a site, navigate browser to it ----
                if skill == "coding" and action == "scaffold_react_website":
                    await self._report("coding skill scaffold started", silent=True)
                    project_path = (previous_result or {}).get("project_path") if isinstance(previous_result, dict) else None
                    if project_path:
                        await self._report(f"coding skill project_path: '{project_path}'", silent=True)
                    local_url = (previous_result or {}).get("local_url") if isinstance(previous_result, dict) else None
                    if local_url:
                        self.logger.info(f"Dev server running at {local_url}. Opening in browser...")
                        await self._report(f"Opening {local_url} in browser...", silent=True)
                        try:
                            nav_result = await self._call_skill("browser", "navigate", {"url": local_url})
                            if nav_result.success:
                                import asyncio as _aio
                                await _aio.sleep(4)  # let page render fully
                                self.logger.info("Browser loaded the running site.")
                            else:
                                self.logger.warning(f"Browser navigate failed: {nav_result.error}")
                        except Exception as nav_exc:
                            self.logger.warning(f"Could not open site in browser: {nav_exc}")
                    # Store URL in context for later steps (e.g. screenshot)
                    if not hasattr(self, "_mission_dev_url"):
                        self._mission_dev_url = local_url

                await self._report(f"Step {step_id} done.", silent=True)
                step_index += 1
            else:
                if is_browser_chat_loop:
                    # Do not reroute/retry this long-running step endlessly.
                    await self._report(f"Step {step_id} completed with interruptions: {last_error}")
                    previous_result = step_result.data if step_result and step_result.data else {"error": last_error}
                    step_index += 1
                    continue

                # NEVER-STOP-UNTIL-DONE: Attempt reroute
                if reroute_count < MAX_REROUTES:
                    reroute_count += 1
                    self.logger.warning(f"Step {step_id} failed. Attempting reroute {reroute_count}/{MAX_REROUTES}...")
                    
                    # Report reroute (NOT silent, as it's a deviation)
                    await self._report(f"Step {step_id} failed. Rerouting...")
                    
                    # Re-plan using the ORIGINAL goal (not a corrupted version)
                    # This ensures search queries stay clean
                    replan_result = await self._call_skill("planning", "plan", {"goal": goal})
                    
                    if replan_result.success and replan_result.data:
                        new_plan = replan_result.data.get("plan", {})
                        new_steps = new_plan.get("steps", [])
                        if new_steps:
                            steps = new_steps
                            step_index = 0
                            await self._report(f"New plan: {len(steps)} steps.", silent=True)
                            continue
                    
                    # If re-plan also failed, move to next step anyway
                    self.logger.error(f"Reroute failed, skipping step {step_id}")
                    step_index += 1
                else:
                    await self._report(f"Step {step_id} failed after {MAX_RETRIES} attempts and {MAX_REROUTES} reroutes: {last_error}")

                    # If failed step produced a partial report/transcript, try to send it.
                    try:
                        if step_result and isinstance(step_result.data, dict):
                            partial_report_path = step_result.data.get("report_path")
                            partial_content = step_result.data.get("content")

                            if partial_report_path:
                                await self._report("Mission failed, but sending partial report...")
                                await self._call_skill("telegram", "send_document", {
                                    "path": partial_report_path,
                                    "caption": f"Partial Mission Report: {goal}"
                                })
                            elif partial_content:
                                snippet = str(partial_content)
                                if len(snippet) > 3500:
                                    snippet = snippet[:3500] + "..."
                                await self._report(f"Mission failed, partial output:\n\n{snippet}")
                    except Exception as report_err:
                        self.logger.warning(f"Failed to send partial mission report: {report_err}")

                    _emit_done()
                    return SkillResult(success=False, error=f"Mission failed at step {step_id}")

        # Report final result if available
        final_msg = f"Mission Complete: {goal}"
        if previous_result:
            # Case 1: Result has a report file (e.g. Deep Research)
            if isinstance(previous_result, dict) and "report_path" in previous_result:
                report_path = previous_result["report_path"]
                summary = previous_result.get("summary", "Research completed.")
                
                # Send summary first
                await self._report(f"{final_msg}\n\nSummary: {summary}\n\nSending full report...")
                
                # Send the file
                try:
                    await self._call_skill("telegram", "send_document", {
                        "path": report_path,
                        "caption": f"Mission Report: {goal}"
                    })
                    _emit_done()
                    return SkillResult(success=True, message="Mission Complete (Report sent)")
                except Exception as e:
                    self.logger.error(f"Failed to send report file: {e}")
                    final_msg += f"\n\n(Failed to send report file: {e}. Path: {report_path})"

            # Case 2: Result has direct content
            elif isinstance(previous_result, dict) and "content" in previous_result:
                # This is a formatted research report
                content = previous_result["content"]
                # Telegram has 4096 char limit per message.
                # If content is large, save to file and send document.
                if len(content) > 3000: # Threshold for file
                    try:
                        # Save to file
                        from pathlib import Path
                        import time
                        
                        mission_dir = Path("agent/data/missions")
                        mission_dir.mkdir(parents=True, exist_ok=True)
                        
                        timestamp = int(time.time())
                        filename = f"mission_report_{timestamp}.md"
                        file_path = mission_dir / filename
                        
                        # Add header
                        file_content = f"# Mission Report: {goal}\n\n"
                        file_content += f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        file_content += content
                        
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(file_content)
                            
                        # Send document
                        await self._report(f"Mission complete. Result is too long for text, sending file: {filename}")
                        await self._call_skill("telegram", "send_document", {
                            "path": str(file_path),
                            "caption": f"Mission Report: {goal}"
                        })
                        _emit_done()
                        return SkillResult(success=True, message="Mission Complete (Sent as file)")
                        
                    except Exception as e:
                        self.logger.error(f"Failed to send file: {e}")
                        # Fallback to chunking
                        await self._report(final_msg)
                        for i in range(0, len(content), 4000):
                            chunk = content[i:i+4000]
                            await self._report(chunk)
                else:
                    final_msg += f"\n\n{content}"
            else:
                # Fallback for other result types
                result_str = str(previous_result)
                if len(result_str) > 3500:
                    result_str = result_str[:3500] + "... (more)"
                final_msg += f"\n\nResult: {result_str}"
        
        await self._report(final_msg)
        _emit_done()
        return SkillResult(success=True, message="Mission Complete")

    async def _call_skill(self, skill_name: str, action: str, params: Dict, context: Dict = None) -> SkillResult:
        """Helper to call other skills via router."""
        if not self._skill_router:
            return SkillResult(success=False, error="Router not linked")
        
        try:
             if hasattr(self._skill_router, 'execute_skill_action'):
                 # Execute and await if needed
                 import inspect
                 result = self._skill_router.execute_skill_action(skill_name, action, params, context)
                 
                 if inspect.isawaitable(result):
                     result = await result
                 
                 # SkillRouter returns ExecutionResult, unwrap to get SkillResult
                 if hasattr(result, 'result') and result.result is not None:
                     return result.result  # This is the actual SkillResult
                 elif hasattr(result, 'success'):
                     # It's already a SkillResult or similar
                     return SkillResult(success=result.success, error=getattr(result, 'error', None))
                 return result
             return SkillResult(success=False, error=f"Router cannot execute {skill_name}.{action}")
        except Exception as e:
             return SkillResult(success=False, error=f"Call failed: {e}")

    async def _report(self, message: str, silent: bool = False) -> None:
        """Send update to live UI + Telegram (Telegram can be silenced)."""
        self.logger.info(f"MISSION REPORT: {message}")

        # Always send to live UI stream when available.
        self._emit_runtime_update(message)

        if silent:
            return

        # Try to send to Telegram
        try:
            await self._call_skill("telegram", "send_message", {"message": message})
        except Exception as e:
            self.logger.warning(f"Failed to report to Telegram: {e}")

    def _emit_runtime_update(self, message: str) -> None:
        """Emit mission progress to websocket listeners via runtime reporter."""
        reporter = self._runtime_reporter
        if reporter is None and self._agent is not None:
            reporter = getattr(self._agent, "sync_broadcast", None)

        if not reporter:
            return

        try:
            reporter("action", "system", f"[Mission] {message}")
        except Exception as exc:
            self.logger.debug(f"Runtime report skipped: {exc}")

    def health(self) -> SkillHealth:
        return SkillHealth.READY

    def _extract_goal_constraints(self, goal: str) -> Dict[str, Any]:
        """Extract explicit execution constraints from user goal text."""
        goal_lower = goal.lower()
        constraints: Dict[str, Any] = {}

        duration_match = re.search(
            r"(?:for\s+)?(?:approximately\s+)?(\d+)\s*(minute|minutes|min|mins|m|hour|hours|hr|hrs|h)\b",
            goal_lower,
            re.IGNORECASE,
        )
        if duration_match:
            amount = int(duration_match.group(1))
            unit = duration_match.group(2).lower()
            if unit in ["hour", "hours", "hr", "hrs", "h"]:
                constraints["duration_minutes"] = max(1, amount * 60)
            else:
                constraints["duration_minutes"] = max(1, amount)

        if "telegram" in goal_lower:
            constraints["report_channel"] = "telegram"

        return constraints

    def _apply_constraints_to_steps(self, steps: List[Dict[str, Any]], constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply extracted constraints onto generated plan steps before execution."""
        if not steps:
            return steps

        duration_minutes = constraints.get("duration_minutes")
        if duration_minutes is None:
            return steps

        for step in steps:
            if step.get("skill") == "browser" and step.get("action") == "browser_chat_loop":
                params = step.get("params") or {}
                params["duration"] = f"{duration_minutes}m"
                step["params"] = params
                step["description"] = f"Engage in conversation loop (Read -> Reply) for {duration_minutes} mins"

        return steps
