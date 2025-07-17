from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class Job(Base):
    __tablename__ = 'jobs'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    organization_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default='pending')
    original_filename = Column(String)
    file_size = Column(Integer)
    language = Column(String)
    target_language = Column(String)
    processing_options = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    processing_time_ms = Column(Integer)
    transcript_data = Column(JSON)
    job_metadata = Column(JSON)
    error_message = Column(Text)

class TranscriptSegment(Base):
    __tablename__ = 'transcript_segments'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey('jobs.id'))
    start = Column(Integer)
    end = Column(Integer)
    text = Column(Text)
    confidence = Column(Integer)
    speaker = Column(String)
    language = Column(String)
    job = relationship("Job", back_populates="segments")

Job.segments = relationship("TranscriptSegment", order_by=TranscriptSegment.start, back_populates="job")

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    organization_id = Column(String, ForeignKey('organizations.id'))
    organization = relationship("Organization", back_populates="users")

class Organization(Base):
    __tablename__ = 'organizations'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)
    users = relationship("User", back_populates="organization")
