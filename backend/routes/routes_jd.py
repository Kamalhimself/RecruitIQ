"""
RecruitIQ - Week 2
FastAPI router for JD upload + parsing.

Drop into your existing FastAPI app:

    from routes_jd import router as jd_router
    app.include_router(jd_router)
"""

import datetime
import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from googleapiclient.errors import HttpError
from sqlalchemy import text, func
from sqlalchemy.orm import sessionmaker

from backend.database.setup_db import get_engine
from backend.database.models import JobDescription, JDStatus, Client
from backend.services.jd_parser import extract_text, parse_jd_with_llm
from backend.services.drive_utils import upload_jd_file

router = APIRouter(prefix="/jds", tags=["job descriptions"])
client_router = APIRouter(prefix="/clients", tags=["clients"])
logger = logging.getLogger(__name__)

engine = get_engine()
Session = sessionmaker(bind=engine)


@router.get("")
def list_jds(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """List all job descriptions in the database."""
    session = Session()
    try:
        jds = session.query(JobDescription).order_by(JobDescription.created_at.desc()).offset(offset).limit(limit).all()
        return [{
            "jd_id": jd.jd_id,
            "jd_code": jd.jd_code,
            "client_id": jd.client_id,
            "client_name": jd.client.client_name if jd.client else None,
            "role_title": jd.role_title,
            "required_skills": jd.required_skills,
            "nice_to_have_skills": jd.nice_to_have_skills,
            "experience_min": float(jd.experience_min) if jd.experience_min is not None else None,
            "experience_max": float(jd.experience_max) if jd.experience_max is not None else None,
            "notice_period_days": jd.notice_period_days,
            "location": jd.location,
            "jd_status": jd.jd_status.value if jd.jd_status else None,
            "created_at": jd.created_at.isoformat() if jd.created_at else None,
            "updated_at": jd.updated_at.isoformat() if jd.updated_at else None,
        } for jd in jds]
    finally:
        session.close()


@client_router.get("")
def list_clients():
    """List all registered clients in the database."""
    session = Session()
    try:
        clients = session.query(Client).order_by(Client.client_id).all()
        return [{
            "client_id": c.client_id,
            "client_name": c.client_name,
            "contact_person": c.contact_person,
            "contact_email": c.contact_email,
            "contact_phone": c.contact_phone,
            "created_by": c.created_by,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "modified_by": c.modified_by,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        } for c in clients]
    finally:
        session.close()


@client_router.post("")
def create_client(
    client_name: str = Form(...),
    contact_person: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    created_by: Optional[str] = Form(None),
):
    """Create a new client/company in the database."""
    session = Session()
    try:
        client = Client(
            client_name=client_name,
            contact_person=contact_person,
            contact_email=contact_email,
            contact_phone=contact_phone,
            created_by=created_by,
        )
        session.add(client)
        session.commit()
        session.refresh(client)
        return {
            "client_id": client.client_id,
            "client_name": client.client_name,
            "contact_person": client.contact_person,
            "contact_email": client.contact_email,
            "contact_phone": client.contact_phone,
            "created_by": client.created_by,
            "created_at": client.created_at.isoformat() if client.created_at else None,
            "modified_by": client.modified_by,
            "updated_at": client.updated_at.isoformat() if client.updated_at else None,
            "message": f"Client '{client_name}' created successfully with client_id={client.client_id}."
        }
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()


@client_router.put("/{client_id}")
def update_client(
    client_id: int,
    client_name: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    modified_by: Optional[str] = Form(None),
):
    """Update an existing client/company in the database."""
    session = Session()
    try:
        client = session.query(Client).filter(Client.client_id == client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail=f"Client with id {client_id} not found.")

        if client_name is not None:
            client.client_name = client_name
        if contact_person is not None:
            client.contact_person = contact_person
        if contact_email is not None:
            client.contact_email = contact_email
        if contact_phone is not None:
            client.contact_phone = contact_phone
        if modified_by is not None:
            client.modified_by = modified_by

        session.commit()
        session.refresh(client)
        return {
            "client_id": client.client_id,
            "client_name": client.client_name,
            "contact_person": client.contact_person,
            "contact_email": client.contact_email,
            "contact_phone": client.contact_phone,
            "created_by": client.created_by,
            "created_at": client.created_at.isoformat() if client.created_at else None,
            "modified_by": client.modified_by,
            "updated_at": client.updated_at.isoformat() if client.updated_at else None,
            "message": f"Client '{client.client_name}' updated successfully."
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        session.close()




@router.post("/parse")
async def parse_jd_preview(file: UploadFile = File(...)):
    """Extracts + parses a JD WITHOUT saving anything. Use this first to
    sanity-check the LLM extraction before committing via POST /jds."""
    file_bytes = await file.read()
    try:
        raw_text = extract_text(file_bytes, file.filename)
        parsed = parse_jd_with_llm(raw_text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {"raw_text_preview": raw_text[:500], "parsed": parsed}


@router.post("")
async def create_jd(
    file: UploadFile = File(...),
    client_id: int = Form(...),
    created_by: Optional[int] = Form(None),
):
    """Full pipeline: extract text -> parse via LLM -> generate jd_code ->
    upload to Drive -> save to job_descriptions."""

    # Normalize created_by: 0 or negative integers sent by Swagger UI should be treated as None
    if created_by is not None and created_by <= 0:
        created_by = None

    file_bytes = await file.read()

    try:
        raw_text = extract_text(file_bytes, file.filename)
        parsed = parse_jd_with_llm(raw_text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Parsing failed: {e}")

    session = Session()
    try:
        from backend.database.models import Client, Recruiter
        client_obj = session.get(Client, client_id)
        if not client_obj:
            raise HTTPException(
                status_code=400,
                detail=f"Client with client_id={client_id} does not exist. Please pass a valid client_id."
            )

        if created_by is not None:
            recruiter_obj = session.get(Recruiter, created_by)
            if not recruiter_obj:
                created_by = None

        jd_code = session.execute(text("SELECT generate_jd_code()")).scalar()

        year = str(datetime.datetime.now().year)
        ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "pdf"
        drive_filename = f"{jd_code}_{parsed['role_title'].replace(' ', '')}.{ext}"

        try:
            drive_info = upload_jd_file(file_bytes, drive_filename, year, mime_type=file.content_type)
        except Exception as exc:
            # Drive setup, expired OAuth tokens, or quota must not block creating a usable JD record.
            logger.warning("JD was saved without a Drive file: %s", exc)
            drive_info = {"drive_id": None, "web_link": None, "path": None}

        jd = JobDescription(
            jd_code=jd_code,
            client_id=client_id,
            role_title=parsed["role_title"],
            required_skills=parsed["required_skills"],
            nice_to_have_skills=parsed["nice_to_have_skills"],
            experience_min=parsed.get("experience_min"),
            experience_max=parsed.get("experience_max"),
            notice_period_days=parsed.get("notice_period_days"),
            location=parsed.get("location"),
            jd_status=JDStatus.open,
            jd_file_drive_id=drive_info.get("drive_id"),
            jd_file_path=drive_info.get("path"),
            raw_text=raw_text,
            created_by=created_by,
        )
        session.add(jd)
        session.commit()
        session.refresh(jd)

        return {
            "jd_id": jd.jd_id,
            "jd_code": jd.jd_code,
            "role_title": jd.role_title,
            "required_skills": jd.required_skills,
            "nice_to_have_skills": jd.nice_to_have_skills,
            "experience_min": float(jd.experience_min) if jd.experience_min is not None else None,
            "experience_max": float(jd.experience_max) if jd.experience_max is not None else None,
            "notice_period_days": jd.notice_period_days,
            "location": jd.location,
            "drive_link": drive_info.get("web_link"),
            "drive_upload_pending": drive_info.get("drive_id") is None,
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        logger.error("Failed to create JD: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        session.close()


@router.put("/{jd_id}")
def update_jd(
    jd_id: int,
    role_title: Optional[str] = Form(None),
    client_id: Optional[int] = Form(None),
    required_skills: Optional[str] = Form(None),
    nice_to_have_skills: Optional[str] = Form(None),
    experience_min: Optional[float] = Form(None),
    experience_max: Optional[float] = Form(None),
    notice_period_days: Optional[int] = Form(None),
    location: Optional[str] = Form(None),
    jd_status: Optional[str] = Form(None),
):
    """Update an existing Job Description specification."""
    session = Session()
    try:
        jd = session.query(JobDescription).filter(JobDescription.jd_id == jd_id).first()
        if not jd:
            raise HTTPException(status_code=404, detail=f"Job Description with id {jd_id} not found.")

        if role_title is not None:
            jd.role_title = role_title
        if client_id is not None:
            jd.client_id = client_id
        if required_skills is not None:
            jd.required_skills = [s.strip() for s in required_skills.split(",") if s.strip()]
        if nice_to_have_skills is not None:
            jd.nice_to_have_skills = [s.strip() for s in nice_to_have_skills.split(",") if s.strip()]
        if experience_min is not None:
            jd.experience_min = experience_min
        if experience_max is not None:
            jd.experience_max = experience_max
        if notice_period_days is not None:
            jd.notice_period_days = notice_period_days
        if location is not None:
            jd.location = location
        if jd_status is not None:
            try:
                jd.jd_status = JDStatus(jd_status.lower())
            except ValueError:
                pass

        jd.updated_at = func.now()
        session.commit()
        session.refresh(jd)

        return {
            "jd_id": jd.jd_id,
            "jd_code": jd.jd_code,
            "client_id": jd.client_id,
            "client_name": jd.client.client_name if jd.client else None,
            "role_title": jd.role_title,
            "required_skills": jd.required_skills,
            "nice_to_have_skills": jd.nice_to_have_skills,
            "experience_min": float(jd.experience_min) if jd.experience_min is not None else None,
            "experience_max": float(jd.experience_max) if jd.experience_max is not None else None,
            "notice_period_days": jd.notice_period_days,
            "location": jd.location,
            "jd_status": jd.jd_status.value if jd.jd_status else None,
            "created_at": jd.created_at.isoformat() if jd.created_at else None,
            "updated_at": jd.updated_at.isoformat() if jd.updated_at else None,
            "message": f"Job Description '{jd.jd_code}' updated successfully."
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        logger.error("Failed to update JD: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        session.close()

