
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, Boolean, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import uuid
import enum

Base = declarative_base()

class TaskStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    description = Column(Text, nullable=False)
    skill_name = Column(String, nullable=False)
    status = Column(String, default="pending") 
    priority = Column(Integer, default=5)
    parameters = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    progress = Column(Integer, default=0)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'skill_name': self.skill_name,
            'status': self.status,
            'priority': self.priority,
            'parameters': self.parameters,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress': self.progress,
            'result': self.result,
            'error': self.error
        }

class TaskQueue(Base):
    __tablename__ = 'task_queue'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey('tasks.id'), nullable=False)
    position = Column(Integer, default=0)
    added_at = Column(DateTime, default=datetime.utcnow)

class TaskHistory(Base):
    __tablename__ = 'task_history'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, ForeignKey('tasks.id'), nullable=False)
    event = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(JSON, default=dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'event': self.event,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details
        }

class ScheduledTask(Base):
    __tablename__ = 'scheduled_tasks'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_description = Column(Text, nullable=False)
    skill_name = Column(String, nullable=False)
    cron_expression = Column(String, nullable=False)
    next_run = Column(DateTime, nullable=False)
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_description': self.task_description,
            'skill_name': self.skill_name,
            'cron_expression': self.cron_expression,
            'next_run': self.next_run.isoformat(),
            'enabled': self.enabled,
            'last_run': self.last_run.isoformat() if self.last_run else None
        }

def init_task_db(db_path: str = 'agent/data/tasks.db'):
    """Initialize the task database."""
    import os
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    return engine
