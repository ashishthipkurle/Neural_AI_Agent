"""
Planning Skill - Multi-step task decomposition and execution.

This is the "brain" of the Clowbot-class agent, providing:
- Task decomposition (complex goal → skill steps)
- Plan execution with progress tracking
- Self-correction on failures
- Goal progress monitoring
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """A single step in a plan."""
    id: int
    skill: str
    action: str
    params: Dict[str, Any]
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str = ""
    depends_on: List[int] = field(default_factory=list)
    
    def to_dict(self):
        return {
            "id": self.id,
            "skill": self.skill,
            "action": self.action,
            "params": self.params,
            "description": self.description,
            "status": self.status.value,
            "result": self.result,
            "error": self.error
        }


@dataclass
class Plan:
    """A multi-step execution plan."""
    goal: str
    steps: List[PlanStep]
    current_step: int = 0
    status: str = "pending"  # pending, running, completed, failed
    
    def to_dict(self):
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "current_step": self.current_step,
            "status": self.status,
            "progress": f"{sum(1 for s in self.steps if s.status == StepStatus.SUCCESS)}/{len(self.steps)}"
        }


class PlanningSkill(BaseSkill):
    """
    Multi-step planning and execution skill.
    
    Actions:
    - plan: Create a plan from a goal
    - execute_plan: Execute a created plan
    - step: Execute next step
    - status: Get plan status
    - retry: Retry failed step
    - abort: Abort current plan
    - list_plans: List available plans
    """
    
    # Known skill→action mappings for common tasks
    TASK_PATTERNS = {
        "open": [("desktop", "launch", {"app_name": "{target}"})],
        "play music": [("desktop", "spotify_play", {})],
        "search for": [("browser", "navigate", {"url": "https://google.com/search?q={query}"})],
        "take screenshot": [("vision", "screenshot", {})],
        "remember": [("memory", "remember", {"content": "{content}"})],
        "what time": [("voice", "speak", {"text": "The current time is {time}"})],
    }
    
    def __init__(self):
        super().__init__()
        self._current_plan: Optional[Plan] = None
        self._plan_history: List[Plan] = []
        self._skill_router = None  # Will be injected
    
    @property
    def name(self) -> str:
        return "planning"
    
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="planning",
            version="1.0.0",
            description="Multi-step task decomposition and execution",
            actions=[
                "plan", "execute_plan", "step", "status",
                "retry", "abort", "list_plans", "decompose"
            ],
            requires=[],
            permissions=["skills"]
        )
    
    def set_skill_router(self, router):
        """Inject skill router for executing other skills."""
        self._skill_router = router
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """Initialize planning skill."""
        super().on_load()
        self.logger.info("Planning skill loaded")
    
    def on_unload(self) -> None:
        """Cleanup."""
        super().on_unload()
    
    # ==================== INTENT MATCHING ====================
    
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill can handle the intent."""
        intent_lower = intent.lower()
        
        # Planning keywords
        if any(x in intent_lower for x in ["plan", "step by step", "how to", "create plan"]):
            return 0.85
        
        # Multi-step indicators
        if " and then " in intent_lower or " after that " in intent_lower:
            return 0.8
        
        # Complex task hints
        if any(x in intent_lower for x in ["automate", "workflow", "sequence"]):
            return 0.75
        
        return 0.0
    
    # ==================== EXECUTION ====================
    
    async def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Execute a planning action."""
        
        handlers = {
            "plan": self._action_plan,
            "decompose": self._action_decompose,
            "execute_plan": self._action_execute_plan,
            "step": self._action_step,
            "status": self._action_status,
            "retry": self._action_retry,
            "abort": self._action_abort,
            "list_plans": self._action_list_plans,
        }
        
        handler = handlers.get(action)
        if not handler:
            return SkillResult(success=False, error=f"Unknown action: {action}")
        
        try:
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                return await handler(params, context or {})
            else:
                return handler(params, context or {})
        except Exception as e:
            self.logger.error(f"Planning action '{action}' failed: {e}")
            return SkillResult(success=False, error=str(e))
    
    # ==================== ACTIONS ====================
    
    def _action_plan(self, params: Dict, context: Dict) -> SkillResult:
        """Create a plan from a goal."""
        goal = params.get("goal", "")
        
        if not goal:
            return SkillResult(success=False, error="Goal required")
        
        # Decompose goal into steps
        steps = self._decompose_goal(goal, context)
        
        if not steps:
            return SkillResult(
                success=False, 
                error="Could not decompose goal into actionable steps"
            )
        
        plan = Plan(goal=goal, steps=steps)
        self._current_plan = plan
        self._plan_history.append(plan)
        
        return SkillResult(
            success=True,
            data={"plan": plan.to_dict()},
            message=f"Created plan with {len(steps)} steps"
        )
    
    def _action_decompose(self, params: Dict, context: Dict) -> SkillResult:
        """Decompose a complex task into skill steps (dry-run)."""
        goal = params.get("goal", "")
        
        if not goal:
            return SkillResult(success=False, error="Goal required")
        
        steps = self._decompose_goal(goal, context)
        
        step_descriptions = [
            f"{i+1}. {s.skill}.{s.action}: {s.description}"
            for i, s in enumerate(steps)
        ]
        
        return SkillResult(
            success=True,
            data={"steps": [s.to_dict() for s in steps]},
            message="Proposed steps:\n" + "\n".join(step_descriptions)
        )
    
    def _decompose_goal(self, goal: str, context: Dict) -> List[PlanStep]:
        """Decompose a natural language goal into skill steps."""
        goal_lower = goal.lower()
        steps = []
        step_id = 1
        
        # ===== COMPOUND PATTERNS (detect multi-step goals) =====
        
        # Pattern: "research/find/search X and save/write to file"
        has_research = any(x in goal_lower for x in ["research", "find out", "look up", "search for"])
        has_save = any(x in goal_lower for x in ["save it to", "write to", "save to", "put in file", "create a file"])
        
        if has_research and has_save:
            # Extract the research topic
            topic = goal_lower
            for prefix in ["research", "find out about", "look up", "search for"]:
                if prefix in topic:
                    topic = topic.split(prefix, 1)[1]
                    break
            # Remove the save part
            for suffix in ["and save it to", "and write to", "and save to", "save it to", "and put in"]:
                if suffix in topic:
                    topic = topic.split(suffix)[0]
                    break
            topic = topic.strip()
            
            # Extract filename if specified
            filename = "research_output.txt"
            for marker in ["to a file", "to file", "to "]:
                if marker in goal_lower.split("save")[-1]:
                    potential_file = goal_lower.split("save")[-1].split(marker)[-1].strip()
                    if potential_file and len(potential_file) < 50:
                        filename = potential_file if "." in potential_file else f"{potential_file.replace(' ', '_')}.txt"
                    break
            
            # Step 1: Search & Click First Result (Robust)
            steps.append(PlanStep(
                id=step_id,
                skill="browser",
                action="google_search",
                params={"query": topic},
                description=f"Search Google for: {topic}"
            ))
            step_id += 1
            
            # Step 2: Scrape content
            steps.append(PlanStep(
                id=step_id,
                skill="browser",
                action="scrape",
                params={"selector": "article, .content, main, body", "attribute": "innerText"},
                description="Scrape page content"
            ))
            step_id += 1
            
            # Step 3: Save to file (this will use result from previous step)
            steps.append(PlanStep(
                id=step_id,
                skill="desktop",
                action="write_file",
                params={"filename": filename, "use_previous_result": True},
                description=f"Save content to {filename}"
            ))
            step_id += 1
            
            # Step 4: Send to Telegram (notify user with the result)
            steps.append(PlanStep(
                id=step_id,
                skill="telegram",
                action="send_message",
                params={"message": f"📄 Research on '{topic}' completed!", "use_previous_result": True},
                description="Send results to Telegram"
            ))
            
            return steps
        
        # ===== INTERACTIVE / CONVERSATION GOALS =====
        # Detect goals that involve navigating to a site and interacting with it
        # e.g. "Interact with ChatGPT to discuss quantum physics"
        interaction_keywords = ["interact with", "conversation", "discuss", "chat on", "talk to", "converse"]
        known_sites = {
            "chatgpt": "https://chatgpt.com",
            "chat.openai": "https://chat.openai.com",
            "gemini": "https://gemini.google.com",
            "claude": "https://claude.ai",
            "perplexity": "https://perplexity.ai",
            "copilot": "https://copilot.microsoft.com",
        }
        
        has_interaction = any(kw in goal_lower for kw in interaction_keywords)
        detected_site = None
        detected_url = None
        for site_name, site_url in known_sites.items():
            if site_name in goal_lower:
                detected_site = site_name
                detected_url = site_url
                break
        
        if has_interaction and detected_site:
            # Extract requested conversation duration from goal (default: 10 minutes)
            requested_minutes = 10
            duration_match = re.search(
                r"(?:for\s+)?(?:approximately\s+)?(\d+)\s*(minute|minutes|min|mins|m|hour|hours|hr|hrs|h)\b",
                goal_lower,
                re.IGNORECASE,
            )
            if duration_match:
                amount = int(duration_match.group(1))
                unit = duration_match.group(2).lower()
                if unit in ["hour", "hours", "hr", "hrs", "h"]:
                    requested_minutes = max(1, amount * 60)
                else:
                    requested_minutes = max(1, amount)

            duration_param = f"{requested_minutes}m"

            # Extract the topic from the goal using regex for better precision
            # Look for "discuss X", "about X", "on X"
            topic_match = re.search(r'\b(discuss|about|on|regarding)\s+(.*?)(\.|for approximately|$)', goal_lower, re.IGNORECASE)
            
            if topic_match:
                raw_topic = topic_match.group(2).strip()
                # Clean up "quantum physics topics" -> "quantum physics"
                raw_topic = re.sub(r'\b(topics|subjects)\b', '', raw_topic).strip()
                # Formulate a natural message
                topic = f"I would like to discuss {raw_topic}."
            else:
                # Fallback: clean up the whole goal if no specific pattern found
                clean_goal = goal_lower
                for noise in interaction_keywords + [detected_site, "interface", "for approximately", "10 minutes", "actions include"]:
                    clean_goal = clean_goal.replace(noise, "")
                clean_goal = re.sub(r'\s+', ' ', clean_goal).strip()
                topic = f"Hello, I'd like to talk about {clean_goal[:100]}."
            
            # Step 1: Navigate to the site
            steps.append(PlanStep(
                id=step_id,
                skill="browser",
                action="navigate",
                params={"url": detected_url},
                description=f"Navigate to {detected_site}"
            ))
            step_id += 1
            
            # Step 2: Type the topic/question into the chat input
            if topic:
                steps.append(PlanStep(
                    id=step_id,
                    skill="browser",
                    action="type",
                    params={"selector": "textarea, [contenteditable='true'], input[type='text']", "text": topic},
                    description=f"Type: {topic[:50]}..."
                ))
                step_id += 1
                
                # Step 3: Press Enter to send
                steps.append(PlanStep(
                    id=step_id,
                    skill="browser",
                    action="press_key",
                    params={"key": "Enter"},
                    description="Press Enter to send"
                ))
                step_id += 1

                # Step 4: Enter conversation loop
                steps.append(PlanStep(
                    id=step_id,
                    skill="browser", 
                    action="browser_chat_loop",
                    params={"duration": duration_param, "topic": topic},
                    description=f"Engage in conversation loop (Read -> Reply) for {requested_minutes} mins"
                ))
                step_id += 1
            
            return steps
        
        # ===== SIMPLE PATTERNS =====
        
        # Parse "and then" sequences
        if " and then " in goal_lower or " then " in goal_lower:
            parts = goal_lower.replace(" and then ", " then ").split(" then ")
            for part in parts:
                sub_steps = self._parse_single_task(part.strip(), step_id)
                steps.extend(sub_steps)
                step_id += len(sub_steps)
            return steps
        
        # Single task
        return self._parse_single_task(goal, 1)
    
    def _parse_single_task(self, task: str, start_id: int) -> List[PlanStep]:
        """Parse a single task into steps."""
        task_lower = task.lower()
        steps = []
        
        # Pattern matching for common tasks
        if task_lower.startswith("open "):
            target = task[5:].strip()
            steps.append(PlanStep(
                id=start_id,
                skill="desktop",
                action="launch",
                params={"app_name": target},
                description=f"Open {target}"
            ))
        
        elif "play" in task_lower and ("music" in task_lower or "spotify" in task_lower):
            steps.append(PlanStep(
                id=start_id,
                skill="desktop",
                action="spotify_play",
                params={},
                description="Play music on Spotify"
            ))
        
        elif task_lower.startswith("go to ") or task_lower.startswith("navigate to "):
            target = task.split("to ", 1)[1].strip()
            
            # 1. Handle compound tasks ("go to X and Y")
            next_task = None
            if " and " in target:
                parts = target.split(" and ", 1)
                target = parts[0].strip()
                next_task = parts[1].strip()
            
            # 2. Map common names to URLs
            shortcuts = {
                "google": "https://google.com",
                "gemini": "https://gemini.google.com",
                "google gemini": "https://gemini.google.com", 
                "chatgpt": "https://chatgpt.com",
                "claude": "https://claude.ai",
                "youtube": "https://youtube.com",
                "github": "https://github.com",
                "twitter": "https://twitter.com",
                "x": "https://x.com",
                "linkedin": "https://linkedin.com",
                "gmail": "https://mail.google.com",
                "calendar": "https://calendar.google.com",
                "maps": "https://maps.google.com"
            }
            
            url = shortcuts.get(target.lower(), target)
            
            # 3. Validation
            # If it still has spaces and isn't a known shortcut, it's likely a search query or malformed URL
            if " " in url and not url.startswith("http"):
                # Treat as search instead
                steps.append(PlanStep(
                    id=start_id,
                    skill="browser",
                    action="google_search",
                    params={"query": target},
                    description=f"Search for: {target}"
                ))
            else:
                if not url.startswith("http"):
                    url = f"https://{url}"
                
                steps.append(PlanStep(
                    id=start_id,
                    skill="browser",
                    action="navigate",
                    params={"url": url},
                    description=f"Navigate to {url}"
                ))
            
            # 4. Handle next task
            if next_task:
                sub_steps = self._parse_single_task(next_task, start_id + 1)
                steps.extend(sub_steps)
        
        elif any(verb in task_lower for verb in ["chat with", "ask", "consult"]):
             # Extract query
             query = task
             for prefix in ["chat with", "ask", "consult", "tell"]:
                 if prefix in task_lower:
                     # Find start index of prefix (case insensitive)
                     start_idx = task_lower.find(prefix) + len(prefix)
                     query = task[start_idx:].strip()
                     
                     # Remove common AI names from start of query
                     for name in ["gemini", "chatgpt", "claude", "ai", "bot"]:
                         if query.lower().startswith(name):
                             query = query[len(name):].strip()
                     break
             
             # Clean up common conversational noise using regex
             # Remove durations: "for 10 min", "for a while"
             query = re.sub(r'for \d+ (min|minute|minutes|hour|hours)', '', query, flags=re.IGNORECASE)
             query = re.sub(r'for a while', '', query, flags=re.IGNORECASE)
             
             # Remove "on" or "about" if at start
             query = re.sub(r'^(on|about|regarding)\s+', '', query.strip(), flags=re.IGNORECASE)
             
             # Remove output requests: "and give me a detailed file", "send to telegram"
             query = re.sub(r'(and )?(give|send|write|create) (me )?(a )?(detailed )?(file|report|document|summary)( on telegram)?', '', query, flags=re.IGNORECASE)
             
             query = query.strip()
             
             steps.append(PlanStep(
                id=start_id,
                skill="browser",
                action="consult_ai",
                params={"query": query},
                description=f"Consult AI: {query[:30]}..."
            ))

        elif "search" in task_lower or "look up" in task_lower or "research" in task_lower:
            # Extract query
            query = task_lower
            for prefix in ["search for", "search", "look up", "research"]:
                if prefix in query:
                    query = query.split(prefix, 1)[1].strip()
                    break
            
            # Strip common prepositions from the start of the query
            # "research on AI" -> "AI", "research about cars" -> "cars"
            for prep in ["on ", "about ", "for ", "regarding "]:
                if query.startswith(prep):
                    query = query[len(prep):].strip()
                    break
            
            # Strip trailing command instructions
            # "deep research on AI and send it to telegram" -> "AI"
            for suffix in [" and send", " send to", " report to", " notify me", " tell me", " send it", " email me"]:
                if suffix in query:
                    query = query.split(suffix, 1)[0].strip()
            
            # Use 'deep_research' action for research/deep queries
            if "research" in task_lower or "deep" in task_lower or "find out" in task_lower:
                steps.append(PlanStep(
                    id=start_id,
                    skill="research",
                    action="deep_research",
                    params={"query": query, "topic": query, "limit": 3},
                    description=f"Deep Research for: {query}"
                ))
            else:
                # Simple navigation for basic search
                steps.append(PlanStep(
                    id=start_id,
                    skill="browser",
                    action="navigate",
                    params={"url": f"https://google.com/search?q={query.replace(' ', '+')}"},
                    description=f"Search for: {query}"
                ))
        
        elif "screenshot" in task_lower:
            steps.append(PlanStep(
                id=start_id,
                skill="vision",
                action="screenshot",
                params={},
                description="Take a screenshot"
            ))
        
        elif "remember" in task_lower or "note" in task_lower:
            content = task_lower.split("remember", 1)[-1].split("note", 1)[-1].strip()
            steps.append(PlanStep(
                id=start_id,
                skill="memory",
                action="remember",
                params={"content": content},
                description=f"Remember: {content}"
            ))
        
        elif "say" in task_lower or "speak" in task_lower or "tell me" in task_lower:
            text = task.split("say", 1)[-1].split("speak", 1)[-1].strip()
            steps.append(PlanStep(
                id=start_id,
                skill="voice",
                action="speak",
                params={"text": text},
                description=f"Say: {text}"
            ))
        
        elif "workflow" in task_lower or "routine" in task_lower:
            name = task_lower.split("run", 1)[-1].replace("workflow", "").replace("routine", "").strip()
            steps.append(PlanStep(
                id=start_id,
                skill="workflow",
                action="run",
                params={"name": name or "morning_routine"},
                description=f"Run workflow: {name}"
            ))

        elif "save" in task_lower or "write" in task_lower:
            # Pattern: "save [content] to [file]" or "write [content] to [file]"
            # Extract filename
            filename = "output.txt"
            if " to " in task_lower:
                filename_part = task_lower.split(" to ")[-1].strip()
                if filename_part and not filename_part.startswith("a "):
                    filename = filename_part if "." in filename_part else f"{filename_part.replace(' ', '_')}.txt"
            
            steps.append(PlanStep(
                id=start_id,
                skill="desktop", 
                action="write_file",
                params={"content": "Content from previous step", "filename": filename, "use_previous_result": True}, 
                description=f"Save to file: {filename}"
            ))
        
        elif "scrape" in task_lower or "extract" in task_lower or "read page" in task_lower:
            steps.append(PlanStep(
                id=start_id,
                skill="browser",
                action="scrape",
                params={"selector": "body"},
                description="Scrape page content"
            ))
        
        elif task_lower.startswith("click ") or task_lower.startswith("click on "):
            # Only match click at the START of the task, not buried in complex text
            target = task_lower.replace("click on", "").replace("click", "").strip()
            steps.append(PlanStep(
                id=start_id,
                skill="browser",
                action="click",
                params={"selector": f"text={target}", "text": target},
                description=f"Click: {target}"
            ))
        
        else:
            # Default: try to parse as a simple action
            steps.append(PlanStep(
                id=start_id,
                skill="voice",
                action="speak",
                params={"text": f"I'm not sure how to: {task}. Please break it down."},
                description=f"Unknown task: {task}"
            ))
        
        return steps

    
    async def _action_execute_plan(self, params: Dict, context: Dict) -> SkillResult:
        """Execute the current plan."""
        if not self._current_plan:
            return SkillResult(success=False, error="No plan to execute")
        
        if not self._skill_router:
            return SkillResult(success=False, error="Skill router not available")
        
        plan = self._current_plan
        plan.status = "running"
        
        results = []
        for step in plan.steps:
            if step.status == StepStatus.SUCCESS:
                continue  # Skip completed steps
            
            step.status = StepStatus.RUNNING
            plan.current_step = step.id
            
            try:
                # Execute via skill router
                import asyncio
                if asyncio.iscoroutinefunction(self._skill_router.execute_skill_action):
                    result = await self._skill_router.execute_skill_action(
                        skill_name=step.skill,
                        action=step.action,
                        params=step.params
                    )
                else:
                    result = self._skill_router.execute_skill_action(
                        skill_name=step.skill,
                        action=step.action,
                        params=step.params
                    )
            
                if result.success:
                    step.status = StepStatus.SUCCESS
                    step.result = result.result.data if result.result else None
                    results.append({"step": step.id, "status": "success"})
                else:
                    step.status = StepStatus.FAILED
                    step.error = result.error
                    results.append({"step": step.id, "status": "failed", "error": result.error})
                    
                    # Stop on failure
                    plan.status = "failed"
                    return SkillResult(
                        success=False,
                        data={"results": results, "plan": plan.to_dict()},
                        error=f"Step {step.id} failed: {result.error}"
                    )
                    
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                plan.status = "failed"
                return SkillResult(
                    success=False,
                    data={"results": results},
                    error=f"Step {step.id} error: {e}"
                )
        
        plan.status = "completed"
        
        return SkillResult(
            success=True,
            data={"results": results, "plan": plan.to_dict()},
            message=f"Plan completed: {len(plan.steps)} steps executed"
        )
    
    async def _action_step(self, params: Dict, context: Dict) -> SkillResult:
        """Execute the next step in the plan."""
        if not self._current_plan:
            return SkillResult(success=False, error="No plan to step through")
        
        plan = self._current_plan
        
        # Find next pending step
        next_step = None
        for step in plan.steps:
            if step.status == StepStatus.PENDING:
                next_step = step
                break
        
        if not next_step:
            return SkillResult(
                success=True,
                data={"plan": plan.to_dict()},
                message="All steps completed"
            )
        
        # Execute single step
        next_step.status = StepStatus.RUNNING
        plan.current_step = next_step.id
        
        if self._skill_router:
            import asyncio
            if asyncio.iscoroutinefunction(self._skill_router.execute_skill_action):
                result = await self._skill_router.execute_skill_action(
                    skill_name=next_step.skill,
                    action=next_step.action,
                    params=next_step.params
                )
            else:
                result = self._skill_router.execute_skill_action(
                    skill_name=next_step.skill,
                    action=next_step.action,
                    params=next_step.params
                )
            
            if result.success:
                next_step.status = StepStatus.SUCCESS
                next_step.result = result.result.data if result.result else None
                return SkillResult(
                    success=True,
                    data={"step": next_step.to_dict(), "plan": plan.to_dict()},
                    message=f"Step {next_step.id} completed: {next_step.description}"
                )
            else:
                next_step.status = StepStatus.FAILED
                next_step.error = result.error
                return SkillResult(
                    success=False,
                    data={"step": next_step.to_dict()},
                    error=f"Step {next_step.id} failed: {result.error}"
                )
        
        return SkillResult(success=False, error="Skill router not available")
    
    def _action_status(self, params: Dict, context: Dict) -> SkillResult:
        """Get current plan status."""
        if not self._current_plan:
            return SkillResult(
                success=True,
                data={"plan": None},
                message="No active plan"
            )
        
        return SkillResult(
            success=True,
            data={"plan": self._current_plan.to_dict()},
            message=f"Plan: {self._current_plan.status}"
        )
    
    async def _action_retry(self, params: Dict, context: Dict) -> SkillResult:
        """Retry failed step."""
        if not self._current_plan:
            return SkillResult(success=False, error="No plan to retry")
        
        step_id = params.get("step_id")
        
        # Find failed step
        failed_step = None
        for step in self._current_plan.steps:
            if step.status == StepStatus.FAILED:
                if step_id is None or step.id == step_id:
                    failed_step = step
                    break
        
        if not failed_step:
            return SkillResult(success=False, error="No failed step to retry")
        
        # Reset and re-execute
        failed_step.status = StepStatus.PENDING
        failed_step.error = ""
        
        return await self._action_step({}, context)
    
    def _action_abort(self, params: Dict, context: Dict) -> SkillResult:
        """Abort current plan."""
        if self._current_plan:
            self._current_plan.status = "aborted"
            self._current_plan = None
        
        return SkillResult(success=True, message="Plan aborted")
    
    def _action_list_plans(self, params: Dict, context: Dict) -> SkillResult:
        """List plan history."""
        plans = [
            {"goal": p.goal, "status": p.status, "steps": len(p.steps)}
            for p in self._plan_history
        ]
        
        return SkillResult(
            success=True,
            data={"plans": plans},
            message=f"{len(plans)} plans in history"
        )
    
    # ==================== HEALTH ====================
    
    def health(self) -> SkillHealth:
        """Check planning skill health."""
        if not self._loaded:
            return SkillHealth.UNAVAILABLE
        if not self._skill_router:
            return SkillHealth.DEGRADED
        return SkillHealth.READY
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """Preview planning action."""
        if action == "plan":
            return f"Would create plan for: {params.get('goal', 'unknown')}"
        if action == "execute_plan":
            return "Would execute current plan"
        if action == "decompose":
            return f"Would decompose: {params.get('goal', 'unknown')} into steps"
        return f"Would execute planning.{action}"
