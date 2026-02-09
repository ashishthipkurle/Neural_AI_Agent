
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from .models import Strategy

logger = logging.getLogger(__name__)

class StrategyOptimizer:
    """
    Manages A/B testing and strategy selection for skills.
    """
    
    def __init__(self, session_factory):
        self.Session = session_factory
        
    def register_strategy(self, name: str, skill_name: str, approach: dict) -> None:
        """Register a new strategy for a skill."""
        import json
        session = self.Session()
        try:
            exists = session.query(Strategy).filter_by(name=name, skill_name=skill_name).first()
            if not exists:
                strat = Strategy(
                    name=name,
                    skill_name=skill_name,
                    approach=json.dumps(approach),
                    task_types=[],
                    parameters={}
                )
                session.add(strat)
                session.commit()
                logger.info(f"Registered strategy '{name}' for {skill_name}")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to register strategy: {e}")
        finally:
            session.close()

    def select_strategy(self, skill_name: str, context: dict) -> str:
        """Select best strategy for context."""
        session = self.Session()
        try:
            # Simple logic: pick highest success rate
            strategies = session.query(Strategy).filter_by(skill_name=skill_name).all()
            if not strategies:
                return "default"
            
            best = max(strategies, key=lambda s: (s.success_count / (s.success_count + s.failure_count + 1)))
            return best.name
        finally:
            session.close()

    def record_result(self, strategy_name: str, success: bool, duration: float) -> None:
        """Record outcome of a strategy."""
        session = self.Session()
        try:
            strat = session.query(Strategy).filter_by(name=strategy_name).first()
            if strat:
                if success:
                    strat.success_count += 1
                else:
                    strat.failure_count += 1
                
                # Update moving average of duration
                n = strat.success_count + strat.failure_count
                strat.average_duration = ((strat.average_duration * (n-1)) + duration) / n
                
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def get_best_strategy(self, skill_name: str) -> str:
        """Get name of historically best strategy."""
        session = self.Session()
        try:
            strategies = session.query(Strategy).filter_by(skill_name=skill_name).all()
            if not strategies:
                return "default"
            
            best = max(strategies, key=lambda s: s.success_count)
            return best.name
        finally:
            session.close()

    def run_ab_test(self, skill_name: str, strategy_a: str, strategy_b: str) -> None:
        """Initiate A/B test (placeholder for future logic)."""
        pass 

    def get_strategies(self, skill_name: str) -> List[dict]:
        """Get all strategies for a skill."""
        session = self.Session()
        try:
            strats = session.query(Strategy).filter_by(skill_name=skill_name).all()
            return [s.to_dict() for s in strats]
        finally:
            session.close()
            
    def optimize_parameters(self, strategy_name: str, feedback: float) -> None:
        """Adjust parameters based on feedback."""
        pass
        
    def get_all_strategies(self) -> List[dict]:
        """Return all strategies."""
        session = self.Session()
        try:
            all_strats = session.query(Strategy).all()
            return [s.to_dict() for s in all_strats]
        finally:
            session.close()
