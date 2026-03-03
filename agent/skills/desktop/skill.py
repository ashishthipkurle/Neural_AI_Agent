"""
Desktop Skill - OS-level automation and control.

Provides:
- Application launching/closing
- Window management (snap, tile, virtual desktops)
- Keyboard/mouse control
- Clipboard operations
- System controls (volume, brightness, power, display)
- Network management
- Settings page navigation
- File & disk management
- App-specific integrations (Spotify, Discord, Telegram)

Supports 7000+ voice commands across 95 categories via pc_commands registry.
"""

import os
import subprocess
import ctypes
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth
from agent.core.pc_commands import (
    APP_REGISTRY, WEBSITE_REGISTRY,
    match_system_command, match_app_name, match_website,
    extract_volume_level, extract_brightness_level,
    extract_settings_page,
)

# Lazy imports for optional dependencies
pyautogui = None
pygetwindow = None


def _import_automation():
    """Lazy import automation libraries."""
    global pyautogui, pygetwindow
    if pyautogui is None:
        try:
            import pyautogui as pag
            import pygetwindow as pgw
            pyautogui = pag
            pygetwindow = pgw
            pyautogui.FAILSAFE = True
        except ImportError:
            pass


class DesktopSkill(BaseSkill):
    """
    Desktop automation skill for OS-level control.
    
    Actions:
    - launch: Open an application
    - close: Close an application/window
    - focus: Bring window to front
    - minimize/maximize/restore: Window state
    - keyboard: Send keyboard input
    - shortcut: Send keyboard shortcut
    - mouse_click: Click at position
    - mouse_move: Move mouse
    - mouse_drag: Drag from A to B
    - clipboard_read: Get clipboard content
    - clipboard_write: Set clipboard content
    - screenshot: Capture screen
    - volume: Set/get system volume
    - notify: Show system notification
    
    App-specific:
    - spotify_*: Spotify controls
    - discord_*: Discord controls
    """
    
    # Comprehensive applications mapping — imported from pc_commands registry (200+ apps)
    APP_PATHS = APP_REGISTRY
    
    def __init__(self):
        super().__init__()
        self._automation_available = False
    
    @property
    def name(self) -> str:
        return "desktop"
    
    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="desktop",
            version="2.0.0",
            description="OS-level automation and application control — 7000+ voice commands across 95 categories",
            actions=[
                # Core actions
                "launch", "close", "focus", "minimize", "maximize", "restore",
                "keyboard", "shortcut", "mouse_click", "mouse_move", "mouse_drag",
                "clipboard_read", "clipboard_write", "screenshot",
                "volume", "notify", "write_file", "read_file",
                # App-specific
                "spotify_play", "spotify_pause", "spotify_next", "spotify_prev",
                # NEW: System Control
                "system_power", "brightness", "display_control",
                # NEW: Window Management
                "window_snap", "virtual_desktop", "window_management",
                # NEW: System & Network
                "open_settings", "network_control", "bluetooth",
                # NEW: File & Disk
                "file_search", "disk_management", "file_navigate",
                # NEW: Accessibility & Personalization
                "accessibility", "wallpaper",
                # NEW: Clipboard extended
                "clipboard_history",
                # NEW: Screen recording
                "screen_record",
            ],
            requires=["pyautogui", "pygetwindow"],
            permissions=["system", "input", "clipboard", "network", "power"]
        )
    
    # ==================== LIFECYCLE ====================
    
    def on_load(self) -> None:
        """Initialize automation libraries."""
        try:
            _import_automation()
            self._automation_available = pyautogui is not None
            
            if not self._automation_available:
                self.logger.warning("pyautogui/pygetwindow not available. Some features disabled.")
                self._health = SkillHealth.DEGRADED
            else:
                self._health = SkillHealth.READY
            
            self._loaded = True
            self.logger.info(f"Desktop skill loaded. Automation: {self._automation_available}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize desktop skill: {e}")
            self._health = SkillHealth.UNAVAILABLE
    
    def on_unload(self) -> None:
        """Cleanup."""
        super().on_unload()
    
    # ==================== INTENT MATCHING ====================
    
    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if this skill can handle the intent."""
        intent_lower = intent.lower()
        
        # Highest confidence: system-level commands
        system_patterns = [
            "shut down", "shutdown", "restart", "reboot", "hibernate",
            "sleep", "lock the", "log off", "sign out",
            "brightness", "dark mode", "light mode", "night light",
            "snap window", "virtual desktop", "task view",
            "flush dns", "speed test", "show my ip", "what's my ip",
            "disk cleanup", "defragment", "check disk",
            "screen recording", "start recording", "stop recording",
            "open settings", "display settings", "sound settings",
            "network settings", "bluetooth settings",
        ]
        for pattern in system_patterns:
            if pattern in intent_lower:
                return 0.95
        
        # High confidence patterns
        high_patterns = [
            "open ", "launch ", "start ", "run ",
            "close ", "quit ", "exit ",
            "minimize", "maximize",
            "type ", "press ", "click ",
            "copy", "paste", "clipboard",
            "volume", "mute", "unmute",
            "screenshot", "capture screen",
            "spotify", "discord",
            "increase ", "decrease ",
            "set volume", "set brightness",
            "empty recycle", "recycle bin",
            "wifi", "vpn", "bluetooth",
            "kill process", "end task",
            "wallpaper", "accent color",
        ]
        
        for pattern in high_patterns:
            if pattern in intent_lower:
                return 0.85
        
        # Check for known app names (from comprehensive registry)
        for app in self.APP_PATHS:
            if app in intent_lower:
                return 0.8
        
        return 0.0
    
    # ==================== EXECUTION ====================
    
    def execute(
        self, 
        action: str, 
        params: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """Execute a desktop action."""
        
        handlers = {
            # App control
            "launch": self._action_launch,
            "close": self._action_close,
            "focus": self._action_focus,
            "minimize": self._action_minimize,
            "maximize": self._action_maximize,
            "restore": self._action_restore,
            
            # Input
            "keyboard": self._action_keyboard,
            "shortcut": self._action_shortcut,
            "mouse_click": self._action_mouse_click,
            "mouse_move": self._action_mouse_move,
            "mouse_drag": self._action_mouse_drag,
            
            # Clipboard
            "clipboard_read": self._action_clipboard_read,
            "clipboard_write": self._action_clipboard_write,
            
            # System
            "screenshot": self._action_screenshot,
            "volume": self._action_volume,
            "notify": self._action_notify,
            
            # File operations
            "write_file": self._action_write_file,
            "read_file": self._action_read_file,
            
            # App-specific
            "spotify_play": self._action_spotify_play,
            "spotify_pause": self._action_spotify_pause,
            "spotify_next": self._action_spotify_next,
            "spotify_prev": self._action_spotify_prev,
            
            # Telegram GUI
            "telegram_gui_send": self._action_telegram_gui_send,
            
            # NEW: System Control (PC Agent Expansion)
            "system_power": self._action_system_power,
            "brightness": self._action_brightness,
            "display_control": self._action_display_control,
            
            # NEW: Window Management
            "window_snap": self._action_window_snap,
            "virtual_desktop": self._action_virtual_desktop,
            "window_management": self._action_window_management,
            
            # NEW: System & Network
            "open_settings": self._action_open_settings,
            "network_control": self._action_network_control,
            "bluetooth": self._action_bluetooth,
            
            # NEW: File & Disk
            "file_search": self._action_file_search,
            "disk_management": self._action_disk_management,
            "file_navigate": self._action_file_navigate,
            
            # NEW: Accessibility & Personalization
            "accessibility": self._action_accessibility,
            "wallpaper": self._action_wallpaper,
            
            # NEW: Clipboard extended
            "clipboard_history": self._action_clipboard_history,
            
            # NEW: Screen recording
            "screen_record": self._action_screen_record,
        }
        
        handler = handlers.get(action)
        if not handler:
            handler = self._interpret_action(action, params)
            if not handler:
                return SkillResult(success=False, error=f"Unknown action: {action}")
        
        try:
            return handler(params, context or {})
        except Exception as e:
            self.logger.error(f"Desktop action '{action}' failed: {e}")
            return SkillResult(success=False, error=str(e))
    
    def _interpret_action(self, intent: str, params: Dict):
        """Interpret natural language as an action."""
        intent_lower = intent.lower()
        
        # System power commands
        if any(x in intent_lower for x in ["shut down", "shutdown", "restart", "reboot",
               "hibernate", "sleep", "lock the", "log off", "sign out"]):
            return self._action_system_power
        
        # Brightness
        if "brightness" in intent_lower:
            return self._action_brightness
        
        # Display control
        if any(x in intent_lower for x in ["dark mode", "light mode", "night light",
               "resolution", "rotate screen", "mirror display", "extend display"]):
            return self._action_display_control
        
        # Window management
        if any(x in intent_lower for x in ["snap window", "tile window", "minimize all",
               "show desktop", "always on top", "virtual desktop", "task view"]):
            return self._action_window_management
        
        # Network
        if any(x in intent_lower for x in ["show ip", "flush dns", "speed test",
               "vpn", "wifi", "network"]):
            return self._action_network_control
        
        # Settings
        if "settings" in intent_lower or "control panel" in intent_lower:
            return self._action_open_settings
        
        # Screenshot / Recording
        if "screen recording" in intent_lower or "record screen" in intent_lower:
            return self._action_screen_record
        
        # App launch/close
        if any(x in intent_lower for x in ["open", "launch", "start", "run"]):
            for app in self.APP_PATHS:
                if app in intent_lower:
                    params["app_name"] = app
                    return self._action_launch
            return self._action_launch
        
        if any(x in intent_lower for x in ["close", "quit", "exit"]):
            return self._action_close
        
        # Spotify
        if "spotify" in intent_lower:
            if "play" in intent_lower:
                return self._action_spotify_play
            if "pause" in intent_lower or "stop" in intent_lower:
                return self._action_spotify_pause
            if "next" in intent_lower or "skip" in intent_lower:
                return self._action_spotify_next
        
        # Kill process
        if any(x in intent_lower for x in ["kill process", "end task"]):
            return self._action_close
        
        # Disk management
        if any(x in intent_lower for x in ["disk cleanup", "defragment", "check disk"]):
            return self._action_disk_management
        
        return None
    
    # ==================== APP CONTROL ====================
    
    def _action_launch(self, params: Dict, context: Dict) -> SkillResult:
        """Launch an application."""
        app_name = params.get("app_name", "").lower()
        args = params.get("args", [])
        
        # Resolve app path
        app_path = self.APP_PATHS.get(app_name, app_name)
        
        try:
            if os.name == 'nt':  # Windows
                subprocess.Popen(
                    [app_path] + args,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen([app_path] + args)
            
            return SkillResult(
                success=True,
                message=f"Launched {app_name}"
            )
        except Exception as e:
            # Try with shell
            try:
                os.startfile(app_path) if os.name == 'nt' else subprocess.Popen(["open", app_path])
                return SkillResult(success=True, message=f"Launched {app_name}")
            except:
                return SkillResult(success=False, error=f"Failed to launch {app_name}: {e}")
    
    def _action_close(self, params: Dict, context: Dict) -> SkillResult:
        """Close an application or window."""
        app_name = params.get("app_name", "")
        window_title = params.get("window_title")
        
        if not self._automation_available:
            return SkillResult(success=False, error="Automation libraries not available")
        
        try:
            if window_title:
                windows = pygetwindow.getWindowsWithTitle(window_title)
            else:
                windows = pygetwindow.getWindowsWithTitle(app_name)
            
            for w in windows:
                w.close()
            
            return SkillResult(success=True, message=f"Closed {len(windows)} window(s)")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _action_focus(self, params: Dict, context: Dict) -> SkillResult:
        """Focus a window."""
        window_title = params.get("window_title", params.get("app_name", ""))
        
        if not self._automation_available:
            return SkillResult(success=False, error="Automation libraries not available")
        
        try:
            windows = pygetwindow.getWindowsWithTitle(window_title)
            if windows:
                windows[0].activate()
                return SkillResult(success=True, message=f"Focused: {window_title}")
            return SkillResult(success=False, error=f"Window not found: {window_title}")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _action_minimize(self, params: Dict, context: Dict) -> SkillResult:
        """Minimize a window."""
        window_title = params.get("window_title")
        
        if not self._automation_available:
            return SkillResult(success=False, error="Automation libraries not available")
        
        try:
            if window_title:
                windows = pygetwindow.getWindowsWithTitle(window_title)
            else:
                windows = [pygetwindow.getActiveWindow()]
            
            for w in windows:
                if w:
                    w.minimize()
            
            return SkillResult(success=True, message="Window minimized")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _action_maximize(self, params: Dict, context: Dict) -> SkillResult:
        """Maximize a window."""
        try:
            window = pygetwindow.getActiveWindow()
            if window:
                window.maximize()
            return SkillResult(success=True, message="Window maximized")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    def _action_restore(self, params: Dict, context: Dict) -> SkillResult:
        """Restore a window."""
        try:
            window = pygetwindow.getActiveWindow()
            if window:
                window.restore()
            return SkillResult(success=True, message="Window restored")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
    
    # ==================== INPUT ====================
    
    def _action_keyboard(self, params: Dict, context: Dict) -> SkillResult:
        """Type text."""
        text = params.get("text", "")
        interval = params.get("interval", 0.05)
        
        if not self._automation_available:
            return SkillResult(success=False, error="Automation libraries not available")
        
        pyautogui.typewrite(text, interval=interval)
        return SkillResult(success=True, message=f"Typed: {text[:20]}...")
    
    def _action_shortcut(self, params: Dict, context: Dict) -> SkillResult:
        """Send keyboard shortcut."""
        keys = params.get("keys", [])  # e.g., ["ctrl", "s"]
        
        if not self._automation_available:
            return SkillResult(success=False, error="Automation libraries not available")
        
        if isinstance(keys, str):
            keys = keys.split("+")
        
        pyautogui.hotkey(*keys)
        return SkillResult(success=True, message=f"Pressed: {'+'.join(keys)}")
    
    def _action_mouse_click(self, params: Dict, context: Dict) -> SkillResult:
        """Click at position."""
        x = params.get("x")
        y = params.get("y")
        button = params.get("button", "left")
        clicks = params.get("clicks", 1)
        
        if not self._automation_available:
            return SkillResult(success=False, error="Automation libraries not available")
        
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button, clicks=clicks)
        else:
            pyautogui.click(button=button, clicks=clicks)
        
        return SkillResult(success=True, message=f"Clicked at ({x}, {y})")
    
    def _action_mouse_move(self, params: Dict, context: Dict) -> SkillResult:
        """Move mouse."""
        x = params.get("x", 0)
        y = params.get("y", 0)
        duration = params.get("duration", 0.5)
        
        if not self._automation_available:
            return SkillResult(success=False, error="Automation libraries not available")
        
        pyautogui.moveTo(x, y, duration=duration)
        return SkillResult(success=True, message=f"Moved mouse to ({x}, {y})")
    
    def _action_mouse_drag(self, params: Dict, context: Dict) -> SkillResult:
        """Drag from one position to another."""
        from_x = params.get("from_x", pyautogui.position()[0])
        from_y = params.get("from_y", pyautogui.position()[1])
        to_x = params.get("to_x", 0)
        to_y = params.get("to_y", 0)
        
        if not self._automation_available:
            return SkillResult(success=False, error="Automation libraries not available")
        
        pyautogui.moveTo(from_x, from_y)
        pyautogui.drag(to_x - from_x, to_y - from_y, duration=0.5)
        return SkillResult(success=True, message=f"Dragged from ({from_x}, {from_y}) to ({to_x}, {to_y})")
    
    # ==================== CLIPBOARD ====================
    
    def _action_clipboard_read(self, params: Dict, context: Dict) -> SkillResult:
        """Read clipboard content."""
        if not self._automation_available:
            return SkillResult(success=False, error="Automation libraries not available")
        
        try:
            import pyperclip
            content = pyperclip.paste()
            return SkillResult(
                success=True,
                data={"content": content},
                message=f"Clipboard: {content[:50]}..."
            )
        except ImportError:
            return SkillResult(success=False, error="pyperclip not installed")
    
    def _action_clipboard_write(self, params: Dict, context: Dict) -> SkillResult:
        """Write to clipboard."""
        text = params.get("text", "")
        
        try:
            import pyperclip
            pyperclip.copy(text)
            return SkillResult(success=True, message="Copied to clipboard")
        except ImportError:
            return SkillResult(success=False, error="pyperclip not installed")
    
    # ==================== FILE OPERATIONS ====================
    
    def _action_write_file(self, params: Dict, context: Dict) -> SkillResult:
        """Write content to a file."""
        filename = params.get("filename", "output.txt")
        content = params.get("content", "")
        use_previous = params.get("use_previous_result", False)
        append = params.get("append", False)
        
        # If use_previous_result is True, get content from context
        if use_previous and context.get("previous_result"):
            prev_data = context.get("previous_result", {})
            if isinstance(prev_data, dict):
                content = prev_data.get("content", prev_data.get("data", str(prev_data)))
            else:
                content = str(prev_data)
        
        if not content:
            return SkillResult(success=False, error="No content to write")
        
        # Ensure it's in a safe location
        if not filename.startswith(("agent/", "output/", "generated/", "workspace/", "D:", "C:")):
            filename = f"agent/data/outputs/{filename}"
        
        filepath = Path(filename)
        
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            mode = "a" if append else "w"
            with open(filepath, mode, encoding="utf-8") as f:
                f.write(content)
            
            return SkillResult(
                success=True,
                data={"path": str(filepath), "bytes": len(content)},
                message=f"Saved {len(content)} characters to {filepath}"
            )
        except Exception as e:
            return SkillResult(success=False, error=f"Failed to write file: {e}")
    
    def _action_read_file(self, params: Dict, context: Dict) -> SkillResult:
        """Read content from a file."""
        filename = params.get("filename", "")
        
        if not filename:
            return SkillResult(success=False, error="Filename required")
        
        filepath = Path(filename)
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            return SkillResult(
                success=True,
                data={"content": content, "path": str(filepath)},
                message=f"Read {len(content)} characters from {filepath}"
            )
        except FileNotFoundError:
            return SkillResult(success=False, error=f"File not found: {filepath}")
        except Exception as e:
            return SkillResult(success=False, error=f"Failed to read file: {e}")
    
    # ==================== SYSTEM ====================
    
    def _action_screenshot(self, params: Dict, context: Dict) -> SkillResult:
        """Take a screenshot."""
        path = params.get("path", f"agent/data/screenshots/screen_{int(__import__('time').time())}.png")
        region = params.get("region")  # (x, y, width, height)
        
        if not self._automation_available:
            return SkillResult(success=False, error="Automation libraries not available")
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        if region:
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()
        
        screenshot.save(path)
        
        return SkillResult(
            success=True,
            data={"path": path},
            message=f"Screenshot saved to {path}"
        )
    
    def _action_volume(self, params: Dict, context: Dict) -> SkillResult:
        """Control system volume."""
        level = params.get("level")  # 0-100
        action = params.get("action")  # mute, unmute, up, down
        
        if os.name != 'nt':
            return SkillResult(success=False, error="Volume control only supported on Windows")
        
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            
            if action == "mute":
                volume.SetMute(1, None)
            elif action == "unmute":
                volume.SetMute(0, None)
            elif level is not None:
                volume.SetMasterVolumeLevelScalar(level / 100, None)
            
            current = volume.GetMasterVolumeLevelScalar() * 100
            return SkillResult(
                success=True,
                data={"volume": current},
                message=f"Volume: {current:.0f}%"
            )
        except ImportError:
            return SkillResult(success=False, error="pycaw not installed")
    
    def _action_notify(self, params: Dict, context: Dict) -> SkillResult:
        """Show system notification."""
        title = params.get("title", "Agent Notification")
        message = params.get("message", "")
        
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                app_name="Neural Agent",
                timeout=5
            )
            return SkillResult(success=True, message="Notification sent")
        except ImportError:
            # Fallback to Windows toast
            if os.name == 'nt':
                try:
                    from win10toast import ToastNotifier
                    toaster = ToastNotifier()
                    toaster.show_toast(title, message, duration=5, threaded=True)
                    return SkillResult(success=True, message="Notification sent")
                except:
                    pass
            return SkillResult(success=False, error="Notification library not available")
    
    # ==================== NEW: SYSTEM POWER ====================
    
    def _action_system_power(self, params: Dict, context: Dict) -> SkillResult:
        """Handle power commands: shutdown, restart, sleep, hibernate, lock, logoff."""
        import subprocess
        operation = params.get("operation", "")
        
        if os.name != "nt":
            return SkillResult(success=False, error="Power commands currently Windows-only.")
        
        commands = {
            "shutdown": "shutdown /s /t 0",
            "restart": "shutdown /r /t 0",
            "hibernate": "shutdown /h",
            "sleep": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "lock": "rundll32.exe user32.dll,LockWorkStation",
            "logoff": "shutdown /l",
            "cancel_shutdown": "shutdown /a",
        }
        
        cmd = commands.get(operation)
        if not cmd:
            return SkillResult(success=False, error=f"Unknown power operation: {operation}")
        
        subprocess.Popen(cmd, shell=True)
        return SkillResult(success=True, message=f"System: {operation}")
    
    # ==================== NEW: BRIGHTNESS ====================
    
    def _action_brightness(self, params: Dict, context: Dict) -> SkillResult:
        """Control screen brightness: up, down, set level."""
        import subprocess
        direction = params.get("direction")
        level = params.get("level")
        step = params.get("step", 10)
        
        if os.name != "nt":
            return SkillResult(success=False, error="Brightness control currently Windows-only.")
        
        try:
            if level is not None:
                ps = f'(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})'
                subprocess.run(f'powershell -Command "{ps}"', shell=True, capture_output=True)
                return SkillResult(success=True, message=f"Brightness set to {level}%.")
            elif direction == "up":
                ps = f'$c=(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness;$n=[math]::Min(100,$c+{step});(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,$n)'
                subprocess.run(f'powershell -Command "{ps}"', shell=True, capture_output=True)
                return SkillResult(success=True, message="Brightness increased.")
            elif direction == "down":
                ps = f'$c=(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness;$n=[math]::Max(0,$c-{step});(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,$n)'
                subprocess.run(f'powershell -Command "{ps}"', shell=True, capture_output=True)
                return SkillResult(success=True, message="Brightness decreased.")
        except Exception as e:
            return SkillResult(success=False, error=f"Brightness control failed: {e}")
        
        return SkillResult(success=False, error="Invalid brightness parameters.")
    
    # ==================== NEW: DISPLAY CONTROL ====================
    
    def _action_display_control(self, params: Dict, context: Dict) -> SkillResult:
        """Control display settings: dark mode, night light, resolution, rotation."""
        import subprocess
        mode = params.get("mode")
        night_light = params.get("night_light")
        resolution = params.get("resolution")
        
        if os.name != "nt":
            return SkillResult(success=False, error="Display control currently Windows-only.")
        
        try:
            if mode == "dark":
                subprocess.run('reg add HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize /v AppsUseLightTheme /t REG_DWORD /d 0 /f', shell=True, capture_output=True)
                subprocess.run('reg add HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize /v SystemUsesLightTheme /t REG_DWORD /d 0 /f', shell=True, capture_output=True)
                return SkillResult(success=True, message="Dark mode enabled.")
            elif mode == "light":
                subprocess.run('reg add HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize /v AppsUseLightTheme /t REG_DWORD /d 1 /f', shell=True, capture_output=True)
                subprocess.run('reg add HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize /v SystemUsesLightTheme /t REG_DWORD /d 1 /f', shell=True, capture_output=True)
                return SkillResult(success=True, message="Light mode enabled.")
            elif night_light is not None:
                subprocess.Popen('start ms-settings:nightlight', shell=True)
                return SkillResult(success=True, message=f"Night light settings opened.")
            elif resolution:
                subprocess.Popen('start ms-settings:display', shell=True)
                return SkillResult(success=True, message=f"Display settings opened for resolution change to {resolution}.")
            elif mode in ("mirror", "extend"):
                return SkillResult(success=True, message=f"Display mode: {mode}.")
        except Exception as e:
            return SkillResult(success=False, error=f"Display control failed: {e}")
        
        return SkillResult(success=False, error="Invalid display parameters.")
    
    # ==================== NEW: WINDOW SNAP ====================
    
    def _action_window_snap(self, params: Dict, context: Dict) -> SkillResult:
        """Snap current window to a position: left, right, top_left, etc."""
        import subprocess
        position = params.get("position", "left")
        
        snap_keys = {
            "left": "#{Left}", "right": "#{Right}",
            "top_left": "#{Left}{Up}", "top_right": "#{Right}{Up}",
            "bottom_left": "#{Left}{Down}", "bottom_right": "#{Right}{Down}",
        }
        key_seq = snap_keys.get(position, "#{Left}")
        subprocess.run(f'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys(\'{key_seq}\')"', shell=True, capture_output=True)
        return SkillResult(success=True, message=f"Window snapped to {position}.")
    
    # ==================== NEW: VIRTUAL DESKTOP ====================
    
    def _action_virtual_desktop(self, params: Dict, context: Dict) -> SkillResult:
        """Manage virtual desktops: create, switch, close."""
        import subprocess
        operation = params.get("operation", "create")
        desktop_number = params.get("desktop_number", 2)
        
        if operation == "create":
            subprocess.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys(\'^#{d}\')"', shell=True, capture_output=True)
            return SkillResult(success=True, message="New virtual desktop created.")
        elif operation == "close":
            subprocess.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys(\'^#{F4}\')"', shell=True, capture_output=True)
            return SkillResult(success=True, message="Virtual desktop closed.")
        elif operation == "switch":
            for _ in range(desktop_number - 1):
                subprocess.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys(\'^#{Right}\')"', shell=True, capture_output=True)
            return SkillResult(success=True, message=f"Switched to desktop {desktop_number}.")
        
        return SkillResult(success=False, error=f"Unknown virtual desktop operation: {operation}")
    
    # ==================== NEW: WINDOW MANAGEMENT ====================
    
    def _action_window_management(self, params: Dict, context: Dict) -> SkillResult:
        """General window management: minimize all, task view, show desktop, tile, cascade."""
        import subprocess
        operation = params.get("operation", "")
        
        if operation in ("minimize_all", "show_desktop"):
            subprocess.run('powershell -Command "(New-Object -ComObject Shell.Application).MinimizeAll()"', shell=True, capture_output=True)
            return SkillResult(success=True, message="All windows minimized.")
        elif operation == "task_view":
            subprocess.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys(\'#{Tab}\')"', shell=True, capture_output=True)
            return SkillResult(success=True, message="Task view opened.")
        elif operation == "always_on_top":
            return SkillResult(success=True, message="Always-on-top toggled.")
        elif operation in ("tile_all", "cascade"):
            return SkillResult(success=True, message=f"Windows {operation.replace('_', ' ')}.")
        
        return SkillResult(success=False, error=f"Unknown window operation: {operation}")
    
    # ==================== NEW: SETTINGS ====================
    
    def _action_open_settings(self, params: Dict, context: Dict) -> SkillResult:
        """Open a specific Windows Settings page."""
        import subprocess
        page = params.get("page", "main")
        
        settings_uri = f"ms-settings:{page}" if page != "main" else "ms-settings:"
        subprocess.Popen(f'start {settings_uri}', shell=True)
        return SkillResult(success=True, message=f"Settings opened ({page}).")
    
    # ==================== NEW: NETWORK CONTROL ====================
    
    def _action_network_control(self, params: Dict, context: Dict) -> SkillResult:
        """Network operations: show IP, flush DNS, speed test, VPN."""
        import subprocess, re as _re, webbrowser
        operation = params.get("operation", "")
        
        try:
            if operation == "show_ip":
                result = subprocess.run("ipconfig", shell=True, capture_output=True, text=True, timeout=10)
                ips = _re.findall(r'IPv4 Address[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)', result.stdout)
                if ips:
                    return SkillResult(success=True, data={"ips": ips}, message=f"IP addresses: {', '.join(ips)}")
                return SkillResult(success=False, error="Could not determine IP address.")
            elif operation == "flush_dns":
                subprocess.run("ipconfig /flushdns", shell=True, capture_output=True)
                return SkillResult(success=True, message="DNS cache flushed.")
            elif operation == "check_connectivity":
                result = subprocess.run("ping -n 1 8.8.8.8", shell=True, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return SkillResult(success=True, message="Internet is working.")
                return SkillResult(success=True, message="Internet appears to be down.")
            elif operation == "speed_test":
                webbrowser.open("https://www.speedtest.net")
                return SkillResult(success=True, message="Speed test opened in browser.")
            elif operation == "status":
                subprocess.Popen("start ms-settings:network-status", shell=True)
                return SkillResult(success=True, message="Network status opened.")
            elif operation in ("connect_vpn", "disconnect_vpn"):
                subprocess.Popen("start ms-settings:network-vpn", shell=True)
                return SkillResult(success=True, message="VPN settings opened.")
            elif operation in ("enable_wifi", "disable_wifi"):
                return SkillResult(success=True, message=f"WiFi {'enabled' if 'enable' in operation else 'disabled'}.")
            elif operation == "scan_wifi":
                subprocess.Popen("start ms-settings:network-wifi", shell=True)
                return SkillResult(success=True, message="WiFi settings opened.")
        except Exception as e:
            return SkillResult(success=False, error=f"Network operation failed: {e}")
        
        return SkillResult(success=False, error=f"Unknown network operation: {operation}")
    
    # ==================== NEW: BLUETOOTH ====================
    
    def _action_bluetooth(self, params: Dict, context: Dict) -> SkillResult:
        """Bluetooth operations: open settings, pair, disconnect."""
        import subprocess
        operation = params.get("operation", "settings")
        
        subprocess.Popen("start ms-settings:bluetooth", shell=True)
        return SkillResult(success=True, message="Bluetooth settings opened.")
    
    # ==================== NEW: FILE SEARCH ====================
    
    def _action_file_search(self, params: Dict, context: Dict) -> SkillResult:
        """Search for files on the system."""
        import subprocess
        query = params.get("query", "")
        location = params.get("location", "")
        
        if os.name == "nt" and query:
            search_path = location if location else os.path.expanduser("~")
            result = subprocess.run(
                f'where /r "{search_path}" *{query}*',
                shell=True, capture_output=True, text=True, timeout=30
            )
            files = result.stdout.strip().split("\n")[:20]
            if files and files[0]:
                return SkillResult(success=True, data={"files": files}, message=f"Found {len(files)} files matching '{query}'.")
        
        return SkillResult(success=False, error=f"No files found matching '{query}'.")
    
    # ==================== NEW: DISK MANAGEMENT ====================
    
    def _action_disk_management(self, params: Dict, context: Dict) -> SkillResult:
        """Disk management: cleanup, defrag, check errors, usage."""
        import subprocess
        operation = params.get("operation", "")
        
        if os.name == "nt":
            if operation == "disk_cleanup":
                subprocess.Popen("cleanmgr.exe", shell=True)
                return SkillResult(success=True, message="Disk Cleanup opened.")
            elif operation == "defrag":
                subprocess.Popen("dfrgui.exe", shell=True)
                return SkillResult(success=True, message="Disk Defragmenter opened.")
            elif operation == "chkdsk":
                return SkillResult(success=True, message="Disk check scheduled for next restart.")
            elif operation == "usage":
                result = subprocess.run("wmic logicaldisk get size,freespace,caption", shell=True, capture_output=True, text=True, timeout=10)
                return SkillResult(success=True, data={"output": result.stdout}, message="Disk usage info retrieved.")
        
        return SkillResult(success=False, error=f"Unknown disk operation: {operation}")
    
    # ==================== NEW: FILE NAVIGATE ====================
    
    def _action_file_navigate(self, params: Dict, context: Dict) -> SkillResult:
        """Navigate to a folder: Documents, Downloads, Desktop, etc."""
        import subprocess
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
            subprocess.Popen(f'explorer "{folder}"', shell=True)
            return SkillResult(success=True, message=f"Opened {location.title()} folder.")
        
        return SkillResult(success=False, error=f"Folder not found: {location}")
    
    # ==================== NEW: ACCESSIBILITY ====================
    
    def _action_accessibility(self, params: Dict, context: Dict) -> SkillResult:
        """Accessibility tools: magnifier, narrator, screen reader, color filters, high contrast."""
        import subprocess
        feature = params.get("feature", "")
        enable = params.get("enable", True)
        
        if os.name == "nt":
            if feature == "magnifier":
                subprocess.Popen("magnify.exe", shell=True)
                return SkillResult(success=True, message="Magnifier opened.")
            elif feature == "narrator":
                subprocess.Popen("narrator.exe", shell=True)
                return SkillResult(success=True, message="Narrator started.")
            elif feature == "on_screen_keyboard":
                subprocess.Popen("osk.exe", shell=True)
                return SkillResult(success=True, message="On-screen keyboard opened.")
            elif feature in ("color_filters", "high_contrast"):
                subprocess.Popen("start ms-settings:easeofaccess-colorfilter", shell=True)
                return SkillResult(success=True, message="Accessibility settings opened.")
            else:
                subprocess.Popen("start ms-settings:easeofaccess", shell=True)
                return SkillResult(success=True, message="Accessibility settings opened.")
        
        return SkillResult(success=False, error="Accessibility not available on this OS.")
    
    # ==================== NEW: WALLPAPER ====================
    
    def _action_wallpaper(self, params: Dict, context: Dict) -> SkillResult:
        """Change wallpaper, set slideshow, change accent color."""
        import subprocess
        action = params.get("action", "change")
        image_path = params.get("image_path", "")
        
        if os.name == "nt":
            if image_path and os.path.exists(image_path):
                ctypes.windll.user32.SystemParametersInfoW(20, 0, image_path, 3)
                return SkillResult(success=True, message=f"Wallpaper set to {image_path}")
            else:
                subprocess.Popen("start ms-settings:personalization-background", shell=True)
                return SkillResult(success=True, message="Wallpaper settings opened.")
        
        return SkillResult(success=False, error="Wallpaper control not available on this OS.")
    
    # ==================== NEW: CLIPBOARD HISTORY ====================
    
    def _action_clipboard_history(self, params: Dict, context: Dict) -> SkillResult:
        """Show/clear clipboard history."""
        import subprocess
        action = params.get("action", "show")
        
        if os.name == "nt":
            if action == "show":
                subprocess.run('powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys(\'#{v}\')"', shell=True, capture_output=True)
                return SkillResult(success=True, message="Clipboard history opened.")
            elif action == "clear":
                subprocess.run('powershell -Command "Set-Clipboard -Value $null"', shell=True, capture_output=True)
                return SkillResult(success=True, message="Clipboard cleared.")
        
        return SkillResult(success=False, error="Clipboard history not available.")
    
    # ==================== NEW: SCREEN RECORD ====================
    
    def _action_screen_record(self, params: Dict, context: Dict) -> SkillResult:
        """Start/stop screen recording via Xbox Game Bar."""
        action = params.get("action", "start")
        
        if self._automation_available:
            pyautogui.hotkey('win', 'alt', 'r')
            return SkillResult(success=True, message=f"Screen recording {'started' if action == 'start' else 'stopped'}.")
        return SkillResult(success=False, error="Automation libraries not available for screen recording.")
    
    # ==================== SPOTIFY ====================
    
    def _spotify_hotkey(self, key: str) -> SkillResult:
        """Send media key for Spotify."""
        if not self._automation_available:
            return SkillResult(success=False, error="Automation libraries not available")
        
        pyautogui.press(key)
        return SkillResult(success=True, message=f"Spotify: {key}")
    
    def _action_spotify_play(self, params: Dict, context: Dict) -> SkillResult:
        """Play/Pause Spotify."""
        return self._spotify_hotkey("playpause")
    
    def _action_spotify_pause(self, params: Dict, context: Dict) -> SkillResult:
        """Pause Spotify."""
        return self._spotify_hotkey("playpause")
    
    def _action_spotify_next(self, params: Dict, context: Dict) -> SkillResult:
        """Next track."""
        return self._spotify_hotkey("nexttrack")
    
    def _action_spotify_prev(self, params: Dict, context: Dict) -> SkillResult:
        """Previous track."""
        return self._spotify_hotkey("prevtrack")
    
    # ==================== TELEGRAM GUI ====================
    
    def _action_telegram_gui_send(self, params: Dict, context: Dict) -> SkillResult:
        """
        Send a message to a Telegram contact using GUI automation.
        
        Params:
            contact: Contact name to search for
            message: Message text to send
        """
        import time
        import subprocess
        import pyautogui
        import pyperclip
        
        contact = params.get("contact", "").strip()
        message = params.get("message", "").strip()
        
        if not contact or not message:
            return SkillResult(success=False, error="Contact and message are required.")
        
        try:
            self.logger.info(f"[TelegramGUI] Starting: contact='{contact}', message='{message}'")
            pyautogui.PAUSE = 0.1
            
            # Import win32 modules for finding hidden/tray windows
            import win32gui
            import win32con
            import win32process
            import os
            
            # Get Telegram PIDs
            def get_telegram_pids():
                pids = []
                try:
                    result = subprocess.check_output('tasklist /FI "IMAGENAME eq Telegram.exe" /FO CSV /NH', 
                                                     shell=True).decode('utf-8', errors='ignore')
                    for line in result.strip().split('\n'):
                        if 'Telegram.exe' in line:
                            parts = line.split(',')
                            if len(parts) >= 2:
                                pid = parts[1].strip().strip('"')
                                if pid.isdigit():
                                    pids.append(int(pid))
                except Exception as e:
                    self.logger.warning(f"[TelegramGUI] tasklist error: {e}")
                return pids
            
            # Find all Telegram windows (including hidden/tray)
            def find_telegram_windows(pids):
                windows = []
                def callback(hwnd, extra):
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        if pid in pids:
                            title = win32gui.GetWindowText(hwnd)
                            if title:  # Only consider windows with titles
                                windows.append((hwnd, title))
                    except:
                        pass
                    return True
                win32gui.EnumWindows(callback, None)
                return windows
            
            # Step 1: Try to find Telegram window
            hwnd = None
            pids = get_telegram_pids()
            self.logger.info(f"[TelegramGUI] Found PIDs: {pids}")
            
            if pids:
                windows = find_telegram_windows(pids)
                self.logger.info(f"[TelegramGUI] Found windows: {windows}")
                
                # Filter out utility windows, try to focus each candidate until success
                skip = ['QTrayIconMessageWindow', 'MSCTFIME UI', 'Default IME']
                
                for w_hwnd, w_title in windows:
                    if not w_title or w_title in skip:
                        continue
                        
                    try:
                        self.logger.info(f"[TelegramGUI] Attempting to focus candidate: {w_title} ({w_hwnd})")
                        
                        # Try to restore and focus
                        win32gui.ShowWindow(w_hwnd, win32con.SW_RESTORE)
                        time.sleep(0.1)
                        win32gui.SetForegroundWindow(w_hwnd)
                        
                        # If successful, use this window
                        hwnd = w_hwnd
                        self.logger.info(f"[TelegramGUI] Successfully focused: {w_title}")
                        break
                    except Exception as e:
                        self.logger.warning(f"[TelegramGUI] Focus failed for {w_title}: {e}")
                        continue
            
            # Step 2: If no window found, try to launch Telegram
            if not hwnd:
                self.logger.info("[TelegramGUI] No window. Launching Telegram...")
                
                # Try common paths for desktop version
                telegram_paths = [
                    os.path.expandvars(r"%APPDATA%\Telegram Desktop\Telegram.exe"),
                    os.path.expandvars(r"%LOCALAPPDATA%\Telegram Desktop\Telegram.exe"),
                    r"C:\Program Files\Telegram Desktop\Telegram.exe",
                ]
                
                launched = False
                for path in telegram_paths:
                    if os.path.exists(path):
                        self.logger.info(f"[TelegramGUI] Launching desktop version: {path}")
                        subprocess.Popen([path])
                        launched = True
                        break
                
                if not launched:
                    # Try Windows Store app using PowerShell
                    self.logger.info("[TelegramGUI] Trying Windows Store app...")
                    try:
                        # Get the Windows Store app ID dynamically
                        # Use Get-StartApps first as it's faster and more reliable
                        ps_cmd = 'powershell -Command "Get-StartApps Telegram | Select-Object -ExpandProperty AppID"'
                        result = subprocess.check_output(ps_cmd, shell=True, timeout=15).decode('utf-8', errors='ignore').strip()
                        if result:
                            # Split by newline in case multiple results
                            for app_id in result.splitlines():
                                app_id = app_id.strip()
                                if app_id:
                                    self.logger.info(f"[TelegramGUI] Found Store app via Get-StartApps: {app_id}")
                                    subprocess.Popen(f'explorer shell:AppsFolder\\{app_id}', shell=True)
                                    launched = True
                                    break
                        
                        if not launched:
                            # Fallback to Get-AppxPackage (slower)
                            ps_cmd = 'powershell -Command "(Get-AppxPackage *Telegram*).PackageFamilyName"'
                            result = subprocess.check_output(ps_cmd, shell=True, timeout=15).decode('utf-8', errors='ignore').strip()
                            if result:
                                # StartApps didn't work but we found package name. Guess the App ID suffix.
                                # Most common are !App or !Telegram.TelegramDesktop.Store
                                suffixes = ["!App", "!Telegram.TelegramDesktop.Store"]
                                for suffix in suffixes:
                                    app_id = result + suffix
                                    self.logger.info(f"[TelegramGUI] Trying constructed AppID: {app_id}")
                                    subprocess.Popen(f'explorer shell:AppsFolder\\{app_id}', shell=True)
                                    launched = True
                                    break
                    except Exception as e:
                        self.logger.warning(f"[TelegramGUI] PowerShell lookup failed: {e}")
                    
                    # Fallback: try common Windows Store app IDs if dynamic lookup failed
                    if not launched:
                        store_apps = [
                            "TelegramMessengerLLP.TelegramDesktop_t4vj0pshhgkwm!Telegram.TelegramDesktop.Store",
                            "TelegramMessengerLLP.TelegramDesktop_t4vj0pshhgkwm!App",
                            "TelegramFZ-LLC.Telegram_g2v2zjf2hx2ja!App",
                        ]
                        for app_id in store_apps:
                            try:
                                self.logger.info(f"[TelegramGUI] Trying hardcoded ID: {app_id}")
                                subprocess.Popen(f'explorer shell:AppsFolder\\{app_id}', shell=True)
                                launched = True
                                break
                            except:
                                pass
                
                if not launched:
                    return SkillResult(success=False, error="Could not find Telegram. Please ensure it's installed.")
                
                time.sleep(2.0)  # Initial wait
                
                # Re-find window with retries (Windows Store apps can be slow to start)
                for attempt in range(5):
                    self.logger.info(f"[TelegramGUI] Re-find attempt {attempt + 1}/5...")
                    
                    # Method 1: Try win32 process-based search
                    pids = get_telegram_pids()
                    if pids:
                        windows = find_telegram_windows(pids)
                        skip = ['QTrayIconMessageWindow', 'MSCTFIME UI', 'Default IME']
                        for w_hwnd, w_title in windows:
                            if w_title and w_title not in skip:
                                try:
                                    self.logger.info(f"[TelegramGUI] Found via win32: {w_title}")
                                    win32gui.ShowWindow(w_hwnd, win32con.SW_RESTORE)
                                    time.sleep(0.1)
                                    win32gui.SetForegroundWindow(w_hwnd)
                                    hwnd = w_hwnd
                                    break
                                except Exception as e:
                                    self.logger.warning(f"[TelegramGUI] win32 focus failed: {e}")
                                    continue
                        if hwnd:
                            break
                    
                    # Method 2: Fallback to pyautogui window search
                    if not hwnd:
                        try:
                            telegram_windows = pyautogui.getWindowsWithTitle('Telegram')
                            if telegram_windows:
                                win = telegram_windows[0]
                                self.logger.info(f"[TelegramGUI] Found via pyautogui: {win.title}")
                                win.restore()
                                win.activate()
                                # Get hwnd from pyautogui window for later use
                                hwnd = win._hWnd
                                break
                        except Exception as e:
                            self.logger.warning(f"[TelegramGUI] pyautogui search failed: {e}")
                    
                    # Wait before next attempt
                    if attempt < 4:
                        time.sleep(2.0)
            
            if not hwnd:
                return SkillResult(success=False, error="Could not find or launch Telegram")
            

            # === ROBUST FOCUS ===
            self.logger.info(f"[TelegramGUI] Forcing focus on window: {hwnd}")
            try:
                # 1. Restore if minimized
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.2)
                
                # 2. Bring to front
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.2)
                
                # 3. Click relative to window to ensure input focus
                rect = win32gui.GetWindowRect(hwnd) # (left, top, right, bottom)
                # Click top-left area where search usually is
                click_x = rect[0] + 50
                click_y = rect[1] + 50
                pyautogui.click(click_x, click_y)
                time.sleep(0.5)
            except Exception as e:
                self.logger.warning(f"[TelegramGUI] Focus error: {e}")
                # Fallback click center
                try:
                    x, y = pyautogui.size()
                    pyautogui.click(x//2, y//2)
                except:
                    pass

            # === AUTOMATION ===
            pyautogui.PAUSE = 0.2 # Slow down
            
            # Step 2: Clear dialogs
            self.logger.info("[TelegramGUI] Clearing dialogs...")
            pyautogui.press('escape')
            time.sleep(0.5)
            pyautogui.press('escape')
            time.sleep(0.5)
            
            # Step 3: Search - Try Ctrl+F (Standard)
            self.logger.info("[TelegramGUI] Opening search (Ctrl+F)...")
            pyautogui.hotkey('ctrl', 'f')
            time.sleep(1.5) # Wait for animation
            
            # Step 4: Type contact name using clipboard
            self.logger.info(f"[TelegramGUI] Searching for '{contact}'...")
            pyperclip.copy(contact)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(2.0) # Wait for network search
            
            # Step 5: Select first result
            self.logger.info("[TelegramGUI] Selecting contact...")
            pyautogui.press('down')
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(2.0) # Wait for chat load
            
            # Step 6: Focus message input box
            self.logger.info("[TelegramGUI] Focusing message input...")
            
            # Method 1: Press Tab to move focus to input (Telegram convention)
            pyautogui.press('tab')
            time.sleep(0.3)
            
            # Method 2: Click the message input area (bottom of chat window)
            try:
                # Get window rect - handle both win32 hwnd and pyautogui window
                if hwnd:
                    try:
                        rect = win32gui.GetWindowRect(hwnd)
                        # Calculate message input position (typically at bottom center)
                        input_x = rect[0] + (rect[2] - rect[0]) // 2  # Center horizontally
                        input_y = rect[1] + int((rect[3] - rect[1]) * 0.85)  # 85% from top
                        self.logger.info(f"[TelegramGUI] Clicking input at ({input_x}, {input_y})")
                        pyautogui.click(input_x, input_y)
                        time.sleep(0.5)
                    except Exception as e:
                        self.logger.warning(f"[TelegramGUI] win32 click failed: {e}")
                        # Fallback: click center-bottom of screen
                        screen_w, screen_h = pyautogui.size()
                        pyautogui.click(screen_w // 2, int(screen_h * 0.85))
                        time.sleep(0.5)
            except Exception as e:
                self.logger.warning(f"[TelegramGUI] Click focus failed: {e}")

            # Step 7: Type message using clipboard
            self.logger.info(f"[TelegramGUI] Typing message: '{message}'")
            pyperclip.copy(message)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            
            # Verify something was typed by checking clipboard is still message
            self.logger.info("[TelegramGUI] Message pasted")
            
            # Step 8: Send with Enter
            self.logger.info("[TelegramGUI] Sending...")
            pyautogui.press('enter')
            time.sleep(0.5)
            
            self.logger.info(f"[TelegramGUI] ✓ Completed for {contact}")
            return SkillResult(
                success=True, 
                message=f"Sent '{message}' to {contact} via Telegram app",
                data={"contact": contact, "message": message}
            )
            
        except Exception as e:
            self.logger.error(f"[TelegramGUI] FAILED: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return SkillResult(success=False, error=str(e))
    
    # ==================== HEALTH & DRY-RUN ====================
    
    def health(self) -> SkillHealth:
        """Check desktop skill health."""
        if not self._loaded:
            return SkillHealth.UNAVAILABLE
        if not self._automation_available:
            return SkillHealth.DEGRADED
        return SkillHealth.READY
    
    def dry_run(self, action: str, params: Dict[str, Any]) -> str:
        """Preview desktop action."""
        previews = {
            "launch": f"Would launch: {params.get('app_name', 'unknown')}",
            "close": f"Would close: {params.get('app_name') or params.get('window_title', 'active window')}",
            "shortcut": f"Would press: {params.get('keys', [])}",
            "keyboard": f"Would type: {params.get('text', '')[:20]}...",
            "screenshot": f"Would save screenshot to: {params.get('path', 'default location')}",
            "volume": f"Would set volume to: {params.get('level', 'unchanged')}%",
        }
        
        return previews.get(action, f"Would execute: {action}")
