-- ============================================================
-- RecruitIQ - Week 1 Deliverable
-- PostgreSQL Schema: JD & Candidate Repository
-- ============================================================

-- Enable UUID generation (cleaner IDs than serial for candidate-facing IDs)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- ENUM TYPES
-- ============================================================

CREATE TYPE jd_status AS ENUM ('open', 'on_hold', 'closed', 'filled');

CREATE TYPE candidate_source AS ENUM ('linkedin_apply', 'linkedin_dm', 'email', 'naukri', 'manual_upload', 'referral');

CREATE TYPE mapping_status AS ENUM (
    'new',              -- just matched, not reviewed
    'shortlisted',      -- AI score above threshold
    'screening_sent',   -- screening email sent
    'screening_replied',
    'recruiter_approved',
    'recruiter_rejected',
    'interview_scheduled',
    'client_submitted',
    'rejected_by_client',
    'offer',
    'closed'
);

CREATE TYPE email_type AS ENUM ('screening', 'follow_up', 'interview_invite', 'rejection', 'other');

CREATE TYPE email_direction AS ENUM ('outbound', 'inbound');

-- ============================================================
-- 1. CLIENTS  (companies sending JDs)
-- ============================================================

CREATE TABLE clients (
    client_id       SERIAL PRIMARY KEY,
    client_name     VARCHAR(150) NOT NULL,
    contact_person  VARCHAR(100),
    contact_email   VARCHAR(150),
    contact_phone   VARCHAR(20),
    created_by      VARCHAR(100),
    modified_by     VARCHAR(100),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 2. RECRUITERS  (internal users / system actors)
-- ============================================================

CREATE TABLE recruiters (
    recruiter_id    SERIAL PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(150) UNIQUE NOT NULL,
    role            VARCHAR(50) DEFAULT 'recruiter',  -- recruiter / admin / lead
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 3. JOB DESCRIPTIONS (JD Repository)
-- ============================================================

CREATE TABLE job_descriptions (
    jd_id               SERIAL PRIMARY KEY,
    jd_code             VARCHAR(20) UNIQUE NOT NULL,  -- human-readable id e.g. JD-2026-0001
    client_id           INTEGER NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,

    role_title          VARCHAR(150) NOT NULL,
    required_skills     TEXT[] NOT NULL DEFAULT '{}',     -- array of skill strings
    nice_to_have_skills TEXT[] DEFAULT '{}',
    experience_min      NUMERIC(4,1),                     -- years, e.g. 3.5
    experience_max      NUMERIC(4,1),
    notice_period_days  INTEGER,                          -- 0 = immediate
    location            VARCHAR(100),

    jd_status           jd_status NOT NULL DEFAULT 'open',

    -- Original file reference
    jd_file_drive_id    VARCHAR(255),       -- Google Drive file ID of JD doc
    jd_file_path        TEXT,               -- folder path convention, see drive_structure.md
    raw_text            TEXT,               -- extracted JD text for embedding

    -- ChromaDB linkage
    embedding_id        VARCHAR(100),       -- ID used in ChromaDB collection for this JD

    created_by          INTEGER REFERENCES recruiters(recruiter_id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_jd_status ON job_descriptions(jd_status);
CREATE INDEX idx_jd_client ON job_descriptions(client_id);
CREATE INDEX idx_jd_required_skills ON job_descriptions USING GIN (required_skills);

-- ============================================================
-- 4. CANDIDATES (Master Candidate Repository - Talent Pool)
-- ============================================================

CREATE TABLE candidates (
    candidate_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_code      VARCHAR(20) UNIQUE NOT NULL,  -- human-readable e.g. CAND-00001

    full_name           VARCHAR(150) NOT NULL,
    email               VARCHAR(150),
    phone               VARCHAR(20),

    -- Parsed structured fields (from CV)
    total_experience    NUMERIC(4,1),     -- years
    current_location    VARCHAR(100),
    notice_period_days  INTEGER,
    skills              TEXT[] DEFAULT '{}',
    parsed_json         JSONB,            -- full structured parse output (spaCy + LLM)

    -- Resume file reference (Drive)
    resume_drive_id     VARCHAR(255) NOT NULL,
    resume_file_path    TEXT NOT NULL,    -- e.g. /TalentPool/2026/06/CAND-00001_JohnDoe.pdf
    resume_text         TEXT,             -- raw extracted text (for re-parsing/debug)

    -- Source tracking
    source              candidate_source NOT NULL,
    source_detail       VARCHAR(255),     -- e.g. "LinkedIn - JD-2026-0001 post" / sender email

    -- ChromaDB linkage
    embedding_id        VARCHAR(100),     -- ID used in ChromaDB collection for this candidate

    -- Duplicate detection helper
    email_normalized    VARCHAR(150) GENERATED ALWAYS AS (LOWER(TRIM(email))) STORED,
    phone_normalized    VARCHAR(20)  GENERATED ALWAYS AS (REGEXP_REPLACE(phone, '[^0-9]', '', 'g')) STORED,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Prevent exact duplicate candidates by email/phone
CREATE UNIQUE INDEX idx_candidate_email_unique ON candidates(email_normalized) WHERE email_normalized IS NOT NULL AND email_normalized <> '';
CREATE INDEX idx_candidate_phone ON candidates(phone_normalized);
CREATE INDEX idx_candidate_skills ON candidates USING GIN (skills);
CREATE INDEX idx_candidate_location ON candidates(current_location);

-- ============================================================
-- 5. CANDIDATE <-> JD MAPPING (the core matching/tracking table)
-- ============================================================

CREATE TABLE candidate_jd_mapping (
    mapping_id          BIGSERIAL PRIMARY KEY,
    candidate_id        UUID NOT NULL REFERENCES candidates(candidate_id) ON DELETE CASCADE,
    jd_id               INTEGER NOT NULL REFERENCES job_descriptions(jd_id) ON DELETE CASCADE,

    -- AI Scoring (0-100 total + component breakdown)
    match_score         NUMERIC(5,2),     -- overall 0-100
    skills_score         NUMERIC(5,2),    -- component scores (weights from proposal)
    experience_score    NUMERIC(5,2),
    notice_period_score NUMERIC(5,2),
    location_score      NUMERIC(5,2),
    match_explanation   TEXT,             -- human-readable AI explanation

    -- Pipeline status
    status              mapping_status NOT NULL DEFAULT 'new',

    -- Direct applicant vs sourced from talent pool
    is_direct_applicant BOOLEAN NOT NULL DEFAULT FALSE,

    -- Recruiter actions
    reviewed_by         INTEGER REFERENCES recruiters(recruiter_id),
    reviewed_at         TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One candidate maps to one JD only once
    CONSTRAINT uq_candidate_jd UNIQUE (candidate_id, jd_id)
);

CREATE INDEX idx_mapping_jd ON candidate_jd_mapping(jd_id);
CREATE INDEX idx_mapping_candidate ON candidate_jd_mapping(candidate_id);
CREATE INDEX idx_mapping_status ON candidate_jd_mapping(status);
CREATE INDEX idx_mapping_score ON candidate_jd_mapping(match_score DESC);

-- ============================================================
-- 6. EMAIL HISTORY (scaffolded now, used heavily in Module 3)
-- ============================================================

CREATE TABLE email_history (
    email_id            BIGSERIAL PRIMARY KEY,
    mapping_id          BIGINT NOT NULL REFERENCES candidate_jd_mapping(mapping_id) ON DELETE CASCADE,

    direction           email_direction NOT NULL,
    email_type          email_type NOT NULL,
    subject             VARCHAR(255),
    body                TEXT,

    sent_at             TIMESTAMPTZ,
    received_at         TIMESTAMPTZ,

    parsed_response     JSONB,      -- AI-parsed answers from candidate replies

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_email_mapping ON email_history(mapping_id);

-- ============================================================
-- 7. TRIGGER: auto-update updated_at columns
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_clients_updated_at BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_jd_updated_at BEFORE UPDATE ON job_descriptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_candidates_updated_at BEFORE UPDATE ON candidates
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_mapping_updated_at BEFORE UPDATE ON candidate_jd_mapping
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- 8. SEQUENCE-BACKED HUMAN-READABLE ID GENERATORS
-- ============================================================
-- candidate_code = CAND-00001, CAND-00002...
-- jd_code        = JD-2026-0001 (year + sequence)

CREATE SEQUENCE candidate_code_seq START 1;
CREATE SEQUENCE jd_code_seq START 1;

-- Helper functions to generate codes (call before insert, or use in app layer)
CREATE OR REPLACE FUNCTION generate_candidate_code()
RETURNS VARCHAR AS $$
BEGIN
    RETURN 'CAND-' || LPAD(nextval('candidate_code_seq')::TEXT, 5, '0');
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION generate_jd_code()
RETURNS VARCHAR AS $$
BEGIN
    RETURN 'JD-' || EXTRACT(YEAR FROM now())::TEXT || '-' || LPAD(nextval('jd_code_seq')::TEXT, 4, '0');
END;
$$ LANGUAGE plpgsql;
