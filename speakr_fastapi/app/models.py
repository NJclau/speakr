from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    JSON,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    provider = Column(String(50), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    role = Column(String(50), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usage_minutes = Column(Integer, default=0)
    monthly_quota = Column(Integer, default=60)
    is_active = Column(Boolean, default=True)
    compliance_accepted = Column(Boolean, default=False)
    last_login = Column(DateTime)
    preferences = Column(JSON, default={})
    organization = relationship("Organization", back_populates="users")
    jobs = relationship("Job", back_populates="user")

class Organization(Base):
    __tablename__ = "organizations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    domain = Column(String(255))
    subscription_tier = Column(String(50), default="free")
    compliance_level = Column(String(50), default="basic")
    created_at = Column(DateTime, default=datetime.utcnow)
    settings = Column(JSON, default={})
    billing_info = Column(JSON, default={})
    users = relationship("User", back_populates="organization")
    jobs = relationship("Job", back_populates="organization")

class Job(Base):
    __tablename__ = "jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    status = Column(String(50), default="pending")
    original_filename = Column(String(255))
    file_size = Column(Integer)
    file_format = Column(String(10))
    duration_seconds = Column(Integer)
    language = Column(String(10), default="en")
    target_language = Column(String(10))
    processing_options = Column(JSON, default={})
    audio_url = Column(Text)
    transcript_data = Column(JSON)
    confidence_scores = Column(JSON)
    speaker_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    processing_time_ms = Column(Integer)
    queue_position = Column(Integer)
    priority = Column(Integer, default=0)
    compliance_flags = Column(JSON, default={})
    user = relationship("User", back_populates="jobs")
    organization = relationship("Organization", back_populates="jobs")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(UUID(as_uuid=True))
    details = Column(JSON)
    ip_address = Column(String) # Using String for INET for broader compatibility
    user_agent = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    session_id = Column(UUID(as_uuid=True))

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    correction_type = Column(String(50), nullable=False)
    original_text = Column(Text)
    corrected_text = Column(Text)
    timestamp_ms = Column(Integer)
    confidence_before = Column(Integer)
    confidence_after = Column(Integer)
    language = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)

class SpeakerProfile(Base):
    __tablename__ = "speaker_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    name = Column(String(255), nullable=False)
    voice_characteristics = Column(JSON)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    usage_count = Column(Integer, default=0)

class ApiKey(Base):
    __tablename__ = "api_keys"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    permissions = Column(JSON, default={})
    rate_limit = Column(Integer, default=1000)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime)
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
