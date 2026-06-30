# ============================================================
# DIGIDEL Hiring Agent v2.2 Database Migration
# PostgreSQL / Supabase / Neon Compatible
# Run this in your Supabase SQL Editor or psql
# ============================================================

# Enable UUID extension (for Supabase)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

# ============================================================
# Table: interview_sessions
# Stores live interview scoring sessions
# ============================================================
CREATE TABLE IF NOT EXISTS interview_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL UNIQUE,
    role_key VARCHAR(50) NOT NULL,
    role_title VARCHAR(200) NOT NULL,
    candidate_name VARCHAR(200) NOT NULL,
    candidate_email VARCHAR(255),
    interviewer VARCHAR(200),
    job_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'in_progress',
    final_notes TEXT,
    overall_score NUMERIC(6, 2),
    recommendation VARCHAR(50),
    recommendation_class VARCHAR(20),
    total_questions INTEGER DEFAULT 0,
    answered_questions INTEGER DEFAULT 0,
    progress_percent NUMERIC(5, 1)
);

CREATE INDEX IF NOT EXISTS idx_interview_sessions_session_id ON interview_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_role_key ON interview_sessions(role_key);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_status ON interview_sessions(status);
CREATE INDEX IF NOT EXISTS idx_interview_sessions_created_at ON interview_sessions(created_at DESC);

# ============================================================
# Table: interview_scores
# Individual question scores per session
# ============================================================
CREATE TABLE IF NOT EXISTS interview_scores (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    question_id VARCHAR(20) NOT NULL,
    section_id VARCHAR(10),
    section_title VARCHAR(200),
    section_weight NUMERIC(5, 2),
    score NUMERIC(4, 1) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interview_scores_session_id ON interview_scores(session_id);
CREATE INDEX IF NOT EXISTS idx_interview_scores_question_id ON interview_scores(question_id);

# ============================================================
# Table: job_descriptions
# Stores job descriptions (standalone mode)
# ============================================================
CREATE TABLE IF NOT EXISTS job_descriptions (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(100) NOT NULL UNIQUE,
    job_title VARCHAR(200) NOT NULL,
    description TEXT,
    required_skills JSONB DEFAULT '[]',
    min_experience NUMERIC(5, 1) DEFAULT 0,
    max_experience NUMERIC(5, 1) DEFAULT 99,
    department VARCHAR(100),
    location VARCHAR(200),
    salary_min NUMERIC(12, 2),
    salary_max NUMERIC(12, 2),
    source VARCHAR(50) DEFAULT 'standalone',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_descriptions_job_id ON job_descriptions(job_id);
CREATE INDEX IF NOT EXISTS idx_job_descriptions_created_at ON job_descriptions(created_at DESC);

# ============================================================
# Table: processed_resumes
# Stores pipeline results from resume uploads
# ============================================================
CREATE TABLE IF NOT EXISTS processed_resumes (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(500) NOT NULL,
    format VARCHAR(20),
    file_size INTEGER,
    text_length INTEGER,
    parse_confidence NUMERIC(5, 2),
    profile_json JSONB,
    filter_decision VARCHAR(20),
    filter_confidence NUMERIC(5, 2),
    filter_summary TEXT,
    failed_rules JSONB,
    yellow_flags JSONB,
    match_json JSONB,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_processed_resumes_decision ON processed_resumes(filter_decision);
CREATE INDEX IF NOT EXISTS idx_processed_resumes_processed_at ON processed_resumes(processed_at DESC);
CREATE INDEX IF NOT EXISTS idx_processed_resumes_file_name ON processed_resumes(file_name);

# ============================================================
# Table: session_stats
# Singleton table for aggregated stats (optional, derived from processed_resumes)
# ============================================================
CREATE TABLE IF NOT EXISTS session_stats (
    id SERIAL PRIMARY KEY,
    total_processed INTEGER DEFAULT 0,
    passed INTEGER DEFAULT 0,
    rejected INTEGER DEFAULT 0,
    yellow_flags INTEGER DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

INSERT INTO session_stats (id, total_processed, passed, rejected, yellow_flags)
VALUES (1, 0, 0, 0, 0)
ON CONFLICT (id) DO NOTHING;

# ============================================================
# Verification
# ============================================================
SELECT 'Tables created successfully' as status;
