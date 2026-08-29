"""
RecruitIQ - Week 1
Seed script: inserts sample client, JD, recruiter, and candidates
so you can test the schema + relationships end-to-end.

Run after setup_db.py:
    python seed_data.py
"""

from sqlalchemy.orm import sessionmaker
from backend.database.setup_db import get_engine
from backend.database.models import (
    Base, Client, Recruiter, JobDescription, Candidate,
    CandidateJDMapping, JDStatus, CandidateSource, MappingStatus
)

engine = get_engine()
Session = sessionmaker(bind=engine)
session = Session()

# ------------------------------------------------------------
# 1. Recruiter
# ------------------------------------------------------------
recruiter = Recruiter(
    full_name="Kamaleswar Sivashanmugam",
    email="kamaleswar.sivashanmugam@gmail.com",
    role="admin",
)
session.add(recruiter)
session.flush()  # get recruiter_id

# ------------------------------------------------------------
# 2. Client
# ------------------------------------------------------------
client = Client(
    client_name="Acme Tech Solutions",
    contact_person="Priya Sharma",
    contact_email="priya@acmetech.com",
    contact_phone="9876543210",
)
session.add(client)
session.flush()  # get client_id

# ------------------------------------------------------------
# 3. Job Description
# ------------------------------------------------------------
jd = JobDescription(
    jd_code="JD-2026-0001",
    client_id=client.client_id,
    role_title="Backend Engineer (Python)",
    required_skills=["python", "fastapi", "postgresql", "docker"],
    nice_to_have_skills=["aws", "kubernetes"],
    experience_min=2,
    experience_max=5,
    notice_period_days=30,
    location="Chennai",
    jd_status=JDStatus.open,
    created_by=recruiter.recruiter_id,
)
session.add(jd)
session.flush()  # get jd_id

# ------------------------------------------------------------
# 4. Candidates
# ------------------------------------------------------------
candidate1 = Candidate(
    candidate_code="CAND-00001",
    full_name="Arun Kumar",
    email="arun.kumar@example.com",
    phone="9123456780",
    total_experience=3.5,
    current_location="Chennai",
    notice_period_days=0,
    skills=["python", "fastapi", "postgresql", "redis"],
    resume_drive_id="dummy_drive_id_001",
    resume_file_path="/TalentPool/2026/06/CAND-00001_ArunKumar.pdf",
    source=CandidateSource.linkedin_apply,
    source_detail="LinkedIn - JD-2026-0001 post",
)

candidate2 = Candidate(
    candidate_code="CAND-00002",
    full_name="Divya Raj",
    email="divya.raj@example.com",
    phone="9988776655",
    total_experience=4,
    current_location="Bangalore",
    notice_period_days=60,
    skills=["python", "django", "mysql", "aws"],
    resume_drive_id="dummy_drive_id_002",
    resume_file_path="/TalentPool/2026/06/CAND-00002_DivyaRaj.pdf",
    source=CandidateSource.naukri,
    source_detail="Naukri application",
)

session.add_all([candidate1, candidate2])
session.flush()

# ------------------------------------------------------------
# 5. Candidate <-> JD Mapping (simulated AI scores)
# ------------------------------------------------------------
mapping1 = CandidateJDMapping(
    candidate_id=candidate1.candidate_id,
    jd_id=jd.jd_id,
    match_score=88.5,
    skills_score=90,
    experience_score=85,
    notice_period_score=100,
    location_score=100,
    match_explanation="4/4 required skills found. Experience and location match exactly. Available immediately.",
    status=MappingStatus.shortlisted,
    is_direct_applicant=True,
)

mapping2 = CandidateJDMapping(
    candidate_id=candidate2.candidate_id,
    jd_id=jd.jd_id,
    match_score=64.0,
    skills_score=70,
    experience_score=90,
    notice_period_score=20,
    location_score=15,
    match_explanation="3/4 required skills found (missing docker). 60-day notice period and location mismatch lower the score.",
    status=MappingStatus.new,
    is_direct_applicant=False,
)

session.add_all([mapping1, mapping2])

session.commit()

print("✅ Seed data inserted successfully.")
print(f"   Client: {client.client_name} (id={client.client_id})")
print(f"   JD: {jd.jd_code} - {jd.role_title} (id={jd.jd_id})")
print(f"   Candidates: {candidate1.candidate_code}, {candidate2.candidate_code}")
print(f"   Mappings: {len(session.query(CandidateJDMapping).all())} rows")

session.close()
