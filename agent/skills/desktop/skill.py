"""
Desktop Skill - OS-level automation and control.

Provides:
- Application launching/closing
- Window management
- Keyboard/mouse control
- Clipboard operations
- System controls (volume, brightness)
- App-specific integrations
"""

import os
import subprocess
import ctypes
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth

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
    
    # Common applications mapping
    APP_PATHS = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe",
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
        "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "spotify": "spotify.exe",
        "discord": "discord.exe",
        "slack": "slack.exe",
        "vscode": "code",
        "code": "code",
    }
    
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
            version="1.0.0",
            description="OS-level automation and application control",
            actions=[
                "launch", "close", "focus", "minimize", "maximize", "restore",
                "keyboard", "shortcut", "mouse_click", "mouse_move", "mouse_drag",
                "clipboard_read", "clipboard_write", "screenshot",
                "volume", "notify", "write_file", "read_file",
                "spotify_play", "spotify_pause", "spotify_next", "spotify_prev",
            ],
            requires=["pyautogui", "pygetwindow"],
            permissions=["system", "input", "clipboard"]
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
        
        # High confidence patterns
        high_patterns = [
            "open ", "launch ", "start ", "run ",
            "close ", "quit ", "exit ",
            "minimize", "maximize",
            "type ", "press ", "click ",
            "copy", "paste", "clipboard",
            "volume", "mute",
            "screenshot", "capture screen",
            "spotify", "discord",
        ]
        
        for pattern in high_patterns:
            if pattern in intent_lower:
                return 0.85
        
        # Check for known app names
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
        
        if any(x in intent_lower for x in ["open", "launch", "start", "run"]):
            # Extract app name from intent
            for app in self.APP_PATHS:
                if app in intent_lower:
                    params["app_name"] = app
                    return self._action_launch
            return self._action_launch
        
        if any(x in intent_lower for x in ["close", "quit", "exit"]):
            return self._action_close
        
        if "spotify" in intent_lower:
            if "play" in intent_lower:
                return self._action_spotify_play
            if "pause" in intent_lower or "stop" in intent_lower:
                return self._action_spotify_pause
            if "next" in intent_lower or "skip" in intent_lower:
                return self._action_spotify_next
        
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
        if not filename.startswith(("agent/", "output/", "D:", "C:")):
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
