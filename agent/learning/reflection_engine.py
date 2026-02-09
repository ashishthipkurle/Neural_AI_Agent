
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from .models import Lesson, ExperienceRecord

logger = logging.getLogger(__name__)

class ReflectionEngine:
    """
    Reflects on past experiences to extract lessons.
    """
    
    def __init__(self, session_factory):
        self.Session = session_factory
        
    def reflect_on_task(self, experience_id: str) -> Dict[str, Any]:
        """Analyze a single experience."""
        session = self.Session()
        try:
            exp = session.query(ExperienceRecord).filter_by(id=experience_id).first()
            if not exp:
                return {}
            
            # Simple reflection logic
            lesson = None
            if not exp.success:
                lesson = self._create_failure_lesson(session, exp)
            
            return lesson.to_dict() if lesson else {}
        finally:
            session.close()

    def _create_failure_lesson(self, session, exp) -> Lesson:
        """Create a lesson from failure."""
        lesson = Lesson(
            task_type=exp.action,
            skill_name=exp.skill_name,
            what_worked="Attempted execution",
            what_failed=exp.error_message or "Unknown failure",
            recommendations="Check logs and retry with different parameters",
            experience_ids=[exp.id]
        )
        session.add(lesson)
        session.commit()
        return lesson
        
    def analyze_failure(self, experience_id: str) -> dict:
        """Deep analysis of a failure."""
        return {"cause": "unknown", "fix": "retry"}
        
    def generate_lessons(self, skill_name: str) -> List[dict]:
        """Generate lessons for a skill from recent history."""
        session = self.Session()
        try:
            lessons = session.query(Lesson).filter_by(skill_name=skill_name).all()
            return [l.to_dict() for l in lessons]
        finally:
            session.close()
            
    def get_improvement_suggestions(self, skill_name: str) -> List[str]:
        """Get suggestions based on lessons."""
        session = self.Session()
        try:
            lessons = session.query(Lesson).filter_by(skill_name=skill_name).limit(5).all()
            return [l.recommendations for l in lessons]
        finally:
            session.close()

    def cleanup_old_lessons(self, days: int) -> int:
        """Remove old lessons."""
        return 0
        
    def get_all_lessons(self) -> List[dict]:
        """Get all lessons."""
        session = self.Session()
        try:
            all_l = session.query(Lesson).all()
            return [l.to_dict() for l in all_l]
        finally:
            session.close()
