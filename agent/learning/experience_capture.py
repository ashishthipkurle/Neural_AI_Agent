
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from .models import ExperienceRecord

logger = logging.getLogger(__name__)

class ExperienceCapture:
    """
    Captures and retrieves execution experiences.
    """
    
    def __init__(self, session_factory):
        self.Session = session_factory

    def log_experience(self, skill_name: str, action: str, context: dict, 
                      outcome: dict, success: bool, duration: float,
                      error_message: str = None) -> str:
        """Log a new experience."""
        session = self.Session()
        try:
            exp = ExperienceRecord(
                skill_name=skill_name,
                action=action,
                context=context,
                outcome=outcome,
                success=success,
                duration=duration,
                error_message=error_message
            )
            session.add(exp)
            session.commit()
            logger.debug(f"Logged experience {exp.id} for {skill_name}.{action}")
            return exp.id
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to log experience: {e}")
            return ""
        finally:
            session.close()

    def get_recent_experiences(self, skill_name: str = None, limit: int = 100) -> List[dict]:
        """Get recent experiences, optionally filtered by skill."""
        session = self.Session()
        try:
            query = session.query(ExperienceRecord)
            if skill_name:
                query = query.filter_by(skill_name=skill_name)
            
            exps = query.order_by(ExperienceRecord.timestamp.desc()).limit(limit).all()
            return [e.to_dict() for e in exps]
        finally:
            session.close()

    def get_successful_patterns(self, skill_name: str) -> List[dict]:
        """Get successful experiences for a skill to analyze patterns."""
        session = self.Session()
        try:
            exps = session.query(ExperienceRecord).filter_by(
                skill_name=skill_name, 
                success=True
            ).limit(50).all()
            return [e.to_dict() for e in exps]
        finally:
            session.close()
            
    def get_failed_patterns(self, skill_name: str) -> List[dict]:
        """Get failed experiences for analysis."""
        session = self.Session()
        try:
            exps = session.query(ExperienceRecord).filter_by(
                skill_name=skill_name,
                success=False
            ).limit(50).all()
            return [e.to_dict() for e in exps]
        finally:
            session.close()

    def export_to_json(self) -> str:
        """Export all experiences to JSON string."""
        import json
        session = self.Session()
        try:
            exps = session.query(ExperienceRecord).all()
            return json.dumps([e.to_dict() for e in exps], indent=2)
        finally:
            session.close()

    def get_experience_by_id(self, exp_id: str) -> Optional[dict]:
        """Retrieve a specific experience."""
        session = self.Session()
        try:
            exp = session.query(ExperienceRecord).filter_by(id=exp_id).first()
            return exp.to_dict() if exp else None
        finally:
            session.close()
            
    def set_user_feedback(self, exp_id: str, rating: int) -> bool:
        """Set user feedback rating (1-5)."""
        session = self.Session()
        try:
            exp = session.query(ExperienceRecord).filter_by(id=exp_id).first()
            if exp:
                exp.user_feedback = rating
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def cleanup_old_records(self, days: int) -> int:
        """Delete records older than X days."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        session = self.Session()
        try:
            deleted = session.query(ExperienceRecord).filter(
                ExperienceRecord.timestamp < cutoff
            ).delete()
            session.commit()
            return deleted
        except Exception as e:
            session.rollback()
            logger.error(f"Cleanup failed: {e}")
            return 0
        finally:
            session.close()
