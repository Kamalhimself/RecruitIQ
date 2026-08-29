"""
RecruitIQ - Week 1 Deliverable
SQLAlchemy models matching schema.sql
Plug into your existing FastAPI app (you already have the FastAPI/Postgres setup
from your other projects, so this should slot in the same way).

Install (if not already):
    pip install sqlalchemy psycopg2-binary
"""

import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Numeric, Boolean,
    TIMESTAMP, ForeignKey, ARRAY, Enum as SAEnum, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ============================================================
# ENUMS (mirror the Postgres ENUM types in schema.sql)
# ============================================================

class JDStatus(str, enum.Enum):
    open = "open"
    on_hold = "on_hold"
    closed = "closed"
    filled = "filled"


class CandidateSource(str, enum.Enum):
    linkedin_apply = "linkedin_apply"
    linkedin_dm = "linkedin_dm"
    email = "email"
    naukri = "naukri"
    manual_upload = "manual_upload"
    referral = "referral"


class MappingStatus(str, enum.Enum):
    new = "new"
    shortlisted = "shortlisted"
    screening_sent = "screening_sent"
    screening_replied = "screening_replied"
    recruiter_approved = "recruiter_approved"
    recruiter_rejected = "recruiter_rejected"
    interview_scheduled = "interview_scheduled"
    client_submitted = "client_submitted"
    rejected_by_client = "rejected_by_client"
    offer = "offer"
    closed = "closed"


class EmailType(str, enum.Enum):
    screening = "screening"
    follow_up = "follow_up"
    interview_invite = "interview_invite"
    rejection = "rejection"
    other = "other"


class EmailDirection(str, enum.Enum):
    outbound = "outbound"
    inbound = "inbound"


# ============================================================
# MODELS
# ============================================================

class Client(Base):
    __tablename__ = "clients"

    client_id = Column(Integer, primary_key=True)
    client_name = Column(String(150), nullable=False)
    contact_person = Column(String(100))
    contact_email = Column(String(150))
    contact_phone = Column(String(20))
    created_by = Column(String(100))
    modified_by = Column(String(100))
    notes = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    job_descriptions = relationship("JobDescription", back_populates="client")


class Recruiter(Base):
    __tablename__ = "recruiters"

    recruiter_id = Column(Integer, primary_key=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    role = Column(String(50), default="recruiter")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    jd_id = Column(Integer, primary_key=True)
    jd_code = Column(String(20), unique=True, nullable=False)
    client_id = Column(Integer, ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False)

    role_title = Column(String(150), nullable=False)
    required_skills = Column(ARRAY(String), default=list, nullable=False)
    nice_to_have_skills = Column(ARRAY(String), default=list)
    experience_min = Column(Numeric(4, 1))
    experience_max = Column(Numeric(4, 1))
    notice_period_days = Column(Integer)
    location = Column(String(100))

    jd_status = Column(SAEnum(JDStatus, name="jd_status"), default=JDStatus.open, nullable=False)

    jd_file_drive_id = Column(String(255))
    jd_file_path = Column(Text)
    raw_text = Column(Text)

    embedding_id = Column(String(100))

    created_by = Column(Integer, ForeignKey("recruiters.recruiter_id"))
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="job_descriptions")
    mappings = relationship("CandidateJDMapping", back_populates="job_description")


class Candidate(Base):
    __tablename__ = "candidates"

    candidate_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_code = Column(String(20), unique=True, nullable=False)

    full_name = Column(String(150), nullable=False)
    email = Column(String(150))
    phone = Column(String(20))

    total_experience = Column(Numeric(4, 1))
    current_location = Column(String(100))
    notice_period_days = Column(Integer)
    skills = Column(ARRAY(String), default=list)
    parsed_json = Column(JSONB)

    resume_drive_id = Column(String(255), nullable=False)
    resume_file_path = Column(Text, nullable=False)
    resume_text = Column(Text)

    source = Column(SAEnum(CandidateSource, name="candidate_source"), nullable=False)
    source_detail = Column(String(255))

    embedding_id = Column(String(100))

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    mappings = relationship("CandidateJDMapping", back_populates="candidate")

    # NOTE: email_normalized / phone_normalized are DB-generated columns
    # (see schema.sql) — don't set these from the app, Postgres computes them.


class CandidateJDMapping(Base):
    __tablename__ = "candidate_jd_mapping"

    mapping_id = Column(BigInteger, primary_key=True)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidates.candidate_id", ondelete="CASCADE"), nullable=False)
    jd_id = Column(Integer, ForeignKey("job_descriptions.jd_id", ondelete="CASCADE"), nullable=False)

    match_score = Column(Numeric(5, 2))
    skills_score = Column(Numeric(5, 2))
    experience_score = Column(Numeric(5, 2))
    notice_period_score = Column(Numeric(5, 2))
    location_score = Column(Numeric(5, 2))
    match_explanation = Column(Text)

    status = Column(SAEnum(MappingStatus, name="mapping_status"), default=MappingStatus.new, nullable=False)

    is_direct_applicant = Column(Boolean, default=False, nullable=False)

    reviewed_by = Column(Integer, ForeignKey("recruiters.recruiter_id"))
    reviewed_at = Column(TIMESTAMP(timezone=True))

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("candidate_id", "jd_id", name="uq_candidate_jd"),
    )

    candidate = relationship("Candidate", back_populates="mappings")
    job_description = relationship("JobDescription", back_populates="mappings")
    emails = relationship("EmailHistory", back_populates="mapping")


class EmailHistory(Base):
    __tablename__ = "email_history"

    email_id = Column(BigInteger, primary_key=True)
    mapping_id = Column(BigInteger, ForeignKey("candidate_jd_mapping.mapping_id", ondelete="CASCADE"), nullable=False)

    direction = Column(SAEnum(EmailDirection, name="email_direction"), nullable=False)
    email_type = Column(SAEnum(EmailType, name="email_type"), nullable=False)
    subject = Column(String(255))
    body = Column(Text)

    sent_at = Column(TIMESTAMP(timezone=True))
    received_at = Column(TIMESTAMP(timezone=True))

    parsed_response = Column(JSONB)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    mapping = relationship("CandidateJDMapping", back_populates="emails")
