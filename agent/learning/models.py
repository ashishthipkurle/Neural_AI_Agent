from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
import json

Base = declarative_base()

class ExperienceRecord(Base):
    __tablename__ = 'experiences'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow)
    skill_name = Column(String, nullable=False)
    action = Column(String, nullable=False)
    context = Column(JSON, default=dict)
    outcome = Column(JSON, default=dict)
    success = Column(Boolean, nullable=False)
    duration = Column(Float, nullable=False)
    error_message = Column(Text, nullable=True)
    user_feedback = Column(Integer, nullable=True)  # 1-5 rating
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'skill_name': self.skill_name,
            'action': self.action,
            'context': self.context,
            'outcome': self.outcome,
            'success': self.success,
            'duration': self.duration,
            'error_message': self.error_message,
            'user_feedback': self.user_feedback
        }

class Pattern(Base):
    __tablename__ = 'patterns'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pattern_type = Column(String, nullable=False)  # 'sequence', 'parameter', 'context'
    description = Column(Text, nullable=False)
    skill_name = Column(String, nullable=False)
    frequency = Column(Integer, default=1)
    success_rate = Column(Float, default=0.0)
    contexts = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'pattern_type': self.pattern_type,
            'description': self.description,
            'skill_name': self.skill_name,
            'frequency': self.frequency,
            'success_rate': self.success_rate,
            'contexts': self.contexts,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat()
        }

class SkillProficiency(Base):
    __tablename__ = 'skill_proficiencies'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    skill_name = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    proficiency_score = Column(Float, default=0.0)  # 0.0 to 1.0
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    examples = Column(JSON, default=list)
    optimal_parameters = Column(JSON, default=dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'skill_name': self.skill_name,
            'category': self.category,
            'description': self.description,
            'proficiency_score': self.proficiency_score,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'examples': self.examples,
            'optimal_parameters': self.optimal_parameters
        }

class Strategy(Base):
    __tablename__ = 'strategies'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    skill_name = Column(String, nullable=False)
    approach = Column(Text, nullable=False)  # JSON serialized approach
    task_types = Column(JSON, default=list)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    average_duration = Column(Float, default=0.0)
    parameters = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'skill_name': self.skill_name,
            'approach': self.approach,
            'task_types': self.task_types,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'average_duration': self.average_duration,
            'parameters': self.parameters,
            'created_at': self.created_at.isoformat()
        }

class Lesson(Base):
    __tablename__ = 'lessons'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type = Column(String, nullable=False)
    skill_name = Column(String, nullable=False)
    what_worked = Column(Text, nullable=False)
    what_failed = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=False)
    experience_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_type': self.task_type,
            'skill_name': self.skill_name,
            'what_worked': self.what_worked,
            'what_failed': self.what_failed,
            'recommendations': self.recommendations,
            'experience_ids': self.experience_ids,
            'created_at': self.created_at.isoformat()
        }

class LearningState(Base):
    __tablename__ = 'learning_states'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String, unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'updated_at': self.updated_at.isoformat()
        }

class KnowledgeBase(Base):
    __tablename__ = 'knowledge_base'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    topic = Column(String, nullable=False)
    category = Column(String, nullable=False)  # 'playbook', 'template', 'best_practice', 'faq'
    content = Column(Text, nullable=False)
    source_skill = Column(String, nullable=True)
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'topic': self.topic,
            'category': self.category,
            'content': self.content,
            'source_skill': self.source_skill,
            'usage_count': self.usage_count,
            'success_rate': self.success_rate,
            'created_at': self.created_at.isoformat()
        }

# Database initialization function
def init_learning_db(db_path: str = 'agent/data/learning.db'):
    """Initialize the learning database with all tables."""
    import os
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    return engine
