
import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from .models import SkillProficiency

logger = logging.getLogger(__name__)

class SkillRegistry:
    """
    Tracks and manages skill proficiency levels.
    """
    
    def __init__(self, session_factory):
        self.Session = session_factory
    
    def register_skill(self, name: str, category: str, description: str = None) -> None:
        """Register a new skill or update existing registration."""
        session = self.Session()
        try:
            skill = session.query(SkillProficiency).filter_by(skill_name=name).first()
            if not skill:
                skill = SkillProficiency(
                    skill_name=name,
                    category=category,
                    description=description
                )
                session.add(skill)
                logger.info(f"Registered new skill: {name}")
            else:
                if description and description != skill.description:
                    skill.description = description
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to register skill {name}: {e}")
        finally:
            session.close()
    
    def update_proficiency(self, name: str, success: bool, duration: float) -> None:
        """Update skill proficiency based on execution result."""
        session = self.Session()
        try:
            skill = session.query(SkillProficiency).filter_by(skill_name=name).first()
            if not skill:
                # Auto-register if unknown
                self.register_skill(name, "unknown", "Auto-discovered skill")
                skill = session.query(SkillProficiency).filter_by(skill_name=name).first()
            
            if success:
                skill.success_count += 1
                # Simple proficiency boost on success
                skill.proficiency_score = min(1.0, skill.proficiency_score + 0.05)
            else:
                skill.failure_count += 1
                # Penalty on failure
                skill.proficiency_score = max(0.0, skill.proficiency_score - 0.02)
                
            skill.last_used = datetime.utcnow()
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update proficiency for {name}: {e}")
        finally:
            session.close()

    def get_proficiency(self, name: str) -> float:
        """Get current proficiency score for a skill."""
        session = self.Session()
        try:
            skill = session.query(SkillProficiency).filter_by(skill_name=name).first()
            return skill.proficiency_score if skill else 0.0
        finally:
            session.close()

    def get_skills_by_category(self, category: str) -> List[dict]:
        """Get all skills in a specific category."""
        session = self.Session()
        try:
            skills = session.query(SkillProficiency).filter_by(category=category).all()
            return [s.to_dict() for s in skills]
        finally:
            session.close()

    def get_expert_skills(self, min_proficiency: float = 0.8) -> List[dict]:
        """Get skills with high proficiency."""
        session = self.Session()
        try:
            skills = session.query(SkillProficiency).filter(
                SkillProficiency.proficiency_score >= min_proficiency
            ).all()
            return [s.to_dict() for s in skills]
        finally:
            session.close()

    def get_learning_recommendations(self) -> List[str]:
        """Get recommendations for skills that need practice."""
        session = self.Session()
        try:
            # Recommend skills with high failure rates or low usage
            skills = session.query(SkillProficiency).filter(
                SkillProficiency.proficiency_score < 0.5
            ).limit(5).all()
            
            recommendations = []
            for s in skills:
                recommendations.append(f"Practice '{s.skill_name}' (Current Proficiency: {s.proficiency_score:.2f})")
            return recommendations
        finally:
            session.close()
    
    def set_optimal_parameters(self, name: str, params: dict) -> None:
        """Save discovered optimal parameters."""
        session = self.Session()
        try:
            skill = session.query(SkillProficiency).filter_by(skill_name=name).first()
            if skill:
                skill.optimal_parameters = params
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to set parameters for {name}: {e}")
        finally:
            session.close()

    def get_optimal_parameters(self, name: str) -> dict:
        """Retrieve optimal parameters."""
        session = self.Session()
        try:
            skill = session.query(SkillProficiency).filter_by(skill_name=name).first()
            return skill.optimal_parameters if skill else {}
        finally:
            session.close()

    def add_example(self, name: str, example: str) -> None:
        """Add a usage example."""
        session = self.Session()
        try:
            skill = session.query(SkillProficiency).filter_by(skill_name=name).first()
            if skill:
                examples = list(skill.examples) if skill.examples else []
                if example not in examples:
                    examples.append(example)
                    skill.examples = examples
                    session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add example for {name}: {e}")
        finally:
            session.close()
            
    def get_all_skills(self) -> List[dict]:
        """Return dicts of all registered skills."""
        session = self.Session()
        try:
            all_skills = session.query(SkillProficiency).all()
            return [s.to_dict() for s in all_skills]
        finally:
            session.close()
