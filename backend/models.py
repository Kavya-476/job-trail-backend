from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    hashed_password = Column(String)
    reset_token = Column(String, nullable=True)
    reset_token_expiry = Column(DateTime, nullable=True)
    education = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    submissions = relationship("Submission", back_populates="user")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True) # e.g., 'job_dev'
    title = Column(String)
    description = Column(Text)
    category = Column(String)
    image_url = Column(String, nullable=True)
    is_upcoming = Column(Integer, default=0) # SQLite Boolean is often Integer 0/1
    skills = Column(Text, nullable=True) # Comma-separated skills
    
    tasks = relationship("Task", back_populates="job")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True) # e.g., 't1', 't2'
    job_id = Column(String, ForeignKey("jobs.id"))
    level = Column(String) # 'Beginner', 'Intermediate', 'Professional'
    number = Column(Integer)
    title = Column(String)
    description = Column(Text)
    initial_code = Column(Text, nullable=True)
    hint = Column(Text, nullable=True)
    duration = Column(Integer, default=30) # Content duration in minutes
    
    job = relationship("Job", back_populates="tasks")
    submissions = relationship("Submission", back_populates="task")

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    task_id = Column(String, ForeignKey("tasks.id"))
    content = Column(Text)
    score = Column(Integer)
    feedback = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="submissions")
    task = relationship("Task", back_populates="submissions")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    message = Column(Text)
    type = Column(String, default="info") # info, success, warning
    read = Column(Integer, default=0) # 0 for False, 1 for True (SQLite doesn't have native Boolean in some contexts but SQLAlchemy maps it, being safe)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")

class Wishlist(Base):
    __tablename__ = "wishlist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    job_id = Column(String, ForeignKey("jobs.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")
    job = relationship("Job")
