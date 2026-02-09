
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from .models import Pattern, ExperienceRecord

logger = logging.getLogger(__name__)

class PatternRecognizer:
    """
    Analyzes experiences to identify successful and unsuccessful patterns.
    """
    
    def __init__(self, session_factory):
        self.Session = session_factory
    
    def analyze_experiences(self, skill_name: str) -> List[dict]:
        """Analyze recent experiences to find patterns."""
        session = self.Session()
        try:
            # Get last 50 experiences
            exps = session.query(ExperienceRecord).filter_by(
                skill_name=skill_name
            ).order_by(ExperienceRecord.timestamp.desc()).limit(50).all()
            
            if not exps:
                return []
                
            # Naive analysis: check for repeated successful actions
            success_map = {}
            for e in exps:
                if e.success:
                    key = f"{e.action}"
                    success_map[key] = success_map.get(key, 0) + 1
            
            # Record patterns that appeared > 3 times
            found_patterns = []
            for action, count in success_map.items():
                if count >= 3:
                     # Check if pattern exists
                     existing = session.query(Pattern).filter_by(
                         skill_name=skill_name, 
                         description=f"Action '{action}' is often successful"
                     ).first()
                     
                     if not existing:
                         pat = Pattern(
                             pattern_type="action",
                             description=f"Action '{action}' is often successful",
                             skill_name=skill_name,
                             frequency=count,
                             success_rate=1.0, # Placeholder
                             contexts=[]
                         )
                         session.add(pat)
                         found_patterns.append(pat.to_dict())
                         logger.info(f"New pattern found for {skill_name}: {action}")
                     else:
                         existing.frequency = count
            
            session.commit()
            return found_patterns
            
        except Exception as e:
            session.rollback()
            logger.error(f"Pattern analysis failed: {e}")
            return []
        finally:
            session.close()

    def find_optimal_parameters(self, skill_name: str, task_type: str) -> dict:
        """Find parameters that lead to highest success."""
        # Simplified: just return empty dict for now, to be expanded with real analysis
        return {}

    def detect_anti_patterns(self, skill_name: str) -> List[dict]:
        """Detect patterns that lead to failure."""
        session = self.Session()
        try:
            exps = session.query(ExperienceRecord).filter_by(
                skill_name=skill_name, success=False
            ).limit(20).all()
            
            failures = {}
            for e in exps:
                key = e.error_message or "Unknown Error"
                failures[key] = failures.get(key, 0) + 1
                
            anti_patterns = []
            for error, count in failures.items():
                if count >= 3:
                     pat = Pattern(
                         pattern_type="anti_pattern",
                         description=f"Frequent error: {error}",
                         skill_name=skill_name,
                         frequency=count,
                         success_rate=0.0,
                         contexts=[]
                     )
                     # Don't save strictly, just return for reporting
                     anti_patterns.append(pat.to_dict())
            return anti_patterns
        finally:
            session.close()

    def suggest_improvements(self, skill_name: str) -> List[dict]:
        """Suggest improvements based on patterns."""
        anti_patterns = self.detect_anti_patterns(skill_name)
        suggestions = []
        for ap in anti_patterns:
            suggestions.append({
                "type": "avoid_error",
                "description": f"Avoid conditions causing: {ap['description']}"
            })
        return suggestions

    def update_pattern_success(self, pattern_id: str, success: bool) -> None:
        """Update success rate of a pattern."""
        session = self.Session()
        try:
            pat = session.query(Pattern).filter_by(id=pattern_id).first()
            if pat:
                pat.frequency += 1
                # Moving average
                alpha = 0.1
                current_rate = pat.success_rate
                new_val = 1.0 if success else 0.0
                pat.success_rate = (current_rate * (1-alpha)) + (new_val * alpha)
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
            
    def get_patterns(self, skill_name: str) -> List[dict]:
        """Get all patterns for a skill."""
        session = self.Session()
        try:
            patterns = session.query(Pattern).filter_by(skill_name=skill_name).all()
            return [p.to_dict() for p in patterns]
        finally:
            session.close()

    def get_all_patterns(self) -> List[dict]:
        """Get all discovered patterns."""
        session = self.Session()
        try:
            patterns = session.query(Pattern).all()
            return [p.to_dict() for p in patterns]
        finally:
            session.close()
