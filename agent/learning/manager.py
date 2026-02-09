
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
from .models import init_learning_db, ExperienceRecord, Pattern, SkillProficiency, Strategy, Lesson, LearningState, KnowledgeBase
from .experience_capture import ExperienceCapture
from .pattern_recognizer import PatternRecognizer
from .skill_registry import SkillRegistry
from .strategy_optimizer import StrategyOptimizer
from .meta_learner import MetaLearner
from .reflection_engine import ReflectionEngine
from .knowledge_consolidator import KnowledgeConsolidator

logger = logging.getLogger(__name__)

class LearningManager:
    """
    Central coordinator for all learning activities.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize LearningManager with configuration.
        """
        self.config = config
        self.db_path = config.get('learning', {}).get('db_path', 'agent/data/learning.db')
        self.engine = None
        self.Session = None
        
        # Components
        self.experience_capture = None
        self.pattern_recognizer = None
        self.skill_registry = None
        self.strategy_optimizer = None
        self.meta_learner = None
        self.reflection_engine = None
        self.knowledge_consolidator = None
        
        # Initialize
        self.initialize()
    
    def initialize(self) -> None:
        """
        Initialize database and load state.
        """
        logger.info(f"Initializing Learning Database at {self.db_path}")
        self.engine = init_learning_db(self.db_path)
        self.Session = sessionmaker(bind=self.engine)
        
        # Init components with session factory
        self.experience_capture = ExperienceCapture(self.Session)
        self.pattern_recognizer = PatternRecognizer(self.Session)
        self.skill_registry = SkillRegistry(self.Session)
        self.strategy_optimizer = StrategyOptimizer(self.Session)
        self.meta_learner = MetaLearner(self.Session)
        self.reflection_engine = ReflectionEngine(self.Session)
        self.knowledge_consolidator = KnowledgeConsolidator(self.Session)
        
    def record_experience(self, skill_name: str, action: str, context: dict, 
                         outcome: dict, success: bool, duration: float,
                         error_message: str = None) -> str:
        """
        Record a new experience.
        """
        # 1. Capture raw experience
        exp_id = self.experience_capture.log_experience(
            skill_name, action, context, outcome, success, duration, error_message
        )
        
        # 2. Update Skill Proficiency
        self.skill_registry.update_proficiency(skill_name, success, duration)
        
        # 3. Update Strategy Stats (if strategy used)
        strategy_name = context.get('strategy')
        if strategy_name:
            self.strategy_optimizer.record_result(strategy_name, success, duration)
            
        return exp_id
    
    def optimize_skill(self, skill_name: str) -> Dict[str, Any]:
        """
        Run optimization for a specific skill.
        Analysis patterns, generating lessons, and strategies.
        """
        logger.info(f"Running optimization for {skill_name}")
        results = {
            "patterns_found": 0,
            "lessons_learned": 0,
            "strategies_updated": 0
        }
        
        # 1. Pattern Analysis
        patterns = self.pattern_recognizer.analyze_experiences(skill_name)
        results["patterns_found"] = len(patterns)
        
        # 2. Generate Lessons
        lessons = self.reflection_engine.generate_lessons(skill_name)
        if not lessons:
             # Try to generate new ones from recent failures based on patterns
             anti = self.pattern_recognizer.detect_anti_patterns(skill_name)
             if anti:
                 for ap in anti:
                     # This is a simplification; normally we'd create lessons here
                     pass
        
        return results
    
    def run_periodic_analysis(self) -> None:
        """
        Run periodic analysis and optimization.
        """
        logger.info("Running periodic learning analysis...")
        skills = self.skill_registry.get_all_skills()
        for skill in skills:
            if skill.get('proficiency_score', 0) < 0.8: # Optimize struggling skills
                self.optimize_skill(skill['skill_name'])
                
    def get_learning_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive learning statistics.
        """
        session = self.Session()
        try:
            total_exp = session.query(ExperienceRecord).count()
            total_patterns = session.query(Pattern).count()
            total_lessons = session.query(Lesson).count()
            avg_proficiency = 0.0
            
            skills = self.skill_registry.get_all_skills()
            if skills:
                avg_proficiency = sum(s['proficiency_score'] for s in skills) / len(skills)
                
            return {
                "total_experiences": total_exp,
                "total_patterns": total_patterns,
                "total_lessons": total_lessons,
                "average_skill_proficiency": avg_proficiency,
                "active_skills": len(skills)
            }
        finally:
            session.close()
    
    def export_learning_data(self) -> Dict[str, Any]:
        """
        Export all learning data.
        """
        return {
            "experiences": self.experience_capture.get_recent_experiences(limit=1000),
            "patterns": self.pattern_recognizer.get_all_patterns(),
            "skills": self.skill_registry.get_all_skills(),
            "strategies": self.strategy_optimizer.get_all_strategies(),
            "lessons": self.reflection_engine.get_all_lessons()
        }
    
    def import_learning_data(self, data: Dict[str, Any]) -> None:
        """
        Import learning data (placeholder).
        """
        logger.info("Importing learning data (not implemented fully)")
        pass
    
    def get_skill_suggestions(self) -> List[str]:
        """
        Get suggestions for skills that need improvement.
        """
        return self.skill_registry.get_learning_recommendations()
    
    def apply_user_feedback(self, experience_id: str, rating: int, 
                           comment: str = None) -> None:
        """
        Apply user feedback to an experience.
        """
        self.experience_capture.set_user_feedback(experience_id, rating)
        # If rating is low, trigger failure analysis
        if rating <= 2:
            self.reflection_engine.analyze_failure(experience_id)
            
    def get_best_practice(self, skill_name: str, task_type: str) -> Optional[str]:
        """
        Get best practice for a skill/task.
        """
        # 1. Check verified strategies
        strat = self.strategy_optimizer.get_best_strategy(skill_name)
        if strat and strat != "default":
            return f"Use strategy: {strat}"
            
        # 2. Check patterns
        patterns = self.pattern_recognizer.get_patterns(skill_name)
        if patterns:
            return f"Follow pattern: {patterns[0]['description']}"
            
        return None
    
    def discover_new_skills(self, experiences: List[ExperienceRecord]) -> List[str]:
        """
        Analyze experiences to discover new skills (placeholder).
        """
        return []
        
    def cleanup_old_data(self, days: int = 90) -> int:
        """
        Clean up old data.
        """
        return self.experience_capture.cleanup_old_records(days)
