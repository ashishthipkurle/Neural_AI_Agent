
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from .models import KnowledgeBase

logger = logging.getLogger(__name__)

class KnowledgeConsolidator:
    """
    Consolidates lessons into a permanent knowledge base.
    """
    
    def __init__(self, session_factory):
        self.Session = session_factory
    
    def create_playbook(self, skill_name: str) -> str:
        """Create a playbook for a skill."""
        return f"Playbook for {skill_name}"
        
    def generate_best_practices(self, skill_name: str) -> List[str]:
        """Extract best practices."""
        return [f"Always verify inputs for {skill_name}"]
        
    def compress_old_experiences(self, days: int = 30) -> None:
        """Summarize old data."""
        pass
        
    def export_skill_guide(self, skill_name: str) -> str:
        """Create a readable guide."""
        return f"Guide for {skill_name}"
        
    def add_knowledge(self, topic: str, content: str, category="general") -> None:
        """Add entry to knowledge base."""
        session = self.Session()
        try:
            kb = KnowledgeBase(
                topic=topic,
                category=category,
                content=content
            )
            session.add(kb)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
            
    def search_knowledge(self, query: str) -> List[dict]:
        """Search knowledge base."""
        session = self.Session()
        try:
            # Simple substring match
            results = session.query(KnowledgeBase).filter(
                KnowledgeBase.content.contains(query)
            ).all()
            return [r.to_dict() for r in results]
        finally:
            session.close()
