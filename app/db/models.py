from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    role_key = Column(String(50), nullable=False)
    role_title = Column(String(200), nullable=False)
    candidate_name = Column(String(200), nullable=False)
    candidate_email = Column(String(255))
    interviewer = Column(String(200))
    job_id = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(20), default="in_progress")
    final_notes = Column(Text)
    overall_score = Column(Numeric(6, 2))
    recommendation = Column(String(50))
    recommendation_class = Column(String(20))
    total_questions = Column(Integer, default=0)
    answered_questions = Column(Integer, default=0)
    progress_percent = Column(Numeric(5, 1))

    # Relationships
    scores = relationship("InterviewScore", back_populates="session", cascade="all, delete-orphan")


class InterviewScore(Base):
    __tablename__ = "interview_scores"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(String(20), nullable=False)
    section_id = Column(String(10))
    section_title = Column(String(200))
    section_weight = Column(Numeric(5, 2))
    score = Column(Numeric(4, 1), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    session = relationship("InterviewSession", back_populates="scores")


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String(100), unique=True, index=True, nullable=False)
    job_title = Column(String(200), nullable=False)
    description = Column(Text)
    required_skills = Column(JSON, default=list)
    min_experience = Column(Numeric(5, 1), default=0)
    max_experience = Column(Numeric(5, 1), default=99)
    department = Column(String(100))
    location = Column(String(200))
    salary_min = Column(Numeric(12, 2))
    salary_max = Column(Numeric(12, 2))
    source = Column(String(50), default="standalone")
    created_at = Column(DateTime, default=datetime.utcnow)


class ProcessedResume(Base):
    __tablename__ = "processed_resumes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_name = Column(String(500), nullable=False)
    format = Column(String(20))
    file_size = Column(Integer)
    text_length = Column(Integer)
    parse_confidence = Column(Numeric(5, 2))
    profile_json = Column(JSON)
    filter_decision = Column(String(20))
    filter_confidence = Column(Numeric(5, 2))
    filter_summary = Column(Text)
    failed_rules = Column(JSON)
    yellow_flags = Column(JSON)
    match_json = Column(JSON)
    processed_at = Column(DateTime, default=datetime.utcnow)


class SessionStat(Base):
    __tablename__ = "session_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    total_processed = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    rejected = Column(Integer, default=0)
    yellow_flags = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
