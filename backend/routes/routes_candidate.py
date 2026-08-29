"""
RecruitIQ - Week 3
FastAPI router for candidate CV upload + parsing.

Mirrors the JD router pattern from Week 2:
    POST /candidates/parse   → preview parse without saving (sanity check)
    POST /candidates         → full pipeline: parse → Drive upload → save to DB
    GET  /candidates         → list all candidates (for dashboard)
    GET  /candidates/{code}  → fetch one candidate by candidate_code

Wire into main.py:
    from routes_candidate import router as candidate_router
    app.include_router(candidate_router)
"""

import datetime
import logging
import re
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from googleapiclient.errors import HttpError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.database.setup_db import get_engine
from backend.database.models import Candidate, CandidateJDMapping, CandidateSource, MappingStatus
from backend.services.cv_parser import parse_cv, extract_text
from backend.services.drive_utils_resume import upload_resume_file

router  = APIRouter(prefix="/candidates", tags=["candidates"])
logger = logging.getLogger(__name__)
engine  = get_engine()
Session = sessionmaker(bind=engine)


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

def _sanitise_name(name: str) -> str:
    """Strip non-alphanumeric chars for use in filename."""
    return re.sub(r"[^a-zA-Z0-9]", "", name)


def _next_candidate_code(session) -> str:
    """Get an unused sequence code, including after manually seeded records."""
    for _ in range(100):
        candidate_code = session.execute(
            text("SELECT generate_candidate_code()")
        ).scalar_one()
        if not session.query(Candidate.candidate_id).filter_by(
            candidate_code=candidate_code
        ).first():
            return candidate_code
    raise RuntimeError("Could not generate an unused candidate code")


def _candidate_to_dict(c: Candidate) -> dict:
    return {
        "candidate_id":    str(c.candidate_id),
        "candidate_code":  c.candidate_code,
        "full_name":       c.full_name,
        "email":           c.email,
        "phone":           c.phone,
        "total_experience": float(c.total_experience) if c.total_experience is not None else None,
        "current_location": c.current_location,
        "notice_period_days": c.notice_period_days,
        "skills":          c.skills or [],
        "resume_file_path": c.resume_file_path,
        "source":          c.source.value if c.source else None,
        "created_at":      c.created_at.isoformat() if c.created_at else None,
    }


# ------------------------------------------------------------------ #
#  POST /candidates/parse  — preview only, nothing saved             #
# ------------------------------------------------------------------ #

@router.post("/parse")
async def parse_cv_preview(file: UploadFile = File(...)):
    """
    Extracts + parses a CV without touching the DB or Drive.
    Use this to eyeball spaCy vs LLM extraction quality before committing.

    Returns:
        raw_text_preview  — first 500 chars of extracted text
        spacy_extract     — what the rule-based layer found
        parsed            — final LLM-corrected structured output
    """
    file_bytes = await file.read()
    try:
        result = parse_cv(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "raw_text_preview": result["raw_text"][:500],
        "spacy_extract":    result["spacy_extract"],
        "parsed":           result["parsed"],
    }


# ------------------------------------------------------------------ #
#  POST /candidates  — full pipeline                                  #
# ------------------------------------------------------------------ #

@router.post("")
async def create_candidate(
    file:          UploadFile       = File(...),
    source:        str              = Form(...),          # CandidateSource value
    jd_id:         Optional[int]    = Form(None),         # if direct applicant for a specific JD
    source_detail: Optional[str]    = Form(None),         # e.g. "LinkedIn - JD-2026-0001 post"
    uploaded_by:   Optional[int]    = Form(None),         # recruiter_id
):
    """
    Full pipeline:
        1. Extract CV text
        2. spaCy pre-extract → Groq LLM fill-in
        3. Generate candidate_code
        4. Upload resume to Drive /TalentPool/<year>/<month>/
        5. Save Candidate row
        6. If jd_id provided → create CandidateJDMapping (is_direct_applicant=True)

    Duplicate handling:
        If a candidate with the same email already exists, we skip creating a new
        Candidate row and just add a new mapping to the provided jd_id (if any).
        Returns the existing candidate + a "duplicate": true flag.
    """
    file_bytes = await file.read()

    # --- normalize optional integer forms (Swagger UI defaults) ---
    if jd_id is not None and jd_id <= 0:
        jd_id = None
    if uploaded_by is not None and uploaded_by <= 0:
        uploaded_by = None

    # --- validate source enum ---
    try:
        source_enum = CandidateSource(source)
    except ValueError:
        valid = [e.value for e in CandidateSource]
        raise HTTPException(
            status_code=422,
            detail=f"Invalid source '{source}'. Must be one of: {valid}"
        )

    # --- parse CV ---
    try:
        result = parse_cv(file_bytes, file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"CV parsing failed: {e}")

    parsed = result["parsed"]

    session = Session()
    try:
        # --- check for duplicate before allocating a code or uploading a file ---
        existing = None
        email = parsed.get("email")
        if email:
            existing = (
                session.query(Candidate)
                .filter(
                    text("email_normalized = :em")
                    .bindparams(em=email.lower().strip())
                )
                .first()
            )

        if existing:
            # --- duplicate: just add a new mapping if jd_id given ---
            candidate   = existing
            is_duplicate = True
            drive_info = {
                "drive_id": candidate.resume_drive_id,
                "web_link": None,
                "path": candidate.resume_file_path,
            }
        else:
            # --- new candidate ---
            candidate_code = _next_candidate_code(session)
            safe_name = _sanitise_name(parsed.get("full_name", "Unknown"))
            ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "pdf"
            drive_filename = f"{candidate_code}_{safe_name}.{ext}"
            try:
                drive_info = upload_resume_file(
                    file_bytes, drive_filename, candidate_code, mime_type=file.content_type
                )
            except Exception as exc:
                # Drive errors (OAuth, token, network) must not block candidate ingestion.
                logger.warning("Candidate was saved without a Drive file: %s", exc)
                drive_info = {
                    "drive_id": "pending",
                    "web_link": None,
                    "path": f"/TalentPool/pending/{drive_filename}",
                }
            candidate = Candidate(
                candidate_code    = candidate_code,
                full_name         = parsed.get("full_name", "Unknown"),
                email             = parsed.get("email"),
                phone             = parsed.get("phone"),
                total_experience  = parsed.get("total_experience"),
                current_location  = parsed.get("current_location"),
                notice_period_days= parsed.get("notice_period_days"),
                skills            = parsed.get("skills", []),
                parsed_json       = parsed,
                resume_drive_id   = drive_info["drive_id"],
                resume_file_path  = drive_info["path"],
                resume_text       = result["raw_text"],
                source            = source_enum,
                source_detail     = source_detail,
            )
            session.add(candidate)
            session.flush()   # get candidate_id
            is_duplicate = False

        # --- create mapping if jd_id provided ---
        mapping_created = False
        if jd_id is not None:
            # check this (candidate, jd) pair doesn't already exist
            existing_mapping = (
                session.query(CandidateJDMapping)
                .filter_by(candidate_id=candidate.candidate_id, jd_id=jd_id)
                .first()
            )
            if not existing_mapping:
                mapping = CandidateJDMapping(
                    candidate_id        = candidate.candidate_id,
                    jd_id               = jd_id,
                    status              = MappingStatus.new,
                    is_direct_applicant = True,
                )
                session.add(mapping)
                mapping_created = True

        session.commit()

        return {
            "candidate_id":    str(candidate.candidate_id),
            "candidate_code":  candidate.candidate_code,
            "full_name":       candidate.full_name,
            "email":           candidate.email,
            "skills":          candidate.skills,
            "total_experience": float(candidate.total_experience) if candidate.total_experience else None,
            "current_location": candidate.current_location,
            "notice_period_days": candidate.notice_period_days,
            "resume_drive_link": drive_info.get("web_link"),
            "resume_path":     drive_info["path"],
            "drive_upload_pending": drive_info["drive_id"] == "pending",
            "parsed_summary":  parsed.get("parsed_summary", ""),
            "duplicate":       is_duplicate,
            "mapping_created": mapping_created,
        }

    except HTTPException:
        session.rollback()
        raise
    except IntegrityError as e:
        session.rollback()
        # Catch DB-level unique constraint on email_normalized
        raise HTTPException(
            status_code=409,
            detail=f"Candidate with this email already exists. {str(e.orig)}"
        )
    except Exception as exc:
        session.rollback()
        logger.exception("Error creating candidate: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error creating candidate: {str(exc)}"
        )
    finally:
        session.close()


# ------------------------------------------------------------------ #
#  GET /candidates  — list                                            #
# ------------------------------------------------------------------ #

@router.get("")
async def list_candidates(
    limit:  int           = Query(50, ge=1, le=200),
    offset: int           = Query(0, ge=0),
    skill:  Optional[str] = Query(None, description="Filter by skill (partial match)"),
):
    """
    Returns a paginated list of candidates.
    Optionally filter by skill — e.g. ?skill=python
    """
    session = Session()
    try:
        q = session.query(Candidate)
        if skill:
            # Postgres ARRAY contains — checks if skill token is in the skills array
            q = q.filter(
                text("skills @> ARRAY[:s]::text[]").bindparams(s=skill.lower().strip())
            )
        total = q.count()
        candidates = q.order_by(Candidate.created_at.desc()).offset(offset).limit(limit).all()

        return {
            "total":  total,
            "offset": offset,
            "limit":  limit,
            "items":  [_candidate_to_dict(c) for c in candidates],
        }
    finally:
        session.close()


# ------------------------------------------------------------------ #
#  GET /candidates/{candidate_code}  — single candidate              #
# ------------------------------------------------------------------ #

@router.get("/{candidate_code}")
async def get_candidate(candidate_code: str):
    """Fetch a single candidate by their human-readable code (e.g. CAND-00001)."""
    session = Session()
    try:
        candidate = (
            session.query(Candidate)
            .filter_by(candidate_code=candidate_code.upper())
            .first()
        )
        if not candidate:
            raise HTTPException(
                status_code=404,
                detail=f"Candidate '{candidate_code}' not found."
            )

        data = _candidate_to_dict(candidate)

        # also return their JD mappings
        mappings = (
            session.query(CandidateJDMapping)
            .filter_by(candidate_id=candidate.candidate_id)
            .all()
        )
        data["mappings"] = [
            {
                "jd_id":       m.jd_id,
                "match_score": float(m.match_score) if m.match_score else None,
                "status":      m.status.value,
                "is_direct_applicant": m.is_direct_applicant,
            }
            for m in mappings
        ]

        return data
    finally:
        session.close()
