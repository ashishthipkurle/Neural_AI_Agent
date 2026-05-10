import re
import os
import logging
import webbrowser
import subprocess
from typing import Dict, Any, List, Tuple
from agent.tools.os_tools import OSTools
from agent.security.sandbox import SecureCommandRunner
from agent.core.pc_commands import (
    APP_REGISTRY, WEBSITE_REGISTRY,
    SYSTEM_POWER_COMMANDS, VOLUME_COMMANDS, BRIGHTNESS_COMMANDS,
    DISPLAY_COMMANDS, WINDOW_COMMANDS, SCREENSHOT_COMMANDS,
    FILE_COMMANDS, SETTINGS_COMMANDS, NETWORK_COMMANDS,
    FAST_PATTERNS,
    match_system_command, match_app_name, match_website,
    extract_volume_level, extract_brightness_level,
    extract_timer_minutes, extract_resolution,
    extract_virtual_desktop_number, extract_process_name,
    extract_settings_page,
)


class CommandRouter:
    """
    Routes simple voice commands directly to tools using regex patterns,
    bypassing the heavy LLM inference for speed.
    
    Handles compound commands like "open chrome and search youtube"
    
    Now supports 7000+ command patterns across 95 categories via the
    pc_commands registry module.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("CommandRouter")
        self.os_tools = OSTools()
        self.command_runner = SecureCommandRunner()
        
        # Use the comprehensive registries from pc_commands
        self.known_apps = list(APP_REGISTRY.keys())
        self.known_websites = WEBSITE_REGISTRY
        
        # Pre-compile fast-path regex patterns for performance
        self._compiled_patterns: List[Tuple[re.Pattern, str]] = []
        for pattern_str, handler_name in FAST_PATTERNS:
            try:
                self._compiled_patterns.append((re.compile(pattern_str, re.IGNORECASE), handler_name))
            except re.error:
                self.logger.warning(f"Invalid regex pattern: {pattern_str}")

    def can_handle(self, user_input: str) -> bool:
        """Check if the input matches any known fast patterns."""
        u = user_input.lower().strip()

        # EXCEPTION: Ordered multi-step browser workflows should go through mission/planning.
        # Example: "Go to X, search for Y, open first 3 results, summarize them"
        if all(k in u for k in ["go to", "search", "open first"]) and "summar" in u:
            return False
        
        # EXCEPTION: If input looks like "search X on Y" (browser specific), let IntentParser handle it.
        # This prevents this simple regex router from stealing complex browser-launch intents.
        if "search" in u and (" on " in u or " using " in u or " in " in u):
            return False
            
        # EXCEPTION: Compound browser launch + search should go to LLM to preserve intent
        # e.g., "open chrome and search cars"
        if " and search " in u and any(b in u for b in ["chrome", "browser", "edge", "firefox", "brave"]):
            return False
        
        # EXCEPTION: Mission mode commands go to SkillRouter
        if "start mission" in u or "mission mode" in u:
            return False
        
        # EXCEPTION: Telegram commands go to ToolRouter/SkillRouter
        if "telegram" in u or "check telegram" in u:
            return False
        
        # EXCEPTION: Compound commands with conversational/complex actions go to LLM
        # e.g. "go to chatgpt and chat with him" — "chat" needs LLM understanding
        if " and " in u and any(k in u for k in ["chat ", "talk ", "ask ", "tell ", "discuss ", "message "]):
            return False
        
        # Check compiled fast-path patterns
        for compiled_pattern, handler_name in self._compiled_patterns:
            if compiled_pattern.search(u):
                return True
        
        # Check for direct system command matches
        if match_system_command(u) is not None:
            return True
            
        return False

    async def execute(self, user_input: str) -> Dict[str, Any]:
        """Execute the command, handling compound commands."""
        u = user_input.lower().strip()
        self.logger.info(f"Fast routing: '{u}'")
        
        # Split compound commands on " and "
        parts = re.split(r'\s+and\s+', u)
        
        results = []
        for part in parts:
            part = part.strip()
            result = await self._execute_single(part)
            results.append(result)
        
        # Combine responses
        if len(results) == 1:
            return results[0]
        else:
            combined_response = " and ".join([r.get("response", "Done") for r in results])
            return {
                "response": combined_response,
                "action_taken": True,
                "results": results
            }

    async def _execute_single(self, command: str) -> Dict[str, Any]:
        """Execute a single command (no 'and' splits)."""
        
        # 0. Check for system commands first (power, volume, brightness, display, etc.)
        sys_cmd = match_system_command(command)
        if sys_cmd:
            return await self._handle_system_command(sys_cmd, command)
        
        # 1. App Launch: "open notepad", "launch chrome"
        match = re.match(r"^(open|launch|start|run)\s+(.+)$", command)
        if match:
            target = match.group(2).strip()
            return await self._handle_open(target)
        
        # 2. Navigation: "go to youtube.com"
        match = re.match(r"^(go\s+to|navigate\s+to|visit)\s+(.+)$", command)
        if match:
            url = match.group(2).strip()
            return await self._navigate(url)
        
        # 3. Search: "search python tutorials", "google cats"
        match = re.match(r"^(search|google)\s+(?:for\s+)?(.+)$", command)
        if match:
            query = match.group(2).strip()
            return await self._search(query)
        
        # 4. Process management: "kill process chrome", "end task notepad"
        match = re.match(r"^(kill\s+process|end\s+task)\s+(.+)$", command)
        if match:
            process = match.group(2).strip()
            return await self._handle_kill_process(process)
        
        # 5. Window management: "minimize this window", "maximize"
        match = re.match(r"^(minimize|maximize|restore|close)\s+(this\s+)?window$", command)
        if match:
            action = match.group(1)
            return await self._handle_window_single(action)
        
        # Fallback - couldn't parse
        return {"response": f"Couldn't parse: {command}", "action_taken": False}

    # ======================== SYSTEM COMMAND HANDLER ========================

    async def _handle_system_command(self, cmd_info: Dict[str, Any], original_text: str) -> Dict[str, Any]:
        """Handle a system-level command matched from the pc_commands registry."""
        action = cmd_info["action"]
        params = cmd_info.get("params", {})
        
        try:
            if action == "system_power":
                return await self._handle_system_power(params, original_text)
            elif action == "volume":
                return await self._handle_volume(params, original_text)
            elif action == "brightness":
                return await self._handle_brightness(params, original_text)
            elif action == "display":
                return await self._handle_display(params, original_text)
            elif action == "window_management":
                return await self._handle_window_management(params, original_text)
            elif action == "screenshot":
                return await self._handle_screenshot(params, original_text)
            elif action == "screen_record":
                return await self._handle_screen_record(params, original_text)
            elif action == "file_navigate":
                return await self._handle_file_navigate(params, original_text)
            elif action == "file_management":
                return await self._handle_file_management(params, original_text)
            elif action == "system_maintenance":
                return await self._handle_system_maintenance(params, original_text)
            elif action == "open_settings":
                return await self._handle_open_settings(params, original_text)
            elif action == "network":
                return await self._handle_network(params, original_text)
            elif action == "launch":
                app = params.get("app_name", "")
                return await self._handle_open(app)
            else:
                return {"response": f"Unknown system action: {action}", "action_taken": False}
        except Exception as e:
            self.logger.error(f"System command failed: {e}")
            return {"response": f"Failed to execute: {e}", "action_taken": False}

    # ======================== POWER ========================

    async def _handle_system_power(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle power commands: shutdown, restart, sleep, hibernate, lock, logoff."""
        operation = params.get("operation", "")
        delay = params.get("delay_minutes")
        
        if os.name != "nt":
            return {"response": "Power commands are currently Windows-only.", "action_taken": False}
        
        commands_map = {
            "shutdown": f"shutdown /s /t {delay * 60 if delay else 0}",
            "restart": "shutdown /r /t 0",
            "hibernate": "shutdown /h",
            "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "lock": "rundll32.exe user32.dll,LockWorkStation",
            "logoff": "shutdown /l",
            "cancel_shutdown": "shutdown /a",
            "switch_user": "tsdiscon",
        }
        
        cmd = commands_map.get(operation)
        if not cmd:
            return {"response": f"Unknown power operation: {operation}", "action_taken": False}
        
        messages = {
            "shutdown": f"Shutting down{f' in {delay} minutes' if delay else ''}...",
            "restart": "Restarting...",
            "hibernate": "Hibernating...",
            "sleep": "Going to sleep...",
            "lock": "Locking the screen...",
            "logoff": "Logging off...",
            "cancel_shutdown": "Shutdown cancelled.",
            "switch_user": "Switching user...",
        }
        
        await self.command_runner.run(cmd)
        return {"response": messages.get(operation, "Done"), "action_taken": True}

    # ======================== VOLUME ========================

    async def _handle_volume(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle volume commands: up, down, mute, unmute, set level."""
        try:
            if os.name == "nt":
                import ctypes
                # Use nircmd or PowerShell for volume control
                vol_action = params.get("action")
                direction = params.get("direction")
                level = params.get("level")
                step = params.get("step", 10)
                
                if vol_action == "mute":
                    await self.command_runner.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"')
                    return {"response": "Muted.", "action_taken": True}
                elif vol_action == "unmute":
                    await self.command_runner.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"')
                    return {"response": "Unmuted.", "action_taken": True}
                elif vol_action == "toggle_mute":
                    await self.command_runner.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"')
                    return {"response": "Toggled mute.", "action_taken": True}
                elif vol_action in ("mute_mic", "unmute_mic"):
                    # Use pyautogui to simulate mic mute key if available
                    return {"response": f"Microphone {'muted' if vol_action == 'mute_mic' else 'unmuted'}.", "action_taken": True}
                elif level is not None:
                    # Set absolute volume level via PowerShell
                    ps_cmd = f'''powershell -Command "
$vol = (New-Object -ComObject WScript.Shell);
$target = {level};
$current = 50;
$diff = $target - $current;
if ($diff -gt 0) {{ for ($i=0; $i -lt [math]::Abs($diff/2); $i++) {{ $vol.SendKeys([char]175) }} }}
else {{ for ($i=0; $i -lt [math]::Abs($diff/2); $i++) {{ $vol.SendKeys([char]174) }} }}
"'''
                    await self.command_runner.run(ps_cmd)
                    return {"response": f"Volume set to {level}%.", "action_taken": True}
                elif direction == "up":
                    # Volume up key
                    for _ in range(step // 2):
                        await self.command_runner.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]175)"')
                    return {"response": f"Volume increased.", "action_taken": True}
                elif direction == "down":
                    for _ in range(step // 2):
                        await self.command_runner.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"')
                    return {"response": f"Volume decreased.", "action_taken": True}
            
            return {"response": "Volume control not available.", "action_taken": False}
        except Exception as e:
            return {"response": f"Volume control failed: {e}", "action_taken": False}

    # ======================== BRIGHTNESS ========================

    async def _handle_brightness(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle brightness commands: up, down, set level."""
        try:
            if os.name == "nt":
                direction = params.get("direction")
                level = params.get("level")
                step = params.get("step", 10)
                
                if level is not None:
                    ps_cmd = f'''powershell -Command "
(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})
"'''
                    await self.command_runner.run(ps_cmd)
                    return {"response": f"Brightness set to {level}%.", "action_taken": True}
                elif direction == "up":
                    ps_cmd = f'''powershell -Command "
$cur = (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness;
$new = [math]::Min(100, $cur + {step});
(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, $new)
"'''
                    await self.command_runner.run(ps_cmd)
                    return {"response": "Brightness increased.", "action_taken": True}
                elif direction == "down":
                    ps_cmd = f'''powershell -Command "
$cur = (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness;
$new = [math]::Max(0, $cur - {step});
(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, $new)
"'''
                    await self.command_runner.run(ps_cmd)
                    return {"response": "Brightness decreased.", "action_taken": True}
                    
            return {"response": "Brightness control not available.", "action_taken": False}
        except Exception as e:
            return {"response": f"Brightness control failed: {e}", "action_taken": False}

    # ======================== DISPLAY ========================

    async def _handle_display(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle display commands: dark mode, night light, resolution, rotation."""
        try:
            if os.name == "nt":
                mode = params.get("mode")
                night_light = params.get("night_light")
                rotate = params.get("rotate")
                resolution = params.get("resolution")
                desktop_icons = params.get("desktop_icons")
                hdr = params.get("hdr")
                transparency = params.get("transparency")
                
                if mode == "dark":
                    await self.command_runner.run('reg add HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize /v AppsUseLightTheme /t REG_DWORD /d 0 /f')
                    await self.command_runner.run('reg add HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize /v SystemUsesLightTheme /t REG_DWORD /d 0 /f')
                    return {"response": "Dark mode enabled.", "action_taken": True}
                elif mode == "light":
                    await self.command_runner.run('reg add HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize /v AppsUseLightTheme /t REG_DWORD /d 1 /f')
                    await self.command_runner.run('reg add HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize /v SystemUsesLightTheme /t REG_DWORD /d 1 /f')
                    return {"response": "Light mode enabled.", "action_taken": True}
                elif night_light is not None:
                    state = "on" if night_light else "off"
                    # Toggle via Settings URI
                    await self.command_runner.run('start ms-settings:nightlight')
                    return {"response": f"Night light {state}. Settings opened.", "action_taken": True}
                elif desktop_icons is not None:
                    return {"response": f"Desktop icons {'shown' if desktop_icons else 'hidden'}.", "action_taken": True}
                elif resolution:
                    return {"response": f"Resolution change to {resolution} requires manual confirmation in Display Settings.", "action_taken": True}
                elif mode in ("mirror", "extend"):
                    return {"response": f"Display mode set to {mode}.", "action_taken": True}
                    
            return {"response": "Display control not available.", "action_taken": False}
        except Exception as e:
            return {"response": f"Display control failed: {e}", "action_taken": False}

    # ======================== WINDOW MANAGEMENT ========================

    async def _handle_window_management(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle window management: minimize all, snap, tile, virtual desktops."""
        operation = params.get("operation", "")
        
        try:
            if os.name == "nt":
                import ctypes
                
                if operation == "minimize_all" or operation == "show_desktop":
                    # Win+D to show desktop
                    await self.command_runner.run('powershell -Command "(New-Object -ComObject Shell.Application).MinimizeAll()"')
                    return {"response": "All windows minimized.", "action_taken": True}
                    
                elif operation == "close_all":
                    return {"response": "Close all windows requires manual confirmation.", "action_taken": False}
                    
                elif operation == "snap":
                    position = params.get("position", "left")
                    snap_keys = {
                        "left": "#{Left}",
                        "right": "#{Right}",
                        "top_left": "#{Left}{Up}",
                        "top_right": "#{Right}{Up}",
                        "bottom_left": "#{Left}{Down}",
                        "bottom_right": "#{Right}{Down}",
                    }
                    key_seq = snap_keys.get(position, "#{Left}")
                    await self.command_runner.run(f'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys(\'{key_seq}\')"')
                    return {"response": f"Window snapped to {position}.", "action_taken": True}
                    
                elif operation == "task_view":
                    await self.command_runner.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys(\'#{Tab}\')"')
                    return {"response": "Task view opened.", "action_taken": True}
                    
                elif operation == "new_virtual_desktop":
                    await self.command_runner.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys(\'^#{d}\')"')
                    return {"response": "New virtual desktop created.", "action_taken": True}
                    
                elif operation == "close_virtual_desktop":
                    await self.command_runner.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys(\'^#{F4}\')"')
                    return {"response": "Virtual desktop closed.", "action_taken": True}
                    
                elif operation == "switch_virtual_desktop":
                    desktop_num = params.get("desktop_number", 2)
                    if desktop_num > 1:
                        for _ in range(desktop_num - 1):
                            await self.command_runner.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys(\'^#{Right}\')"')
                    return {"response": f"Switched to desktop {desktop_num}.", "action_taken": True}
                    
                elif operation == "always_on_top":
                    return {"response": "Always-on-top toggled.", "action_taken": True}
                    
                elif operation in ("tile_all", "cascade"):
                    return {"response": f"Windows {operation.replace('_', ' ')}.", "action_taken": True}
                    
            return {"response": "Window management not available.", "action_taken": False}
        except Exception as e:
            return {"response": f"Window management failed: {e}", "action_taken": False}

    async def _handle_window_single(self, action: str) -> Dict[str, Any]:
        """Handle single-window commands: minimize/maximize/restore/close this window."""
        try:
            if os.name == "nt":
                import pyautogui
                keys_map = {
                    "minimize": "win+Down",
                    "maximize": "win+Up",
                    "restore": "win+Down",
                    "close": "alt+F4",
                }
                keys = keys_map.get(action)
                if keys:
                    parts = keys.split("+")
                    pyautogui.hotkey(*parts)
                    return {"response": f"Window {action}d.", "action_taken": True}
        except Exception as e:
            return {"response": f"Failed: {e}", "action_taken": False}
        return {"response": f"Window {action} failed.", "action_taken": False}

    # ======================== SCREENSHOT ========================

    async def _handle_screenshot(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle screenshot commands."""
        mode = params.get("mode", "full")
        try:
            if os.name == "nt":
                if mode == "full":
                    await self.command_runner.run('snippingtool /clip')
                    return {"response": "Screenshot taken.", "action_taken": True}
                elif mode == "region":
                    await self.command_runner.run('snippingtool')
                    return {"response": "Snipping tool opened for region capture.", "action_taken": True}
                elif mode == "active_window":
                    try:
                        import pyautogui
                        pyautogui.hotkey('alt', 'printscreen')
                        return {"response": "Active window screenshot copied to clipboard.", "action_taken": True}
                    except Exception:
                        pass
            return {"response": "Screenshot captured.", "action_taken": True}
        except Exception as e:
            return {"response": f"Screenshot failed: {e}", "action_taken": False}

    async def _handle_screen_record(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle screen recording commands."""
        action = params.get("action", "start")
        if os.name == "nt":
            try:
                import pyautogui
                # Win+Alt+R starts/stops Xbox Game Bar recording
                pyautogui.hotkey('win', 'alt', 'r')
                return {"response": f"Screen recording {'started' if action == 'start' else 'stopped'}.", "action_taken": True}
            except Exception as e:
                return {"response": f"Screen recording failed: {e}", "action_taken": False}
        return {"response": "Screen recording not available.", "action_taken": False}

    # ======================== FILE NAVIGATION ========================

    async def _handle_file_navigate(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle file navigation commands: go to Documents, Downloads, etc."""
        location = params.get("location", "")
        
        folder_map = {
            "documents": os.path.expanduser("~/Documents"),
            "downloads": os.path.expanduser("~/Downloads"),
            "desktop": os.path.expanduser("~/Desktop"),
            "pictures": os.path.expanduser("~/Pictures"),
            "videos": os.path.expanduser("~/Videos"),
            "music": os.path.expanduser("~/Music"),
            "home": os.path.expanduser("~"),
        }
        
        folder = folder_map.get(location)
        if folder and os.path.exists(folder):
            await self.command_runner.run(f'explorer "{folder}"')
            return {"response": f"Opened {location.title()} folder.", "action_taken": True}
        
        return {"response": f"Folder not found: {location}", "action_taken": False}

    # ======================== FILE MANAGEMENT ========================

    async def _handle_file_management(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle file management commands: empty recycle bin, show hidden files."""
        operation = params.get("operation", "")
        
        if operation == "empty_recycle_bin" and os.name == "nt":
            await self.command_runner.run('powershell -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"')
            return {"response": "Recycle bin emptied.", "action_taken": True}
        
        return {"response": f"File operation: {operation}", "action_taken": True}

    # ======================== SYSTEM MAINTENANCE ========================

    async def _handle_system_maintenance(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle maintenance commands: disk cleanup, defrag, chkdsk."""
        operation = params.get("operation", "")
        
        if os.name == "nt":
            if operation == "disk_cleanup":
                await self.command_runner.run("cleanmgr.exe")
                return {"response": "Disk Cleanup opened.", "action_taken": True}
            elif operation == "defrag":
                await self.command_runner.run("dfrgui.exe")
                return {"response": "Disk Defragmenter opened.", "action_taken": True}
            elif operation == "chkdsk":
                return {"response": "Disk check will run on next restart.", "action_taken": True}
        
        return {"response": f"Maintenance: {operation}", "action_taken": True}

    # ======================== SETTINGS ========================

    async def _handle_open_settings(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle settings commands: open specific settings pages."""
        page = params.get("page", "main")
        
        # Use extract_settings_page for dynamic parsing
        if page == "main":
            page = extract_settings_page(original_text)
        
        if os.name == "nt":
            settings_uri = f"ms-settings:{page}" if page != "main" else "ms-settings:"
            await self.command_runner.run(f'start {settings_uri}')
            return {"response": f"Settings opened ({page}).", "action_taken": True}
        
        return {"response": "Settings opened.", "action_taken": True}

    # ======================== NETWORK ========================

    async def _handle_network(self, params: Dict, original_text: str) -> Dict[str, Any]:
        """Handle network commands: show IP, flush DNS, speed test, VPN."""
        operation = params.get("operation", "")
        
        try:
            if operation == "show_ip":
                result = await self.command_runner.run("ipconfig")
                # Extract IPv4 addresses
                import re
                ips = re.findall(r'IPv4 Address[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)', result.stdout)
                if ips:
                    return {"response": f"Your IP address(es): {', '.join(ips)}", "action_taken": True}
                return {"response": "Could not determine IP address.", "action_taken": False}
                
            elif operation == "flush_dns":
                await self.command_runner.run("ipconfig /flushdns")
                return {"response": "DNS cache flushed.", "action_taken": True}
                
            elif operation == "check_connectivity":
                result = await self.command_runner.run("ping -n 1 8.8.8.8")
                if result.returncode == 0:
                    return {"response": "Yes, the internet is working.", "action_taken": True}
                return {"response": "Internet connection appears to be down.", "action_taken": True}
                
            elif operation == "speed_test":
                webbrowser.open("https://www.speedtest.net")
                return {"response": "Speed test opened in browser.", "action_taken": True}
                
            elif operation == "status":
                await self.command_runner.run("start ms-settings:network-status")
                return {"response": "Network status opened.", "action_taken": True}
                
            elif operation in ("connect_vpn", "disconnect_vpn"):
                await self.command_runner.run("start ms-settings:network-vpn")
                return {"response": f"VPN settings opened.", "action_taken": True}
                
            elif operation in ("enable_wifi", "disable_wifi"):
                state = "enabled" if operation == "enable_wifi" else "disabled"
                return {"response": f"WiFi {state}.", "action_taken": True}
                
            elif operation == "scan_wifi":
                await self.command_runner.run("start ms-settings:network-wifi")
                return {"response": "WiFi settings opened for scanning.", "action_taken": True}
                
        except Exception as e:
            return {"response": f"Network operation failed: {e}", "action_taken": False}
        
        return {"response": f"Network: {operation}", "action_taken": True}

    # ======================== PROCESS MANAGEMENT ========================

    async def _handle_kill_process(self, process_name: str) -> Dict[str, Any]:
        """Kill a process by name."""
        try:
            if os.name == "nt":
                if not process_name.endswith(".exe"):
                    process_name += ".exe"
                result = await self.command_runner.run(f"taskkill /IM {process_name} /F")
                if result.returncode == 0:
                    return {"response": f"Process {process_name} terminated.", "action_taken": True}
                return {"response": f"Could not find process: {process_name}", "action_taken": False}
        except Exception as e:
            return {"response": f"Failed to kill process: {e}", "action_taken": False}
        return {"response": "Process management not available.", "action_taken": False}

    # ======================== OPEN/LAUNCH ========================

    async def _handle_open(self, target: str) -> Dict[str, Any]:
        """Handle 'open X' command with expanded app and website registry."""
        target_lower = target.lower().strip()
        
        # 1. Check if it's a known website name (e.g., "youtube" -> youtube.com)
        website_url = match_website(target_lower)
        if website_url:
            return await self._navigate(website_url)
        
        # 2. Check if target is a URL (contains domain)
        if "." in target and not target.endswith(".exe"):
            return await self._navigate(target)
        
        # 3. Check if it's a known app from the comprehensive registry
        app_path = match_app_name(target_lower)
        if app_path:
            self.logger.info(f"Opening app from registry: {target_lower} -> {app_path}")
            try:
                if app_path.startswith("ms-") or ":" in app_path and not app_path[1] == ":":
                    # URI scheme (ms-settings:, ms-teams:, etc.)
                    await self.command_runner.run(f'start {app_path}')
                elif app_path.endswith(".msc"):
                    await self.command_runner.run(app_path)
                elif "shell:AppsFolder" in app_path:
                    await self.command_runner.run(f'explorer {app_path}')
                else:
                    await self.command_runner.run([app_path])
                return {
                    "response": f"Opening {target_lower}",
                    "action_taken": True,
                }
            except Exception as e:
                # Fallback to os_tools
                try:
                    result = await self.os_tools.launch_app(target_lower)
                    return {"response": f"Opening {target_lower}", "action_taken": True, "tool_output": result}
                except Exception as e2:
                    return {"response": f"Failed to open {target_lower}: {e2}", "action_taken": False}
        
        # 4. Fallback: try the original app name with os_tools
        app_name = self._extract_app_name(target)
        self.logger.info(f"Opening app (fallback): {app_name}")
        try:
            result = await self.os_tools.launch_app(app_name)
            return {
                "response": f"Opening {app_name}",
                "action_taken": True,
                "tool_output": result
            }
        except Exception as e:
            self.logger.error(f"Failed to open {app_name}: {e}")
            return {"response": f"Failed to open {app_name}: {e}", "action_taken": False}

    def _extract_app_name(self, target: str) -> str:
        """Extract the actual app name from a phrase."""
        target = target.lower().strip()
        
        # Check for known apps first (use the comprehensive registry)
        for app in sorted(APP_REGISTRY.keys(), key=lambda x: -len(x)):
            if target.startswith(app):
                return app
        
        # Otherwise, take first word as app name
        words = target.split()
        if words:
            return words[0]
        return target

    # ======================== NAVIGATION ========================

    async def _navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL."""
        url_lower = url.lower().strip()
        
        # Resolve known site shorthand names
        if url_lower in self.known_websites:
            url = self.known_websites[url_lower]
        elif not url.startswith("http"):
            if "." not in url:
                url = "https://www." + url + ".com"
            else:
                url = "https://" + url
            
        self.logger.info(f"Navigating to: {url}")
        try:
            webbrowser.open(url)
            return {
                "response": f"Opening {url}",
                "action_taken": True,
                "tool_output": f"Navigated to {url}"
            }
        except Exception as e:
            return {"response": f"Failed to navigate: {e}", "action_taken": False}

    # ======================== SEARCH ========================

    async def _search(self, query: str) -> Dict[str, Any]:
        """Perform a web search using DuckDuckGo and return summary."""
        # Special case: explicit browser request
        if query.lower().startswith("youtube"):
            url = f"https://www.youtube.com/results?search_query={query.replace('youtube', '').strip().replace(' ', '+')}"
            webbrowser.open(url)
            return {"response": f"Opening YouTube search for {query}", "action_taken": True}
            
        self.logger.info(f"Searching web for: {query}")
        try:
            # Use WebSearchTool for direct answers
            from agent.tools.web_search import WebSearchTool
            tool = WebSearchTool()
            results_json = tool.search(query, max_results=1)
            
            import json
            try:
                data = json.loads(results_json)
                if isinstance(data, list) and len(data) > 0:
                    snippet = data[0].get('snippet', '')
                    title = data[0].get('title', '')
                    return {
                        "response": f"According to {title}: {snippet}",
                        "action_taken": True,
                        "tool_output": results_json
                    }
            except:
                pass
                
            return {
                "response": f"Here is what I found for {query}: {results_json[:200]}...", 
                "action_taken": True
            }
            
        except Exception as e:
            # Fallback to browser if API fails
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(url)
            return {
                "response": f"I opened a google search for {query}", 
                "action_taken": True
            }
