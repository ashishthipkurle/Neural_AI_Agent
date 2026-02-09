from typing import Dict, Any, List
from agent.skills.base_skill import BaseSkill, SkillResult
import os

class CodingSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "coding"

    @property
    def manifest(self):
        from agent.skills.base_skill import SkillManifest
        return SkillManifest(
            name="coding",
            version="1.0.0",
            description="Handles code reading, writing, refactoring and testing.",
            actions=["read_file", "write_file", "list_files", "run_command"],
            permissions=["filesystem", "command_execution"]
        )

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        """Check if skill can handle intent."""
        intent = intent.lower()
        keywords = ["code", "script", "file", "run", "execute", "python", "debug"]
        if any(k in intent for k in keywords):
            return 0.9
        return 0.0

    def __init__(self):
        super().__init__()

    async def execute(self, action: str, params: Dict[str, Any], context: Dict[str, Any] = None) -> SkillResult:
        """
        Execute coding actions.
        Supported actions:
        - read_file(path)
        - write_file(path, content)
        - list_files(directory)
        - run_command(command, cwd)
        """
        if action == "read_file":
            return await self._read_file(params.get("path"))
        elif action == "write_file":
            return await self._write_file(params.get("path"), params.get("content"))
        elif action == "list_files":
            return await self._list_files(params.get("directory", "."))
        elif action == "run_command":
            return await self._run_command(params.get("command"), params.get("cwd", "."))
        else:
            return SkillResult(success=False, error=f"Unknown action: {action}")

    async def _read_file(self, path: str) -> SkillResult:
        try:
            if not os.path.exists(path):
                return SkillResult(success=False, error="File not found")
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return SkillResult(success=True, message=content, data={"content": content})
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _write_file(self, path: str, content: str) -> SkillResult:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return SkillResult(success=True, message=f"File written to {path}")
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _list_files(self, directory: str) -> SkillResult:
        try:
            files = []
            for entry in os.scandir(directory):
                files.append(entry.name)
            return SkillResult(success=True, message="\n".join(files), data={"files": files})
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    async def _run_command(self, command: str, cwd: str) -> SkillResult:
        import asyncio
        import subprocess
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            output = stdout.decode().strip()
            error = stderr.decode().strip()
            
            if process.returncode == 0:
                return SkillResult(success=True, message=output, data={"stdout": output, "stderr": error})
            else:
                return SkillResult(success=False, error=f"Command failed: {error}", data={"stdout": output})
        except Exception as e:
            return SkillResult(success=False, error=str(e))
