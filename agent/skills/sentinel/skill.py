"""
Sentinel Skill - Background screen monitoring and alerting.

This skill runs a background thread that periodically checks the screen for
specific conditions (text, visual changes) and sends alerts via Telegram.
"""

import time
import threading
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from ..base_skill import BaseSkill, SkillResult, SkillManifest, SkillHealth

class SentinelSkill(BaseSkill):
    """
    Background screen monitoring agent.
    
    Actions:
    - start_watch: Begin monitoring for a condition.
    - stop_watch: Stop monitoring.
    - status: Check current monitoring status.
    """

    def __init__(self):
        super().__init__()
        self._skill_router = None  # Injected
        self._is_running = False
        self._thread = None
        self._stop_event = threading.Event()
        self._current_config = {}
        
    @property
    def name(self) -> str:
        return "sentinel"

    @property
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            name="sentinel",
            version="1.0.0",
            description="Background screen monitoring and alerting.",
            actions=["start_watch", "stop_watch", "status"],
            requires=["vision", "telegram"],
            permissions=["screen", "background_task"]
        )

    def set_skill_router(self, router):
        self._skill_router = router

    def on_unload(self):
        """Stop background thread on unload."""
        self.stop_monitoring()
        super().on_unload()

    # ==================== INTENT MATCHING ====================

    def can_handle(self, intent: str, context: Optional[Dict] = None) -> float:
        intent_lower = intent.lower()
        if "watch" in intent_lower or "monitor" in intent_lower:
            if "screen" in intent_lower or "display" in intent_lower:
                return 0.85
        return 0.0

    # ==================== EXECUTION ====================

    async def execute(self, action: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        if action == "start_watch":
            return await self._start_watch(params)
        elif action == "stop_watch":
            return self._stop_watch()
        elif action == "status":
            return self._status()
        
        return SkillResult(success=False, error=f"Unknown action: {action}")

    # ==================== ACTIONS ====================

    async def _start_watch(self, params: Dict) -> SkillResult:
        """Start the monitoring loop."""
        if self._is_running:
            return SkillResult(success=False, error="Sentinel is already running. Stop it first.")

        condition = params.get("condition") or params.get("text")
        if not condition:
            return SkillResult(success=False, error="Monitoring condition required (e.g. text to find)")

        interval = params.get("interval", 10)  # Seconds
        
        self._current_config = {
            "condition": condition,
            "interval": interval,
            "type": "text"  # For now only text matching
        }
        
        self._stop_event.clear()
        self._is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        
        return SkillResult(
            success=True, 
            message=f"Sentinel started. Watching for '{condition}' every {interval}s."
        )

    def _stop_watch(self) -> SkillResult:
        """Stop the monitoring loop."""
        if not self._is_running:
            return SkillResult(success=True, message="Sentinel is not running.")
            
        self.stop_monitoring()
        return SkillResult(success=True, message="Sentinel stopped.")

    def _status(self) -> SkillResult:
        """Get status."""
        state = "Running" if self._is_running else "Stopped"
        return SkillResult(
            success=True, 
            message=f"Sentinel Status: {state}", 
            data={"running": self._is_running, "config": self._current_config}
        )

    def stop_monitoring(self):
        """Internal stop."""
        self._is_running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    # ==================== BACKGROUND LOOP ====================

    # ==================== BACKGROUND LOOP ====================

    def _monitor_loop(self):
        """Main background loop."""
        condition = self._current_config.get("condition")
        interval = self._current_config.get("interval", 10)
        
        self.logger.info(f"Sentinel Loop Started: {condition} every {interval}s")
        
        while not self._stop_event.is_set():
            try:
                # 1. Check Condition
                if self._check_condition():
                    self.logger.info(f"Sentinel: Condition '{condition}' met! Sending Alert...")
                    self._send_alert()
                    
                    # Wait longer after alert to avoid spam?
                    # For now just wait normal interval
                
            except Exception as e:
                self.logger.error(f"Sentinel loop error: {e}")
            
            # Wait for next interval
            if self._stop_event.wait(interval):
                break
        
        self.logger.info("Sentinel Loop Stopped")

    def _check_condition(self) -> bool:
        """Check if condition is met using VisionSkill."""
        if not self._skill_router:
            return False
            
        condition_text = self._current_config.get("condition", "").lower()
        
        # Get Vision Skill directly
        vision_info = self._skill_router.get_skill("vision")
        # Handle if it returns (skill, manifest) tuple or just skill instance
        # Based on typical SkillRouter implementation
        vision_skill = vision_info[0] if isinstance(vision_info, tuple) else vision_info
        
        if not vision_skill:
            self.logger.warning("Sentinel: Vision skill not found")
            return False
            
        # Execute OCR (blockingly)
        try:
            result = vision_skill.execute("ocr", {"capture_screen": True})
            if result.success:
                text = result.data.get("text", "").lower()
                if condition_text in text:
                    return True
        except Exception as e:
            self.logger.error(f"Sentinel check failed: {e}")
                
        return False

    def _send_alert(self):
        """Send Telegram alert."""
        if not self._skill_router:
            return

        telegram_info = self._skill_router.get_skill("telegram")
        telegram_skill = telegram_info[0] if isinstance(telegram_info, tuple) else telegram_info
        
        if not telegram_skill:
            return
            
        condition = self._current_config.get("condition")
        
        # 1. Take Screenshot for proof
        vision_info = self._skill_router.get_skill("vision")
        vision_skill = vision_info[0] if isinstance(vision_info, tuple) else vision_info
        
        path = f"agent/data/sentinel_alert_{int(time.time())}.png"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        if vision_skill:
            vision_skill.execute("screenshot", {"path": path})
        
        # 2. Send Text Alert
        telegram_skill.execute("send_message", {
            "text": f"🚨 **Sentinel Alert!**\n\nCondition met: found text '{condition}' on screen."
        })
        
        # 3. Send Screenshot
        if vision_skill:
            # Wait a moment for file to save
            time.sleep(1)
            telegram_skill.execute("send_photo", {
                "path": str(Path(path).absolute()),
                "caption": f"Screen capture at {time.strftime('%H:%M:%S')}"
            })
