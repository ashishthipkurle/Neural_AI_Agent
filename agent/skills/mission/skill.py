"""
Mission Control Skill - Autonomous objective execution with remote reporting.
Wrapper around PlanningSkill that adds resilience and Telegram updates.
"""

import logging
import time
from typing import Dict, Any, Optional, List

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth

class MissionControlSkill(BaseSkill):
    """
    Manages long-running "Missions".
    
    Actions:
    - start_mission: Begin an autonomous mission.
    """

    def __init__(self):
        super().__init__()
        self._skill_router = None # Injected
        self._telegram_skill = None # Injected or resolved via router

    @property
    def name(self) -> str:
        return "mission"

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="mission",
            version="1.0.0",
            description="Autonomous mission controller with remote reporting.",
            actions=["start_mission"],
            requires=[],
            permissions=["skills", "network"]
        )

    def set_skill_router(self, router):
        self._skill_router = router
        self.logger.info(f"MissionSkill received router: {type(router).__name__}")

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

        await self._report(f"Mission: {goal}")

        # 1. Decompose Goal (using PlanningSkill)
        plan_result = await self._call_skill("planning", "plan", {"goal": goal})
        if not plan_result.success:
            await self._report(f"Planning failed: {plan_result.error}")
            return SkillResult(success=False, error=plan_result.error)

        plan = plan_result.data.get("plan") if plan_result.data else {}
        steps = plan.get("steps", []) if plan else []
        
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
            
            # Pass previous result to next step via context
            step_context = {"previous_result": previous_result}
            
            # Execute with AUTO-RETRY
            step_result = None
            last_error = None
            
            for attempt in range(1, MAX_RETRIES + 1):
                step_result = await self._call_skill(skill, action, step_params, step_context)
                
                if step_result.success:
                    break
                else:
                    last_error = step_result.error
                    if attempt < MAX_RETRIES:
                        self.logger.warning(f"Step {step_id} failed (attempt {attempt}): {last_error}. Retrying...")
                        import asyncio
                        await asyncio.sleep(1 + attempt)  # Increasing backoff
            
            if step_result and step_result.success:
                previous_result = step_result.data
                await self._report(f"Step {step_id} done.", silent=True)
                step_index += 1
            else:
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
                    return SkillResult(success=False, error=f"Mission failed at step {step_id}")

        # Report final result if available
        final_msg = f"Mission Complete: {goal}"
        if previous_result:
            # Extract clean content from research result
            if isinstance(previous_result, dict) and "content" in previous_result:
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
        """Send update to Telegram (and log)."""
        self.logger.info(f"MISSION REPORT: {message}")
        
        if silent:
            return

        # Try to send to Telegram
        try:
            await self._call_skill("telegram", "send_message", {"message": message})
        except Exception as e:
            self.logger.warning(f"Failed to report to Telegram: {e}")

    def health(self) -> SkillHealth:
        return SkillHealth.READY
