"""
INDRA Task Planner — Breaks tasks into atomic steps.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import get_logger

logger = get_logger("Planner")


class Planner:
    """Breaks a high-level task description into atomic executable steps."""

    def plan(self, task_description: str) -> list[str]:
        """
        Generate a simple step plan from a task description.
        For complex tasks, the vision brain handles step-by-step dynamically.
        This provides an initial outline for logging/narration.
        """
        # Simple keyword-based planning for common patterns
        task_lower = task_description.lower()

        if "search" in task_lower and ("google" in task_lower or "web" in task_lower):
            query = task_description.split("search for")[-1].strip() if "search for" in task_lower else task_description
            return [
                "Open Chrome browser",
                f"Navigate to Google",
                f"Type search query: {query}",
                "Press Enter",
                "Review results"
            ]

        if "open" in task_lower:
            target = task_description.split("open")[-1].strip()
            return [f"Open {target}", "Verify it launched"]

        if "download" in task_lower:
            return [
                "Navigate to download source",
                "Locate download button/link",
                "Click download",
                "Wait for download to complete",
                "Verify file saved"
            ]

        if "type" in task_lower or "write" in task_lower:
            return [
                "Focus target text field",
                "Type the content",
                "Verify content entered"
            ]

        # Default: let vision brain handle it dynamically
        return [
            f"Analyse screen for: {task_description}",
            "Execute required actions",
            "Verify completion"
        ]
