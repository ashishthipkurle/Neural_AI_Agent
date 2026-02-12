
import sqlite3
import logging
import os
import datetime
from typing import List, Dict, Any, Optional

class SelfLearningEngine:
    """
    Module 11: Self-Learning Engine
    Optimize prompts and skills over time based on outcomes.
    """

    def __init__(self, db_path: str = "agent_data/learning.db"):
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        try:
            with self._get_connection() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                
                # Skill Performance
                conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_name TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN,
                    execution_time REAL,
                    error_message TEXT,
                    prompt_used TEXT
                )
                """)
                
                # Prompt Templates
                conn.execute("""
                CREATE TABLE IF NOT EXISTS prompt_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    template TEXT NOT NULL,
                    success_rate REAL DEFAULT 0.0,
                    usage_count INTEGER DEFAULT 0
                )
                """)
        except Exception as e:
            self.logger.error(f"Failed to init Learning DB: {e}")

    def record_outcome(self, task_type: str, skill_name: str,
                       prompt_used: str, success: bool,
                       execution_time: float, error_message: str = None) -> None:
        """Store outcome for analysis"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO skill_performance (skill_name, success, execution_time, error_message, prompt_used)
                    VALUES (?, ?, ?, ?, ?)
                """, (skill_name, success, execution_time, error_message, prompt_used))
                
                # Update prompt stats if template tracking logic existed
                # For now just logging raw performance
        except Exception as e:
            self.logger.error(f"Error recording outcome: {e}")

    def get_improved_prompt(self, task_type: str, base_prompt: str) -> str:
        """
        Analyze successful prompts for this task_type.
        Return optimized version incorporating patterns.
        """
        # Placeholder logic: In real system, would query `skill_performance` for successful prompts 
        # similar to `base_prompt` and try to merge/optimize.
        # For now, return base.
        return base_prompt

    def suggest_skill_improvement(self) -> List[Dict[str, Any]]:
        """
        Query skill_performance.
        Return skills with <80% success rate.
        """
        improvements = []
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                # Calculate success rate per skill
                cursor = conn.execute("""
                    SELECT skill_name, 
                           AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as rate,
                           COUNT(*) as count
                    FROM skill_performance
                    GROUP BY skill_name
                    HAVING count > 5
                """)
                for row in cursor:
                    if row['rate'] < 0.8:
                        improvements.append({
                            "skill": row['skill_name'],
                            "success_rate": row['rate'],
                            "suggestion": "Analyze error logs for common patterns."
                        })
        except Exception as e:
            self.logger.error(f"Error analyzing skills: {e}")
        return improvements

    def adapt_to_user_style(self, feedback: List[Dict[str, Any]]) -> None:
        """
        Learn from user corrections/preferences.
        Update approach based on feedback.
        """
        # Stub
        pass
