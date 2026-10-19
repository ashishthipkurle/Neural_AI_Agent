"""
INDRA Project Manager -- Long-running project CRUD and status tracking.
Persists to JSON for easy inspection and survives across sessions.
"""

import json
import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import MEMORY_DB_PATH
from utils.logger import get_logger

logger = get_logger("Projects")

PROJECTS_FILE = Path(MEMORY_DB_PATH) / "projects.json"


class ProjectManager:
    def __init__(self):
        self.projects = self._load()
        logger.info(f"Loaded {len(self.projects)} projects ({len(self.get_active())} active)")

    def _load(self) -> dict:
        if PROJECTS_FILE.exists():
            try:
                return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Projects file corrupt, starting fresh: {e}")
                return {}
        return {}

    def _save(self):
        PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROJECTS_FILE.write_text(
            json.dumps(self.projects, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def create(self, name: str, description: str) -> str:
        """Create a new project. Returns project ID."""
        pid = f"proj_{int(datetime.datetime.now().timestamp())}"
        self.projects[pid] = {
            "id": pid,
            "name": name,
            "description": description,
            "status": "active",
            "created": datetime.datetime.now().isoformat(),
            "last_updated": datetime.datetime.now().isoformat(),
            "notes": []
        }
        self._save()
        logger.info(f"Created project: {name} ({pid})")
        return pid

    def update_status(self, pid: str, status: str):
        """Update project status. status: 'active' | 'paused' | 'done'"""
        if pid in self.projects:
            self.projects[pid]["status"] = status
            self.projects[pid]["last_updated"] = datetime.datetime.now().isoformat()
            self._save()
            logger.info(f"Project {pid} -> {status}")
        else:
            logger.warning(f"Project not found: {pid}")

    def add_note(self, pid: str, note: str):
        """Add a timestamped note to a project."""
        if pid in self.projects:
            self.projects[pid]["notes"].append({
                "text": note,
                "timestamp": datetime.datetime.now().isoformat()
            })
            self.projects[pid]["last_updated"] = datetime.datetime.now().isoformat()
            self._save()
            logger.debug(f"Note added to {pid}: {note[:60]}...")
        else:
            logger.warning(f"Project not found: {pid}")

    def get_active(self) -> list[dict]:
        """Get all active projects."""
        return [p for p in self.projects.values() if p["status"] == "active"]

    def get_all(self) -> list[dict]:
        """Get all projects regardless of status."""
        return list(self.projects.values())

    def find_by_name(self, name: str) -> dict | None:
        """Find a project by name (case-insensitive partial match)."""
        name_lower = name.lower()
        for p in self.projects.values():
            if name_lower in p["name"].lower():
                return p
        return None

    def get_briefing(self) -> str:
        """
        Returns a spoken briefing string for startup.
        e.g. "You have 2 active projects: the INDRA build, and the portfolio website."
        Returns empty string if no active projects.
        """
        active = self.get_active()
        if not active:
            return ""
        names = [p["name"] for p in active]
        if len(names) == 1:
            return f"You have one active project: {names[0]}."
        return f"You have {len(names)} active projects: {', '.join(names[:-1])}, and {names[-1]}."
