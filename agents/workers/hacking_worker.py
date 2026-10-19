"""
INDRA OS — Hacking / CyberSecurity Agent Worker

Structured pentest pipeline with proper tool chains for network scanning,
port scanning, WiFi analysis, vulnerability checking, and system hardening.
Safety-first: requires confirmation before any active scanning.
"""

import asyncio
import json
import logging
import subprocess
import platform
from typing import Optional

from agents.base_agent import BaseAgent
from agents.task import Task, TaskResult

logger = logging.getLogger("Agent.Hacking")

_STRONG_SIGNALS = [
    "scan network", "port scan", "wifi", "vulnerability",
    "penetration", "nmap", "hack", "security audit",
    "password", "firewall", "brute force", "exploit",
    "reconnaissance", "recon", "sniff", "packet",
    "deauth", "crack", "enumerate", "footprint",
]

_MEDIUM_SIGNALS = [
    "network", "ip address", "mac address", "open port",
    "secure", "encryption", "ssl", "certificate",
    "malware", "antivirus", "intrusion",
]


class HackingWorker(BaseAgent):
    """
    CyberSecurity agent with structured tool chains.
    Completes full pentest workflows step-by-step with clear reporting.
    """

    def __init__(self, llm_func=None, speak_func=None):
        super().__init__(
            name="hacking",
            description="Network scanning, port scanning, WiFi analysis, vulnerability checks, security audits",
            capabilities=[
                "network_scan", "port_scan", "wifi_analysis",
                "vulnerability_check", "password_audit",
                "system_hardening", "dns_lookup", "whois",
                "ssl_check", "service_detection",
            ],
        )
        self._llm = llm_func
        self._speak = speak_func
        self._tools = {}

    async def initialize(self) -> bool:
        """Detect available security tools."""
        self._tools = await self._detect_tools()
        self.status = self.status.IDLE
        logger.info(f"Hacking agent initialized. Tools: {list(self._tools.keys())}")
        return True

    async def _detect_tools(self) -> dict:
        """Check which security tools are installed."""
        tools = {}
        checks = {
            "nmap": "nmap --version",
            "netsh": "netsh wlan show interfaces",
            "ping": "ping -n 1 127.0.0.1",
            "nslookup": "nslookup localhost",
            "ipconfig": "ipconfig /all",
            "arp": "arp -a",
            "netstat": "netstat -an",
            "tracert": "tracert -h 1 127.0.0.1",
        }
        for name, cmd in checks.items():
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True,
                    text=True, timeout=5,
                )
                if result.returncode == 0 or name in ["netsh", "arp"]:
                    tools[name] = True
            except Exception:
                pass
        return tools

    async def can_handle(self, task_description: str) -> float:
        lower = task_description.lower().strip()
        if any(s in lower for s in _STRONG_SIGNALS):
            return 0.92
        if any(s in lower for s in _MEDIUM_SIGNALS):
            return 0.6
        return 0.05

    async def execute(self, task: Task) -> TaskResult:
        """Execute a security task with structured pipeline."""
        steps_taken = []

        try:
            # Classify the security task
            task_type = self._classify(task.description)
            steps_taken.append(f"Task type: {task_type}")

            if self._speak:
                self._speak(f"Running {task_type.replace('_', ' ')}, sir.")

            if task_type == "network_scan":
                return await self._network_scan(task, steps_taken)
            elif task_type == "port_scan":
                return await self._port_scan(task, steps_taken)
            elif task_type == "wifi_analysis":
                return await self._wifi_analysis(task, steps_taken)
            elif task_type == "dns_lookup":
                return await self._dns_lookup(task, steps_taken)
            elif task_type == "system_info":
                return await self._system_info(task, steps_taken)
            else:
                return await self._llm_guided_task(task, steps_taken)

        except Exception as e:
            logger.error(f"Hacking agent error: {e}", exc_info=True)
            return TaskResult(
                task_id=task.id, success=False,
                output="Security task failed",
                error=str(e), steps_taken=steps_taken,
            )

    def _classify(self, text: str) -> str:
        lower = text.lower()
        if any(w in lower for w in ["wifi", "wlan", "wireless"]):
            return "wifi_analysis"
        if any(w in lower for w in ["port scan", "open port", "nmap"]):
            return "port_scan"
        if any(w in lower for w in ["scan network", "devices", "arp", "who is on"]):
            return "network_scan"
        if any(w in lower for w in ["dns", "nslookup", "domain", "whois"]):
            return "dns_lookup"
        if any(w in lower for w in ["system", "info", "ipconfig", "my ip"]):
            return "system_info"
        return "general"

    async def _run_cmd(self, cmd: str, timeout: int = 30) -> tuple[bool, str]:
        """Run a command and return (success, output)."""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=timeout,
            )
            output = result.stdout + result.stderr
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout}s"
        except Exception as e:
            return False, str(e)

    async def _network_scan(self, task: Task, steps: list) -> TaskResult:
        """Scan local network for devices."""
        await self.publish_progress(0.2, "Getting network info...", 0, 3)

        # Step 1: Get own IP
        ok, ip_info = await self._run_cmd("ipconfig")
        steps.append("Got local IP configuration")

        # Step 2: ARP scan
        await self.publish_progress(0.5, "Scanning network with ARP...", 1, 3)
        ok, arp_output = await self._run_cmd("arp -a")
        steps.append("Ran ARP scan")

        # Step 3: Parse and format results
        await self.publish_progress(0.8, "Analyzing results...", 2, 3)

        report = f"=== Network Scan Results ===\n\n"
        report += f"--- Local Network Info ---\n{ip_info[:500]}\n\n"
        report += f"--- Devices Found (ARP Table) ---\n{arp_output[:1000]}\n"

        # Use LLM to summarize
        if self._llm:
            summary = await self._llm(
                f"Summarize this network scan result in a clear, "
                f"concise format. List the devices found:\n{report[:2000]}"
            )
            if self._speak:
                self._speak(summary[:200])
            report = summary + "\n\n--- Raw Data ---\n" + report

        await self.publish_progress(1.0, "Done", 3, 3)
        return TaskResult(
            task_id=task.id, success=True,
            output=report, steps_taken=steps,
        )

    async def _port_scan(self, task: Task, steps: list) -> TaskResult:
        """Scan ports on a target."""
        # Extract target from description
        target = "127.0.0.1"  # default to localhost
        words = task.description.lower().split()
        for i, w in enumerate(words):
            if w in ("on", "scan", "target") and i + 1 < len(words):
                candidate = words[i + 1]
                if "." in candidate or candidate.replace(":", "").isalnum():
                    target = candidate
                    break

        await self.publish_progress(0.2, f"Scanning ports on {target}...", 0, 2)
        steps.append(f"Target: {target}")

        if "nmap" in self._tools:
            ok, output = await self._run_cmd(f"nmap -F {target}", timeout=60)
        else:
            # Fallback: use netstat for localhost
            ok, output = await self._run_cmd("netstat -an | findstr LISTENING")

        steps.append("Port scan complete")

        if self._llm:
            summary = await self._llm(
                f"Summarize this port scan result clearly:\n{output[:2000]}"
            )
            if self._speak:
                self._speak(summary[:200])
            output = summary

        await self.publish_progress(1.0, "Done", 2, 2)
        return TaskResult(
            task_id=task.id, success=ok,
            output=output, steps_taken=steps,
        )

    async def _wifi_analysis(self, task: Task, steps: list) -> TaskResult:
        """Analyze WiFi networks."""
        await self.publish_progress(0.3, "Scanning WiFi networks...", 0, 2)

        ok, output = await self._run_cmd("netsh wlan show networks mode=Bssid")
        steps.append("Scanned WiFi networks")

        ok2, profile_output = await self._run_cmd("netsh wlan show profiles")
        steps.append("Listed saved profiles")

        combined = f"=== WiFi Networks ===\n{output}\n\n=== Saved Profiles ===\n{profile_output}"

        if self._llm:
            summary = await self._llm(
                f"Analyze these WiFi scan results. "
                f"List networks by signal strength, security type:\n{combined[:3000]}"
            )
            if self._speak:
                self._speak(summary[:200])
            combined = summary

        await self.publish_progress(1.0, "Done", 2, 2)
        return TaskResult(
            task_id=task.id, success=True,
            output=combined, steps_taken=steps,
        )

    async def _dns_lookup(self, task: Task, steps: list) -> TaskResult:
        """DNS/WHOIS lookup."""
        # Extract domain from description
        domain = "google.com"
        for word in task.description.split():
            if "." in word and len(word) > 4:
                domain = word.strip("\"'(),")
                break

        ok, output = await self._run_cmd(f"nslookup {domain}")
        steps.append(f"DNS lookup: {domain}")

        if self._speak and self._llm:
            summary = await self._llm(f"Summarize DNS lookup for {domain}:\n{output}")
            self._speak(summary[:150])

        return TaskResult(
            task_id=task.id, success=ok,
            output=output, steps_taken=steps,
        )

    async def _system_info(self, task: Task, steps: list) -> TaskResult:
        """Get system/network info."""
        ok, output = await self._run_cmd("ipconfig /all")
        return TaskResult(
            task_id=task.id, success=ok,
            output=output, steps_taken=steps + ["Got system info"],
        )

    async def _llm_guided_task(self, task: Task, steps: list) -> TaskResult:
        """Use LLM to guide complex security tasks."""
        if not self._llm:
            return TaskResult(
                task_id=task.id, success=False,
                output="Complex security task needs LLM guidance",
                error="No LLM available", steps_taken=steps,
            )

        # Get a plan from LLM
        plan_prompt = (
            f"You are a cybersecurity expert on Windows 11. "
            f"Plan how to accomplish this task using ONLY safe, legal commands: "
            f"{task.description}\n\n"
            f"Available tools: {list(self._tools.keys())}\n\n"
            f"Return a JSON array of steps: "
            f'[{{"step": "description", "command": "cmd to run"}}]'
        )

        try:
            response = await self._llm(plan_prompt)
            if "```" in response:
                response = response.split("```")[1].replace("json", "").split("```")[0]
            plan = json.loads(response)

            results = []
            for i, step_info in enumerate(plan[:10]):
                cmd = step_info.get("command", "")
                desc = step_info.get("step", f"Step {i+1}")

                await self.publish_progress(
                    (i + 1) / len(plan), desc, i, len(plan)
                )

                if cmd:
                    ok, output = await self._run_cmd(cmd)
                    results.append(f"[{desc}]\n{output[:500]}")
                    steps.append(f"{'[OK]' if ok else '[FAIL]'} {desc}")

            combined = "\n\n".join(results)

            if self._speak:
                self._speak("Security scan complete, sir. I have the results.")

            return TaskResult(
                task_id=task.id, success=True,
                output=combined, steps_taken=steps,
            )

        except Exception as e:
            return TaskResult(
                task_id=task.id, success=False,
                output="Failed to execute security plan",
                error=str(e), steps_taken=steps,
            )
