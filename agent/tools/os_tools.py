import os
import shutil
import subprocess
import logging
import json
from agent.security.permissions import PermissionManager
from agent.security.sandbox import SecureCommandRunner

class OSTools:
    def __init__(self):
        self.permissions = PermissionManager()
        self.command_runner = SecureCommandRunner()
        self.logger = logging.getLogger("OSTools")
        self.app_index = {}
        self._build_app_index()

    def _build_app_index(self):
        """
        Scans common Start Menu locations to build a map of App Name -> Shortcut Path.
        """
        try:
            paths = [
                os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
                os.path.join(os.environ.get("APPDATA", "C:\\Users\\Default\\AppData"), r"Microsoft\Windows\Start Menu\Programs")
            ]

            for root_path in paths:
                if not os.path.exists(root_path): continue
                
                for root, dirs, files in os.walk(root_path):
                    for file in files:
                        if file.lower().endswith(".lnk"):
                            # Normalize name: "Google Chrome.lnk" -> "google chrome"
                            name = file[:-4].lower()
                            full_path = os.path.join(root, file)
                            self.app_index[name] = full_path
            
            # Index Store Apps
            self._index_store_apps()
            
            self.logger.info(f"Indexed {len(self.app_index)} applications from Start Menu & Store.")
        except Exception as e:
            self.logger.error(f"Error indexing apps: {e}")

    def _index_store_apps(self):
        """
        Indexes UWP/Store apps using PowerShell Get-StartApps.
        """
        try:
            cmd = ["powershell", "-Command", "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json"]
            out = subprocess.check_output(cmd, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0).decode('utf-8', errors='ignore')
            data = json.loads(out)
            
            if isinstance(data, dict):
                data = [data]
                
            for item in data:
                name = item.get("Name", "").lower()
                appid = item.get("AppID", "")
                if name and appid:
                    self.app_index[name] = f"shell:AppsFolder\\{appid}"
        except Exception as e:
            self.logger.warning(f"Could not index Store apps: {e}")

    # --- INPUT AUTOMATION ---
    def move_mouse(self, x: int, y: int):
        import pyautogui
        pyautogui.moveTo(x, y, duration=0.5)
        return f"Moved mouse to {x}, {y}"

    def click_mouse(self):
        import pyautogui
        pyautogui.click()
        return "Clicked mouse."

    def type_text(self, text: str):
        import pyautogui
        pyautogui.typewrite(text)
        return f"Typed: {text}"

    def press_key(self, key: str):
        import pyautogui
        if key in pyautogui.KEY_NAMES:
            pyautogui.press(key)
            return f"Pressed key {key}"
        return f"Invalid key: {key}"

    def read_file(self, path: str) -> str:
        """
        Safely reads a text file.
        """
        if not self.permissions.is_path_allowed(path):
            return f"Error: Access denied to {path}"

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read(2048) # Limit read to 2KB for safety in this phase
                if len(content) == 2048:
                    content += "\n...[truncated]"
                return content
        except FileNotFoundError:
            return f"Error: File not found: {path}"
        except Exception as e:
            return f"Error reading file: {e}"

    def write_file(self, path: str, content: str) -> str:
        """
        Safely writes content to a file. Overwrites if exists.
        """
        if not self.permissions.is_path_allowed(path):
            return f"Error: Access denied to {path}"

        # Check for confirmation
        if not self.permissions.request_permission(f"Overwrite/Write file at {path}"):
             return "Action cancelled by user."

        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    def delete_path(self, path: str, recursive: bool = True) -> str:
        """
        Safely deletes a file or directory.
        - Files are deleted directly.
        - Directories require recursive=True to be removed.
        """
        if not self.permissions.is_path_allowed(path):
            return f"Error: Access denied to {path}"

        if not self.permissions.request_permission(f"Delete path at {path}"):
            return "Action cancelled by user."

        try:
            normalized = os.path.normpath(path)

            if not os.path.exists(normalized):
                return f"Error: Path not found: {path}"

            if os.path.isfile(normalized):
                os.remove(normalized)
                return f"Successfully deleted file: {path}"

            if os.path.isdir(normalized):
                if not recursive:
                    return f"Error: Directory deletion requires recursive=True: {path}"
                shutil.rmtree(normalized)
                return f"Successfully deleted directory: {path}"

            return f"Error: Unsupported path type: {path}"
        except Exception as e:
            return f"Error deleting path: {e}"

    async def launch_app(self, app_name: str, extra_args: str = None) -> str:
        """
        Launches an application. 
        1. Checks hardcoded safe aliases.
        2. Checks dynamically indexed Start Menu shortcuts & Store Apps.
           - Supports Exact Match
           - Supports Fuzzy Match (e.g. "teams" -> "Microsoft Teams")
        3. Falls back to raw system shell launch (with warning).
        Support 'extra_args' for specific app switches (e.g. Chrome profiles).
        """
        # Dictionary of common safe aliases
        app_map = {
            "notepad": "notepad.exe",
            "calc": "calc.exe",
            "calculator": "calc.exe",
            "chrome": "chrome.exe",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
            "browser": "msedge.exe", # Default to edge if they just say 'browser'
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "explorer": "explorer.exe",
            "store": "ms-windows-store:",
            "microsoft store": "ms-windows-store:",
            "settings": "ms-settings:",
            "code": "code",
            "vscode": "code",
            "paint": "mspaint.exe",
            "excel": "excel.exe",
            "word": "winword.exe"
        }
        
        # SPECIAL HANDLING: For browsers, try to find full path first to avoid 'start' command argument dropping issues
        if app_name.lower() in ["chrome", "google chrome"]:
            full_path = self._find_browser_path("chrome.exe")
            if full_path:
                target = full_path
                # We found the executable, empty out app_map logic for this
                app_map_target = None 
            else:
                target = "chrome.exe" # Fallback
                app_map_target = None
        elif app_name.lower() in ["edge", "microsoft edge", "browser"]:
            full_path = self._find_browser_path("msedge.exe")
            if full_path:
                target = full_path
                app_map_target = None
            else:
                target = "msedge.exe"
                app_map_target = None
        else:
             target = None
             app_map_target = app_map.get(app_name.lower())
        
        if app_map_target:
            target = app_map_target
        
        # If not in hardcoded map, check dynamic index
        if not target:
            # 1. Exact Match
            target = self.app_index.get(app_name.lower())
            
            # 2. Fuzzy Match
            if not target:
                for name, path in self.app_index.items():
                    if app_name.lower() in name:
                        target = path
                        self.logger.info(f"Fuzzy match: '{app_name}' -> '{name}'")
                        break
        
        cmd_args = ""
        # Handle Chrome Profile Logic
        if "chrome" in app_name.lower() and extra_args and extra_args.startswith("profile:"):
            # Resolving profile name to directory
            requested_name = extra_args.replace("profile:", "").strip()
            profile_dir = self._resolve_chrome_profile(requested_name)
            if profile_dir:
                cmd_args = f' --profile-directory="{profile_dir}"'
                self.logger.info(f"Resolved Chrome profile '{requested_name}' to '{profile_dir}'")
            else:
                return f"Error: Could not find Chrome profile named '{requested_name}'"
        elif extra_args:
             # Generic Argument Support (e.g. file paths)
             cmd_args = f' "{extra_args}"'

        if not target:
            # Fallback: Try raw launch
            description = f"Launch UNKNOWN application '{app_name}' (System Shell)"
            target = app_name 
        else:
            description = f"Launch application {target}"

        if not self.permissions.request_permission(description):
            return "Action cancelled by user."

        try:
            # Use 'start' to handle both .exe and .lnk files
            # For 'start', the first quoted argument is the window title, so we pass an empty title ""
            # cmd_args is already quoted if needed (e.g. "https://...")
            
            if cmd_args:
                # If we have args, we append them.
                # NOTE: cmd_args already has a leading space and quotes around the value e.g. ' "http://..."'
                
                # OPTIMIZATION: If target is a known executable path (e.g. Chrome/Edge), 
                # run directly with Popen to avoid 'start' swallowing arguments.
                # We check for .exe suffix to identify direct executable paths vs shortcuts.
                if target.lower().endswith(".exe"):
                    # Strip leading space/quotes from cmd_args to get raw arg
                    # cmd_args is likely ' "http...""
                    raw_arg = cmd_args.strip()
                    if raw_arg.startswith('"') and raw_arg.endswith('"'):
                        raw_arg = raw_arg[1:-1]
                    
                    self.logger.info(f"Direct Popen: '{target}' '{raw_arg}'")
                    await self.command_runner.run(f"{target} {raw_arg}")
                    return f"Launched {app_name} directly"

                # Fallback to start
                cmd = f'start "" "{target}"{cmd_args}'
            else:
                cmd = f'start "" "{target}"'
                
            self.logger.info(f"Executing: {cmd}")
            await self.command_runner.run(cmd)
            
            # Wait for app to open (rudimentary fix for typing race condition)
            import time
            time.sleep(2.0) 
            
            return f"Launched {app_name} {cmd_args}"
        except Exception as e:
            return f"Error launching app: {e}"

    def _resolve_chrome_profile(self, display_name: str) -> str:
        """
        Reads Chrome Local State to find the internal profile directory name 
        (e.g., "Profile 2") given a display name (e.g., "Ashish").
        """
        import json
        try:
            local_app_data = os.environ.get("LOCALAPPDATA")
            if not local_app_data: return None
            
            state_path = os.path.join(local_app_data, r"Google\Chrome\User Data\Local State")
            if not os.path.exists(state_path):
                self.logger.warning("Chrome Local State file not found.")
                return None

            with open(state_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            info_cache = data.get("profile", {}).get("info_cache", {})
            
            # Search for partial match case-insensitive
            for dir_name, info in info_cache.items():
                name = info.get("name", "").lower()
                if display_name.lower() in name:
                    return dir_name # Return internal name e.g. "Default" or "Profile 1"
            
            return None
        except Exception as e:
            self.logger.error(f"Error resolving Chrome profile: {e}")
            return None
            
    def _find_browser_path(self, exe_name: str) -> str:
        """Finds common browser executables."""
        paths = [
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), f"Microsoft\\Edge\\Application\\{exe_name}"),
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), f"Microsoft\\Edge\\Application\\{exe_name}"),
            os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), f"Google\\Chrome\\Application\\{exe_name}"),
            os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), f"Google\\Chrome\\Application\\{exe_name}"),
        ]
        for p in paths:
             if os.path.exists(p): return p
        return None
