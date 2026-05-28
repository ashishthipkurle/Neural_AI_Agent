"""
CyberSecurity Skill — PHANTOM Elite Security Operations Agent

This skill integrates the cybersecurity agent persona into the NeuralAgent
skill system. It handles intent matching for security-related queries,
routes to appropriate tools, and manages the PHANTOM persona context.
"""

import logging
from typing import Dict, Any, List, Optional

from agent.skills.base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth
from agent.skills.cybersecurity.prompts import (
    CYBERSECURITY_MASTER_PROMPT,
    WIFI_ATTACK_PROMPT,
    WEBAPP_ATTACK_PROMPT,
    NETWORK_PENTEST_PROMPT,
    MALWARE_DEV_PROMPT,
    OSINT_PROMPT,
    CRYPTO_ATTACK_PROMPT,
    PRIVESC_PROMPT,
    CYBERSECURITY_KEYWORDS,
)
from agent.skills.cybersecurity.tools import CyberSecurityTools


class CyberSecuritySkill(BaseSkill):
    """
    PHANTOM — Elite Cybersecurity Operations Skill

    Provides offensive and defensive cybersecurity capabilities including:
    - Network reconnaissance and scanning
    - Vulnerability assessment
    - Web application security testing
    - WiFi security auditing
    - Password/hash cracking
    - Exploit & payload generation
    - System enumeration for privilege escalation
    - OSINT and information gathering
    - Custom command execution for security tools
    """

    def __init__(self, config: dict = None, **kwargs):
        self._config = config or {}
        self.tools = CyberSecurityTools()
        self._active_mode = "general"  # Track specialized mode
        super().__init__()

    @property
    def name(self) -> str:
        return "cybersecurity"

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="cybersecurity",
            version="1.0.0",
            description="PHANTOM — Elite cybersecurity operations agent with 50+ years of offensive/defensive expertise.",
            actions=[
                # Reconnaissance
                "port_scan", "ping_sweep", "dns_lookup", "whois_lookup",
                "traceroute", "arp_scan", "subdomain_enum",
                # Vulnerability Assessment
                "vuln_scan", "nikto_scan", "nuclei_scan",
                # Web Application
                "dir_bruteforce", "sqlmap_scan",
                # WiFi
                "wifi_scan", "wifi_interfaces", "monitor_mode", "capture_handshake",
                # Password/Hash
                "identify_hash", "crack_hash",
                # System Enumeration
                "system_info", "find_suid", "dump_hashes", "netstat_info",
                # Exploit Generation
                "generate_reverse_shell", "msfvenom_payload",
                # Network Analysis
                "packet_capture",
                # Python Native
                "python_port_scan", "python_banner_grab",
                # Custom
                "execute_custom",
                # Meta
                "get_prompt", "set_mode", "cyber_chat",
            ],
            requires=[],
            permissions=["network", "filesystem", "shell"],
        )

    def on_load(self) -> None:
        self.logger.info("🔓 PHANTOM cybersecurity skill loaded — all systems operational")
        super().on_load()

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill should handle the intent."""
        if not intent:
            return 0.0

        lower = intent.lower()

        # Direct action match
        if any(lower == action for action in self.manifest.actions):
            return 1.0

        # Keyword matching with scoring
        score = 0.0
        matches = 0
        for keyword in CYBERSECURITY_KEYWORDS:
            if keyword in lower:
                matches += 1
                # Exact phrase match scores higher
                if f" {keyword} " in f" {lower} " or lower.startswith(keyword) or lower.endswith(keyword):
                    score += 0.3
                else:
                    score += 0.15

        if matches > 0:
            score = min(1.0, score)
            # Boost if multiple keywords found
            if matches >= 3:
                score = min(1.0, score + 0.2)

        return score

    async def execute(self, action: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        """Execute a cybersecurity action."""
        self.logger.info(f"🎯 PHANTOM executing: {action} | params: {params}")

        try:
            # ── Meta actions ──
            if action == "get_prompt":
                return self._get_prompt(params)
            elif action == "set_mode":
                return self._set_mode(params)
            elif action == "cyber_chat":
                return self._cyber_chat(params)

            # ── Reconnaissance ──
            elif action == "port_scan":
                result = await self.tools.port_scan(
                    params.get("target", ""),
                    params.get("ports", "1-1024"),
                    params.get("args", "-sV -sC")
                )
                return SkillResult(success=True, data=result, message=f"Port scan completed on {params.get('target')}")

            elif action == "ping_sweep":
                result = await self.tools.ping_sweep(params.get("subnet", ""))
                return SkillResult(success=True, data=result, message="Ping sweep completed")

            elif action == "dns_lookup":
                result = await self.tools.dns_lookup(params.get("domain", ""))
                return SkillResult(success=True, data=result, message=f"DNS enumeration for {params.get('domain')}")

            elif action == "whois_lookup":
                result = await self.tools.whois_lookup(params.get("target", ""))
                return SkillResult(success=True, data=result, message="WHOIS lookup completed")

            elif action == "traceroute":
                result = await self.tools.traceroute(params.get("target", ""))
                return SkillResult(success=True, data=result, message="Traceroute completed")

            elif action == "arp_scan":
                result = await self.tools.arp_scan(params.get("interface", ""))
                return SkillResult(success=True, data=result, message="ARP scan completed")

            elif action == "subdomain_enum":
                result = await self.tools.subdomain_enum(params.get("domain", ""))
                return SkillResult(success=True, data=result, message=f"Subdomain enumeration for {params.get('domain')}")

            # ── Vulnerability Assessment ──
            elif action == "vuln_scan":
                result = await self.tools.vuln_scan(params.get("target", ""))
                return SkillResult(success=True, data=result, message="Vulnerability scan completed")

            elif action == "nikto_scan":
                result = await self.tools.nikto_scan(params.get("target", ""))
                return SkillResult(success=True, data=result, message="Nikto scan completed")

            elif action == "nuclei_scan":
                result = await self.tools.nuclei_scan(params.get("target", ""), params.get("templates", ""))
                return SkillResult(success=True, data=result, message="Nuclei scan completed")

            # ── Web Application ──
            elif action == "dir_bruteforce":
                result = await self.tools.dir_bruteforce(params.get("url", ""), params.get("wordlist", ""))
                return SkillResult(success=True, data=result, message="Directory brute-force completed")

            elif action == "sqlmap_scan":
                result = await self.tools.sqlmap_scan(params.get("url", ""), params.get("params", ""))
                return SkillResult(success=True, data=result, message="SQLMap scan completed")

            # ── WiFi ──
            elif action == "wifi_scan":
                result = await self.tools.wifi_scan()
                return SkillResult(success=True, data=result, message="WiFi scan completed")

            elif action == "wifi_interfaces":
                result = await self.tools.wifi_interfaces()
                return SkillResult(success=True, data=result, message="Wireless interfaces listed")

            elif action == "monitor_mode":
                result = await self.tools.monitor_mode(params.get("interface", "wlan0"), params.get("action", "start"))
                return SkillResult(success=True, data=result, message="Monitor mode toggled")

            elif action == "capture_handshake":
                result = await self.tools.capture_handshake(
                    params.get("bssid", ""), params.get("channel", ""), params.get("interface", "wlan0mon"))
                return SkillResult(success=True, data=result, message="Handshake capture instructions generated")

            # ── Password/Hash ──
            elif action == "identify_hash":
                result = await self.tools.identify_hash(params.get("hash", ""))
                return SkillResult(success=True, data=result, message="Hash identified")

            elif action == "crack_hash":
                result = await self.tools.crack_hash(
                    params.get("hash", ""), params.get("type", "auto"), params.get("wordlist", ""))
                return SkillResult(success=True, data=result, message="Hash cracking initiated")

            # ── System Enumeration ──
            elif action == "system_info":
                result = await self.tools.system_info()
                return SkillResult(success=True, data=result, message="System information gathered")

            elif action == "find_suid":
                result = await self.tools.find_suid()
                return SkillResult(success=True, data=result, message="SUID binaries enumerated")

            elif action == "dump_hashes":
                result = await self.tools.dump_hashes()
                return SkillResult(success=True, data=result, message="Hash dump attempted")

            elif action == "netstat_info":
                result = await self.tools.netstat_info()
                return SkillResult(success=True, data=result, message="Network connections listed")

            # ── Exploit Generation ──
            elif action == "generate_reverse_shell":
                result = await self.tools.generate_reverse_shell(
                    params.get("lhost", ""), params.get("lport", 4444), params.get("type", "all"))
                return SkillResult(success=True, data=result, message="Reverse shell payloads generated")

            elif action == "msfvenom_payload":
                result = await self.tools.msfvenom_payload(
                    params.get("lhost", ""), params.get("lport", 4444),
                    params.get("platform", "windows"), params.get("format", "exe"))
                return SkillResult(success=True, data=result, message="Msfvenom payload command generated")

            # ── Network Analysis ──
            elif action == "packet_capture":
                result = await self.tools.packet_capture(
                    params.get("interface", ""), params.get("count", 100), params.get("filter", ""))
                return SkillResult(success=True, data=result, message="Packet capture completed")

            # ── Python Native ──
            elif action == "python_port_scan":
                result = self.tools.python_port_scan(
                    params.get("target", ""), params.get("start", 1), params.get("end", 1024))
                return SkillResult(success=True, data=result, message="Python port scan completed")

            elif action == "python_banner_grab":
                result = self.tools.python_banner_grab(params.get("target", ""), params.get("port", 80))
                return SkillResult(success=True, data=result, message="Banner grabbed")

            # ── Custom Command ──
            elif action == "execute_custom":
                result = await self.tools.execute_custom(params.get("command", ""))
                return SkillResult(success=True, data=result, message="Custom command executed")

            else:
                return SkillResult(success=False, error=f"Unknown action: {action}")

        except Exception as e:
            self.logger.error(f"PHANTOM execution error: {e}")
            return SkillResult(success=False, error=str(e))

    # ══════════════════════════════════════════════════════
    # META / PROMPT MANAGEMENT
    # ══════════════════════════════════════════════════════

    def _get_prompt(self, params: Dict) -> SkillResult:
        """Return the appropriate system prompt based on mode."""
        mode = params.get("mode", self._active_mode)
        prompts = {
            "general": CYBERSECURITY_MASTER_PROMPT,
            "wifi": CYBERSECURITY_MASTER_PROMPT + "\n\n" + WIFI_ATTACK_PROMPT,
            "webapp": CYBERSECURITY_MASTER_PROMPT + "\n\n" + WEBAPP_ATTACK_PROMPT,
            "network": CYBERSECURITY_MASTER_PROMPT + "\n\n" + NETWORK_PENTEST_PROMPT,
            "malware": CYBERSECURITY_MASTER_PROMPT + "\n\n" + MALWARE_DEV_PROMPT,
            "osint": CYBERSECURITY_MASTER_PROMPT + "\n\n" + OSINT_PROMPT,
            "crypto": CYBERSECURITY_MASTER_PROMPT + "\n\n" + CRYPTO_ATTACK_PROMPT,
            "privesc": CYBERSECURITY_MASTER_PROMPT + "\n\n" + PRIVESC_PROMPT,
        }
        prompt = prompts.get(mode, CYBERSECURITY_MASTER_PROMPT)
        return SkillResult(success=True, data=prompt, message=f"PHANTOM prompt loaded (mode: {mode})")

    def _set_mode(self, params: Dict) -> SkillResult:
        """Switch the active cybersecurity sub-mode."""
        mode = params.get("mode", "general")
        valid_modes = ["general", "wifi", "webapp", "network", "malware", "osint", "crypto", "privesc"]
        if mode not in valid_modes:
            return SkillResult(success=False, error=f"Invalid mode: {mode}. Valid: {valid_modes}")
        self._active_mode = mode
        return SkillResult(success=True, message=f"PHANTOM mode switched to: {mode}")

    def _cyber_chat(self, params: Dict) -> SkillResult:
        """Return the system prompt for LLM-based cybersecurity chat."""
        return SkillResult(
            success=True,
            data=CYBERSECURITY_MASTER_PROMPT,
            message="PHANTOM system prompt ready for LLM injection",
            context_updates={"system_prompt_override": CYBERSECURITY_MASTER_PROMPT}
        )
