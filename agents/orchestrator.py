"""
INDRA OS — Orchestrator (INDRA's Manager Brain)

This is the core intelligence that makes INDRA a manager, not just a chatbot.
It receives user input, classifies intent, decomposes complex tasks,
delegates to specialist agents, monitors their progress, and reports back.

INDRA doesn't do the work — INDRA manages the workers.
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

from agents.base_agent import AgentStatus, BaseAgent
from agents.agent_registry import AgentRegistry
from agents.message_bus import Message, MessageBus
from agents.task import Task, TaskResult, TaskPriority, TaskStatus

logger = logging.getLogger("Orchestrator")


class IndraOrchestrator:
    """
    INDRA's manager brain. Routes user requests to the right agent,
    monitors progress, handles failures, and reports back to the user.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        bus: MessageBus,
        llm_func=None,
        speak_func=None,
    ):
        """
        Args:
            registry: The agent registry with all registered agents.
            bus: The message bus for inter-agent communication.
            llm_func: async callable(prompt) -> str for LLM queries.
            speak_func: callable(text) to speak to the user via TTS.
        """
        self.registry = registry
        self.bus = bus
        self._llm = llm_func
        self._speak = speak_func

        # Active tasks being monitored
        self._active_tasks: dict[str, Task] = {}
        self._task_history: list[TaskResult] = []

        # Subscribe to agent events
        self._setup_subscriptions()

    def _setup_subscriptions(self):
        """Subscribe to all agent events on the message bus."""
        self.bus.subscribe("agent.*.result", self._on_agent_result, "orchestrator")
        self.bus.subscribe("agent.*.error", self._on_agent_error, "orchestrator")
        self.bus.subscribe("agent.*.progress", self._on_agent_progress, "orchestrator")

    # ── Main Entry Point ──────────────────────────────────────────────────

    async def process_user_input(self, text: str) -> dict:
        """
        Main entry point. User says something → INDRA decides what to do.

        Returns:
            dict with keys: action ("chat", "delegate", "multi_delegate"),
            agent, task_id, response, etc.
        """
        text = text.strip()
        if not text:
            return {"action": "error", "response": "Empty input"}

        logger.info(f"Processing user input: {text[:80]}")

        # Step 1: Classify the intent
        classification = await self._classify_intent(text)

        action = classification.get("action", "chat")
        target_agent = classification.get("agent", "")
        agents_list = classification.get("agents", [])

        # Step 2: Route based on classification
        if action == "chat":
            # Pure conversation — route to general agent
            return await self._handle_chat(text)

        elif action == "delegate":
            # Single agent task
            return await self._handle_delegation(text, target_agent)

        elif action == "multi_delegate":
            # Complex task needing multiple agents
            return await self._handle_multi_delegation(text, agents_list)

        else:
            return await self._handle_chat(text)

    # ── Intent Classification ─────────────────────────────────────────────

    async def _classify_intent(self, text: str) -> dict:
        """
        Use LLM to classify user intent and determine routing.

        Returns dict:
            action: "chat" | "delegate" | "multi_delegate"
            agent: str (for single delegation)
            agents: list[dict] (for multi-delegation)
        """
        # Fast-path keyword routing (no LLM needed)
        fast = self._fast_route(text)
        if fast:
            return fast

        # LLM-based classification
        if not self._llm:
            return {"action": "chat"}

        agent_list = ", ".join(
            f'"{a.name}" ({a.description})'
            for a in self.registry.get_all()
        )

        prompt = f"""You are INDRA, an AI manager routing tasks to specialist agents.

Available agents: {agent_list}

User said: "{text}"

Classify this request. Respond with ONLY valid JSON:

For pure conversation (questions, greetings, opinions):
{{"action": "chat"}}

For a task one agent can handle:
{{"action": "delegate", "agent": "<agent_name>"}}

For a complex task needing multiple agents working together:
{{"action": "multi_delegate", "agents": [
    {{"agent": "<name>", "task": "<specific sub-task description>"}},
    {{"agent": "<name>", "task": "<specific sub-task description>"}}
]}}

JSON response:"""

        try:
            response = await self._llm(prompt)
            # Extract JSON from response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            result = json.loads(response)
            logger.info(f"LLM classification: {result}")
            return result
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}, falling back to chat")
            return {"action": "chat"}

    def _fast_route(self, text: str) -> Optional[dict]:
        """
        Keyword-based fast routing using scoring. Each agent category
        gets points for matching keywords. Highest score wins.
        Returns None if no strong match (falls through to LLM).
        """
        lower = text.lower().strip()

        # Check greetings first (these are clearly not tasks)
        chat_words = [
            "hello", "hi", "hey", "how are you", "what do you think",
            "explain", "tell me", "what is", "who is", "why",
            "good morning", "good evening", "thanks", "thank you",
        ]
        if any(lower.startswith(w) for w in chat_words):
            return {"action": "chat"}

        # Score each agent category
        scores: dict[str, int] = {}

        trading_words = [
            "buy", "sell", "trade", "stock", "share",
            "market", "nifty", "sensex", "reliance", "price of",
            "stop loss", "position", "holdings", "broker",
            "invest", "dividend", "ipo",
        ]
        scores["trading"] = sum(2 if w in lower else 0 for w in trading_words)

        coding_words = [
            "write code", "create a script", "build a website",
            "build a app", "build an app", "fix this code", "fix the code",
            "debug", "python script", "javascript", "create a website",
            "create a project", "write a function", "refactor",
            "website", "html", "css", "react", "program", "code",
        ]
        scores["coding"] = sum(2 if w in lower else 0 for w in coding_words)

        hacking_words = [
            "scan network", "scan my network", "scan the network",
            "port scan", "wifi", "vulnerability", "penetration",
            "nmap", "hack", "security audit", "password audit",
            "firewall", "reconnaissance", "enumerate",
            "network scan", "devices on my network",
        ]
        scores["hacking"] = sum(2 if w in lower else 0 for w in hacking_words)

        control_words = [
            "open ", "close ", "click", "type ", "navigate",
            "go to ", "minimize", "maximize", "switch to",
            "download", "install", "screenshot", "copy file",
            "move file", "delete file", "rename",
        ]
        scores["computer_control"] = sum(2 if w in lower else 0 for w in control_words)

        workflow_words = [
            "automate", "workflow", "schedule", "every morning",
            "every day", "recurring", "when i get", "trigger",
            "automatically", "cron",
        ]
        scores["workflow"] = sum(2 if w in lower else 0 for w in workflow_words)

        content_words = [
            "write a post", "create content", "instagram post",
            "linkedin post", "tweet", "blog post", "thumbnail",
            "generate image", "create video", "make a reel",
            "social media", "article",
        ]
        scores["content_creator"] = sum(2 if w in lower else 0 for w in content_words)

        # Find best match
        best_agent = max(scores, key=scores.get)
        best_score = scores[best_agent]

        if best_score >= 2:
            return {"action": "delegate", "agent": best_agent}

        # No strong keyword match — let LLM decide
        return None

    # ── Task Handlers ─────────────────────────────────────────────────────

    async def _handle_chat(self, text: str) -> dict:
        """Route to general agent for conversation."""
        agent = self.registry.get("general")
        if not agent:
            # Fallback: use any available agent
            return {
                "action": "chat",
                "response": "I'll handle that directly, sir.",
            }

        task = Task(
            description=text,
            assigned_to="general",
            assigned_by="user",
            priority=TaskPriority.NORMAL,
        )

        # Run chat asynchronously
        asyncio.create_task(self._execute_and_report(agent, task))

        return {
            "action": "chat",
            "task_id": task.id,
            "agent": "general",
        }

    async def _handle_delegation(self, text: str, target_agent: str) -> dict:
        """Delegate a task to a single specialist agent."""
        agent = self.registry.get(target_agent)

        if not agent:
            # Try auto-routing via confidence scores
            agent = await self.registry.find_best(text)
            if not agent:
                if self._speak:
                    self._speak(
                        f"I don't have an agent available for that, sir. "
                        f"Let me handle it through general conversation."
                    )
                return await self._handle_chat(text)

        # Check if agent is busy
        if agent.status == AgentStatus.WORKING:
            if self._speak:
                self._speak(
                    f"The {agent.name} agent is currently busy, sir. "
                    f"I'll queue your request."
                )

        task = Task(
            description=text,
            assigned_to=agent.name,
            assigned_by="user",
            priority=TaskPriority.NORMAL,
        )

        self._active_tasks[task.id] = task

        if self._speak:
            self._speak(f"On it, sir. Routing to {agent.name}.")

        # Execute in background
        asyncio.create_task(self._execute_and_report(agent, task))

        return {
            "action": "delegate",
            "task_id": task.id,
            "agent": agent.name,
            "response": f"Task assigned to {agent.name} agent.",
        }

    async def _handle_multi_delegation(
        self, text: str, agents_list: list[dict]
    ) -> dict:
        """
        Handle complex tasks that need multiple agents working together.
        Decomposes into sub-tasks, assigns to agents, monitors all.
        """
        parent_task = Task(
            description=text,
            assigned_to="indra",
            assigned_by="user",
            priority=TaskPriority.HIGH,
        )

        if self._speak:
            self._speak(
                f"Complex task received, sir. "
                f"I'm breaking it down for {len(agents_list)} agents."
            )

        # Create sub-tasks
        for item in agents_list:
            agent_name = item.get("agent", "")
            sub_description = item.get("task", text)

            agent = self.registry.get(agent_name)
            if not agent:
                logger.warning(f"Agent '{agent_name}' not found, skipping sub-task")
                continue

            sub_task = Task(
                description=sub_description,
                assigned_to=agent_name,
                assigned_by="indra",
                priority=TaskPriority.HIGH,
                parent_id=parent_task.id,
            )
            parent_task.subtasks.append(sub_task)
            self._active_tasks[sub_task.id] = sub_task

            # Launch each sub-task concurrently
            asyncio.create_task(self._execute_and_report(agent, sub_task))

        self._active_tasks[parent_task.id] = parent_task

        return {
            "action": "multi_delegate",
            "task_id": parent_task.id,
            "sub_tasks": [
                {"agent": st.assigned_to, "task": st.description}
                for st in parent_task.subtasks
            ],
            "response": (
                f"Breaking this into {len(parent_task.subtasks)} sub-tasks. "
                f"I'll coordinate everything."
            ),
        }

    # ── Execution & Monitoring ────────────────────────────────────────────

    async def _execute_and_report(self, agent: BaseAgent, task: Task) -> None:
        """Execute a task and handle the result."""
        try:
            result = await agent.run_task(task)

            # Publish result to message bus
            await self.bus.publish(
                f"agent.{agent.name}.result",
                result.to_dict(),
                sender=agent.name,
            )

            # Store in history
            self._task_history.append(result)
            if len(self._task_history) > 200:
                self._task_history = self._task_history[-100:]

            # Report to user
            if self._speak:
                if result.success:
                    self._speak(
                        f"Done, sir. {result.output[:150]}"
                    )
                else:
                    self._speak(
                        f"The {agent.name} agent ran into a problem, sir. "
                        f"{result.error or 'Unknown error.'}"
                    )

            # Remove from active
            self._active_tasks.pop(task.id, None)

            # Check if this was a sub-task — update parent
            if task.parent_id and task.parent_id in self._active_tasks:
                await self._check_parent_completion(task.parent_id)

        except Exception as e:
            logger.error(f"Execute and report failed: {e}", exc_info=True)
            self._active_tasks.pop(task.id, None)

    async def _check_parent_completion(self, parent_id: str) -> None:
        """Check if all sub-tasks of a parent task are done."""
        parent = self._active_tasks.get(parent_id)
        if not parent:
            return

        all_done = all(
            st.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED)
            for st in parent.subtasks
        )

        if all_done:
            successes = sum(1 for st in parent.subtasks if st.status == TaskStatus.DONE)
            total = len(parent.subtasks)
            parent.complete()
            self._active_tasks.pop(parent_id, None)

            if self._speak:
                if successes == total:
                    self._speak(
                        f"All {total} sub-tasks completed successfully, sir."
                    )
                else:
                    self._speak(
                        f"{successes} of {total} sub-tasks succeeded, sir. "
                        f"{total - successes} had issues."
                    )

    # ── Event Handlers ────────────────────────────────────────────────────

    async def _on_agent_result(self, msg: Message) -> None:
        """Handle agent result events."""
        logger.info(f"Agent result: {msg.sender} → {msg.payload.get('output', '')[:60]}")

    async def _on_agent_error(self, msg: Message) -> None:
        """Handle agent error events."""
        logger.warning(f"Agent error: {msg.sender} → {msg.payload}")

        if self._speak:
            agent_name = msg.sender or "an agent"
            self._speak(
                f"Sir, {agent_name} encountered an error. "
                f"I'm looking into it."
            )

    async def _on_agent_progress(self, msg: Message) -> None:
        """Handle agent progress events."""
        # Just log — UI will pick this up via WebSocket
        pass

    # ── Status & Introspection ────────────────────────────────────────────

    def get_active_tasks(self) -> list[dict]:
        """Get all currently active tasks."""
        return [t.to_dict() for t in self._active_tasks.values()]

    def get_task_history(self, limit: int = 20) -> list[dict]:
        """Get recent task history."""
        return [r.to_dict() for r in self._task_history[-limit:]]

    def get_system_status(self) -> dict:
        """Full system status for dashboard."""
        return {
            "agents": self.registry.get_status_report(),
            "active_tasks": self.get_active_tasks(),
            "total_agents": self.registry.agent_count,
            "active_agents": self.registry.active_count,
            "tasks_in_queue": len(self._active_tasks),
            "tasks_completed_total": len(self._task_history),
        }
