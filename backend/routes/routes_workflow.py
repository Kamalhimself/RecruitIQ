"""Recruiter-controlled screening email workflow endpoints."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import sessionmaker

from backend.services.email_service import screening_email, send_email
from backend.database.models import CandidateJDMapping, EmailDirection, EmailHistory, EmailType, MappingStatus
from backend.database.setup_db import get_engine

router = APIRouter(prefix="/workflow", tags=["workflow"])
Session = sessionmaker(bind=get_engine())


def _mapping_or_404(session, mapping_id: int) -> CandidateJDMapping:
    mapping = session.get(CandidateJDMapping, mapping_id)
    if not mapping:
        raise HTTPException(404, f"Mapping {mapping_id} was not found")
    return mapping


@router.post("/mappings/{mapping_id}/screening-email")
def send_screening_email(mapping_id: int):
    """Send a screening email only after a recruiter selects a candidate."""
    session = Session()
    try:
        mapping = _mapping_or_404(session, mapping_id)
        candidate, jd = mapping.candidate, mapping.job_description
        if not candidate.email:
            raise HTTPException(422, "This candidate has no email address")
        if mapping.status not in {MappingStatus.shortlisted, MappingStatus.recruiter_approved}:
            raise HTTPException(409, "Screening email can be sent only to shortlisted or approved candidates")
        subject, body = screening_email(candidate.full_name, jd.role_title)
        message_id = send_email(candidate.email, subject, body)
        session.add(EmailHistory(
            mapping_id=mapping.mapping_id, direction=EmailDirection.outbound,
            email_type=EmailType.screening, subject=subject, body=body,
            sent_at=datetime.now(timezone.utc), parsed_response={"gmail_message_id": message_id},
        ))
        mapping.status = MappingStatus.screening_sent
        session.commit()
        return {"mapping_id": mapping_id, "sent": True, "gmail_message_id": message_id}
    except RuntimeError as exc:
        session.rollback()
        raise HTTPException(503, str(exc)) from exc
    finally:
        session.close()


@router.post("/mappings/{mapping_id}/status/{status}")
def update_mapping_status(mapping_id: int, status: MappingStatus):
    """Record a recruiter decision; prevents automatic outbound email without approval."""
    session = Session()
    try:
        mapping = _mapping_or_404(session, mapping_id)
        mapping.status = status
        session.commit()
        return {"mapping_id": mapping_id, "status": mapping.status.value}
    finally:
        session.close()


@router.get("/follow-ups-due")
def follow_ups_due(hours: int = 48):
    """Return screening emails awaiting a reply. Call this from a daily scheduler."""
    session = Session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = session.query(EmailHistory).join(CandidateJDMapping).filter(
            EmailHistory.email_type == EmailType.screening,
            EmailHistory.sent_at <= cutoff,
            CandidateJDMapping.status == MappingStatus.screening_sent,
        ).all()
        return [{
            "mapping_id": row.mapping_id, "candidate_code": row.mapping.candidate.candidate_code,
            "candidate_email": row.mapping.candidate.email, "sent_at": row.sent_at,
        } for row in rows]
    finally:
        session.close()
